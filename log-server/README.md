# Log Server

A FastAPI service that generates realistic style logs with errors and warnings, then ships them to a Log Analyzer service for anomaly detection and incident management.

## Overview

- **In-memory log generation** — Produces structured log lines with realistic error patterns, warnings, and info messages
- **Automatic log shipping** — Batches and sends logs to the Log Analyzer service via HTTP API
- **Realistic-style errors** — Database timeouts, NullPointerExceptions, Redis failures, payment errors, authentication issues, and more
- **API control** — Start, stop, and monitor log generation via REST endpoints
- **Statistics tracking** — Real-time metrics on logs generated, shipped, and incidents created

## Architecture

The log server generates logs in-memory (no file I/O) and ships them directly to the analyzer service. Logs are buffered up to 20 lines, then sent in batches of 10+ to the analyzer's ingest endpoint.

## Project Structure

```
log-server/
├── server.py           # FastAPI app with log generation and shipping
├── requirements.txt    # Python dependencies
├── Dockerfile         # Container configuration
└── README.md          # This file
```

## Setup

### Environment Variables

Create a `.env` file in the `log-server` directory:

```env
ANALYZER_URL=http://localhost:8000/api/ingest
LOGSHIPPER_API_KEY=your_api_key_here
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

- **ANALYZER_URL** — Log Analyzer ingest endpoint (required)
- **LOGSHIPPER_API_KEY** — API key for authenticating with this server (required)
- **CORS_ORIGINS** — Comma-separated list of allowed frontend origins (required)

### Local Development

```bash
cd log-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Server

```bash
uvicorn server:app --host 0.0.0.0 --port 5001 --reload
```

- **Root:** http://localhost:5001/ — Service info
- **Docs:** http://localhost:5001/docs — Swagger UI
- **Health:** http://localhost:5001/health — Health check

### Docker

```bash
docker build -t log-server .
docker run -p 5001:5001 --env-file .env log-server
```

## API Endpoints

All endpoints except `/` and `/health` require the `X-API-Key` header.

| Method | Path          | Auth Required | Description                                 |
| ------ | ------------- | ------------- | ------------------------------------------- |
| GET    | `/`           | No            | Service information and endpoint list       |
| GET    | `/health`     | No            | Health check                                |
| POST   | `/api/start`  | Yes           | Start log generation (runs for 300 seconds) |
| POST   | `/api/stop`   | Yes           | Stop log generation and return statistics   |
| GET    | `/api/status` | Yes           | Get current status and statistics           |

### Example Usage

**Start log generation:**

```bash
curl -X POST http://localhost:5001/api/start \
  -H "X-API-Key: your_api_key_here"
```

**Check status:**

```bash
curl http://localhost:5001/api/status \
  -H "X-API-Key: your_api_key_here"
```

**Stop generation:**

```bash
curl -X POST http://localhost:5001/api/stop \
  -H "X-API-Key: your_api_key_here"
```

## How It Works

### Log Generation

When started, the log server:

1. Generates 3 log entries per second
2. Buffers logs in-memory (max 20 entries)
3. Ships logs in batches of 10+ to the analyzer every second
4. Runs for 300 seconds (5 minutes) by default
5. Ships any remaining logs when stopped or finished

### Error Patterns

The server simulates 10 types of production errors with a 15% error rate:

- **Database timeouts** — Connection timeouts to various DB hosts (30-60s)
- **NullPointerException** — Java-style NPEs with stack traces
- **Redis connection failures** — Connection refused, timeouts, readonly replicas
- **API rate limits** — Third-party API throttling (Stripe, SendGrid, Twilio, AWS S3)
- **Payment failures** — Card declined, insufficient funds, expired cards, CVV mismatches
- **File not found** — Missing upload files
- **Out of memory** — Java heap space exhaustion
- **Authentication failures** — Token expired, invalid signatures, revoked tokens
- **External service errors** — HTTP 500/502/503/504 from internal services
- **SQL syntax errors** — Missing tables and query failures

### Warning Patterns

5% of logs are slow request warnings (2-5 second delays).

### Info Patterns

80% of logs are normal operational messages:

- User lookups
- Order creation
- File uploads
- Cache hits
- Health checks

## Statistics

The server tracks:

- **logs_generated** — Total logs created
- **logs_shipped** — Total logs successfully sent to analyzer
- **incidents_created** — New incidents created by analyzer
- **incidents_updated** — Existing incidents updated

Statistics are returned when stopping the server or checking status.

## Dependencies

```
fastapi==0.109.0
requests==2.31.0
python-multipart==0.0.22
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
```

## Configuration

### Tunable Parameters (in `server.py`)

- **ERROR_RATE** — Probability of generating an error log (default: 0.15)
- **SLOW_REQUEST_RATE** — Probability of generating a slow request warning (default: 0.05)
- **Log buffer size** — Maximum in-memory logs before forced shipping (default: 20)
- **Batch size** — Minimum logs before shipping (default: 10)
- **Generation interval** — Time between log generation cycles (default: 1 second)
- **Run duration** — How long generation runs when started (default: 300 seconds)

## Use Case

This server is designed for:

- Testing log-based anomaly detection systems
- Generating training data for incident detection models
- Simulating production log patterns for evaluation
- Demonstrating real-time log analysis and incident management

The output is consumed by the Log Analyzer service, which detects patterns, creates incidents, and provides incident management capabilities.
