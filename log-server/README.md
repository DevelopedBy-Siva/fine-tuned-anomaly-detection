# Log Server

A FastAPI service that simulates a production API with **realistic errors** and **variable latency**. It writes structured log lines (including errors and warnings) to a file and console, intended for generating training or evaluation data for log-based anomaly detection.

## Overview

- **API server** — Multiple endpoints that randomly return errors, slow responses, or success.
- **Error patterns** — Production-style messages (DB timeouts, NPEs, Redis/cache, payment, auth, external services, etc.).
- **Traffic generator** — Optional script to hit the server continuously so logs accumulate.
- **Log shipper** — Tails `logs/app.log` and sends batches to the Log Analyzer’s ingest API.

## Project structure

| File                   | Description                                                                        |
| ---------------------- | ---------------------------------------------------------------------------------- |
| `main.py`              | FastAPI app and route definitions; injects errors and slow requests.               |
| `error_patterns.py`    | `ErrorPatterns` class and `ERROR_GENERATORS` — realistic error message generators. |
| `logger_config.py`     | Logger setup: file (`logs/app.log`) and console with ISO timestamps.               |
| `traffic_generator.py` | Script to send random requests to the server for load/log generation.              |
| `log_shipper.py`       | Tails `logs/app.log` and POSTs batches to the Log Analyzer at `/api/ingest`.       |
| `requirements.txt`     | Python dependencies.                                                               |

## Setup

```bash
cd log-server
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Full workflow (4 terminals)

Run in this order. The **Log Analyzer** and **Log Server** must be running before the traffic generator and log shipper.

| Terminal | Component             | Command                                                | Port / URL                  |
| -------- | --------------------- | ------------------------------------------------------ | --------------------------- |
| 1        | **Log Analyzer**      | (already running)                                      | 8000                        |
| 2        | **Log Server**        | `uvicorn main:app --host 0.0.0.0 --port 5001 --reload` | 5001                        |
| 3        | **Traffic Generator** | `python traffic_generator.py`                          | hits 5001                   |
| 4        | **Log Shipper**       | `python log_shipper.py`                                | tails `logs/app.log` → 8000 |

## Running the server

Start the Log Server on port 5001 (required by the traffic generator):

```bash
uvicorn main:app --host 0.0.0.0 --port 5001 --reload
```

- **Root:** [http://localhost:5001/](http://localhost:5001/) — service info
- **Docs:** [http://localhost:5001/docs](http://localhost:5001/docs) — Swagger UI

## Generating traffic and logs

In a separate terminal (with the same venv):

```bash
cd ~/Desktop/fine-tuned-anomaly-detection/log-server
source .venv/bin/activate
python traffic_generator.py
```

You should see:

```
Generating traffic for 300s at 3 req/s
Press Ctrl+C to stop

[20s] Sent 60 requests
[40s] Sent 120 requests
...
```

This sends random requests to `http://localhost:5001` for 5 minutes at 3 requests/second. Adjust `BASE_URL` in `traffic_generator.py` if you run the server on a different host/port.

Logs are written to:

- **File:** `logs/app.log`
- **Console:** stdout of the server process

## Log Shipper

The log shipper tails `logs/app.log` and POSTs batches to the Log Analyzer’s ingest API (`http://localhost:8000/api/ingest`). **Start the Log Analyzer (port 8000) before running the log shipper.**

In a separate terminal:

```bash
cd ~/Desktop/fine-tuned-anomaly-detection/log-server
source .venv/bin/activate
python log_shipper.py
```

You should see:

```
Tailing logs/app.log → http://localhost:8000/api/ingest
Batch size: 10, Poll interval: 2s

Shipped 15 logs | Created: 3 | Updated: 0
Shipped 12 logs | Created: 1 | Updated: 4
Shipped 18 logs | Created: 0 | Updated: 5
...
```

- **Batch size:** 10 (configurable via `BATCH_SIZE` in `log_shipper.py`)
- **Poll interval:** 2 seconds
- **Payload:** `{"source": "log-server", "environment": "prod", "logs": [...]}`

If the analyzer is not running, you’ll see: `Cannot connect to analyzer. Is it running on port 8000?`

## API endpoints

| Method | Path                     | Behavior                                               |
| ------ | ------------------------ | ------------------------------------------------------ |
| GET    | `/`                      | Service info                                           |
| GET    | `/api/users/{user_id}`   | User lookup; may error or be slow                      |
| POST   | `/api/orders`            | Order creation; extra chance of payment errors         |
| POST   | `/api/upload`            | File upload; may trigger file-not-found style errors   |
| GET    | `/api/cache/{key}`       | Cache lookup; may trigger Redis-style errors           |
| POST   | `/api/external/notify`   | External notification; may trigger dependency failures |
| GET    | `/api/health`            | Health check; rarely fails                             |
| POST   | `/internal/cron/cleanup` | Simulated cron job; DB/timeout/OOM style errors        |

Rates (tunable in `main.py`):

- **Base error rate:** 15% (`ERROR_RATE`)
- **Slow request rate:** 5% (`SLOW_REQUEST_RATE`)
- Some routes have additional route-specific error probabilities.

## Error types (from `error_patterns.py`)

- Database timeouts and SQL syntax errors
- NullPointerException-style stack traces
- Redis connection/timeout/readonly
- API rate limits (e.g. Stripe, SendGrid, Twilio)
- Payment failures (card declined, insufficient funds, etc.)
- File not found
- Out of memory (heap)
- Authentication (token expired, invalid signature, etc.)
- External service down (HTTP 5xx)

## Dependencies

- **fastapi** — Web framework
- **uvicorn** — ASGI server
- **requests** — Used by `traffic_generator.py` and `log_shipper.py`
- **python-multipart** — File upload support

## Use case

Use this server to produce log streams that mix normal and anomalous behavior (errors, slowness, varied messages). The output in `logs/app.log` can be used for training or evaluating log-based anomaly detection or fine-tuned models.
