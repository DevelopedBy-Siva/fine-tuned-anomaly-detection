# 🔍 AI-Powered Log Analyzer

An intelligent log analysis system that automatically detects, clusters, and analyzes production incidents using rule-based runbooks and LLM-powered insights with multi-project support and real-time notifications.

![Dashboard Preview](docs/dashboard-preview.png)

---

## 🌟 Features

### Core Capabilities

- **Multi-Project Support** - Isolated projects with individual authentication
- **Intelligent Log Parsing** - Extracts structured data from unstructured logs
- **Smart Clustering** - Groups similar errors using signature-based deduplication
- **Runbook Matching** - Applies predefined YAML rules for known issues
- **AI Analysis** - Uses LLMs (Groq/Llama) to analyze unknown incidents
- **Real-time Dashboard** - Live monitoring with auto-refresh
- **Action Recommendations** - Generates next steps and ticket drafts
- **Multi-Channel Alerts** - Discord webhooks and email notifications

### What Makes It Smart

- **Signature Generation** - Normalizes variable data (IDs, timestamps) to create stable patterns
- **Time-based Clustering** - Groups related errors within configurable time windows
- **Hybrid Approach** - Fast rule-based matching + intelligent LLM fallback
- **Structured Outputs** - LLM returns JSON with severity, disposition, and action items
- **Validated Integrations** - Live verification of Discord webhooks and log sources

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│     React Frontend (Port 3000)          │
│  - Project registration & login         │
│  - Real-time incident dashboard         │
│  - Settings & configuration             │
└──────────────┬──────────────────────────┘
               │ JWT Auth
               ▼
┌─────────────────────────────────────────┐
│      FastAPI Backend (Port 8000)         │
│  - Multi-project authentication         │
│  - Log ingestion & parsing              │
│  - Runbook & LLM analysis               │
│  - Discord/Email notifications          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       PostgreSQL (Port 5432)            │
│  - Projects (auth, webhooks, settings)  │
│  - Incidents (clustered logs)           │
│  - Analyses (runbook/AI decisions)      │
└─────────────────────────────────────────┘
               ▲
               │
┌──────────────┴──────────────────────────┐
│        Log Sources                       │
│  - Log Server (FastAPI - Port 5001)     │
│  - Log Shipper (File tailer)            │
│  - Direct HTTP ingestion                │
└─────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 16+ (for React frontend)
- PostgreSQL 12+
- Groq API key (free tier: https://console.groq.com/keys)
- Discord webhooks (for alerts)

---

### 1. Database Setup

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql
```

In PostgreSQL shell:

```sql
CREATE DATABASE log_analyzer;
CREATE USER log_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE log_analyzer TO log_user;
\q
```

---

### 2. Backend Setup (Log Analyzer)

```bash
cd log-analyzer
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Configure environment
cat > .env << EOF
DATABASE_URL=postgresql://log_user:secure_password_here@localhost:5432/log_analyzer
GROQ_API_KEY=your-groq-api-key-here
SECRET_KEY=your-jwt-secret-key-change-in-production
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
EOF

# Start the analyzer
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 3. Frontend Setup (React)

```bash
cd log-analyzer-frontend
npm install
npm start
```

Frontend will be available at: **http://localhost:3000**

---

### 4. Log Server Setup (Optional - for testing)

```bash
cd log-server
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# Start the log server
uvicorn main:app --host 0.0.0.0 --port 5001 --reload
```

---

### 5. Generate Test Traffic (Optional)

**Terminal 1:** Traffic Generator

```bash
cd log-server
source .venv/bin/activate
python traffic_generator.py
```

**Terminal 2:** Log Shipper

```bash
cd log-server
source .venv/bin/activate
python log_shipper.py
```

---

## 📋 Project Registration Flow

### What You Need

1. **Project Name** - Unique identifier (3-50 chars, alphanumeric + `-_`)
2. **Password** - Secure password (min 8 chars)
3. **Log Source URL** - URL of your log server (e.g., `http://localhost:5001`)
4. **User Email** - Your email for incident notifications
5. **Discord Webhook (ESCALATE)** - For critical incidents
6. **Discord Webhook (DEV)** - For development team alerts

### Validation Process

The system validates all inputs during registration:

✅ **Log Source URL**

- Validates URL format
- Connects to the server
- Verifies it's a valid log server
- Checks for proper JSON response

✅ **Discord Webhooks**

- Validates Discord webhook URL format
- Sends test message to verify connectivity
- Confirms webhook is active

✅ **Email**

- Validates email format
- Ensures proper domain structure

### Getting Discord Webhooks

1. Go to your Discord server
2. Right-click the channel (e.g., `#incidents-critical`)
3. Edit Channel → Integrations → Webhooks
4. Click "New Webhook"
5. Copy the webhook URL
6. Paste during registration

---

## 🎯 How It Works

### 1. Log Parsing

Extracts structured data from raw logs:

```python
Input:  "[2024-02-13T10:30:45] ERROR: Database connection timeout after 30s"
Output: {
  "timestamp": "2024-02-13T10:30:45",
  "level": "ERROR",
  "message": "Database connection timeout after 30s",
  "exception_type": None
}
```

### 2. Signature Generation

Creates stable fingerprints by normalizing variable data:

```python
Original: "Database connection timeout after 30s connecting to db-primary-1"
Original: "Database connection timeout after 45s connecting to db-replica-2"
         ↓ (normalize numbers and hostnames)
Signature: "Database connection timeout after Ns connecting to db-host"
         ↓ (hash)
Result: "f5e4d3c2b1a0..." (same for both!)
```

### 3. Clustering

Groups errors with the same signature within a 5-minute window:

```
10:30:10 - DB timeout → Create incident #1 (count: 1)
10:30:15 - DB timeout → Update incident #1 (count: 2)
10:30:20 - DB timeout → Update incident #1 (count: 3)
10:36:00 - DB timeout → Create incident #2 (old one expired)
```

### 4. Analysis Decision Tree

```
New incident
    ├─→ Try runbook matching
    │   ├─→ High confidence (≥50%) → Use runbook
    │   └─→ Low confidence (<50%) → Use LLM
    └─→ Generate notification based on disposition
```

### 5. Alert Routing

| Disposition      | Action               | Channel                    |
| ---------------- | -------------------- | -------------------------- |
| **ESCALATE**     | Critical alert       | Discord (ESCALATE webhook) |
| **NEEDS_ONCALL** | On-call notification | Email                      |
| **NEEDS_DEV**    | Development ticket   | Discord (DEV webhook)      |
| **OBSERVE**      | Monitor only         | No notification            |
| **NO_ACTION**    | Known noise          | No notification            |

---

## 🗂️ Project Structure

```
log-analyzer/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── api/
│   │   ├── routes_auth.py      # Authentication & registration
│   │   ├── routes_ingest.py    # Log ingestion endpoint
│   │   ├── routes_incidents.py # Incident management
│   │   └── routes_dashboard.py # Dashboard HTML
│   ├── core/
│   │   ├── parser.py           # Log parsing logic
│   │   ├── signatures.py       # Signature generation
│   │   ├── clustering.py       # Time-based clustering
│   │   ├── runbook_loader.py   # YAML runbook loader
│   │   ├── runbook_matcher.py  # Pattern matching
│   │   └── decision_engine.py  # LLM integration (Groq)
│   ├── services/
│   │   ├── storage.py          # PostgreSQL models
│   │   ├── auth.py             # JWT & password hashing
│   │   ├── notifications.py    # Discord & email alerts
│   │   └── validators.py       # URL/webhook validation
│   └── models/
│       └── schemas.py          # Pydantic schemas
├── runbooks/                   # YAML runbook definitions
│   ├── db_connection_timeout.yaml
│   ├── redis_connection.yaml
│   ├── payment_failed.yaml
│   └── ...
├── .env                        # Environment variables
└── requirements.txt

log-analyzer-frontend/
├── src/
│   ├── components/
│   │   ├── Login.jsx           # Login page
│   │   ├── Register.jsx        # Registration form
│   │   ├── Dashboard.jsx       # Main dashboard
│   │   ├── IncidentCard.jsx    # Incident display
│   │   ├── Settings.jsx        # Project settings
│   │   └── Navbar.jsx          # Navigation
│   ├── services/
│   │   └── api.js              # API client
│   ├── App.js
│   └── index.js
└── package.json

log-server/
├── main.py                     # FastAPI log generation server
├── error_patterns.py           # Realistic error generators
├── logger_config.py            # Logging setup
├── traffic_generator.py        # HTTP traffic simulator
├── log_shipper.py              # Log file tailer
└── logs/
    └── app.log                 # Generated logs
```

---

## 🔧 Configuration

### Backend Environment Variables (`.env`)

```env
# Database
DATABASE_URL=postgresql://log_user:password@localhost:5432/log_analyzer

# JWT Authentication
SECRET_KEY=your-secret-key-change-in-production

# LLM
GROQ_API_KEY=your-groq-api-key

# Email (Default SMTP settings)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

### Clustering Settings (`app/core/clustering.py`)

```python
CLUSTER_WINDOW_MINUTES = 5  # Time window for grouping
MAX_SAMPLES = 10            # Max sample logs per incident
```

### Severity Thresholds (`app/api/routes_dashboard.py`)

```python
# Based on occurrence count:
count >= 10 → CRITICAL
count >= 5  → HIGH
count >= 2  → MEDIUM
count == 1  → LOW
```

---

## 📊 Database Schema

### Projects Table

```sql
- id (UUID)
- name (unique)
- password_hash (bcrypt)
- log_source_url
- user_email
- discord_webhook_escalate
- discord_webhook_dev
- created_at
- is_active
```

### Incidents Table

```sql
- id (UUID)
- project_id (FK)
- source
- environment
- signature (indexed)
- first_seen (indexed)
- last_seen (indexed)
- count
- sample_lines (JSON)
- status (indexed)
```

### Analyses Table

```sql
- id (UUID)
- incident_id (FK)
- severity
- disposition
- confidence
- summary
- next_steps (JSON)
- matched_runbook_id
- ticket_title
- ticket_body
- analysis_source (runbook/llm)
```

---

## 🔐 API Endpoints

### Authentication

- `POST /api/auth/register` - Create new project
- `POST /api/auth/login` - Login to project
- `GET /api/auth/me` - Get current project info
- `PUT /api/auth/settings` - Update project settings

### Validation (Pre-registration)

- `POST /api/auth/validate/url` - Validate log source URL
- `POST /api/auth/validate/discord-escalate` - Test ESCALATE webhook
- `POST /api/auth/validate/discord-dev` - Test DEV webhook
- `POST /api/auth/validate/email` - Validate email format

### Ingestion

- `POST /api/ingest` - Receive log batches (requires auth)

### Incidents

- `GET /api/incidents` - List incidents (filterable)
- `GET /api/incidents/{id}` - Get single incident
- `POST /api/incidents/{id}/close` - Mark as resolved
- `POST /api/incidents/{id}/ignore` - Ignore false positive

### Visualization

- `GET /api/dashboard` - Real-time HTML dashboard

---

## 📈 Sample Metrics

From a 5-minute test run:

- **Logs Processed:** 1,247
- **Incidents Created:** 23
- **Runbook Matches:** 18 (78%)
- **LLM Analysis:** 5 (22%)
- **Clustering Accuracy:** ~95%
- **Average LLM Latency:** 1.2s (Groq)
- **Discord Alerts Sent:** 12
- **Email Notifications:** 3

---

## 🐛 Troubleshooting

### "Cannot connect to PostgreSQL"

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Verify connection
psql -U log_user -d log_analyzer -h localhost
```

### "Log source URL validation failed"

- Ensure log server is running on the specified URL
- Check that the server returns JSON with `{"service": "...", "status": "running"}`
- Verify firewall/network allows connection

### "Discord webhook validation failed"

- Verify webhook URL format: `https://discord.com/api/webhooks/{id}/{token}`
- Check that webhook hasn't been deleted in Discord
- Ensure bot has permission to post in the channel

### "LLM analysis not working"

- Verify `GROQ_API_KEY` in `.env`
- Check Groq API quota: https://console.groq.com
- Review analyzer logs for error messages

### "No incidents appearing"

- Check that log shipper is running and connected
- Verify traffic generator is creating errors
- Ensure log level is ERROR/WARN (not INFO)
- Check analyzer logs for parsing errors

---

## 📚 Technologies Used

### Backend

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Production-grade relational database
- **SQLAlchemy** - SQL toolkit and ORM
- **LangChain** - LLM orchestration framework
- **Groq** - Ultra-fast LLM inference (Llama 3.3 70B)
- **Pydantic** - Data validation using Python type hints
- **PassLib** - Password hashing (bcrypt)
- **python-jose** - JWT token generation

### Frontend

- **React** - UI library
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Recharts** - Data visualization
- **Lucide React** - Icon library

### DevOps

- **Docker** - Containerization (coming soon)
- **Docker Compose** - Multi-container orchestration

---

## 🚧 TODO / Roadmap

### Phase 1: Frontend Enhancement ✅

- [x] React frontend with authentication
- [x] Registration with live validation
- [x] Dashboard with real-time updates
- [x] Settings page for configuration

### Phase 2: Deployment (In Progress)

- [ ] Docker Compose for full stack
- [ ] Environment-based configuration
- [ ] Production-ready setup guide
- [ ] Health checks and monitoring

### Phase 3: Advanced Features

- [ ] WebSocket for real-time dashboard updates
- [ ] Advanced filtering and search
- [ ] Analytics dashboard (charts & metrics)
- [ ] Incident detail page with full history
- [ ] Runbook editor UI
- [ ] Feedback loop for analysis accuracy

### Phase 4: Integrations

- [ ] GitHub Issues integration
- [ ] Jira ticket creation
- [ ] PagerDuty integration
- [ ] Slack notifications (alternative to Discord)

### Phase 5: ML Enhancements

- [ ] Fine-tune small model on collected data
- [ ] Automatic runbook generation from patterns
- [ ] Anomaly detection for unusual error spikes
- [ ] Sentiment analysis on error messages

---

## 📝 License

MIT License - feel free to use this project for learning or portfolio purposes.

---

## 📸 Screenshots

### Registration with Live Validation

![Registration](docs/registration.png)

### Dashboard Overview

![Dashboard](docs/dashboard.png)

### Runbook Match

![Runbook Match](docs/runbook-match.png)

### AI Analysis with Ticket Draft

![AI Analysis](docs/ai-analysis.png)

### Settings Page

![Settings](docs/settings.png)

---
