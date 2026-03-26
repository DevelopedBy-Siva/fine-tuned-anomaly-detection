# Log Server

A simple FastAPI service that generates realistic application logs and sends them directly to Grafana Loki.

---

## What it does

- Generates logs (info, warnings, errors) in memory
- Simulates real production issues (DB timeouts, OOM, auth failures, etc.)
- Ships logs directly to **Grafana Loki** (no Redis)
- Lets you trigger **scenarios** for demo/debugging
- Exposes a small API to control everything

---

## How it works

1. Logs are generated in memory
2. Buffered briefly
3. Sent to Loki using HTTP (`/loki/api/v1/push`)
4. Viewed in Grafana (Explore or dashboards)

---

## Environment variables

```env
LOGSHIPPER_API_KEY=your_api_key

LOKI_URL=https://logs-prod-XXX.grafana.net
LOKI_USERNAME=your_numeric_id
LOKI_API_KEY=your_loki_token

LOG_SERVICE_NAME=log-server
CORS_ORIGINS=http://localhost:3000
```

---

## Run locally

```bash
uvicorn server:app --host 0.0.0.0 --port 5001 --reload
```

- API: [http://localhost:5001](http://localhost:5001)
- Docs: [http://localhost:5001/docs](http://localhost:5001/docs)

---

## API

| Method | Endpoint               | Description           |
| ------ | ---------------------- | --------------------- |
| GET    | `/health`              | Check Loki connection |
| POST   | `/api/start`           | Start log generation  |
| POST   | `/api/stop`            | Stop generation       |
| GET    | `/api/status`          | Current stats         |
| POST   | `/api/scenario/{name}` | Run a scenario        |
| GET    | `/api/scenario`        | List scenarios        |

All `/api/*` endpoints require:

```
X-Api-Key: dev
```

---

## Quick test

Start generator:

```bash
curl -X POST "http://localhost:5001/api/start?duration=60" \
  -H "X-Api-Key: dev"
```

Or run a scenario:

```bash
curl -X POST http://localhost:5001/api/scenario/db_cascade \
  -H "X-Api-Key: dev"
```

---

## View logs (Grafana)

Go to **Explore → Loki** and run:

```logql
{service="log-server"}
```

Useful filters:

```logql
{service="log-server"} |= "ERROR"
{service="log-server", scenario="db_cascade"}
```

---

## Scenarios

- `db_cascade`
- `auth_cascade`
- `deployment_gone_wrong`
- `memory_leak`

Each scenario emits a sequence of related logs over time.

---

## Notes

- Logs are currently plain text (not fully structured JSON yet)
- Loki is the only transport (Redis removed)
- Most logs are INFO by default (~70%)

---

## Use case

- Demoing observability setups
- Testing log pipelines
- Simulating production incidents

---

That’s it — start the server, generate logs, and watch them in Grafana.
