#!/usr/bin/env python3
"""HTTP layer: proxy OpenAI-compatible + API de control + panel web."""
from __future__ import annotations

import json
import secrets
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from console_core import (BASE, CATALOG, CONFIGS, HOST, LOGS, PORT, TOKEN_FILE,
                          MAX_BODY_BYTES, detail_of, get_active, gpu_state, http_json, model_ids, ram_state,
                          save_catalog, slug, status_of, switch_to, validate_model_id, safe_child,
                          systemctl, unit_name, load_catalog, find)
import history_core
import tunnel_core
import update_core
import update_monitor
import optimize_core
import trace_core
import connection_core
import backend_core
import job_core
import evaluation_core

UI = BASE / "web"
OPENAPI = BASE / "docs" / "api" / "openapi.json"
PARAMS_HELP = BASE / "data" / "params_help.json"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def token() -> str:
    """Return a non-empty private token, creating it atomically on first use."""
    try:
        current = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if current:
            return current
    except OSError:
        pass
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(32)
    tmp = TOKEN_FILE.with_name(f".{TOKEN_FILE.name}.{secrets.token_hex(6)}.tmp")
    tmp.write_text(value + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(TOKEN_FILE)
    return value


def query(path: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(path).query, keep_blank_values=True)


def first_query(path: str, key: str, default: str | None = None) -> str | None:
    return query(path).get(key, [default])[0]

# banderas engine soportadas por /api/config (key -> flag, tipo)
ENGINE_FLAGS = {
    "max_context": "--max-context", "kv": "--kv", "spec": "--spec",
    "spec_min_p": "--spec-min-p", "mtp_max": "--mtp-max-t",
    "lookup_chain": "--lookup-chain", "suffix_draft": "--suffix-draft",
    "vram_reserve_mib": "--vram-reserve-mib", "pcie_frac": "--pcie-frac",
    "expert_cache": "--expert-cache", "adapt_swaps": "--adapt-swaps",
    "adapt_decay": "--adapt-decay", "prefill": "--prefill",
    "prompt_cache": "--prompt-cache", "conversation_cache_mib": "--conversation-cache-mib",
    "kv_resident": "--kv-resident", "pool_workers": "--pool-workers",
    "batch": "--batch", "rope_scaling": "--rope-scaling",
    "expert_profile": "--expert-profile", "expert_profile_save": "--expert-profile-save",
    "control_vector": "--control-vector-scaled",
}
ENGINE_BOOLS = {"kv_grow": "--kv-grow", "vision": "--vision",
                "vram_elastic": "--vram-elastic"}
CFG_BOOLS = {"lazy_load": "--lazy", "fit_max_tokens": "--fit-max-tokens",
             "api_monitor": "--api-monitor"}


def sampler_loop():
    """Cada 60 s guarda un sample de métricas por modelo con su setup vigente."""
    import threading
    while True:
        try:
            cat = load_catalog()
            for entry in cat["models"]:
                m = detail_of(entry)
                if m.get("available"):
                    history_core.record(entry, m)
        except Exception:
            pass
        import time
        time.sleep(60)


threading.Thread(target=sampler_loop, daemon=True).start()
update_monitor.start()


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    sent = handler.headers.get("X-Strata-Token") or ""
    if not sent:
        auth = handler.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            sent = auth[7:]
    return secrets.compare_digest(sent, token())


def jbytes(v) -> bytes:
    return json.dumps(v, ensure_ascii=False).encode("utf-8")


def add_model(cat: dict, req: dict) -> dict:
    gguf = Path(req["gguf_path"]).expanduser()
    if not gguf.exists() or not gguf.is_file() or gguf.stat().st_size <= 0:
        raise ValueError(f"GGUF inexistente o vacío: {gguf}")
    mid = validate_model_id(req.get("id") or slug(gguf.stem))
    if mid in model_ids(cat):
        raise ValueError(f"ya existe un modelo con id {mid}")
    ports = {int(m["port"]) for m in cat["models"]}
    port = int(req.get("port") or max([8080] + list(ports)) + 1)
    if not 1024 <= port <= 65535 or port == PORT:
        raise ValueError(f"puerto inválido o reservado: {port}")
    if port in ports:
        raise ValueError(f"puerto {port} ya en uso por otro modelo")
    pack = req.get("pack") or str(gguf.parent / f"pack-{slug(mid)}")
    cfgname = f"{mid}.json"
    base_cfg = json.loads((CONFIGS / "iq3_s.json").read_text(encoding="utf-8"))
    shards = sorted(gguf.parent.glob(gguf.stem.split("-00001")[0] + "*.gguf")) if "-00001-of-" in gguf.name else [gguf]
    native = str(gguf)
    ple = next((str(s) for s in shards if "-00002-of-" in s.name), None)
    args = base_cfg["args"]
    def setflag(flag, val):
        if flag in args:
            args[args.index(flag) + 1] = val
    setflag("--pack", pack)
    setflag("--native", native)
    if ple:
        setflag("--ple-gguf", ple)
    elif "--ple-gguf" in args:
        i = args.index("--ple-gguf")
        del args[i:i + 2]
    for flag in ("--expert-profile",):
        if flag in args and req.get("expert_profile"):
            setflag(flag, req["expert_profile"])
    base_cfg["args"] = args
    base_cfg["model_name"] = mid
    base_cfg["port"] = port
    base_cfg["tokenizer"] = str(Path(pack) / "tokenizer")
    base_cfg["log"] = str(LOGS / f"{mid}.log")
    (CONFIGS / cfgname).write_text(json.dumps(base_cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    entry = {"id": mid, "label": req.get("label") or mid, "port": port,
             "config": f"configs/{cfgname}", "pack": pack, "gguf": str(gguf.parent),
             "note": req.get("note", "alta desde la consola")}
    cat["models"].append(entry)
    save_catalog(cat)
    return entry


def remove_model(cat: dict, mid: str) -> dict:
    entry = find(cat, mid)
    if not entry:
        raise ValueError(f"modelo desconocido: {mid}")
    if len(cat.get("models", [])) <= 1:
        raise ValueError("no se puede quitar el último modelo del catálogo")
    systemctl("stop", unit_name(entry))
    if entry.get("legacy_unit"):
        systemctl("stop", entry["legacy_unit"])
    cfg = safe_child(CONFIGS, Path(entry["config"]).name)
    if cfg.exists() and cfg.is_file():
        cfg.unlink()
    # Solo se elimina el unit generado por la consola; nunca el legacy ni GGUF/pack.
    generated = Path.home() / ".config" / "systemd" / "user" / f"{unit_name(entry)}.service"
    if generated.exists():
        text = generated.read_text(encoding="utf-8", errors="ignore")
        if "Strata Console" in text:
            generated.unlink()
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cat["models"] = [m for m in cat["models"] if m["id"] != mid]
    if cat.get("default_model") == mid:
        cat["default_model"] = cat["models"][0]["id"]
    save_catalog(cat)
    return {"status": "removed", "model": mid, "files_deleted": [str(cfg)] if not cfg.exists() else [],
            "note": "Se quitó del catálogo. Los GGUF y packs no fueron borrados."}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        print(fmt % a, flush=True)

    def remote_guard(self) -> bool:
        if connection_core.remote_allowed(self.client_address[0], authorized(self)):
            return True
        self.send_json(401, {"error": {"type": "authentication_error", "message": "token requerido para clientes remotos"}})
        return False

    def control_guard(self) -> bool:
        if authorized(self):
            return True
        self.send_json(401, {"error": {"type": "authentication_error", "message": "token requerido"}})
        return False

    def end_headers(self):
        if connection_core.status(HOST, PORT, TOKEN_FILE).get("cors"):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Strata-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def send_json(self, code, payload):
        raw = jbytes(payload)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self) -> bytes:
        raw_length = self.headers.get("Content-Length", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length inválido") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError(f"cuerpo demasiado grande: máximo {MAX_BODY_BYTES} bytes")
        return self.rfile.read(length)

    # ---- proxy hacia el modelo activo ----
    def proxy(self, path: str, body: bytes | None):
        if not connection_core.remote_allowed(self.client_address[0], authorized(self)):
            return self.send_json(401, {"error": {"type": "authentication_error", "message": "token requerido para clientes remotos"}})
        if evaluation_core.is_blocked():
            return self.send_json(423, {"error": {"code": "EVALUATION_IN_PROGRESS", "message": "el modelo está bloqueado durante la evaluación", "job_id": evaluation_core.active_job()}})
        cat = load_catalog()
        mid = None
        if body:
            try:
                mid = json.loads(body).get("model")
            except (ValueError, json.JSONDecodeError):
                mid = None
        target = mid if mid in model_ids(cat) else (cat.get("default_model") or get_active())
        trace_id = None
        if body and path.split("?", 1)[0] in {"/v1/chat/completions", "/v1/messages", "/v1/responses", "/v1/embeddings"}:
            try:
                trace_id = trace_core.begin(path.split("?", 1)[0], target, json.loads(body),
                                           bool(json.loads(body).get("stream")))
            except (ValueError, TypeError, json.JSONDecodeError):
                trace_id = None
        try:
            port = switch_to(target, cat)
        except (TimeoutError, KeyError, subprocess.CalledProcessError) as exc:
            if trace_id:
                trace_core.finish(trace_id, 503, error=str(exc))
            return self.send_json(503, {"error": {"type": "server_error", "message": str(exc)}})
        req = urllib.request.Request(f"http://{HOST}:{port}{path}", data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in {"host", "content-length", "connection"}:
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                ctype = resp.headers.get("Content-Type", "")
                if "text/event-stream" in ctype or resp.headers.get("Transfer-Encoding"):
                    # streaming: copiar de a trozos, sin buffering (Hermes usa SSE)
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        if k.lower() not in {"content-length", "connection", "transfer-encoding"}:
                            self.send_header(k, v)
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        if trace_id:
                            trace_core.append_sse(trace_id, chunk)
                        self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"0\r\n\r\n")
                    if trace_id:
                        trace_core.finish(trace_id, resp.status)
                    return
                payload = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in {"content-length", "connection", "transfer-encoding"}:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                if trace_id:
                    try:
                        trace_core.finish(trace_id, resp.status, json.loads(payload))
                    except (ValueError, TypeError):
                        trace_core.finish(trace_id, resp.status)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            if trace_id:
                trace_core.finish(trace_id, exc.code, error=payload.decode("utf-8", errors="replace")[:2000])
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (OSError, ValueError) as exc:
            if trace_id:
                trace_core.finish(trace_id, 502, error=str(exc))
            self.send_json(502, {"error": {"type": "proxy_error", "message": str(exc)}})

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/panel", "/index.html"):
            page = (UI / "index.html").read_bytes() if (UI / "index.html").exists() else b"<h1>no panel</h1>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        if p.startswith("/web/"):
            f = (UI / p[5:]).resolve()
            if not str(f).startswith(str(UI.resolve())) or not f.is_file():
                self.send_error(404)
                return
            data = f.read_bytes()
            kind = "text/css" if f.suffix == ".css" else "application/javascript" if f.suffix == ".js" else "text/html"
            self.send_response(200)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if p == "/v1/models":
            if not connection_core.remote_allowed(self.client_address[0], authorized(self)):
                self.send_json(401, {"error": {"type": "authentication_error", "message": "token requerido para clientes remotos"}})
                return
            cat = load_catalog()
            self.send_json(200, {"object": "list",
                                 "data": [{"id": m, "object": "model"} for m in model_ids(cat)]})
            return
        if p == "/health":
            self.send_json(200, {"status": "ok"})
            return
        if p == "/api/status":
            if not self.remote_guard():
                return
            cat = load_catalog()
            self.send_json(200, {"status": "ok", "active_model": get_active(),
                                 "models": [status_of(m) for m in cat["models"]],
                                 "gpu": gpu_state(), "ram": ram_state()})
            return
        if p == "/api/detail":
            if not self.remote_guard():
                return
            cat = load_catalog()
            mid = first_query(self.path, "model") or cat.get("default_model")
            e = find(cat, mid)
            if not e:
                self.send_json(404, {"error": {"message": f"modelo desconocido: {mid}"}})
                return
            self.send_json(200, detail_of(e))
            return
        if p == "/api/config-get":
            if not self.remote_guard():
                return
            cat = load_catalog()
            mid = first_query(self.path, "model") or cat.get("default_model")
            e = find(cat, mid)
            if not e:
                self.send_json(404, {"error": {"message": f"modelo desconocido: {mid}"}})
                return
            cfg = json.loads(safe_child(CONFIGS, Path(e["config"]).name).read_text(encoding="utf-8"))
            args = cfg.get("args", [])
            def flag(f):
                return args[args.index(f) + 1] if f in args else None
            self.send_json(200, {"model": mid, "file": str(BASE / e["config"]),
                                 "sampling": cfg.get("sampling") or {},
                                 "values": {"max_context": flag("--max-context"), "kv": flag("--kv"),
                                            "spec": flag("--spec"), "spec_min_p": flag("--spec-min-p"),
                                            "vram_reserve_mib": flag("--vram-reserve-mib"),
                                            "pcie_frac": flag("--pcie-frac"),
                                            "lookup_chain": flag("--lookup-chain"),
                                            "reasoning_budget_tokens": cfg.get("reasoning_budget_tokens"),
                                            "idle_unload_s": cfg.get("idle_unload_s"),
                                            "lazy_load": cfg.get("lazy_load"),
                                            "fit_max_tokens": cfg.get("fit_max_tokens"),
                                            "parallel": cfg.get("parallel")}})
            return
        if p == "/api/optimize":
            if not self.remote_guard():
                return
            q = query(self.path)
            try:
                ctx = int(q.get("context", ["200000"])[0])
            except (TypeError, ValueError):
                self.send_json(400, {"error": {"code": "INVALID_CONTEXT", "message": "context debe ser un entero"}})
                return
            model = q.get("model", [""])[0]
            entry = find(load_catalog(), model) if model else None
            self.send_json(200, optimize_core.optimize(ctx, q.get("profile", ["balanced"])[0], entry=entry))
            return
        if p == "/api/traces":
            if not authorized(self):
                self.send_json(401, {"error": {"message": "token requerido"}})
                return
            q = dict(kv.split("=", 1) for kv in self.path.split("?", 1)[1].split("&") if "=" in kv) if "?" in self.path else {}
            self.send_json(200, {"traces": trace_core.list_traces(int(q.get("limit", 50)))})
            return
        if p.startswith("/api/traces/"):
            if not authorized(self):
                self.send_json(401, {"error": {"message": "token requerido"}})
                return
            item = trace_core.get(p.rsplit("/", 1)[-1])
            self.send_json(200 if item else 404, item or {"error": {"message": "traza no encontrada"}})
            return
        if p.startswith("/api/evaluations/"):
            if not self.remote_guard():
                return
            evaluation_id = p.rsplit("/", 1)[-1]
            item = job_core.get(evaluation_id)
            self.send_json(200 if item else 404, item or {"error": {"code": "EVALUATION_NOT_FOUND", "message": "evaluación no encontrada"}})
            return
        if p == "/api/jobs":
            if not self.remote_guard():
                return
            try:
                limit = max(1, min(int(first_query(self.path, "limit", "50") or 50), 100))
            except ValueError:
                self.send_json(400, {"error": {"code": "INVALID_LIMIT", "message": "limit debe ser un entero"}})
                return
            self.send_json(200, {"jobs": job_core.list_jobs(limit)})
            return
        if p.startswith("/api/jobs/"):
            if not self.remote_guard():
                return
            job_id = p.rsplit("/", 1)[-1]
            item = job_core.get(job_id)
            self.send_json(200 if item else 404, item or {"error": {"code": "JOB_NOT_FOUND", "message": "job no encontrado"}})
            return
        if p == "/api/openapi.json":
            if not self.remote_guard():
                return
            if not OPENAPI.is_file():
                self.send_json(503, {"error": {"code": "OPENAPI_MISSING", "message": "falta el contrato OpenAPI"}})
                return
            self.send_json(200, json.loads(OPENAPI.read_text(encoding="utf-8")))
            return
        if p == "/api/params-help":
            if not self.remote_guard():
                return
            if not PARAMS_HELP.is_file():
                self.send_json(503, {"error": {"code": "PARAMETER_SCHEMA_MISSING", "message": "falta el esquema de parámetros"}})
                return
            self.send_json(200, json.loads(PARAMS_HELP.read_text(encoding="utf-8")))
            return
        if p == "/api/history":
            if not self.remote_guard():
                return
            q = query(self.path)
            mid = q.get("model", [load_catalog().get("default_model")])[0]
            try:
                mid = validate_model_id(mid)
            except ValueError:
                self.send_json(400, {"error": {"code": "INVALID_MODEL_ID", "message": "modelo inválido"}})
                return
            try:
                since = int(q.get("since", ["0"])[0])
            except ValueError:
                self.send_json(400, {"error": {"code": "INVALID_SINCE", "message": "since debe ser un entero"}})
                return
            self.send_json(200, {"model": mid, "rows": history_core.history(mid, since)})
            return
        if p == "/api/history-compare":
            if not self.remote_guard():
                return
            q = query(self.path)
            mid = q.get("model", [load_catalog().get("default_model")])[0]
            try:
                mid = validate_model_id(mid)
            except ValueError:
                self.send_json(400, {"error": {"code": "INVALID_MODEL_ID", "message": "modelo inválido"}})
                return
            self.send_json(200, {"model": mid, "setups": history_core.compare_setups(mid)})
            return
        if p == "/api/update-status":
            if not self.remote_guard():
                return
            cat = load_catalog()
            info = update_core.check_update(cat, fetch=(first_query(self.path, "fresh", "0") == "1"))
            info["engine_version"] = update_core.engine_version(cat.get("engine_root", ""))
            self.send_json(200, info)
            return
        if p == "/api/update-notifications":
            if not self.remote_guard():
                return
            self.send_json(200, update_monitor.status())
            return
        if p == "/api/backends":
            if not authorized(self):
                self.send_json(401, {"error": {"message": "token requerido"}})
                return
            self.send_json(200, backend_core.status(HOST, PORT))
            return
        if p == "/api/connection":
            if not authorized(self):
                self.send_json(401, {"error": {"message": "token requerido"}})
                return
            self.send_json(200, connection_core.status(HOST, PORT, TOKEN_FILE))
            return
        if p == "/api/tunnel-status":
            if not self.remote_guard():
                return
            self.send_json(200, tunnel_core.status(public=True))
            return
        if p == "/api/catalog":
            if not authorized(self):
                self.send_json(401, {"error": {"message": "token requerido"}})
                return
            self.send_json(200, load_catalog())
            return
        if p.startswith("/v1/"):
            self.proxy(self.path, None)
            return
        self.send_error(404)

    def do_POST(self):
        p = self.path.split("?")[0]
        if p in ("/v1/chat/completions", "/v1/messages", "/v1/responses", "/v1/embeddings"):
            try:
                body = self.read_body()
            except ValueError as exc:
                return self.send_json(413, {"error": {"type": "request_too_large", "message": str(exc)}})
            self.proxy(self.path, body)
            return
        if not self.control_guard():
            return
        try:
            body = self.read_body()
        except ValueError as exc:
            self.send_json(413, {"error": {"type": "request_too_large", "message": str(exc)}})
            return
        try:
            req = json.loads(body or b"{}")
        except ValueError:
            self.send_json(400, {"error": {"message": "JSON invalido"}})
            return
        cat = load_catalog()
        try:
            if p.startswith("/api/evaluations/") and p.endswith("/apply"):
                evaluation_id = p.split("/")[-2]
                try:
                    selected = evaluation_core.apply_result(evaluation_id, int(req.get("candidate_index")), cat)
                except (TypeError, ValueError) as exc:
                    raise ValueError(str(exc)) from exc
                self.send_json(200, selected)
            elif p == "/api/evaluations":
                try:
                    context = max(4096, min(int(req.get("context", 200000)), 262144))
                    runs = max(1, min(int(req.get("runs", 3)), 8))
                    long_chars = max(1024, min(int(req.get("long_prompt_chars", 120000)), 500000))
                except (TypeError, ValueError) as exc:
                    raise ValueError("context, runs y long_prompt_chars deben ser enteros") from exc
                model = req.get("model") or cat.get("default_model") or get_active()
                if not model:
                    raise ValueError("selecciona un modelo para evaluar")
                job = evaluation_core.submit(cat, model, context, str(req.get("profile", "balanced")), runs, long_chars,
                                              self.headers.get("Idempotency-Key"))
                self.send_json(202, {"status": job["status"], "job_id": job["id"]})
            elif p.startswith("/api/jobs/") and p.endswith("/cancel"):
                job_id = p.split("/")[-2]
                self.send_json(200 if job_core.cancel(job_id) else 409, {"job_id": job_id, "status": "cancel_requested"})
            elif p == "/api/select":
                model = validate_model_id(req.get("model"))
                if not find(cat, model):
                    raise ValueError(f"modelo desconocido: {model}")
                key = self.headers.get("Idempotency-Key")
                job = job_core.submit("model.select", {"model": model},
                                       lambda _job_id: {"active_model": model, "port": switch_to(model, cat)},
                                       key)
                self.send_json(202, {"status": job["status"], "job_id": job["id"]})
            elif p == "/api/stop":
                e = find(cat, req["model"])
                if not e:
                    raise ValueError(f"modelo desconocido: {req['model']}")
                systemctl("stop", unit_name(e))
                if e.get("legacy_unit"):
                    systemctl("stop", e["legacy_unit"])
                self.send_json(200, {"status": "stopped", "model": req["model"]})
            elif p == "/api/unload":
                e = find(cat, req["model"])
                if not e:
                    raise ValueError(f"modelo desconocido: {req['model']}")
                self.send_json(200, http_json(f"http://{HOST}:{e['port']}/unload", "POST", b"{}", 20))
            elif p == "/api/load":
                e = find(cat, req["model"])
                if not e:
                    raise ValueError(f"modelo desconocido: {req['model']}")
                self.send_json(200, http_json(f"http://{HOST}:{e['port']}/load", "POST", b"{}", 60))
            elif p == "/api/add":
                self.send_json(200, add_model(cat, req))
            elif p == "/api/remove":
                self.send_json(200, remove_model(cat, req["model"]))
            elif p == "/api/config":
                e = find(cat, req["model"])
                if not e:
                    raise ValueError(f"modelo desconocido: {req['model']}")
                path = safe_child(CONFIGS, Path(e["config"]).name)
                if not path.is_file():
                    raise ValueError("configuración de modelo no encontrada")
                cfg = json.loads(path.read_text(encoding="utf-8"))
                cfg.setdefault("sampling", {}).update(req.get("sampling") or {})
                for k in ("reasoning_budget_tokens", "fit_max_tokens", "idle_unload_s",
                          "lazy_load", "api_monitor", "parallel", "expert_profile_save",
                          "api_key"):
                    if k in req:
                        cfg[k] = req[k]
                a = cfg["args"]
                for key, flag in ENGINE_FLAGS.items():
                    if key in req:
                        if flag in a:
                            a[a.index(flag) + 1] = str(req[key])
                        else:
                            a += [flag, str(req[key])]
                for key, flag in ENGINE_BOOLS.items():
                    if key in req:
                        if req[key] and flag not in a:
                            a.append(flag)
                        elif not req[key] and flag in a:
                            a.remove(flag)
                cfg["args"] = a
                bak = path.with_suffix(".json.bak")
                bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
                path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                self.send_json(200, {"status": "saved", "file": str(path), "backup": str(bak),
                                     "note": "se aplica al reiniciar el modelo"})
            elif p == "/api/default":
                if not find(cat, req["model"]):
                    raise ValueError(f"modelo desconocido: {req['model']}")
                cat["default_model"] = req["model"]
                save_catalog(cat)
                self.send_json(200, {"status": "ok", "default_model": req["model"]})
            elif p == "/api/update":
                key = self.headers.get("Idempotency-Key")
                job = job_core.submit("engine.update", {}, lambda _job_id: update_core.do_update(cat), key)
                self.send_json(202, {"status": job["status"], "job_id": job["id"]})
            elif p == "/api/update-revert":
                self.send_json(200, update_core.revert_update(cat, req["to_commit"]))
            elif p == "/api/connection":
                result = connection_core.apply(str(req.get("mode", "local")), bool(req.get("cors", False)))
                self.send_json(200, result)
            elif p == "/api/tunnel-start":
                job = job_core.submit("tunnel.start", {"force_key": bool(req.get("force_key", True))},
                                       lambda _job_id: tunnel_core.start(PORT, force_key=bool(req.get("force_key", True))),
                                       self.headers.get("Idempotency-Key"))
                self.send_json(202, {"status": job["status"], "job_id": job["id"]})
            elif p == "/api/tunnel-stop":
                job = job_core.submit("tunnel.stop", {}, lambda _job_id: tunnel_core.stop(), self.headers.get("Idempotency-Key"))
                self.send_json(202, {"status": job["status"], "job_id": job["id"]})
            elif p == "/api/fit-check":
                paths = req.get("gguf_paths") or ([req["gguf_path"]] if req.get("gguf_path") else [])
                self.send_json(200, history_core.fit_check(paths,
                                                           int(req.get("max_context", 200000)),
                                                           str(req.get("kv", "q4_0"))))
            else:
                self.send_error(404)
        except KeyError as exc:
            self.send_json(400, {"error": {"message": f"falta el campo {exc}"}})
        except ValueError as exc:
            self.send_json(400, {"error": {"message": str(exc)}})
        except (TimeoutError, subprocess.SubprocessError, OSError) as exc:
            self.send_json(500, {"error": {"message": str(exc)}})


if __name__ == "__main__":
    LOGS.mkdir(exist_ok=True)
    print(f"Strata Console en http://{HOST}:{PORT}  (panel: /; token stored in {TOKEN_FILE})", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
