"""
worker/loki_watcher.py

Replaces stream.py entirely.
Polls Grafana Loki every 30 seconds for new ERROR/WARN/CRITICAL logs
and feeds them into the existing process_log_batch() pipeline.

Environment variables:
  LOKI_URL        — e.g. https://logs-prod-006.grafana.net  (no trailing slash)
  LOKI_USERNAME   — numeric Grafana user ID
  LOKI_API_KEY    — Grafana Cloud API key (MetricsPublisher role)
  LOKI_SERVICE    — label value for {service=} filter (default: log-server)
  POLL_INTERVAL   — seconds between polls (default: 30)

How it works:
  1. On startup, sets last_queried = now - POLL_INTERVAL
  2. Every POLL_INTERVAL seconds, queries Loki for logs between
     last_queried and now with level ERROR, WARN, or CRITICAL
  3. Parses each log line through the existing process_log_batch() pipeline
  4. Advances last_queried to now so entries are never double-processed
"""

import base64
import httpx
import os
import time
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

LOKI_URL = os.getenv("LOKI_URL", "")
LOKI_USERNAME = os.getenv("LOKI_USERNAME", "")
LOKI_API_KEY = os.getenv("LOKI_API_KEY", "")
LOKI_SERVICE = os.getenv("LOKI_SERVICE", "log-server")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

# Loki LogQL query — fetch ERROR, WARN, CRITICAL from our service
# Adjust the label selectors if your log server uses different labels
LOKI_QUERY = f'{{service="{LOKI_SERVICE}"}} |~ "ERROR|WARN|CRITICAL"'

# How many log lines to fetch per poll at most
MAX_LINES_PER_POLL = 500

# Source / environment labels passed into process_log_batch
LOG_SOURCE = os.getenv("LOG_SOURCE", "log-server")
LOG_ENVIRONMENT = os.getenv("LOG_ENVIRONMENT", "prod")


# ---------------------------------------------------------------------------
# Loki HTTP client
# ---------------------------------------------------------------------------


def _auth_header() -> str:
    token = base64.b64encode(f"{LOKI_USERNAME}:{LOKI_API_KEY}".encode()).decode()
    return f"Basic {token}"


def _to_loki_ns(dt: datetime) -> str:
    """Convert a UTC datetime to nanosecond-precision Unix timestamp string."""
    return str(int(dt.timestamp() * 1_000_000_000))


def fetch_logs(start: datetime, end: datetime) -> list[str]:
    """
    Query Loki for log lines between start and end (UTC datetimes).
    Returns a flat list of raw log line strings, oldest first.

    Loki query_range response shape:
    {
      "data": {
        "result": [
          {
            "stream": {"service": "log-server", ...},
            "values": [
              ["<nanosecond_timestamp>", "<log line>"],
              ...
            ]
          }
        ]
      }
    }
    """
    if not all([LOKI_URL, LOKI_USERNAME, LOKI_API_KEY]):
        print("[LOKI-WATCHER] Credentials not configured — skipping poll")
        return []

    params = {
        "query": LOKI_QUERY,
        "start": _to_loki_ns(start),
        "end": _to_loki_ns(end),
        "limit": MAX_LINES_PER_POLL,
        "direction": "forward",  # oldest first
    }

    try:
        response = httpx.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            headers={"Authorization": _auth_header()},
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            print(
                f"[LOKI-WATCHER] Query failed: {response.status_code} — {response.text[:200]}"
            )
            return []

        data = response.json()
        streams = data.get("data", {}).get("result", [])

        lines = []
        for stream in streams:
            for _ts, line in stream.get("values", []):
                lines.append(line)

        return lines

    except Exception as e:
        print(f"[LOKI-WATCHER] fetch_logs exception: {e}")
        return []


# ---------------------------------------------------------------------------
# Main poll loop
# ---------------------------------------------------------------------------


def run():
    """
    Main entry point — runs forever, polling Loki every POLL_INTERVAL seconds.
    Called from app/main.py in a daemon thread, same as stream.run() was.
    """
    print(
        f"[LOKI-WATCHER] Starting — service='{LOKI_SERVICE}' poll_interval={POLL_INTERVAL}s"
    )
    print(f"[LOKI-WATCHER] Loki endpoint: {LOKI_URL or 'NOT SET'}")

    if not all([LOKI_URL, LOKI_USERNAME, LOKI_API_KEY]):
        print(
            "[LOKI-WATCHER] ERROR: LOKI_URL / LOKI_USERNAME / LOKI_API_KEY not set — exiting"
        )
        return

    # Import here (same pattern as stream.py) to avoid circular imports
    from worker.tasks import process_log_batch

    # Start polling from now minus one interval so we catch any logs
    # generated while the worker was starting up
    last_queried = datetime.now(timezone.utc) - timedelta(seconds=POLL_INTERVAL)

    # Verify Loki is reachable before entering the loop
    test_lines = fetch_logs(
        start=last_queried,
        end=datetime.now(timezone.utc),
    )
    print(
        f"[LOKI-WATCHER] Startup check — {len(test_lines)} log(s) found in initial window"
    )

    while True:
        try:
            poll_start = datetime.now(timezone.utc)

            lines = fetch_logs(start=last_queried, end=poll_start)

            if lines:
                print(f"[LOKI-WATCHER] Fetched {len(lines)} log line(s) from Loki")

                # Determine project api_key
                # The log server no longer stamps api_key on each log line.
                # We use LOGSHIPPER_API_KEY from env (same key the log server uses)
                # so process_log_batch can look up the project.
                api_key = os.getenv("LOGSHIPPER_API_KEY", "")

                payload = {
                    "api_key": api_key,
                    "source": LOG_SOURCE,
                    "environment": LOG_ENVIRONMENT,
                    "logs": lines,
                }

                try:
                    result = process_log_batch(payload)
                    if result:
                        print(
                            f"[LOKI-WATCHER] Processed — "
                            f"created: {result.get('incidents_created', 0)}, "
                            f"updated: {result.get('incidents_updated', 0)}, "
                            f"failed: {result.get('failed', 0)}"
                        )
                except Exception as e:
                    print(f"[LOKI-WATCHER] process_log_batch error: {e}")
                    # Don't advance last_queried — retry these logs next poll
                    time.sleep(POLL_INTERVAL)
                    continue
            else:
                print(
                    f"[LOKI-WATCHER] No new logs since {last_queried.strftime('%H:%M:%S')}"
                )

            # Advance the window — next poll starts from here
            last_queried = poll_start

        except KeyboardInterrupt:
            print("[LOKI-WATCHER] Shutting down")
            break

        except Exception as e:
            print(
                f"[LOKI-WATCHER] Unexpected error: {e} — retrying in {POLL_INTERVAL}s"
            )

        time.sleep(POLL_INTERVAL)
