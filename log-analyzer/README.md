# Log Analyzer

A FastAPI service that ingests log lines, parses them, clusters similar errors into **incidents**, and exposes them via REST API. Built for aggregating and deduplicating application logs (e.g. from a log server or agents) into actionable incident records.

---

## Overview

- **Ingest**: Accept batches of raw log lines (with `source` and `environment`).
- **Parse**: Extract timestamp, level, message, and exception type from each line.
- **Cluster**: Group logs that match the same “signature” (normalized error pattern) into a single incident, with a time window so recurring errors are counted and updated instead of creating duplicates.
- **Query**: List/filter incidents, get one by ID, and close or ignore incidents.

Data is persisted in SQLite under `data/app.db`.

---

## Architecture & Code Analysis

### High-level flow

```
POST /api/ingest (logs) → Parser → Signature generation → Clustering → SQLite
GET /api/incidents*     → Storage (SQLAlchemy) → JSON response
```

### Directory layout

| Path                          | Role                                                                      |
| ----------------------------- | ------------------------------------------------------------------------- |
| `app/main.py`                 | FastAPI app, lifespan (DB init), CORS, route mounting, root info endpoint |
| `app/models/schemas.py`       | Pydantic request/response models for API                                  |
| `app/core/parser.py`          | Parse raw log lines into structured `ParsedLog`                           |
| `app/core/signatures.py`      | Normalize message + build stable hash (signature) for clustering          |
| `app/core/clustering.py`      | Find-or-create incident by signature within a time window                 |
| `app/services/storage.py`     | SQLAlchemy engine, `Incident` model, `init_db`, `get_db`                  |
| `app/api/routes_ingest.py`    | `POST /api/ingest`                                                        |
| `app/api/routes_incidents.py` | `GET/POST /api/incidents` and by-id/close/ignore                          |

---

### Module-by-module analysis

#### `app/main.py`

- Uses an **async lifespan** context manager to call `init_db()` on startup.
- Registers CORS with `allow_origins=["*"]` (suitable for dev; consider restricting in production).
- Mounts ingest and incidents routers under `/api`.
- Root `GET /` returns service name, status, and a short list of endpoints.

#### `app/models/schemas.py`

- **IngestRequest**: `source`, optional `environment` (default `"dev"`), `logs: List[str]`.
- **IngestResponse**: counts for `incidents_created`, `incidents_updated`, `total_logs_processed`.
- **IncidentResponse**: id, source, environment, signature, first_seen, last_seen, count, status, optional `sample_lines`; uses `from_attributes = True` for ORM compatibility.

#### `app/core/parser.py`

- **ParsedLog**: holds `raw`, `timestamp`, `level`, `message`, `exception_type`.
- **Timestamp**: regex for `[YYYY-MM-DDTHH:MM:SS...]`; falls back to `datetime.utcnow()` on parse failure.
- **Level**: first match of CRITICAL/ERROR/WARN/WARNING/INFO/DEBUG in the line (case-insensitive); default `"INFO"`.
- **Message**: line with timestamp and level prefix stripped.
- **Exception type**: Java-style `*Exception`, Python tracebacks/`Error:`, or SQL-related errors; otherwise `None`.

Ingest only processes ERROR/WARN/WARNING/CRITICAL, so INFO/DEBUG are effectively discarded at the route layer.

#### `app/core/signatures.py`

- **normalize_message**: reduces variability so similar errors get the same pattern (e.g. UUIDs → `UUID`, `ORD-123` → `ORD-N`, numbers → `N`, paths under `/tmp/` → `/tmp/FILE`, tokens/hashes, hex addresses). This is what makes clustering stable across different variable values.
- **generate_signature**: builds a string from `source | level | normalized_message` (and `exception_type` if present), then returns an MD5 hex digest. Same pattern ⇒ same signature ⇒ same incident in clustering.

#### `app/core/clustering.py`

- **Cluster window**: 5 minutes (`CLUSTER_WINDOW_MINUTES`). An incident is “reused” only if same signature, same source, `last_seen >= cutoff`, and `status == "open"`.
- **cluster_log**: looks up such an incident; if found, increments `count`, updates `last_seen`, and appends to `sample_lines` (up to `MAX_SAMPLES = 10`). Otherwise creates a new `Incident` with one sample.
- Uses a **new session per call** and explicitly closes it; suitable for request-scoped use from the ingest endpoint.

#### `app/services/storage.py`

- **SQLite**: `sqlite:///data/app.db`; `data` directory created at import.
- **Incident**: id (UUID), source, environment, signature, first_seen, last_seen, count, sample_lines (JSON), status (open/closed/ignored); indexes on source, signature, status.
- **init_db**: `create_all` for the engine.
- **get_db**: generator dependency for FastAPI; yields a session and closes on exit. Note: ingest route does not use `get_db`; it uses the session created inside `cluster_log` instead.

#### `app/api/routes_ingest.py`

- **POST /api/ingest**: for each line, parses → skips non–ERROR/WARN/WARNING/CRITICAL → generates signature → calls `cluster_log`. Tracks incident ids in `created` vs `updated` sets and returns counts. Endpoint is synchronous; each log line triggers a separate DB session in `cluster_log`.

#### `app/api/routes_incidents.py`

- **GET /api/incidents**: optional query params `status`, `source`, `limit` (default 50); orders by `last_seen` desc.
- **GET /api/incidents/{incident_id}**: returns one incident; if not found, returns `{"error": "Incident not found"}`. Response model is `IncidentResponse`, so a 200 with a dict can be inconsistent; returning 404 via `HTTPException` would align better with the schema.
- **POST /api/incidents/{id}/close** and **/ignore**: set `status` to `"closed"` or `"ignored"`; return a small JSON body or error dict.

---

## Dependencies

- **fastapi** (0.109.0) – web framework
- **uvicorn[standard]** (0.27.0) – ASGI server
- **pydantic** (2.5.0) – validation and schemas
- **sqlalchemy** (2.0.23) – ORM and SQLite

See `requirements.txt`.

---

## Setup and run

```bash
cd log-analyzer
python -m venv .venv
source .venv/bin/activate
# or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`

---

## API summary

| Method | Path                         | Description                                                      |
| ------ | ---------------------------- | ---------------------------------------------------------------- |
| GET    | `/`                          | Service info and endpoint list                                   |
| POST   | `/api/ingest`                | Send logs; body: `{ "source", "environment?", "logs": ["..."] }` |
| GET    | `/api/incidents`             | List incidents (optional `status`, `source`, `limit`)            |
| GET    | `/api/incidents/{id}`        | Get one incident                                                 |
| POST   | `/api/incidents/{id}/close`  | Set status to closed                                             |
| POST   | `/api/incidents/{id}/ignore` | Set status to ignored                                            |

---

## Design notes

- **Clustering**: Signature + 5‑minute window keeps the same logical error as one incident while allowing the same pattern to open a new incident after the window or after close/ignore.
- **Samples**: Up to 10 raw log lines per incident give a quick view of variety within the cluster.
- **Persistence**: Single SQLite file and no migrations; fine for single-instance or dev. For multiple workers or production scale, consider a shared DB and proper migrations.
- **Security**: CORS is permissive; tighten `allow_origins` and add auth if the API is exposed.
