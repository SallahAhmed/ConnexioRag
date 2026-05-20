# Connexio Production Monitoring & Observability

Adds production-grade error tracking (Sentry) and metrics/logs (Grafana Cloud) across the
Connexio ecosystem using only **forever-free** SaaS tiers. No self-hosted monitoring servers —
both Python services run on Hugging Face Spaces (single port 7860) and the Node backend runs on
Hostinger shared/app hosting (no Docker, no second process).

> **Status of accounts:** Grafana Cloud ✅ created · Sentry ✅ created · No uptime pinger
> (cron-job.org health pings already keep the HF Spaces awake — they do **not** sleep).

---

## Components & current state (verified in repos)

| Service | Path | Runtime | Already has |
| :--- | :--- | :--- | :--- |
| Node Backend | `f:\connexio_back2` | Express (`app.js`) on Hostinger | nothing |
| Connexio RAG | `c:\Users\salla\Connexios` | FastAPI (`src/main.py`) on HF Space `ConnexioRag` | Prometheus `/metrics` ✅ |
| MasarX Agent | `f:\MasarX_A` | FastAPI (`src/main.py`) on HF Space `ConnexioAgent` | Prometheus `/metrics` ✅ |
| Frontend | `f:\Connexio_Frontend2` | Vite + React 19 (`src/main.jsx`) | nothing |

**Already done (do not redo):** both Python services call `setup_metrics(app)` and expose Prometheus
counters/histograms at the obfuscated path `/TrhBVe_m5gg2002_E5VVqS`
(`prometheus-client==0.25.0` is in `src/Requirements.txt`). The gap is purely **getting that data
out to Grafana Cloud**, plus error tracking and the missing Celery Beat scheduler.

---

## Architecture decisions

### 1. Sentry = errors + performance (highest ROI, lowest effort)
One Sentry **project per service** (4 DSNs total). SDKs push outbound over HTTPS, so they work
identically on HF Spaces and Hostinger. Sentry "performance" transactions also give us latency,
throughput, and error-rate per endpoint — covering most "is it up / slow / erroring" needs on its own.

> Free tier = 5k errors + 10k performance txns / month. We **must** set
> `traces_sample_rate ≈ 0.1` or a busy production will exhaust the quota and go blind.

### 2. Grafana Cloud metrics & logs = OpenTelemetry SDK **push** (not scrape)
Prometheus normally *scrapes* `/metrics`. Grafana Cloud's free tier will **not** reach into HF/Hostinger
to scrape, and we have no Alloy/agent to run. So every service **pushes** to Grafana Cloud's
**OTLP gateway** over HTTPS using the OpenTelemetry SDK (in-process). One mechanism, no extra
processes, works on shared hosting. The existing `/metrics` endpoints stay as a local debug convenience.

**Implementation per runtime (important nuance):**
- **Python (RAG + MasarX):** auto-instrumentation via `opentelemetry-instrument` wrapping uvicorn in
  `start.sh`. Gives traces + metrics + logs with zero code in `main.py`. Conditional on
  `OTEL_EXPORTER_OTLP_ENDPOINT` being set, so plain uvicorn runs locally with no overhead.
- **Node backend:** **metrics only** via a standalone OTel `MeterProvider` + `@opentelemetry/host-metrics`
  in `instrument.js`. We deliberately do **not** register a tracer provider here because `@sentry/node`
  v8 runs its own OpenTelemetry tracing and a second tracer provider would conflict. Request traces
  stay in Sentry; CPU/memory/event-loop metrics go to Grafana.

> **Rejected: Grafana Beyla.** Beyla is eBPF-based and needs privileged kernel access (`CAP_BPF`, root,
> `/sys/kernel` mounts) — unavailable on HF Spaces and Hostinger shared hosting. The OpenTelemetry SDK
> (in-process) is the correct choice when you own the code but can't run a privileged agent.
>
> **Rejected: Grafana Alloy sidecar.** Reuses the `/metrics` scrape but needs the Alloy binary baked
> into each HF Dockerfile + an extra process, and cannot run on Hostinger shared hosting at all.

### 3. Celery Beat is missing in production
Both `start.sh` files launch only `celery worker` + `uvicorn`. Scheduled jobs (stale-session cleanup,
digests, workload alerts) never fire. Fix: run beat **embedded in the worker** with `-B` (one process,
fine at this scale) rather than a separate background process.

---

## Proposed changes

### A. Node Backend — `f:\connexio_back2`

#### [MODIFY] `package.json`
Add deps:
- `@sentry/node` (+ `@sentry/profiling-node` optional) — error + performance tracking.
- `@opentelemetry/sdk-node`, `@opentelemetry/auto-instrumentations-node`,
  `@opentelemetry/exporter-metrics-otlp-http`, `@opentelemetry/exporter-trace-otlp-proto` — OTLP push to Grafana Cloud.

#### [NEW] `instrument.js`
Sentry + OpenTelemetry init. Must be imported **first**, before everything else.

#### [MODIFY] `app.js`
- `import './instrument.js'` as the very first line.
- Register Sentry Express error handler **after** routes are mounted (Sentry v8 style: `Sentry.setupExpressErrorHandler(app)`), wired into `bootstrap(app)` flow.

> Backend metrics travel via OTLP (in-process exporter) — no `/metrics` route needed on Hostinger
> shared hosting since nothing can scrape it there.

### B. Connexio RAG — `c:\Users\salla\Connexios`

#### [MODIFY] `src/Requirements.txt`
Add: `sentry-sdk[fastapi]`, `opentelemetry-distro`, `opentelemetry-exporter-otlp`,
`opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-logging`.

#### [MODIFY] `src/main.py`
- At top of module (before app creation): `import sentry_sdk` + `sentry_sdk.init(dsn=..., traces_sample_rate=..., environment=...)` guarded by `if SENTRY_DSN`.
- OTLP exporters configured via env vars (see table) — FastAPI auto-instrumentation hooks `app`.
- Keep existing `setup_metrics(app)` (local `/metrics` debug endpoint).

#### [MODIFY] `start.sh`
```bash
# was: celery -A celery_app worker --loglevel=info &
celery -A celery_app worker -B --loglevel=info &      # -B = embedded beat scheduler
uvicorn main:app --host 0.0.0.0 --port 7860
```

#### [MODIFY] `src/helpers/config.py`
Add settings fields: `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` (so Pydantic loads them from env without erroring).

### C. MasarX Agent — `f:\MasarX_A`
Same shape as RAG:
- [MODIFY] `src/requirements.txt` — add the same Sentry + OTLP packages.
- [MODIFY] `src/main.py` — add `sentry_sdk.init(...)`; OTLP via env; keep `setup_metrics(app)`.
- [MODIFY] `start.sh` — `celery -A celery_app worker -B --loglevel=info &`.
- [MODIFY] `src/helpers/config.py` — add `SENTRY_*` settings fields.

### D. Frontend — `f:\Connexio_Frontend2`

#### [MODIFY] `package.json`
Add `@sentry/react`.

#### [MODIFY] `src/main.jsx`
`Sentry.init({ dsn: import.meta.env.VITE_SENTRY_DSN, integrations: [browserTracingIntegration(), replayIntegration()], tracesSampleRate: 0.1, replaysOnErrorSampleRate: 1.0 })` before `ReactDOM.createRoot`.

#### [MODIFY] `vite.config.js` (optional)
Add `@sentry/vite-plugin` later for source-map upload (better stack traces). Skip for v1.

> Frontend metrics (Grafana Faro) are out of scope for v1 — Sentry React covers errors + web vitals.

---

## Environment variables / secrets to add

### Sentry — one DSN per project (create 4 projects in Sentry: Node, RAG (Python), MasarX (Python), React)

| Where | Variable | Value |
| :--- | :--- | :--- |
| Hostinger env (backend) | `SENTRY_DSN` | backend project DSN |
| HF Space `ConnexioRag` secret | `SENTRY_DSN` | RAG project DSN |
| HF Space `ConnexioAgent` secret | `SENTRY_DSN` | MasarX project DSN |
| Frontend `.env` (build-time) | `VITE_SENTRY_DSN` | React project DSN |
| all of the above | `SENTRY_ENVIRONMENT` | `production` |
| all of the above | `SENTRY_TRACES_SAMPLE_RATE` | `0.1` |

### Grafana Cloud OTLP — same gateway values for all three backend services
From Grafana Cloud → **Connections → OTLP / "Configure OpenTelemetry"** (gives endpoint + instance ID + a token; base64 `instanceID:token` for Basic auth).

| Variable | Value |
| :--- | :--- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://otlp-gateway-<zone>.grafana.net/otlp` |
| `OTEL_EXPORTER_OTLP_HEADERS` | `Authorization=Basic <base64(instanceID:token)>` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_SERVICE_NAME` | `connexio-backend` / `connexio-rag` / `masarx-agent` |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.namespace=connexio,deployment.environment=production` |
| `OTEL_METRICS_EXPORTER` | `otlp` |
| `OTEL_TRACES_EXPORTER` | `otlp` (Python only; Node traces go to Sentry) |
| `OTEL_LOGS_EXPORTER` | `otlp` (Python only) |

> Set the OTEL vars in **HF Space secrets** for the two Python spaces and in **Hostinger env** for Node.
> The Node backend only reads `OTEL_EXPORTER_OTLP_ENDPOINT/_HEADERS/_PROTOCOL` + `OTEL_SERVICE_NAME`
> (metrics-only); the `*_EXPORTER` signal vars matter only for the Python `opentelemetry-instrument` path.

> **Node OTel version pin (learned the hard way):** keep `@opentelemetry/sdk-metrics` on the **1.30.x**
> line with `@opentelemetry/host-metrics@^0.35.4`. Pinning sdk-metrics to 2.x creates a duplicate copy
> and throws `Unsupported Aggregation` from host-metrics. See buglog `bug-057`.

---

## Where to view things
- **Sentry:** sentry.io → each project's Issues (errors) + Performance (latency/throughput).
- **Grafana Cloud metrics:** grafana.net → Explore / Dashboards (Prometheus data source) — request counts, latency histograms, host/runtime metrics from OTel.
- **Grafana Cloud logs:** Grafana → Drilldown → Logs (Loki) — stdout routed through the OTLP gateway, filterable by `service.name`.
- **Celery jobs (optional, local):** run Flower locally pointed at the **production Upstash Redis** broker (see security note).

---

## ⚠️ Security note (carried from the original plan)
The original plan pasted a **live-looking Upstash Redis URL with its password** into the Flower
`docker run` command. That is your Celery broker credential. **Rotate that Upstash token** and never
commit it. If you run Flower locally, pass the broker URL via an env var, e.g.:
```bash
docker run -d -p 5556:5556 -e CELERY_BROKER_URL="$UPSTASH_REDIS_URL" mher/flower
```

---

## Verification plan

### Local
1. Backend: `npm start`, hit a route, trigger a deliberate `throw` on a test route → confirm the error appears in Sentry within ~1 min.
2. RAG / MasarX: run `uvicorn`, hit `/TrhBVe_m5gg2002_E5VVqS` → confirm Prometheus text; raise a test exception → confirm Sentry receives it.
3. Confirm OTel exporter logs "exported N metrics" (or no auth errors) on startup.
4. Frontend: `npm run dev`, throw in a component → confirm in Sentry React project.

### Production (after deploy)
1. Set all secrets above on HF Spaces + Hostinger, redeploy.
2. Confirm metrics for all three services appear in Grafana Explore (filter `service.name`).
3. Confirm logs flow into Grafana Loki.
4. Confirm `celery worker -B` logs show beat scheduling ticks on the HF Space.

---

## Build order
1. **Sentry on all 4 services** (highest value, lowest risk) + Celery Beat `-B` fix.
2. **Grafana OTLP** wiring on the 3 backend services.
3. Deploy, set secrets, verify dashboards.
