# Log Anomaly

An agentic log monitoring system that autonomously detects, clusters, analyzes, and routes production errors using pattern matching and LLM-based decision-making.

**Live Demo:** https://log-anomaly.vercel.app

## Overview

Log Anomaly Agent autonomously processes application logs by grouping similar errors, analyzing their severity, and routing notifications to the right people through Discord or email. The agent uses runbook-based pattern matching for known errors and LLM-powered analysis for unknown patterns, making intelligent triage decisions without manual intervention.

The system consists of three main components:

- **Log Server** - Simulates production logs with realistic errors
- **Log Analyzer** - Processes logs, detects patterns, and manages incidents
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
       │ HTTP POST
       │ /api/ingest
       ▼
┌─────────────┐
│    Log      │ Parses logs → Generates signatures
│  Analyzer   │ → Clusters into incidents → Analyzes
│  (Render)   │ → Routes notifications (Discord/Email)
└──────┬──────┘
       │
       │ PostgreSQL (NeonDB)
       │
       ▼
┌─────────────┐
│  Frontend   │ View incidents, manage settings,
│  (Vercel)   │ control log generation
└─────────────┘
```

## Features

**Intelligent Log Processing**

- Automatic log parsing and signature generation
- Time-based clustering (groups similar errors within 5-minute windows)
- Deduplication with occurrence counting

**Dual Analysis Engine**

- Pattern-based runbook matching for known errors
- LLM-powered analysis (Groq/Llama) for unknown patterns
- Automatic severity and disposition assignment

**Smart Notification Routing**

- Critical/High severity → Discord (escalate channel) or Email (on-call)
- Medium severity → Discord (dev channel)
- Low severity → Monitor and observe
- Configurable escalation thresholds

**Multi-Project Support**

- Project-based isolation with API keys
- JWT authentication for web interface
- Per-project notification configuration

**Web Dashboard**

- Real-time incident tracking
- Filter by status, severity, or keywords
- Close or ignore incidents
- Start/stop log generation
- Project settings management

## Tech Stack

**Backend**

- FastAPI (Python) - REST API framework
- PostgreSQL (NeonDB) - Database
- SQLAlchemy - ORM
- LangChain + Groq - LLM analysis
- YAML - Runbook definitions

**Frontend**

- React - UI framework
- Tailwind CSS - Styling
- Axios - HTTP client

**Deployment**

- Frontend: Vercel
- Servers: Render
- Database: NeonDB (PostgreSQL)

## Project Structure

```
log-anomaly/
├── log-server/              # Log generation service
│   ├── server.py           # FastAPI server with error patterns
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── log-analyzer/           # Core analysis engine
│   ├── app/
│   │   ├── main.py        # FastAPI application
│   │   ├── api/           # REST endpoints
│   │   │   ├── routes_auth.py      # Authentication & projects
│   │   │   ├── routes_ingest.py    # Log ingestion
│   │   │   └── routes_incidents.py # Incident management
│   │   ├── core/          # Business logic
│   │   │   ├── parser.py          # Log parsing
│   │   │   ├── signatures.py      # Signature generation
│   │   │   ├── clustering.py      # Incident clustering
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
│   ├── runbooks/          # YAML runbook definitions
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── log-analyzer-frontend/  # React web dashboard
│   ├── src/
│   │   ├── App.js
│   │   ├── components/
│   │   │   ├── Dashboard.jsx    # Main incident view
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

The log server generates realistic production-style logs:

- 80% info messages (normal operations)
- 15% error messages (database timeouts, NPEs, Redis failures, etc.)
- 5% warning messages (slow requests)

Logs are buffered in-memory and shipped to the analyzer in batches every second.

### 2. Log Processing Pipeline

**Parse → Sign → Cluster → Analyze → Notify**

**Parsing:** Extract timestamp, log level, and message from each log line

**Signature Generation:** Create a unique hash by normalizing the error message:

- Remove dynamic values (IDs, timestamps, numbers)
- Keep error type and core message
- Example: `log-server:ERROR:Database_connection_timeout_after`

**Clustering:** Group logs with the same signature within a 5-minute window:

- First occurrence → Create new incident
- Subsequent occurrences → Update count and last_seen
- Store up to 10 sample log lines per incident

**Analysis:** Two-path approach:

1. **Runbook Matching** - Check YAML runbooks for pattern matches
   - If match score ≥ 50% → Use runbook analysis
   - Apply escalation rules (e.g., escalate after 20 occurrences)
2. **LLM Analysis** - Fallback for unknown patterns
   - Uses Groq (Llama 3.3 70B) via LangChain
   - Generates severity, disposition, summary, next steps, and ticket draft
   - Validates output for consistency

**Notification Routing:** Based on disposition from analysis:

- `ESCALATE` → Discord (escalate webhook)
- `NEEDS_ONCALL` → Email (SMTP)
- `NEEDS_DEV` → Discord (dev webhook)
- `OBSERVE` or `NO_ACTION` → No notification

### 3. Incident Management

Through the web dashboard, you can:

- View all incidents with real-time updates
- Filter by status, severity, or search terms
- See full analysis including severity, summary, and next steps
- Close resolved incidents
- Ignore known noise
- Control log generation (start/stop)

## Setup

### Prerequisites

- Node.js 16+ (for frontend)
- Python 3.10+ (for backend services)
- PostgreSQL (NeonDB or local)
- Groq API key (optional, for LLM analysis)
- Discord webhooks (optional, for notifications)
- SMTP credentials (optional, for email notifications)

### Local Development

**1. Clone the repository:**

```bash
git clone <your-repo-url>
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
# Optional SMTP settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EOF

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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
ANALYZER_URL=http://localhost:8000/api/ingest
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
- Log Analyzer: http://localhost:8000
- Log Server: http://localhost:5001

### Deployment

The application is deployed across three platforms:

**Frontend (Vercel):**

- Automatic deployments from main branch
- Environment variable: `REACT_APP_API_URL` (points to Render backend)

**Log Analyzer (Render):**

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Environment variables: `DATABASE_URL`, `SECRET_KEY`, `GROQ_API_KEY`, `CORS_ORIGINS`, SMTP settings

**Log Server (Render):**

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn server:app --host 0.0.0.0 --port 5001`
- Environment variables: `ANALYZER_URL`, `LOGSHIPPER_API_KEY`, `CORS_ORIGINS`

**Database (NeonDB):**

- Serverless PostgreSQL
- Connection string format: `postgresql://user:password@host/database?sslmode=require`

## Configuration

### Runbooks

Runbooks are YAML files that define pattern-based responses to known errors. They live in `log-analyzer/runbooks/`.

Example runbook structure:

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
  - Review connection pool settings
  - Check for long-running queries
  - Verify network connectivity

observe_threshold:
  count: 15 # Escalate after 15 occurrences
  window_minutes: 5 # Within 5 minutes
  escalate_to: ESCALATE # New disposition

cooldown_minutes: 15 # Prevent notification spam
```

To add a new runbook, create a YAML file in the `runbooks/` directory and restart the log analyzer.

### Environment Variables

**Log Analyzer:**

- `DATABASE_URL` - PostgreSQL connection string (required)
- `SECRET_KEY` - JWT signing key (required)
- `GROQ_API_KEY` - Groq API key for LLM analysis (optional)
- `CORS_ORIGINS` - Comma-separated allowed origins (required)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - Email config (optional)

**Log Server:**

- `ANALYZER_URL` - Log analyzer ingest endpoint (required)
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

### Log Ingestion

**Send logs:**

```bash
POST /api/ingest
Headers: X-API-Key: <your-api-key>
{
  "source": "log-server",
  "environment": "prod",
  "logs": [
    "[2024-02-15T10:30:00] ERROR: Database connection timeout",
    "[2024-02-15T10:30:01] WARN: Slow request detected: 3.45s"
  ]
}

Response:
{
  "incidents_created": 1,
  "incidents_updated": 0,
  "total_logs_processed": 2
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
    "signature": "log-server:ERROR:Database_connection_timeout",
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
      "ticket_title": "Database connection timeout",
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
Headers: X-API-Key: <your-api-key>

Response:
{
  "message": "Log generation started",
  "status": "running"
}
```

**Stop log generation:**

```bash
POST /api/log-server/stop
Headers: X-API-Key: <your-api-key>

Response:
{
  "message": "Stopped",
  "stats": {
    "logs_generated": 900,
    "logs_shipped": 900,
    "incidents_created": 45,
    "incidents_updated": 120
  },
  "status": "idle"
}
```

**Check status:**

```bash
GET /api/log-server/status
Headers: X-API-Key: <your-api-key>
```

## Usage Flow

1. **Register a project** at https://log-anomaly.vercel.app
   - Provide project name, password, and notification settings
   - Copy your API key for log server configuration

2. **Configure your log server** (or use the demo server)
   - Set `ANALYZER_URL` to your analyzer endpoint
   - Set `LOGSHIPPER_API_KEY` to your project API key

3. **Start log generation** from the dashboard
   - Generates 3 logs per second for 5 minutes
   - Includes realistic error patterns

4. **Monitor incidents** in the dashboard
   - View real-time clustering and analysis
   - Receive notifications via Discord or email
   - Take action (close/ignore) as needed

5. **Review analysis**
   - Check severity and disposition
   - Read AI-generated summary and next steps
   - Use ticket draft for issue tracking

## Error Patterns

The log server simulates 10 types of production errors:

1. **Database Timeouts** - Connection timeouts (30-60s)
2. **NullPointerException** - Java-style NPEs with stack traces
3. **Redis Connection Failures** - Connection refused, timeouts, readonly replicas
4. **API Rate Limits** - Stripe, SendGrid, Twilio, AWS S3 throttling
5. **Payment Failures** - Card declined, insufficient funds, expired cards
6. **File Not Found** - Missing upload files
7. **Out of Memory** - Java heap space exhaustion
8. **Authentication Failures** - Expired tokens, invalid signatures
9. **External Service Errors** - HTTP 500/502/503/504 responses
10. **SQL Syntax Errors** - Missing tables, query failures

## Limitations & Notes

- **5-minute clustering window** - Incidents are grouped within 5-minute windows
- **Database cleanup on startup** - The analyzer wipes all incidents on restart (intended for demo/testing)
- **Runbook caching** - Runbooks are loaded once at startup; requires restart to reload
- **LLM rate limits** - Groq API has rate limits on the free tier
- **Single log server** - Each project connects to one log source URL

## License

This is a personal project. Feel free to use and modify as needed.
