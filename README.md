# IncidentLens

Policy-bound incident analysis agent for noisy logs.

IncidentLens turns raw error streams into clustered incidents, routes known patterns through deterministic runbooks, uses an LLM for unknown cases, applies guarded automated actions, and verifies outcomes after the fact. The goal is not "fully autonomous ops." The goal is faster triage with auditability and hard safety boundaries.

## Why This Project Matters

Modern services produce too many logs for manual triage, but letting an LLM act directly on infrastructure is risky. IncidentLens explores a middle ground:

- deterministic routing for known incidents
- bounded LLM reasoning for ambiguous incidents
- policy gates before any automated action
- full evidence, action, and verifier audit trails

This makes the system useful as an engineering project, not just an AI demo.

## Measured Results

These are the metrics worth keeping:

- `95.0%` root-cause accuracy on a manually labeled 20-case incident eval set
- `78.9%` runbook hit rate on analyzed incidents
- `1.05s` median investigation latency
- `4.84s` P95 agent runtime
- `88.7%` verifier resolution rate
- `115.3 logs/sec` clustering-only throughput on synthetic benchmark traffic
- `100.0%` suppression precision with `0.0%` suppression false positives on an 8-case suppression eval set

The full LLM-heavy pipeline is intentionally not presented as a throughput strength. In practice, the fast path is deterministic routing plus bounded investigation for only the incidents that need it.

## Architecture

```text
  Log Server / Loki
         |
         v
  Parser + Signature Normalization
         |
         v
  Incident Clustering
         |
         v
  Evidence Bundle
  - sample logs
  - related incidents
  - matched runbook
  - known root cause
         |
         v
  Analysis
  - runbook fast-path for known cases
  - LLM reasoning for unknown cases
         |
         v
  Policy Engine
  - confidence thresholds
  - cooldown checks
  - disposition floors
  - count-based escalation rules
         |
         v
  Actions
  - auto_enrich
  - auto_suppress
  - notifications
         |
         v
  Verifier
  - resolved vs still_firing
  - re-escalation for under-triaged incidents
  - runbook tuning hints
```

## What It Does

- Clusters repeated log events into incidents using normalized signatures and time windows
- Matches incidents against a runbook catalog for deterministic triage
- Builds an evidence bundle before analysis so decisions are grounded in context
- Uses LLM reasoning for incidents that do not cleanly match a runbook
- Links cascade incidents to earlier likely root causes
- Applies policy gating before any automated action
- Auto-enriches incidents with summaries and ticket-ready context
- Auto-suppresses high-confidence noise incidents
- Verifies whether actioned incidents actually quiet down

## Safety Model

IncidentLens is intentionally conservative.

- It never restarts services, edits infrastructure, mutates databases, or touches external systems beyond notifications
- High-impact actions stay human-controlled
- The policy layer can override weak or inconsistent model output
- All agent runs are inspectable through stored evidence, tool calls, decisions, and outcomes

This is the core design choice of the project: use AI for analysis, not uncontrolled execution.

## What’s Technically Interesting

- Post-action verification loop instead of treating model output as final truth
- Hybrid incident routing: deterministic runbooks for common cases, LLM reasoning for long-tail incidents
- Root-cause chaining across temporally related incidents
- End-to-end measurement harness for clustering quality, reasoning quality, suppression behavior, and latency

## Example Scenarios

- `db_cascade`
  Pool exhaustion -> payment timeout -> null pointer -> unhandled exception
- `auth_cascade`
  Session store failure -> JWT verification failures -> rate-limit anomalies
- `deployment_gone_wrong`
  Config change -> resource pressure -> downstream failures
- `memory_leak`
  Memory pressure -> OOM kill -> restart cycle

These scenarios exist to exercise clustering, runbook routing, cascade detection, verification, and auditability under repeatable conditions.

## Evaluation and Benchmarking

Use the built-in scripts to reproduce the main metrics:

```bash
# Live metrics from a project in the database
python log-analyzer/scripts/metrics_report.py live --project <project-name>

# LLM root-cause eval
python log-analyzer/scripts/metrics_report.py analysis-eval --project <project-name>

# One-command wrapper
./log-analyzer/scripts/run_resume_evals.sh <project-name>
```

The eval harness includes:

- labeled clustering cases
- labeled root-cause cases
- suppression/noise-policy cases
- cluster-only and full-pipeline benchmarks

## Screenshots

![Incident dashboard](./imgs/dashboard.png)
---
![Incidents view](./imgs/incident.png)
---
![Settings](./imgs/settings.png)
---
![Discord](./imgs/discord.png)
---
![Email](./imgs/email.png)

Recommended capture set:

- IncidentLens dashboard with clustered incidents
- Incident details / investigation view
- Settings / project configuration view
- Grafana dashboard showing the underlying log stream or service behavior

## Inspectability

Every incident can be inspected through APIs:

```text
GET /api/incidents/{id}/evidence
GET /api/incidents/{id}/actions
GET /api/incidents/{id}/investigation
```

That makes it easy to answer recruiter-style questions like:

- What evidence did the agent use?
- Was the decision deterministic or LLM-driven?
- What action was taken?
- Did the incident actually resolve?

## Tech Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Log generation: FastAPI, Grafana Loki
- Frontend: React, Tailwind CSS
- LLM: `llama-3.3-70b-versatile`
- Observability: Langfuse
- Notifications: Discord webhooks, SMTP email

## Quick Start

```bash
# Install backend deps
pip install -r log-analyzer/requirements.txt

# Start backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir log-analyzer

# Start log server in another terminal
pip install -r log-server/requirements.txt
python -m uvicorn server:app --host 0.0.0.0 --port 5001 --app-dir log-server

# Start frontend
cd log-analyzer-frontend
npm install
npm start
```

## Environment

Core backend environment:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/log_analyzer

# Loki
LOKI_URL=https://logs-prod-xxx.grafana.net
LOKI_USERNAME=your_numeric_id
LOKI_API_KEY=your_token

# LLM access
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.3-70b-versatile

# Optional fallback chain
GROQ_MODEL_FALLBACKS=model-a,model-b

# App
LOG_SERVER_URL=http://localhost:5001
CORS_ORIGINS=http://localhost:3000
RESET_DATA_ON_STARTUP=false
```