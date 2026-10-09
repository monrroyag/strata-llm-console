#!/usr/bin/env python3
"""Bot Telegram de control remoto para Strata Console.

Configuración exclusiva por entorno:
  TELEGRAM_STRATA_BOT_TOKEN=...
  TELEGRAM_STRATA_ADMIN_IDS=123,456

No imprime tokens. Solo usuarios allowlisted pueden ejecutar acciones.
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import state_store

BASE = Path(__file__).resolve().parent
API = os.environ.get("STRATA_CONSOLE_API", "http://127.0.0.1:8090")
TOKEN = os.environ.get("TELEGRAM_STRATA_BOT_TOKEN", "")
ADMIN_IDS = {x.strip() for x in os.environ.get("TELEGRAM_STRATA_ADMIN_IDS", "").split(",") if x.strip()}
ADMIN_CHAT_IDS = {x.strip() for x in os.environ.get("TELEGRAM_STRATA_CHAT_IDS", "").split(",") if x.strip()}
OFFSET_FILE = BASE / "data" / "telegram-offset"
LANG_FILE = BASE / "data" / "telegram-languages.json"
LANGS = {"es": "🇪🇸 Español", "en": "🇬🇧 English", "pt": "🇧🇷 Português", "fr": "🇫🇷 Français", "de": "🇩🇪 Deutsch"}
TEXT = {
    "en": {"menu": "STRATA CONTROL CENTER\nSelect an operation.", "status": "Local status", "active": "Active", "models": "Models", "traces": "Traces", "connection": "Connection", "backends": "Backends", "optimizer": "Optimizer", "update": "Update Strata", "stop": "Stop model", "language": "Language", "back": "Back", "choose_model": "Select a model.", "not_found": "Model not found.", "confirm_stop": "Confirm stopping <code>{model}</code>?", "confirm_remove": "Remove <code>{model}</code> from the catalog? GGUF/packs are not deleted.", "confirm_update": "Confirm updating the official Strata repository?", "cancel": "Cancel", "confirm": "Confirm", "unauthorized": "Private bot: chat_id not authorized.", "no_traces": "No observed requests.", "last_traces": "Latest traces", "error": "Error", "response": "Response", "reasoning": "Exposed reasoning", "detail": "Detail", "no_model": "No model selected.", "saved": "Language saved: {language}"},
    "es": {"menu": "CENTRO DE CONTROL STRATA\nSelecciona una operación.", "status": "Estado local", "active": "Activo", "models": "Modelos", "traces": "Trazas", "connection": "Conexión", "backends": "Backends", "optimizer": "Optimizador", "update": "Actualizar Strata", "stop": "Detener modelo", "language": "Idioma", "back": "Volver", "choose_model": "Selecciona un modelo.", "not_found": "Modelo no encontrado.", "confirm_stop": "¿Confirmar detener <code>{model}</code>?", "confirm_remove": "¿Quitar <code>{model}</code> del catálogo? No se borran GGUF/packs.", "confirm_update": "¿Confirmar actualización del repositorio oficial de Strata?", "cancel": "Cancelar", "confirm": "Confirmar", "unauthorized": "Bot privado: chat_id no autorizado.", "no_traces": "No hay requests observados.", "last_traces": "Últimas trazas", "error": "Error", "response": "Respuesta", "reasoning": "Razonamiento expuesto", "detail": "Detalle", "no_model": "No hay modelo seleccionado.", "saved": "Idioma guardado: {language}"},
    "pt": {"menu": "CENTRO DE CONTROLE STRATA\nSelecione uma operação.", "status": "Estado local", "active": "Ativo", "models": "Modelos", "traces": "Rastreamento", "connection": "Conexão", "backends": "Backends", "optimizer": "Otimizador", "update": "Atualizar Strata", "stop": "Parar modelo", "language": "Idioma", "back": "Voltar", "choose_model": "Selecione um modelo.", "not_found": "Modelo não encontrado.", "confirm_stop": "Confirmar parada de <code>{model}</code>?", "confirm_remove": "Remover <code>{model}</code> do catálogo? GGUF/packs não serão apagados.", "confirm_update": "Confirmar atualização do repositório oficial do Strata?", "cancel": "Cancelar", "confirm": "Confirmar", "unauthorized": "Bot privado: chat_id não autorizado.", "no_traces": "Nenhuma requisição observada.", "last_traces": "Últimos rastreamentos", "error": "Erro", "response": "Resposta", "reasoning": "Raciocínio exposto", "detail": "Detalhes", "no_model": "Nenhum modelo selecionado.", "saved": "Idioma salvo: {language}"},
    "fr": {"menu": "CENTRE DE CONTRÔLE STRATA\nSélectionnez une opération.", "status": "État local", "active": "Actif", "models": "Modèles", "traces": "Traçabilité", "connection": "Connexion", "backends": "Backends", "optimizer": "Optimiseur", "update": "Mettre à jour Strata", "stop": "Arrêter le modèle", "language": "Langue", "back": "Retour", "choose_model": "Sélectionnez un modèle.", "not_found": "Modèle introuvable.", "confirm_stop": "Confirmer l'arrêt de <code>{model}</code> ?", "confirm_remove": "Retirer <code>{model}</code> du catalogue ? Les GGUF/packs ne seront pas supprimés.", "confirm_update": "Confirmer la mise à jour du dépôt officiel Strata ?", "cancel": "Annuler", "confirm": "Confirmer", "unauthorized": "Bot privé : chat_id non autorisé.", "no_traces": "Aucune requête observée.", "last_traces": "Dernières traces", "error": "Erreur", "response": "Réponse", "reasoning": "Raisonnement exposé", "detail": "Détail", "no_model": "Aucun modèle sélectionné.", "saved": "Langue enregistrée : {language}"},
    "de": {"menu": "STRATA CONTROL CENTER\nOperation auswählen.", "status": "Lokaler Status", "active": "Aktiv", "models": "Modelle", "traces": "Nachverfolgung", "connection": "Verbindung", "backends": "Backends", "optimizer": "Optimierer", "update": "Strata aktualisieren", "stop": "Modell stoppen", "language": "Sprache", "back": "Zurück", "choose_model": "Modell auswählen.", "not_found": "Modell nicht gefunden.", "confirm_stop": "<code>{model}</code> wirklich stoppen?", "confirm_remove": "<code>{model}</code> aus dem Katalog entfernen? GGUF/Packs werden nicht gelöscht.", "confirm_update": "Aktualisierung des offiziellen Strata-Repos bestätigen?", "cancel": "Abbrechen", "confirm": "Bestätigen", "unauthorized": "Privater Bot: chat_id nicht autorisiert.", "no_traces": "Keine Anfragen beobachtet.", "last_traces": "Letzte Traces", "error": "Fehler", "response": "Antwort", "reasoning": "Ausgegebenes Denken", "detail": "Details", "no_model": "Kein Modell ausgewählt.", "saved": "Sprache gespeichert: {language}"},
}


def _languages():
    data = state_store.load_or_migrate("telegram_languages", LANG_FILE, {})
    return data if isinstance(data, dict) else {}


def lang_for(chat_id):
    value = _languages().get(str(chat_id), "en")
    return value if value in LANGS else "en"


def set_lang(chat_id, lang):
    data = _languages(); data[str(chat_id)] = lang
    state_store.put("telegram_languages", data)
    state_store.atomic_json_export(LANG_FILE, data, mode=0o600)


def tx(chat_id, key, **kwargs):
    template = TEXT.get(lang_for(chat_id), TEXT["es"]).get(key, TEXT["en"].get(key, key))
    return template.format(**kwargs)


def tg(method: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=35) as resp:
        data = json.loads(resp.read())
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram API error"))
    return data.get("result")


def console_token() -> str:
    try:
        return (BASE / "token").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def local(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Strata-Token": console_token(), "Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=35) as resp:
        return json.loads(resp.read())


def allowed(chat_id, user_id=None) -> bool:
    if user_id is None or str(user_id) not in ADMIN_IDS:
        return False
    chat = str(chat_id)
    # Private chats are safe when the user id is allowlisted. Groups need an explicit chat allowlist.
    return chat == str(user_id) or chat in ADMIN_CHAT_IDS


def safe(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def short(text, limit=3600):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "\n… [recortado]"


def keyboard(rows):
    return {"inline_keyboard": [[{"text": text, "callback_data": data} for text, data in row] for row in rows]}


def send(chat_id, text, rows=None, message_id=None):
    payload = {"chat_id": chat_id, "text": short(text), "parse_mode": "HTML", "disable_web_page_preview": True}
    if rows is not None:
        payload["reply_markup"] = keyboard(rows)
    if message_id:
        payload.update({"message_id": message_id})
        try:
            return tg("editMessageText", payload)
        except Exception:
            return tg("sendMessage", {k: v for k, v in payload.items() if k != "message_id"})
    return tg("sendMessage", payload)


def menu(chat_id, message_id=None):
    return send(chat_id, f"<b>{tx(chat_id, 'menu')}</b>", [
        [("📊 " + tx(chat_id, "status"), "status"), ("🧠 " + tx(chat_id, "models"), "models")],
        [("🧪 " + tx(chat_id, "traces"), "traces"), ("⚙️ " + tx(chat_id, "optimizer"), "opt")],
        [("🌐 " + tx(chat_id, "connection"), "connection"), ("🔌 " + tx(chat_id, "backends"), "backends")],
        [("⬆️ " + tx(chat_id, "update"), "update"), ("🛑 " + tx(chat_id, "stop"), "stop")],
        [("🌐 " + tx(chat_id, "language"), "languages")],
    ], message_id)


def language_menu(chat_id):
    return send(chat_id, f"<b>{tx(chat_id, 'language')}</b>", [[(label, f"setlang:{code}")] for code, label in LANGS.items()] + [[("↩️ " + tx(chat_id, "back"), "menu")]])


def status(chat_id):
    d = local("/api/status"); active = d.get("active_model")
    rows = [f"<b>{tx(chat_id, 'status')}</b>", f"{tx(chat_id, 'active')}: <code>{safe(active)}</code>",
            f"Modelos: {len(d.get('models', []))}",
            f"GPU: {safe(d.get('gpu', {}).get('util'))}% · VRAM {safe(d.get('gpu', {}).get('used_mib'))}/{safe(d.get('gpu', {}).get('total_mib'))} MiB",
            f"RAM: {safe(d.get('ram', {}).get('used_mib'))}/{safe(d.get('ram', {}).get('total_mib'))} MiB"]
    send(chat_id, "\n".join(rows), [[("↩️ Menú", "menu")]])


def models(chat_id):
    d = local("/api/status"); rows = []
    for m in d.get("models", []):
        state = "✅" if m.get("active") else "🟡" if m.get("running") else "⚪"
        rows.append([(f"{state} {m.get('label', m['id'])}", f"model:{m['id']}")])
    send(chat_id, f"<b>{tx(chat_id, 'models')}</b>\n{tx(chat_id, 'choose_model')}", rows + [[("↩️ " + tx(chat_id, "back"), "menu")]])


def model_detail(chat_id, mid):
    d = local("/api/status"); m = next((x for x in d.get("models", []) if x.get("id") == mid), None)
    if not m:
        send(chat_id, "❌ " + tx(chat_id, "not_found"), [[("↩️ " + tx(chat_id, "models"), "models")]]); return
    text = (f"<b>{safe(m.get('label'))}</b>\n<code>{safe(mid)}</code>\n\n"
            f"Estado: {safe(m.get('state') or ('activo' if m.get('active') else 'detenido'))}\n"
            f"Puerto: {safe(m.get('port'))}\nContexto: {safe(m.get('context'))}\nKV: {safe(m.get('kv'))}\n"
            f"VRAM libre: {safe(m.get('vram_free_mib'))} MiB")
    send(chat_id, text, [[("▶️ Usar", f"use:{mid}"), ("🛑 Detener", f"askstop:{mid}")],
                         [("🗑️ Quitar catálogo", f"askremove:{mid}")], [("↩️ Modelos", "models")]])


def traces(chat_id):
    d = local("/api/traces?limit=8"); rows = d.get("traces", [])
    if not rows:
        send(chat_id, f"<b>{tx(chat_id, 'traces')}</b>\n{tx(chat_id, 'no_traces')}", [[("↩️ " + tx(chat_id, "back"), "menu")]]); return
    text = [f"<b>{tx(chat_id, 'last_traces')}</b>"]
    for r in rows:
        icon = "❌" if r.get("status") == "error" else "✅" if r.get("status") == "completed" else "⏳"
        text.append(f"{icon} <code>{safe(r.get('id'))}</code> · {safe(r.get('model'))} · {safe(r.get('duration_ms'))} ms")
        if r.get("error"): text.append(f"   <b>Error:</b> {safe(r['error'])[:500]}")
    send(chat_id, "\n".join(text), [[("🔎 Ver detalle", f"trace:{rows[0]['id']}")], [("↩️ Menú", "menu")]])


def trace_detail(chat_id, tid):
    r = local(f"/api/traces/{urllib.parse.quote(tid)}")
    text = (f"<b>Traza {safe(tid)}</b>\nEstado: {safe(r.get('status'))}\n"
            f"Modelo: <code>{safe(r.get('model'))}</code>\nDuración: {safe(r.get('duration_ms'))} ms\n"
            f"\n<b>{tx(chat_id, 'response')}</b>\n{safe(r.get('response') or '—')}\n")
    if r.get("error"): text += f"\n<b>❌ Error</b>\n<code>{safe(r['error'])}</code>\n"
    if r.get("reasoning"): text += f"\n<b>{tx(chat_id, 'reasoning')}</b>\n{safe(r['reasoning'])}\n"
    send(chat_id, text, [[("↩️ " + tx(chat_id, "traces"), "traces"), ("↩️ " + tx(chat_id, "back"), "menu")]])


def connection(chat_id):
    d = local("/api/connection")
    send(chat_id, (f"<b>{tx(chat_id, 'connection')}</b>\nModo: {safe(d.get('mode'))}\nAPI local: <code>{safe(d.get('local_url'))}</code>\n"
                   f"API LAN: <code>{safe(d.get('lan_url') or 'no expuesta')}</code>\nCORS: {safe(d.get('cors'))}\n"
                   "Autenticación remota: Bearer token"), [[("↩️ Menú", "menu")]])


def backends(chat_id):
    d = local("/api/backends"); text = [f"<b>{tx(chat_id, 'backends')}</b>"]
    for b in d.get("backends", []): text.append(f"{'✅' if b['running'] else '⚪'} <b>{safe(b['label'])}</b>: {safe(b['api'])}\n   {safe(', '.join(b['features']))}")
    send(chat_id, "\n".join(text), [[("↩️ " + tx(chat_id, "back"), "menu")]])


def optimize(chat_id):
    d = local("/api/optimize?context=200000&profile=balanced")
    r = d.get("recommended") or {}; e = r.get("estimates", {})
    send(chat_id, (f"<b>{tx(chat_id, 'optimizer')}</b> 200k\nConfianza: {safe(d.get('confidence'))}\n"
                   f"KV: {safe(r.get('config', {}).get('kv'))}\nMTP: {safe(r.get('config', {}).get('spec'))}\n"
                   f"KV VRAM: {safe(e.get('kv_vram_mib'))} MiB\nExpert budget: {safe(e.get('expert_budget_mib'))} MiB\n"
                   f"{safe(r.get('why'))}"), [[("↩️ Menú", "menu")]])


def update(chat_id):
    d = local("/api/update-status")
    changes = d.get("changes") or []
    detail = "\n".join(f"• {safe(x.get('commit'))} {safe(x.get('date'))} — {safe(x.get('subject'))}" for x in changes[:5])
    if d.get("changelog_url"):
        detail += f"\n<a href=\"{safe(d.get('changelog_url'))}\">Changelog</a>"
    send(chat_id, (f"<b>{tx(chat_id, 'update')}</b>\nLocal: <code>{safe(d.get('local_commit'))}</code>\n"
                   f"Remoto: <code>{safe(d.get('remote_commit'))}</code>\nAtrás: {safe(d.get('behind'))}\n"
                   f"Actualización: {safe(d.get('update_available'))}\n{detail}"), [[("⬆️ Aplicar actualización", "askupdate")], [("↩️ Menú", "menu")]])


def callback(chat_id, data, callback_id):
    tg("answerCallbackQuery", {"callback_query_id": callback_id})
    if data == "languages": return language_menu(chat_id)
    if data.startswith("setlang:"):
        code = data.split(":", 1)[1]
        if code in LANGS: set_lang(chat_id, code)
        return menu(chat_id)
    if data == "menu": return menu(chat_id)
    if data == "status": return status(chat_id)
    if data == "models": return models(chat_id)
    if data == "traces": return traces(chat_id)
    if data == "connection": return connection(chat_id)
    if data == "backends": return backends(chat_id)
    if data == "opt": return optimize(chat_id)
    if data == "update": return update(chat_id)
    if data.startswith("model:"): return model_detail(chat_id, data[6:])
    if data.startswith("trace:"): return trace_detail(chat_id, data[6:])
    if data.startswith("use:"):
        local("/api/select", {"model": data[4:]}); return status(chat_id)
    if data.startswith("askstop:"):
        return send(chat_id, tx(chat_id, "confirm_stop", model=safe(data[8:])), [[(tx(chat_id, "confirm"), f"stop:{data[8:]}"), (tx(chat_id, "cancel"), "models")]])
    if data.startswith("stop:"):
        local("/api/stop", {"model": data[5:]}); return status(chat_id)
    if data.startswith("askremove:"):
        return send(chat_id, tx(chat_id, "confirm_remove", model=safe(data[10:])), [[(tx(chat_id, "confirm"), f"remove:{data[10:]}"), (tx(chat_id, "cancel"), "models")]])
    if data.startswith("remove:"):
        local("/api/remove", {"model": data[7:]}); return models(chat_id)
    if data == "askupdate":
        return send(chat_id, tx(chat_id, "confirm_update"), [[(tx(chat_id, "confirm"), "do_update"), (tx(chat_id, "cancel"), "menu")]])
    if data == "do_update":
        return send(chat_id, json.dumps(local("/api/update", {}), ensure_ascii=False, indent=2), [[("↩️ Menú", "menu")]])


def handle(update):
    msg = update.get("message") or {}
    cb = update.get("callback_query")
    chat_id = (cb or {}).get("message", msg).get("chat", {}).get("id")
    actor_id = ((cb or {}).get("from") or msg.get("from") or {}).get("id")
    if chat_id is None or not allowed(chat_id, actor_id):
        if chat_id is not None: send(chat_id, "⛔ " + tx(chat_id, "unauthorized"))
        return
    if cb: return callback(chat_id, cb.get("data", ""), cb.get("id"))
    user_lang = (msg.get("from") or {}).get("language_code", "")[:2]
    if user_lang in LANGS and str(chat_id) not in _languages(): set_lang(chat_id, user_lang)
    text = (msg.get("text") or "").strip()
    if text in ("/start", "/menu", "/help"): return menu(chat_id)
    if text == "/lang": return language_menu(chat_id)
    if text == "/status": return status(chat_id)
    if text == "/models": return models(chat_id)
    send(chat_id, "Usa /menu para abrir el centro de control.", [[("Abrir menú", "menu")]])


def main():
    if not TOKEN or not ADMIN_IDS:
        raise SystemExit("Configura TELEGRAM_STRATA_BOT_TOKEN y TELEGRAM_STRATA_ADMIN_IDS en el entorno.")
    me = tg("getMe")
    tg("setMyCommands", {"commands": [
        {"command": "start", "description": "Abrir centro de control"},
        {"command": "menu", "description": "Mostrar menú completo"},
        {"command": "status", "description": "Estado GPU/RAM/modelo"},
        {"command": "models", "description": "Listar modelos"},
        {"command": "help", "description": "Ayuda"},
        {"command": "lang", "description": "Cambiar idioma"},
    ]})
    print(f"Telegram Strata Control activo como @{me.get('username', 'bot')}; admins={len(ADMIN_IDS)}", flush=True)
    try: offset = int(OFFSET_FILE.read_text().strip())
    except (OSError, ValueError): offset = 0
    while True:
        try:
            updates = tg("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message", "callback_query"]})
            for item in updates:
                offset = item["update_id"] + 1
                OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True); OFFSET_FILE.write_text(str(offset))
                try: handle(item)
                except Exception as exc: print(f"control error: {type(exc).__name__}: {exc}", flush=True)
        except Exception as exc:
            print(f"poll error: {type(exc).__name__}", flush=True); time.sleep(5)


if __name__ == "__main__": main()
