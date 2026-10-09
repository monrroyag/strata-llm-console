#!/usr/bin/env python3
"""STRATA CONSOLE command-line operator interface.

Dependency-free CLI for the same control surface exposed by the web panel.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BRAND = "STRATA CONSOLE // OPERATIONS"
DEFAULT_URL = os.environ.get("STRATA_CONSOLE_API", "http://127.0.0.1:8090").rstrip("/")


class CliError(RuntimeError):
    pass


class ConsoleClient:
    def __init__(self, base_url: str, token: str = "", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(self, path: str, method: str = "GET", payload: dict | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if self.token:
            request.add_header("X-Strata-Token", self.token)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(16 * 1024 * 1024)
        except urllib.error.HTTPError as exc:
            raw = exc.read(1024 * 1024)
            try:
                detail = json.loads(raw).get("error", {})
                message = detail.get("message") or str(detail) or exc.reason
            except (ValueError, TypeError):
                message = raw.decode("utf-8", "replace")[:400] or str(exc.reason)
            raise CliError(f"HTTP {exc.code}: {message}") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise CliError(f"No se pudo conectar a {self.base_url}: {exc}") from exc
        try:
            return json.loads(raw or b"{}")
        except ValueError as exc:
            raise CliError("La consola devolvió una respuesta JSON inválida") from exc


def _token(path: str | None) -> str:
    if path:
        return path
    value = os.environ.get("STRATA_CONSOLE_TOKEN", "")
    if value:
        return value
    candidates = [Path(__file__).resolve().parent / "token", Path(__file__).resolve().parent / "data" / "token", Path(os.environ["STRATA_CONSOLE_STATE_DIR"]) / "token" if os.environ.get("STRATA_CONSOLE_STATE_DIR") else None, Path.home() / ".local/state/strata-llm-console/token"]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            value = candidate.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            continue
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="strata-console", description=BRAND)
    parser.add_argument("--url", default=DEFAULT_URL, help="URL base de la consola")
    parser.add_argument("--token", help="token de control; también STRATA_CONSOLE_TOKEN")
    parser.add_argument("--json", action="store_true", help="emitir JSON sin formato humano")
    commands = parser.add_subparsers(dest="command", required=True)

    for name, help_text in {
        "status": "estado de modelos y hardware",
        "models": "inventario y ciclo de vida de modelos",
        "traces": "trazas de requests",
        "updates": "actualizaciones del engine y la consola",
        "connection": "estado o configuración de conexión",
        "tunnel": "estado y control del túnel",
    }.items():
        sub = commands.add_parser(name, help=help_text)
        if name == "traces":
            sub.add_argument("--limit", type=int, default=20)
        if name == "connection":
            sub.add_argument("--mode", choices=("local", "lan"))
            sub.add_argument("--cors", action="store_true")
            sub.add_argument("--apply", action="store_true")
        if name == "tunnel":
            sub.add_argument("action", nargs="?", choices=("status", "start", "stop"), default="status")

    optimize = commands.add_parser("optimize", help="recomendación basada en evidencia")
    optimize.add_argument("--context", type=int, default=200000)
    optimize.add_argument("--profile", choices=("balanced", "speed", "long", "code"), default="balanced")
    optimize.add_argument("--model")

    update = commands.add_parser("update", help="aplicar actualización explícita del engine")
    update.add_argument("--wait", action="store_true", help="esperar el job hasta terminar")

    config = commands.add_parser("config", help="leer o escribir configuración de modelo")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    config_get = config_sub.add_parser("get")
    config_get.add_argument("--model", required=True)
    config_set = config_sub.add_parser("set")
    config_set.add_argument("--model", required=True)
    config_set.add_argument("--values", required=True, help="objeto JSON de parámetros")

    evaluation = commands.add_parser("evaluation", help="evaluación medida de configuraciones")
    eval_sub = evaluation.add_subparsers(dest="evaluation_action", required=True)
    eval_run = eval_sub.add_parser("run")
    eval_run.add_argument("--model", required=True)
    eval_run.add_argument("--context", type=int, default=200000)
    eval_run.add_argument("--profile", choices=("balanced", "speed", "long", "code"), default="balanced")
    eval_run.add_argument("--runs", type=int, default=3)
    eval_run.add_argument("--long-prompt-chars", type=int, default=120000)
    eval_status = eval_sub.add_parser("status")
    eval_status.add_argument("job_id")
    eval_apply = eval_sub.add_parser("apply")
    eval_apply.add_argument("job_id")
    eval_apply.add_argument("candidate_index", type=int)

    chat = commands.add_parser("chat", help="chat OpenAI-compatible desde la terminal")
    chat.add_argument("--model")
    chat.add_argument("--message")
    chat.add_argument("--max-tokens", type=int, default=512)
    chat.add_argument("--stream", action="store_true", help="reservado para streaming futuro; no altera el contrato")

    serve = commands.add_parser("serve", help="iniciar el servidor local")
    serve.add_argument("server_args", nargs=argparse.REMAINDER)
    commands.add_parser("doctor", help="comprobación rápida de salud y API")
    return parser


def wait_job(client: ConsoleClient, job_id: str, interval: float = 1.0, timeout: int = 900):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = client.request(f"/api/jobs/{urllib.parse.quote(job_id)}")
        if result.get("status") in {"succeeded", "failed", "cancelled"}:
            return result
        time.sleep(interval)
    raise CliError("timeout esperando el job")


def _print(value, as_json: bool = False):
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                print(f"{key}:\n{json.dumps(item, ensure_ascii=False, indent=2)}")
            else:
                print(f"{key}: {item}")
    else:
        print(value)


def _run_chat(client: ConsoleClient, args):
    model = args.model
    message = args.message
    while not message:
        try:
            message = input("you> ").strip()
        except EOFError:
            return {"status": "closed"}
        if not message:
            continue
    body = {"messages": [{"role": "user", "content": message}], "max_tokens": args.max_tokens, "stream": False}
    if model:
        body["model"] = model
    result = client.request("/v1/chat/completions", method="POST", payload=body)
    if not args.json:
        choices = result.get("choices") or []
        if choices:
            print((choices[0].get("message") or {}).get("content", "—"))
    return result


def dispatch(args, client: ConsoleClient):
    if args.command == "status":
        return client.request("/api/status")
    if args.command == "models":
        return client.request("/api/status").get("models", [])
    if args.command == "traces":
        return client.request(f"/api/traces?limit={max(1, min(args.limit, 100))}")
    if args.command == "updates":
        return client.request("/api/update-notifications")
    if args.command == "optimize":
        params = urllib.parse.urlencode({"context": args.context, "profile": args.profile, "model": args.model or ""})
        return client.request(f"/api/optimize?{params}")
    if args.command == "update":
        result = client.request("/api/update", method="POST", payload={})
        if args.wait and result.get("job_id"):
            return wait_job(client, result["job_id"])
        return result
    if args.command == "config":
        if args.config_action == "get":
            return client.request(f"/api/config-get?model={urllib.parse.quote(args.model)}")
        values = json.loads(args.values)
        if not isinstance(values, dict):
            raise CliError("--values debe ser un objeto JSON")
        values["model"] = args.model
        return client.request("/api/config", method="POST", payload=values)
    if args.command == "evaluation":
        if args.evaluation_action == "run":
            return client.request("/api/evaluations", method="POST", payload={"model": args.model, "context": args.context, "profile": args.profile, "runs": args.runs, "long_prompt_chars": args.long_prompt_chars})
        if args.evaluation_action == "status":
            return client.request(f"/api/jobs/{urllib.parse.quote(args.job_id)}")
        return client.request(f"/api/evaluations/{urllib.parse.quote(args.job_id)}/apply", method="POST", payload={"candidate_index": args.candidate_index})
    if args.command == "connection":
        if not args.apply:
            return client.request("/api/connection")
        return client.request("/api/connection", method="POST", payload={"mode": args.mode or "local", "cors": bool(args.cors)})
    if args.command == "tunnel":
        if args.action == "status":
            return client.request("/api/tunnel-status")
        endpoint = "/api/tunnel-start" if args.action == "start" else "/api/tunnel-stop"
        return client.request(endpoint, method="POST", payload={"force_key": True} if args.action == "start" else {})
    if args.command == "doctor":
        return {"health": client.request("/health"), "status": client.request("/api/status"), "updates": client.request("/api/update-notifications")}
    if args.command == "chat":
        return _run_chat(client, args)
    if args.command == "serve":
        root = Path(__file__).resolve().parent
        os.execv(sys.executable, [sys.executable, str(root / "console_server.py"), *args.server_args])
    raise CliError(f"comando no soportado: {args.command}")


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        dispatch(args, ConsoleClient(args.url, _token(args.token)))
        return 0
    try:
        result = dispatch(args, ConsoleClient(args.url, _token(args.token)))
        if not (args.command == "chat" and not args.json):
            if not args.json:
                print(f"\n{BRAND}\n{'─' * len(BRAND)}")
            _print(result, args.json)
        return 0
    except (CliError, json.JSONDecodeError, ValueError) as exc:
        print(f"{BRAND} · error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
