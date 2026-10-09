# Changelog

All notable changes to Strata LLM Console are documented here.

## 0.3.0 — 2026-10-09

- Add the branded `strata-console` operations CLI over the shared control API.
- Add a local chat workspace with streaming, reasoning visibility, effort controls, themes, local persistence and Markdown export.
- Generate and validate the OpenAPI contract in CI.
- Add HTTP surface tests, gateway rate limiting, bounded upstream responses and graceful SIGTERM shutdown.
- Add capability-based runtime drivers for Strata, Ollama and vLLM.
- Validate model configuration ranges and add Telegram update idempotency/rate limiting.
- Make Docker and Debian runtime state explicit and persistent without installation-directory symlinks.
- Prevent package hooks from cloning or executing upstream engine code; engine installation is an explicit operator action.
- Pin and verify the tunnel binary with SHA-256, add ETag-aware update checks and stale-cache reporting.

## 0.2.6 — 2026-10-09

- Monitor the Strata engine and console repository every 10 minutes.
- Show update details in the panel and Telegram without applying changes silently.
- Keep engine checkout bootstrap available as an explicit operator action.

## 0.2.5

- Bootstrap the official Strata checkout when it is absent.
- Preserve local engine changes during explicit updates.

## 0.2.4

- Publish the native Debian/Ubuntu package.
- Preserve transactional runtime state across upgrades.

## 0.2.1

- Add measured evaluation jobs, cancellation, ranking and reversible application.

## 0.1.0

- Initial authenticated control plane, OpenAI-compatible gateway, web panel and Telegram control surface.
