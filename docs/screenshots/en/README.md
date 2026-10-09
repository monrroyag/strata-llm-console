# Strata LLM Console — English UI capture gallery

These captures were regenerated from the current English-first interface at a fixed 1440×1000 desktop viewport. They document the visible control surfaces and empty-state behavior; they are not benchmark results and do not imply that a model is loaded in the capture environment.

## 01 — Model inventory and grouped navigation

![Model inventory and grouped navigation](01-models.png)

Shows the four task groups — **Operate**, **Observe**, **Connect** and **System** — plus the model inventory entry point. This is where an operator selects, loads, unloads or removes a catalog entry.

## 02 — Performance

![Performance view](02-performance.png)

Shows the live metrics and historical-performance surface. The production view uses real engine telemetry when a model is available; an empty state is intentionally shown when no model is selected.

## 03 — Request traces

![Request traces](03-traces.png)

Shows the request-trace list and execution-detail area for prompts, engine-emitted reasoning, responses, tools, usage, latency and errors. No trace is fabricated when the backend has no observations.

## 04 — Connection

![Connection and exposure](04-connection.png)

Shows loopback/LAN mode, CORS opt-in, authentication guidance and copyable connection details. LAN is not enabled by default.

## 05 — Preferences

![Preferences](05-preferences.png)

Shows theme, density, motion, reasoning visibility and the quick-help explanation of each product area. Preferences are browser-local.

## 06 — Parameters

![Parameters](06-parameters.png)

Shows the parameter-editing surface backed by the versioned parameter schema. Engine flags, sampling values, restart requirements and validation belong here.

## 07 — Optimizer and measured evaluation

![Optimizer and measured evaluation](07-optimizer-evaluation.png)

Shows static/historical configuration analysis plus the **Measured Evaluation** panel. The evaluation blocks normal inference, tests candidate configurations with short and long prompts, reports speed/reliability/stability metrics and lets the operator apply one measured candidate.

## 08 — Strata updates

![Strata update center](08-updates.png)

Shows local/remote engine version status and the explicit update action. Checking status is read-only; applying an update is a separate controlled operation.

## 09 — Encrypted tunnel

![Encrypted tunnel](09-tunnel.png)

Shows tunnel status and the explicit start/stop controls. The tunnel surface does not display persisted API secrets.

## 10 — Model registration

![Model registration](10-registration.png)

Shows GGUF registration, pack/profile inputs and fit-check controls. Model artifacts remain outside Git and are not deleted by catalog removal.

## 11 — Activity

![Activity log](11-activity.png)

Shows local console activity and operator-visible action feedback. Request-level details belong in the Trace view.

## Capture contract

- Locale: English (`en-US`).
- Viewport: 1440×1000.
- Source: current `web/index.html`, `web/app.js`, `web/app.css` and `web/i18n.js`.
- Empty values such as `—` are intentional unavailable states, not invented telemetry.
- Numeric values shown in a live deployment come from the local API; these captures are UI documentation only.
