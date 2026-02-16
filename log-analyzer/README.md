# Log Analyzer

A FastAPI service that ingests logs, detects anomalies, clusters incidents, performs intelligent analysis using runbooks and LLM, and routes notifications to appropriate channels based on severity and disposition.

## Overview

- **Multi-tenant projects** — Project-based authentication with API keys and JWT tokens
- **Log ingestion** — Receives logs from multiple sources and environments
- **Intelligent clustering** — Groups similar errors into incidents using signature-based deduplication
- **Dual analysis engine** — Runbook pattern matching with automatic LLM fallback
- **Smart routing** — Sends notifications to Discord (dev/escalate) or email (on-call) based on disposition
- **Incident management** — Track, filter, close, and ignore incidents via REST API
- **Log server control** — Start, stop, and monitor connected log servers

## Architecture

```
Log Sources → Ingest API → Parser → Signature Generation → Clustering
                                                              ↓
                                         Incident (new or updated)
                                                              ↓
                                    Runbook Match (pattern-based)
                                                              ↓
                                    LLM Analysis (if no runbook match)
                                                              ↓
                                         Notification Routing
                                         (Discord/Email)
```

## Project Structure

```
log-analyzer/
├── app/
│   ├── main.py                    # FastAPI app initialization
│   ├── api/                       # API route handlers
│   │   ├── routes_auth.py        # Authentication & project management
│   │   ├── routes_ingest.py      # Log ingestion & log server control
│   │   └── routes_incidents.py   # Incident management
│   ├── core/                      # Core business logic
│   │   ├── parser.py             # Log parsing
│   │   ├── signatures.py         # Signature generation
│   │   ├── clustering.py         # Incident clustering
│   │   ├── runbook_loader.py    # YAML runbook loading
│   │   ├── runbook_matcher.py   # Pattern matching
│   │   └── decision_engine.py   # LLM analysis (Groq)
│   ├── models/
│   │   └── schemas.py            # Pydantic models
│   └── services/                  # Support services
│       ├── storage.py            # PostgreSQL models
│       ├── auth.py               # JWT & password hashing
│       ├── validators.py         # URL/webhook/email validation
│       ├── notifications.py      # Discord & email notifications
│       └── cleanup.py            # Database cleanup
├── runbooks/                      # YAML runbook definitions
│   ├── db_connection_timeout.yaml
│   ├── file_not_found.yaml
│   ├── memory_error.yaml
│   ├── payment_failed.yaml
│   └── redis_connection.yaml
├── data/                          # Persistent data directory
├── requirements.txt
├── Dockerfile
└── README.md
```

## Setup

### Environment Variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql://log_user:password@localhost:5432/log_analyzer

# Authentication
SECRET_KEY=your-secret-key-change-in-production

# LLM Analysis (optional - falls back to runbooks only)
GROQ_API_KEY=your_groq_api_key_here

# Email Notifications (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Local Development

**1. Install PostgreSQL:**

```bash
# macOS
brew install postgresql
brew services start postgresql

# Ubuntu/Debian
sudo apt-get install postgresql
sudo systemctl start postgresql
```

**2. Create database:**

```bash
psql postgres
CREATE DATABASE log_analyzer;
CREATE USER log_user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE log_analyzer TO log_user;
\q
```

**3. Install Python dependencies:**

```bash
cd log-analyzer
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**4. Run the server:**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Root:** http://localhost:8000/ — Service info
- **Docs:** http://localhost:8000/docs — Swagger UI
- **Health:** http://localhost:8000/health — Health check

### Docker

```bash
docker build -t log-analyzer .
docker run -p 8000:8000 --env-file .env log-analyzer
```

## API Endpoints

### Authentication & Projects

| Method | Path                                  | Auth | Description                       |
| ------ | ------------------------------------- | ---- | --------------------------------- |
| POST   | `/api/auth/register`                  | No   | Register new project              |
| POST   | `/api/auth/login`                     | No   | Login to project (get JWT)        |
| GET    | `/api/auth/me`                        | JWT  | Get current project info          |
| PUT    | `/api/auth/settings`                  | JWT  | Update project settings           |
| POST   | `/api/auth/validate/url`              | No   | Validate log source URL           |
| POST   | `/api/auth/validate/discord-escalate` | No   | Validate Discord escalate webhook |
| POST   | `/api/auth/validate/discord-dev`      | No   | Validate Discord dev webhook      |
| POST   | `/api/auth/validate/email`            | No   | Validate email format             |

### Log Ingestion

| Method | Path          | Auth    | Description                             |
| ------ | ------------- | ------- | --------------------------------------- |
| POST   | `/api/ingest` | API Key | Ingest logs and create/update incidents |

### Incident Management

| Method | Path                                  | Auth | Description                 |
| ------ | ------------------------------------- | ---- | --------------------------- |
| GET    | `/api/incidents`                      | JWT  | List incidents with filters |
| GET    | `/api/incidents/{incident_id}`        | JWT  | Get single incident details |
| POST   | `/api/incidents/{incident_id}/close`  | JWT  | Mark incident as closed     |
| POST   | `/api/incidents/{incident_id}/ignore` | JWT  | Mark incident as ignored    |

### Log Server Control

| Method | Path                     | Auth    | Description           |
| ------ | ------------------------ | ------- | --------------------- |
| POST   | `/api/log-server/start`  | API Key | Start log generation  |
| POST   | `/api/log-server/stop`   | API Key | Stop log generation   |
| GET    | `/api/log-server/status` | API Key | Get log server status |

**Note:** Log server control endpoints are available in both `/api/` (API Key auth) and `/api/auth/` (JWT auth) routes.

## Authentication Methods

The system supports two authentication methods:

### 1. JWT Tokens (Frontend)

Used for web interface and user-facing endpoints:

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "password": "my-password"}'

# Use token
curl http://localhost:8000/api/incidents \
  -H "Authorization: Bearer <token>"
```

### 2. API Keys (Log Servers)

Used for log ingestion from external services:

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "X-API-Key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"source": "app", "environment": "prod", "logs": [...]}'
```

## How It Works

### 1. Log Ingestion Pipeline

**Step 1: Parse**

```python
ParsedLog(raw_line)
# Extracts: timestamp, level, message
```

**Step 2: Generate Signature**

```python
generate_signature(source, parsed_log)
# Creates: Unique hash for clustering similar errors
# Example: "log-server:ERROR:Database_connection_timeout_after"
```

**Step 3: Cluster**

```python
cluster_log(project_id, source, environment, parsed_log, signature)
# Finds existing incident within 5-minute window OR creates new one
# Updates: count, last_seen, sample_lines (max 10)
```

### 2. Analysis Engine (Dual Path)

**Path A: Runbook Matching**

- Loads YAML runbooks from `runbooks/` directory
- Scores each runbook against incident text (patterns)
- If score ≥ 50% → applies runbook analysis
- Checks escalation thresholds (e.g., "escalate after 20 occurrences")
- Example: Redis errors → "OBSERVE" until 15 occurrences → "ESCALATE"

**Path B: LLM Analysis (Fallback)**

- Triggers when no runbook matches
- Uses Groq (llama-3.3-70b-versatile) via LangChain
- Generates structured output:
  - Severity: low/medium/high/critical
  - Disposition: NO_ACTION/OBSERVE/NEEDS_DEV/NEEDS_ONCALL/ESCALATE
  - Summary, next steps, ticket title/body
- Validates consistency (e.g., critical severity requires ESCALATE)

### 3. Notification Routing

Based on `disposition` from analysis:

| Disposition  | Channel | Webhook/Config             | Use Case                      |
| ------------ | ------- | -------------------------- | ----------------------------- |
| ESCALATE     | Discord | `discord_webhook_escalate` | Critical issues, page on-call |
| NEEDS_ONCALL | Email   | `user_email` (SMTP)        | High severity, notify on-call |
| NEEDS_DEV    | Discord | `discord_webhook_dev`      | Standard dev tickets          |
| OBSERVE      | None    | —                          | Monitor for patterns          |
| NO_ACTION    | None    | —                          | Known noise                   |

### 4. Incident Lifecycle

```
NEW → open (count=1)
      ↓
  RECURRING (count increases within 5-min window)
      ↓
  ANALYZED (runbook or LLM)
      ↓
  NOTIFIED (Discord/Email based on disposition)
      ↓
  CLOSED/IGNORED (manual action via API)
```

## Configuration

### Clustering Parameters (in `app/core/clustering.py`)

- **CLUSTER_WINDOW_MINUTES** — Time window for grouping similar errors (default: 5)
- **MAX_SAMPLES** — Maximum sample logs to store per incident (default: 10)

### Runbook Thresholds

Runbooks support escalation based on occurrence count:

```yaml
disposition: OBSERVE
observe_threshold:
  count: 20 # Escalate after 20 occurrences
  window_minutes: 10 # Within 10 minutes
  escalate_to: NEEDS_DEV # New disposition
cooldown_minutes: 30 # Wait 30 min before re-notifying
```

### LLM Configuration (in `app/core/decision_engine.py`)

- **Model:** llama-3.3-70b-versatile (Groq)
- **Temperature:** 0.3 (deterministic)
- **Output:** Structured Pydantic model with validation
- **Validation rules:** Ensures severity/disposition alignment

## Runbooks

Runbooks are YAML files in the `runbooks/` directory that define pattern-based responses to known errors.

### Example Runbook

```yaml
id: db_connection_timeout
name: Database Connection Timeout
description: Database connection pool exhaustion or network issues
default_severity: high
disposition: NEEDS_ONCALL

patterns:
  - "database connection timeout"
  - "connection pool"
  - "regex:timeout.*db-.*\\d+s"

steps:
  - Check database server health and CPU/memory
  - Review connection pool settings (max_connections)
  - Check for long-running queries blocking connections
  - Verify network connectivity to database host
  - Review application logs for connection leaks

routing:
  team: database
  notify: [email, slack]

observe_threshold:
  count: 15
  window_minutes: 5
  escalate_to: ESCALATE

cooldown_minutes: 15
```

### Runbook Fields

- **id** — Unique identifier
- **patterns** — List of strings or `regex:` patterns to match
- **default_severity** — low/medium/high/critical
- **disposition** — Action to take (NO_ACTION, OBSERVE, NEEDS_DEV, NEEDS_ONCALL, ESCALATE)
- **steps** — Remediation steps for responders
- **observe_threshold** — Auto-escalation rules
- **cooldown_minutes** — Prevent notification spam

## Dependencies

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
pydantic==2.5.3
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0
pyyaml==6.0.1
langchain==0.1.0
langchain-groq==0.0.1
requests==2.31.0
```

## Database Schema

### Projects Table

- Multi-tenant isolation
- Stores: name, password_hash, api_key, log_source_url, notification configs
- Used for: Authentication and routing

### Incidents Table

- Stores: signature, source, environment, first_seen, last_seen, count, status
- Indexed by: project_id, signature, status, first_seen
- Status: open/closed/ignored

### Analyses Table

- Stores: severity, disposition, confidence, summary, next_steps, ticket details
- Links to: incident_id
- Tracks: analysis_source (runbook/llm), runbook_match_score

## Startup Behavior

On server start (see `app/main.py` lifespan):

1. Initializes PostgreSQL tables
2. **Cleans all incidents and analyses** (fresh slate)
3. Loads runbooks from `runbooks/` directory
4. Starts FastAPI server

**Note:** The cleanup behavior ensures a clean state for testing but should be removed or made optional for production use.

## Security Features

- **Password hashing** — bcrypt with SHA256 pre-hash for long passwords
- **JWT tokens** — HS256 with 24-hour expiration
- **API key authentication** — URL-safe tokens for log sources
- **Multi-tenant isolation** — All queries filtered by project_id
- **Validation** — URL, webhook, and email validation on registration
- **Test project protection** — Read-only mode for demo projects

## Use Cases

1. **SRE Teams** — Automatic incident detection and triage from production logs
2. **DevOps** — Centralized error tracking across multiple services
3. **On-call Engineers** — Smart notification routing (email for urgent, Discord for standard)
4. **Development Teams** — Automatic ticket drafts with context and next steps
5. **Log Analysis** — Pattern detection and anomaly clustering

## Limitations & Notes

- **5-minute clustering window** — Incidents are grouped within 5 minutes by default
- **Runbook caching** — Runbooks are loaded once at startup (requires restart to reload)
- **LLM rate limits** — Groq API has rate limits; consider adding retry logic
- **Database cleanup on startup** — Wipes all incidents/analyses (intended for testing)
- **Single project fallback** — If no API key provided, uses first active project

## Troubleshooting

**Database connection errors:**

```bash
# Check PostgreSQL is running
brew services list  # macOS
sudo systemctl status postgresql  # Linux

# Verify credentials in .env match database
psql -U log_user -d log_analyzer
```

**Runbooks not loading:**

```bash
# Check runbooks directory exists and has .yaml files
ls -la runbooks/

# Look for errors in server logs
[LOG-ANALYZER] Loaded 0 runbooks  # Bad - check YAML syntax
[LOG-ANALYZER] Loaded 5 runbooks  # Good
```

**LLM analysis not working:**

```bash
# Verify GROQ_API_KEY is set
echo $GROQ_API_KEY

# Check server logs for:
"Warning: GROQ_API_KEY not found. LLM analysis disabled."
```

**Notifications not sending:**

- Discord: Test webhook URL with Postman/curl
- Email: Verify SMTP settings and app password (not regular password)
- Check server logs for error messages

## Future Enhancements

- Configurable clustering window per project
- Runbook hot-reload without restart
- Notification cooldown tracking in database
- Incident deduplication across projects (optional)
- Webhook retry logic with exponential backoff
- Support for additional LLM providers (OpenAI, Anthropic)
- Web UI for runbook management
