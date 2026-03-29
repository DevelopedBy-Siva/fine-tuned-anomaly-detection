# IncidentLens

> A policy-bound autonomous observability agent that clusters logs into incidents,
> investigates with LLM tool use and runbooks, takes safe automated actions,
> and verifies outcomes over time.

---

## Architecture

```
  ┌─────────────┐     push      ┌─────────────────┐
  │  Log Server │ ──────────── ▶│   Grafana Loki  │
  │  (FastAPI)  │               └────────┬────────┘
  └─────────────┘                        │ poll every 30s
                                         ▼
                                ┌─────────────────┐
                                │  loki_watcher   │
                                └────────┬────────┘
                                         │ raw log lines
                                         ▼
                          ┌──────────────────────────┐
                          │   Parser + Signatures    │  extract level, exception,
                          │   Clustering (2min window)│  deduplicate by signature
                          └─────────────┬────────────┘
                                        │ new or updated incident
                                        ▼
                   ┌────────────────────────────────────────┐
                   │           Evidence Bundle              │
                   │  sample logs · related incidents       │
                   │  runbook match · root cause link       │
                   └──────────────────┬─────────────────────┘
                                      │
                                      ▼
                   ┌────────────────────────────────────────┐
                   │         Investigation Loop             │
                   │  LLM tool-calling agent (≤4 rounds)    │
                   │  tools: logs · incidents · runbook     │
                   │         timeline                       │
                   │  fallback → single-shot analysis       │
                   └──────────────────┬─────────────────────┘
                                      │ IncidentAnalysis
                                      ▼
                   ┌────────────────────────────────────────┐
                   │           Policy Engine                │
                   │  confidence gate · cooldown check      │
                   │  count floor · disposition rules       │
                   └──────┬──────────────────┬─────────────-┘
                          │ blocked          │ allowed
                          ▼                  ▼
                    (log only)      ┌────────────────────┐
                                    │   Notifications    │
                                    │  Discord · Email   │
                                    └────────────────────┘
                                             │
                                             ▼
                   ┌────────────────────────────────────────┐
                   │          Action Executor               │
                   │  auto_enrich · auto_suppress           │
                   │  ActionLog write                       │
                   └──────────────────┬─────────────────────┘
                                      │ (15 min later)
                                      ▼
                   ┌────────────────────────────────────────┐
                   │             Verifier                   │
                   │  re-check outcome · mark resolved      │
                   │  re-escalate if still firing           │
                   │  emit runbook tuning hints             │
                   └────────────────────────────────────────┘
```

**Everything is inspectable.** Every incident exposes:

```
GET /api/incidents/{id}/evidence      → what the agent saw
GET /api/incidents/{id}/actions       → what the agent did and why
GET /api/incidents/{id}/investigation → full audit trail
```

---

## What the agent can do

| Action            | Description                                                             |
| ----------------- | ----------------------------------------------------------------------- |
| Cluster logs      | Groups related errors by signature + time window                        |
| Match runbooks    | Deterministic pattern matching against 30 YAML runbooks                 |
| Investigate       | LLM tool-calling loop — fetches logs, related incidents, runbook steps  |
| Enrich incidents  | Writes ticket body + cause explanation to the incident record           |
| Suppress noise    | Auto-ignores high-confidence `NO_ACTION` incidents                      |
| Notify            | Routes to Discord (escalate/dev) or email (on-call)                     |
| Chain root causes | Links cascade incidents to their origin                                 |
| Verify outcomes   | Re-checks incidents 15 min after action, marks resolved or re-escalates |

## What the agent cannot do

The agent is deliberately **read-only on infrastructure**. It will never:

- Restart services or pods
- Roll back deployments
- Modify databases or queues
- Delete or mutate logs
- Take any action outside the IncidentLens database

All high-impact actions (paging on-call, creating tickets externally) require human approval via the notification channel. The agent surfaces the decision; humans execute it.

---

## Demo scenarios

Run these from the dashboard (demo project) or via API:

| Scenario                | What it simulates                             | Expected agent behavior                                       |
| ----------------------- | --------------------------------------------- | ------------------------------------------------------------- |
| `db_cascade`            | Pool exhaustion → payment timeout → NPE       | Three linked incidents, root cause chained to pool exhaustion |
| `memory_leak`           | Gradual heap growth → OOM kill → restart      | Severity escalates from OBSERVE → ESCALATE across re-analyses |
| `deployment_gone_wrong` | Config change halves pool → OOM               | Deployment log linked as root cause                           |
| `auth_cascade`          | Redis down → JWT invalid → rate limiter fires | Session store identified as root cause                        |

**Full demo loop (~3 min):**

1. Start demo project, click "DB Cascade" scenario
2. Watch incidents appear and cluster in real time
3. Open any incident → "Why did the agent do this?" drawer
4. See: evidence gathered → tools called → policy decision → actions taken
5. Wait 15 min → verifier marks incident resolved or re-escalates

---

## Safety design

IncidentLens uses **deterministic safeguards on top of LLM reasoning**:

- **Policy engine** gates every action — confidence threshold, cooldown, count floor
- **Runbook fast-path** — high-confidence pattern matches bypass LLM entirely
- **Validation layer** — `validate_analysis()` enforces severity/disposition consistency rules regardless of LLM output
- **Fallback chain** — investigation loop → single-shot LLM → no action (never crashes silently)
- **Audit trail** — every decision is recorded in `InvestigationRun` and `ActionLog` tables

---

## Tech stack

| Layer          | Technology                        |
| -------------- | --------------------------------- |
| Log generation | FastAPI + Grafana Loki            |
| Backend        | FastAPI + SQLAlchemy + PostgreSQL |
| LLM            | Groq (llama-3.3-70b-versatile)    |
| Observability  | Langfuse                          |
| Notifications  | Discord webhooks + SMTP           |
| Frontend       | React + Tailwind CSS              |

---

## Quick start

```bash
# 1. Clone and install
pip install -r log-analyzer/requirements.txt

# 2. Configure
cp .env.example .env
# Fill: GROQ_API_KEY, LOKI_URL, LOKI_USERNAME, LOKI_API_KEY, DATABASE_URL

# 3. Migrate
python migrations/incidentlens_migrate.py

# 4. Run
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. Run log server (separate terminal)
uvicorn server:app --host 0.0.0.0 --port 5001

# 6. Frontend
cd log-analyzer-frontend && npm install && npm start
```

---

## Environment variables

```env
# Loki
LOKI_URL=https://logs-prod-XXX.grafana.net
LOKI_USERNAME=your_numeric_id
LOKI_API_KEY=your_loki_token

# LLM
GROQ_API_KEY=your_groq_key

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/log_analyzer

# Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@yourco.com
SMTP_PASSWORD=your_app_password

# App
SECRET_KEY=change_in_production
CORS_ORIGINS=http://localhost:3000
LOG_SERVER_URL=http://localhost:5001
POLL_INTERVAL=30
```

---

Built with: FastAPI · PostgreSQL · Groq · Langfuse · React · Grafana Loki
