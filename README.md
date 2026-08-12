# IncidentLens

A policy-bound AIOps agent that turns noisy application logs into actionable incidents.

IncidentLens clusters logs from Grafana Loki, routes known failures through deterministic runbooks, uses LLM reasoning for ambiguous incidents, and gates automated actions behind safety policies.

## What It Does

* Clusters repeated logs into incidents using normalized signatures and time windows
* Matches known failures against deterministic runbooks
* Uses LLaMA 3 for ambiguous incidents and root-cause analysis
* Correlates related incidents to detect failure cascades
* Applies confidence, severity, and cooldown policies before automated actions
* Verifies outcomes and re-escalates unresolved incidents
* Generates incident summaries and sends Discord/email notifications

## Architecture

```text
Grafana Loki
     |
     v
Parser + Signature Normalization
     |
     v
Incident Clustering
     |
     v
Evidence Bundle
     |
     v
Runbook Match ----> LLM Investigation
     |                    |
     +---------+----------+
               |
               v
         Policy Engine
               |
               v
      Actions + Verification
```

Known failure patterns take the deterministic runbook path, while unknown or ambiguous incidents are analyzed using the LLM. The policy layer sits between analysis and automation so model output cannot directly trigger actions.

## Evaluation

IncidentLens includes a **150+ scenario labeled evaluation suite** covering:

* known production failure patterns
* incidents requiring LLM reasoning
* misleading severity and log-volume signals
* low-frequency, high-impact failures
* policy and auto-suppression edge cases

Latest completed evaluation:

```text
Correct triage:      157/170 (92.4%)
Unsafe automation:     9/170 (5.3%)
False suppression:     1/170 (0.6%)
```

A case is considered correctly triaged only when its expected **severity, disposition, and root cause or runbook** match.

Run the evaluation with:

```bash
python log-analyzer/scripts/metrics_report.py triage-eval
```

## Safety

IncidentLens intentionally limits autonomous actions.

The LLM cannot restart services, modify infrastructure, deploy code, or mutate databases. Automated actions are limited to incident enrichment, high-confidence noise suppression, and notifications.

High-impact remediation stays human-controlled.


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

## Tech Stack

**Backend:** FastAPI, SQLAlchemy, PostgreSQL
**Frontend:** React, Tailwind CSS
**LLM:** LLaMA 3.3 70B, LangChain, Groq
**Observability:** Grafana Loki, Langfuse
**Notifications:** Discord, SMTP email

## Quick Start

```bash
# Backend
pip install -r log-analyzer/requirements.txt
python -m uvicorn app.main:app --port 8000 --app-dir log-analyzer

# Log server
pip install -r log-server/requirements.txt
python -m uvicorn server:app --port 5001 --app-dir log-server

# Frontend
cd log-analyzer-frontend
npm install
npm start
```

## Environment

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/log_analyzer

LOKI_URL=https://logs-prod-xxx.grafana.net
LOKI_USERNAME=your_username
LOKI_API_KEY=your_token

GROQ_API_KEY=your_key
GROQ_API_KEY_2=your_second_key
GROQ_API_KEY_3=your_third_key
GROQ_MODEL=llama-3.3-70b-versatile

LOG_SERVER_URL=http://localhost:5001
CORS_ORIGINS=http://localhost:3000
```
