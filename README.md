# Log Anomaly

An agentic log monitoring system that autonomously detects, clusters, analyzes, and routes production errors using event-driven architecture, pattern matching, and LLM-based decision-making.

**Live Demo:** https://log-anomaly.vercel.app

## Overview

Log Anomaly Agent autonomously processes application logs by grouping similar errors, analyzing their severity, and routing notifications to the right people through Discord or email. The agent uses runbook-based pattern matching for known errors and LLM-powered analysis for unknown patterns, making intelligent triage decisions without manual intervention.

The system consists of four main components:

- **Log Server** - Simulates production logs with realistic errors
- **Redis Stream** - Event transport layer between log server and analyzer
- **Log Analyzer + Worker** - Consumes stream events, clusters logs, analyzes incidents
- **Frontend Dashboard** - View and manage incidents through a web interface

## Screenshots

**Dashboard View**
![Dashboard](imgs/dashboard.jpeg)

**Incident Details**
![Incident Details](imgs/incidents.jpeg)

**Registration Page**
![Registration](imgs/register.jpeg)

**Login Page**
![Login](imgs/login.jpeg)

**Settings Page**
![Settings](imgs/settings.jpeg)

**Discord Message**
![Discord](imgs/discord.png)

**Email**
![Email](imgs/email.png)

## Architecture

```
┌─────────────┐
│ Log Server  │ Generates realistic production logs
│  (Render)   │ with errors, warnings, and info messages
└──────┬──────┘
       │ XADD every 3s
       │ (Redis Stream)
       ▼
┌─────────────┐
│Redis Stream │ Durable event queue with consumer groups
│ (Redis      │ Guarantees at-least-once delivery
│  Cloud)     │ Auto-reclaims stuck entries after 60s
└──────┬──────┘
       │ XREADGROUP (blocking, 1s timeout)
       ▼
┌─────────────┐
│   Worker    │ Consumes stream → Parses logs
│  (Render)   │ → Clusters into incidents
│             │ → Runbook match or LLM analysis
│             │ → Routes notifications
└──────┬──────┘
       │ PostgreSQL (NeonDB)
       ▼
┌─────────────┐
│  Frontend   │ Polls /api/incidents every 5s
│  (Vercel)   │ View incidents, manage settings,
│             │ control log generation
└─────────────┘
```

## Features

**Event-Driven Pipeline**

- Log server pushes to Redis Stream every 3 seconds
- Worker consumes via `XREADGROUP` — reacts within 1s of each entry
- Consumer groups enable multiple worker instances without duplicate processing
- Failed entries stay in PEL and are auto-reclaimed after 60s via `XAUTOCLAIM`

**Intelligent Log Processing**

- Automatic log parsing and signature generation
- Redis-backed clustering (groups similar errors within 2-minute windows)
- Deduplication with occurrence counting
- Re-analysis triggered at occurrence milestones (5x, 10x, 20x)

**Dual Analysis Engine**

- Pattern-based runbook matching for known errors — instant, no LLM call
- LLM-powered analysis (Groq/Llama 3.3 70B) for unknown patterns only
- Automatic severity and disposition assignment with validation
- 22 runbooks covering database, auth, payment, security, infra, and app errors

**Smart Notification Routing**

- `ESCALATE` → Discord (escalate channel)
- `NEEDS_ONCALL` → Email (on-call engineer)
- `NEEDS_DEV` → Discord (dev channel)
- `OBSERVE` or `NO_ACTION` → No notification
- Configurable escalation thresholds and cooldown periods

**Multi-Project Support**

- Project-based isolation with API keys
- JWT authentication for web interface
- Per-project notification configuration

**Web Dashboard**

- Auto-refreshing incident list (every 5 seconds)
- Filter by status, severity, or ticket title
- Close or ignore incidents
- Start/stop log generation
- Project settings management

## Tech Stack

**Backend**

- FastAPI (Python) - REST API framework
- PostgreSQL (NeonDB) - Database
- SQLAlchemy - ORM
- Redis Streams - Event transport and clustering cache
- LangChain + Groq - LLM analysis for unknown errors
- YAML - Runbook definitions

**Frontend**

- React - UI framework
- Tailwind CSS - Styling
- Axios - HTTP client

**Deployment**

- Frontend: Vercel
- Servers: Render
- Database: NeonDB (PostgreSQL)
- Redis: Redis Cloud

## Project Structure

```
log-anomaly/
├── log-server/              # Log generation service
│   ├── server.py           # FastAPI server — generates logs, pushes to Redis Stream
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── log-analyzer/           # Core analysis engine + worker
│   ├── app/
│   │   ├── main.py        # FastAPI application
│   │   ├── api/           # REST endpoints
│   │   │   ├── routes_auth.py      # Authentication & projects
│   │   │   ├── routes_logserver.py # Log server control (start/stop/status)
│   │   │   └── routes_incidents.py # Incident management
│   │   ├── core/          # Business logic
│   │   │   ├── parser.py          # Log parsing
│   │   │   ├── signatures.py      # Signature generation
│   │   │   ├── runbook_loader.py  # YAML runbook loading
│   │   │   ├── runbook_matcher.py # Pattern matching
│   │   │   └── decision_engine.py # LLM analysis
│   │   ├── models/        # Pydantic schemas
│   │   └── services/      # Supporting services
│   │       ├── storage.py        # Database models
│   │       ├── auth.py           # JWT & password hashing
│   │       ├── validators.py     # Input validation
│   │       ├── notifications.py  # Discord & email
│   │       └── cleanup.py        # Database cleanup
│   ├── worker/            # Stream consumer
│   │   ├── stream.py        # XREADGROUP loop, XAUTOCLAIM, ACK logic
│   │   └── tasks.py       # Log processing, clustering, analysis
│   ├── runbooks/          # YAML runbook definitions (22 runbooks)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── log-analyzer-frontend/  # React web dashboard
│   ├── src/
│   │   ├── App.js
│   │   ├── components/
│   │   │   ├── Dashboard.jsx    # Main incident view with auto-refresh
│   │   │   ├── IncidentCard.jsx # Individual incident display
│   │   │   ├── Login.jsx        # Login form
│   │   │   ├── Register.jsx     # Registration form
│   │   │   ├── Settings.jsx     # Project settings
│   │   │   └── Navbar.jsx       # Navigation bar
│   │   └── services/
│   │       └── api.js           # API client
│   ├── public/
│   ├── package.json
│   └── README.md
│
└── README.md              # This file
```

## How It Works

### 1. Log Generation

The log server generates realistic production-style logs and pushes them to a Redis Stream every 3 seconds:

- 70% info messages (normal operations)
- 20% error messages (33 distinct error types across database, auth, payment, security, infra, and app categories)
- 10% warning messages (slow requests)

Logs are buffered in-memory and flushed to the Redis Stream as a batch every 3 seconds.

### 2. Event-Driven Processing Pipeline

**Stream → Parse → Sign → Cluster → Analyze → Notify**

**Stream Consumption:** The worker uses `XREADGROUP` with a 1-second blocking timeout, reacting to new stream entries as they arrive. Failed entries remain in the Pending Entries List (PEL) and are reclaimed via `XAUTOCLAIM` after 60 seconds of idle time.

**Parsing:** Extract timestamp, log level, and message from each log line. Only `ERROR`, `WARN`, `WARNING`, and `CRITICAL` level logs are processed.

**Signature Generation:** Create a unique MD5 hash by normalizing the error message:

- Remove dynamic values (IDs, timestamps, IP addresses, numbers)
- Keep error type and core message
- Example: `log-server:ERROR:databaseconnectionerror_connection_timeout_after`

**Clustering:** Group logs with the same signature within a 2-minute window using Redis as a fast lookup cache:

- First occurrence → Create new incident in DB, cache signature → incident ID in Redis
- Subsequent occurrences → Increment count, update last_seen
- Store up to 10 sample log lines per incident
- Re-analysis triggered at 5x, 10x, and 20x occurrence milestones

**Analysis:** Two-path approach:

1. **Runbook Matching** - Check 22 YAML runbooks for pattern matches
   - If match score ≥ 50% → Use runbook severity, disposition, and steps instantly (no LLM call)
   - Apply escalation rules (e.g., escalate after threshold occurrences)
   - Shown as `Runbook` badge on dashboard

2. **LLM Analysis** - Fallback for unknown patterns only
   - Uses Groq (Llama 3.3 70B) via LangChain
   - Generates severity, disposition, summary, next steps, and ticket draft
   - Output validated for severity/disposition consistency
   - Shown as `✨ AI` badge on dashboard

**Notification Routing:** Based on disposition:

- `ESCALATE` → Discord (escalate webhook)
- `NEEDS_ONCALL` → Email (SMTP)
- `NEEDS_DEV` → Discord (dev webhook)
- `OBSERVE` or `NO_ACTION` → No notification
- Cooldown periods prevent notification spam

### 3. Incident Management

Through the web dashboard, you can:

- View incidents with auto-refresh every 5 seconds
- Filter by status, severity, or ticket title
- See full analysis including severity, summary, next steps, and ticket draft
- Close resolved incidents or ignore known noise
- Control log generation (start/stop)

## Setup

### Prerequisites

- Node.js 16+ (for frontend)
- Python 3.10+ (for backend services)
- PostgreSQL (NeonDB or local)
- Redis (Redis Cloud or local)
- Groq API key (optional, for LLM analysis on unknown errors)
- Discord webhooks (optional, for notifications)
- SMTP credentials (optional, for email notifications)

### Local Development

**1. Clone the repository:**

```bash
git clone https://github.com/DevelopedBy-Siva/log-anomaly.git
cd log-anomaly
```

**2. Set up Log Analyzer:**

```bash
cd log-analyzer

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://user:password@localhost:5432/log_analyzer
SECRET_KEY=your-secret-key-here
GROQ_API_KEY=your-groq-api-key
CORS_ORIGINS=http://localhost:3000
REDIS_URL=redis://localhost:6379
# Optional SMTP settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EOF

# Run the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In a separate terminal, run the stream worker
python -m worker.main
```

**3. Set up Log Server:**

```bash
cd log-server

# Use same virtual environment or create new one
source ../.venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
REDIS_URL=redis://localhost:6379
STREAM_KEY=logs:stream
LOGSHIPPER_API_KEY=your-api-key
CORS_ORIGINS=http://localhost:3000
EOF

# Run the server
uvicorn server:app --host 0.0.0.0 --port 5001 --reload
```

**4. Set up Frontend:**

```bash
cd log-analyzer-frontend

# Install dependencies
npm install

# Create .env file
cat > .env << EOF
REACT_APP_API_URL=http://localhost:8000
EOF

# Run development server
npm start
```

**5. Access the application:**

- Frontend: http://localhost:3000
- Log Analyzer API: http://localhost:8000
- Log Server: http://localhost:5001

### Deployment

**Frontend (Vercel):**

- Automatic deployments from main branch
- Environment variable: `REACT_APP_API_URL` (points to Render backend)

**Log Analyzer API (Render):**

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Environment variables: `DATABASE_URL`, `SECRET_KEY`, `GROQ_API_KEY`, `CORS_ORIGINS`, `REDIS_URL`, SMTP settings

**Worker (Render):**

- Build command: `pip install -r requirements.txt`
- Start command: `python -m worker.main`
- Environment variables: `DATABASE_URL`, `REDIS_URL`, `STREAM_KEY`, `GROQ_API_KEY`

**Log Server (Render):**

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn server:app --host 0.0.0.0 --port 5001`
- Environment variables: `REDIS_URL`, `STREAM_KEY`, `LOGSHIPPER_API_KEY`, `CORS_ORIGINS`

**Database (NeonDB):**

- Serverless PostgreSQL
- Connection string format: `postgresql://user:password@host/database?sslmode=require`

**Redis (Redis Cloud):**

- Free tier — 30MB, sufficient for stream and clustering cache
- Connection string format: `redis://default:password@host:port`

## Configuration

### Runbooks

Runbooks are YAML files that define pattern-based responses to known errors. They live in `log-analyzer/runbooks/`. 22 runbooks are included covering:

- Database errors (connection timeout, deadlock, pool exhaustion, replication lag)
- Authentication failures (expired tokens, invalid signatures, rate limiting)
- Payment errors (card declined, gateway timeout, fraud, double charge)
- Security alerts (SQL injection, XSS, brute force)
- Infrastructure (service unavailable, message queue, cache stampede, disk space)
- Application exceptions (NPE, stack overflow, OOM, unhandled exceptions)
- Data/integration (validation failures, schema mismatch, file upload, CSV parse)

Example runbook structure:

```yaml
id: db_connection_timeout
name: Database Connection Timeout
description: Database connection pool exhaustion or network issues
default_severity: high
disposition: NEEDS_ONCALL

patterns:
  - "database connection timeout"
  - "databaseconnectionerror"
  - "connection pool exhausted"
  - "db-primary"

steps:
  - Check database health metrics (CPU, memory, connections)
  - Verify network connectivity between app and database
  - Check connection pool configuration (max connections)
  - Review recent deployments or schema changes

observe_threshold:
  count: 10
  window_minutes: 5
  escalate_to: ESCALATE

cooldown_minutes: 15
```

To add a new runbook, create a YAML file in the `runbooks/` directory and restart the worker.

### Environment Variables

**Log Analyzer API:**

- `DATABASE_URL` - PostgreSQL connection string (required)
- `SECRET_KEY` - JWT signing key (required)
- `GROQ_API_KEY` - Groq API key for LLM analysis (optional)
- `CORS_ORIGINS` - Comma-separated allowed origins (required)
- `REDIS_URL` - Redis connection string (required)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - Email config (optional)

**Worker:**

- `DATABASE_URL` - PostgreSQL connection string (required)
- `REDIS_URL` - Redis connection string (required)
- `STREAM_KEY` - Redis stream key, default `logs:stream` (optional)
- `GROQ_API_KEY` - Groq API key for LLM analysis (optional)

**Log Server:**

- `REDIS_URL` - Redis connection string (required)
- `STREAM_KEY` - Redis stream key, default `logs:stream` (optional)
- `LOGSHIPPER_API_KEY` - API key for authentication (required)
- `CORS_ORIGINS` - Comma-separated allowed origins (required)

**Frontend:**

- `REACT_APP_API_URL` - Log analyzer base URL (required)

## API Documentation

### Authentication

**Register a new project:**

```bash
POST /api/auth/register
{
  "name": "my-project",
  "password": "secure-password",
  "log_source_url": "https://your-log-server.onrender.com",
  "user_email": "oncall@example.com",
  "discord_webhook_escalate": "https://discord.com/api/webhooks/...",
  "discord_webhook_dev": "https://discord.com/api/webhooks/..."
}
```

**Login:**

```bash
POST /api/auth/login
{
  "name": "my-project",
  "password": "secure-password"
}

Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "project": { ... }
}
```

### Incident Management

**List incidents:**

```bash
GET /api/incidents?status=open&severity=high&limit=50
Headers: Authorization: Bearer <jwt-token>

Response:
[
  {
    "id": "abc123...",
    "source": "log-server",
    "environment": "prod",
    "signature": "a1b2c3d4...",
    "first_seen": "2024-02-15T10:30:00",
    "last_seen": "2024-02-15T10:35:00",
    "count": 12,
    "status": "open",
    "sample_lines": ["..."],
    "analysis": {
      "severity": "high",
      "disposition": "NEEDS_ONCALL",
      "confidence": 0.95,
      "summary": "Database connection pool exhausted...",
      "next_steps": ["Check DB server health", "Review pool settings"],
      "ticket_title": "Database Connection Timeout",
      "ticket_body": "...",
      "analysis_source": "runbook"
    }
  }
]
```

**Close incident:**

```bash
POST /api/incidents/{incident_id}/close
Headers: Authorization: Bearer <jwt-token>
```

**Ignore incident:**

```bash
POST /api/incidents/{incident_id}/ignore
Headers: Authorization: Bearer <jwt-token>
```

### Log Server Control

**Start log generation:**

```bash
POST /api/log-server/start
Headers: Authorization: Bearer <jwt-token>

Response:
{
  "message": "Log generation started",
  "status": "running"
}
```

**Stop log generation:**

```bash
POST /api/log-server/stop
Headers: Authorization: Bearer <jwt-token>

Response:
{
  "message": "Stopped",
  "stats": {
    "logs_generated": 900,
    "logs_shipped": 900,
    "batches_pushed": 300
  },
  "status": "idle"
}
```

**Check status:**

```bash
GET /api/log-server/status
Headers: Authorization: Bearer <jwt-token>
```

## Usage Flow

1. **Register a project** at https://log-anomaly.vercel.app
   - Provide project name, password, and notification settings
   - Save your API key shown after registration

2. **Start log generation** from the dashboard
   - Generates logs every 3 seconds for 5 minutes
   - Pushes to Redis Stream automatically

3. **Monitor incidents** in the dashboard
   - Auto-refreshes every 5 seconds
   - Runbook-matched incidents appear almost instantly
   - Unknown errors show AI analysis within a few seconds
   - Receive notifications via Discord or email based on severity

4. **Review analysis**
   - `Runbook` badge — matched a known pattern, instant analysis
   - `AI` badge — unknown error, LLM-generated analysis
   - Check severity, disposition, next steps, and ticket draft

5. **Take action**
   - Close resolved incidents
   - Ignore known noise
   - Use ticket draft for your issue tracker

## Error Patterns

The log server simulates 33 distinct production error types:

**Database** — connection timeout, deadlock, pool exhaustion, replication lag

**Authentication** — expired JWT, invalid signature, rate limiting, session store failure

**Payment** — gateway timeout, card declined, fraud detection, duplicate charge

**Infrastructure** — service unavailable, message queue full, cache stampede, disk space critical

**Application** — null pointer, stack overflow, out of memory, unhandled exceptions

**Data/Integration** — validation failure, API schema mismatch, file upload error, CSV parse error

**Security** — SQL injection attempt, XSS attempt, brute force detection

**Unknown (LLM analyzed)** — Kubernetes OOM kill, gRPC deadline exceeded, Elasticsearch shard failure, WebSocket connection dropped, feature flag timeout, CDN origin pull failure

## Limitations & Notes

- **2-minute clustering window** — incidents are grouped within 2-minute windows
- **Database cleanup on startup** — the worker wipes all incidents on restart (intended for demo/testing)
- **Runbook caching** — runbooks are loaded once at startup; requires worker restart to reload
- **LLM rate limits** — Groq API has rate limits on the free tier; only unknown errors hit the LLM
- **Single log server per project** — each project connects to one log source URL
- **Free tier latency** — Redis Cloud and Render free tiers may introduce cross-region latency
