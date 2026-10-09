#!/usr/bin/env python3
"""Generate the checked-in OpenAPI contract from the control-plane route table."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CONTROL = [{"ConsoleToken": []}]
BEARER = [{"BearerToken": []}]
ERROR = {"$ref": "#/components/responses/Error"}


def operation(summary: str, tags: list[str], *, security=CONTROL, body=False, status="200", query=None):
    out = {"tags": tags, "summary": summary, "security": security, "responses": {status: {"description": summary}}}
    if security and "401" not in out["responses"]:
        out["responses"]["401"] = ERROR
    if body:
        out["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/JSON"}}}}
    if query:
        out["parameters"] = query
    return out


def query_param(name: str, schema: dict, required: bool = False):
    return {"name": name, "in": "query", "required": required, "schema": schema}


paths = {}
def add(path: str, method: str, summary: str, tags: list[str], **kwargs):
    item = operation(summary, tags, **kwargs)
    path_parameters = re.findall(r"\{([^}]+)\}", path)
    if path_parameters:
        item.setdefault("parameters", [])
        item["parameters"] = [{"name": name, "in": "path", "required": True, "schema": {"type": "string"}} for name in path_parameters] + item["parameters"]
    paths.setdefault(path, {})[method] = item

add("/health", "get", "Liveness", ["Health"], security=[])
add("/v1/models", "get", "List available models", ["Gateway"], security=BEARER)
for path, summary in {
    "/v1/chat/completions": "OpenAI-compatible chat completion",
    "/v1/responses": "Responses-compatible forwarding",
    "/v1/messages": "Anthropic-compatible forwarding",
    "/v1/embeddings": "Embedding forwarding",
}.items():
    add(path, "post", summary, ["Gateway"], security=BEARER, body=True)

add("/api/status", "get", "Models and hardware status", ["Control"])
add("/api/detail", "get", "Model detail", ["Control"], query=[query_param("model", {"type": "string"})])
add("/api/catalog", "get", "Model catalog", ["Control"])
add("/api/backends", "get", "Runtime capability discovery", ["Control"])
add("/api/params-help", "get", "Versioned parameter help", ["Control"])
add("/api/openapi.json", "get", "This API contract", ["Control"])
add("/api/config-get", "get", "Read model configuration", ["Control"], query=[query_param("model", {"type": "string"})])
add("/api/config", "post", "Validate and save model configuration", ["Control"], body=True)
add("/api/add", "post", "Register a model", ["Control"], body=True, status="200")
add("/api/select", "post", "Select and load a model", ["Control"], body=True)
add("/api/load", "post", "Load a model", ["Control"], body=True)
add("/api/unload", "post", "Unload a model", ["Control"], body=True)
add("/api/stop", "post", "Stop a model", ["Control"], body=True)
add("/api/remove", "post", "Remove a model from the catalog", ["Control"], body=True)
add("/api/default", "post", "Set default model", ["Control"], body=True)
add("/api/fit-check", "post", "Check model fit", ["Control"], body=True)
add("/api/optimize", "get", "Evidence-backed optimization recommendation", ["Control"], query=[
    query_param("context", {"type": "integer", "minimum": 4096, "maximum": 262144}),
    query_param("profile", {"type": "string", "enum": ["balanced", "speed", "long", "code"]}),
    query_param("model", {"type": "string"}),
])
add("/api/history", "get", "Performance history", ["Observability"], query=[query_param("model", {"type": "string"}), query_param("since", {"type": "integer"})])
add("/api/history-compare", "get", "Compare recorded setups", ["Observability"], query=[query_param("model", {"type": "string"})])
add("/api/traces", "get", "Bounded request traces", ["Observability"], query=[query_param("limit", {"type": "integer", "minimum": 1, "maximum": 100})])
add("/api/traces/{trace_id}", "get", "Trace detail", ["Observability"])
add("/api/evaluations", "post", "Create measured evaluation", ["Control"], body=True, status="202")
add("/api/evaluations/{job_id}", "get", "Evaluation result/job status", ["Control"])
add("/api/evaluations/{job_id}/apply", "post", "Apply measured candidate", ["Control"], body=True)
add("/api/jobs", "get", "Durable jobs", ["Control"], query=[query_param("limit", {"type": "integer", "minimum": 1, "maximum": 100})])
add("/api/jobs/{job_id}", "get", "Job status", ["Control"])
add("/api/jobs/{job_id}/cancel", "post", "Cancel job", ["Control"], body=True)
add("/api/connection", "get", "Connection status", ["Control"])
add("/api/connection", "post", "Prepare connection change", ["Control"], body=True)
add("/api/tunnel-status", "get", "Tunnel status", ["Control"])
add("/api/tunnel-start", "post", "Start tunnel job", ["Control"], body=True, status="202")
add("/api/tunnel-stop", "post", "Stop tunnel job", ["Control"], body=True, status="202")
add("/api/update-status", "get", "Engine update check", ["Updates"])
add("/api/update-notifications", "get", "Engine and console update notifications", ["Updates"])
add("/api/update", "post", "Apply explicit engine update", ["Updates"], body=True, status="202")
add("/api/update-revert", "post", "Revert engine update", ["Updates"], body=True)

spec = {
    "openapi": "3.0.3",
    "info": {
        "title": "Strata LLM Console API",
        "version": VERSION,
        "description": "Authenticated control plane and OpenAI-compatible gateway for local inference.",
    },
    "servers": [{"url": "http://127.0.0.1:8090"}],
    "tags": [{"name": "Health"}, {"name": "Gateway"}, {"name": "Control"}, {"name": "Observability"}, {"name": "Updates"}],
    "components": {
        "securitySchemes": {
            "ConsoleToken": {"type": "apiKey", "in": "header", "name": "X-Strata-Token"},
            "BearerToken": {"type": "http", "scheme": "bearer"},
        },
        "responses": {"Error": {"description": "Structured error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}},
        "schemas": {
            "Error": {"type": "object", "required": ["error"], "properties": {"error": {"type": "object", "properties": {"code": {"type": "string"}, "type": {"type": "string"}, "message": {"type": "string"}}, "required": ["message"]}}},
            "JSON": {"type": "object", "additionalProperties": True},
        },
    },
    "paths": paths,
}
(ROOT / "docs/api/openapi.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"generated {len(paths)} paths for {VERSION}")
