import os
import json
import socket
import time
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_KEY = os.getenv("STREAM_KEY", "logs:stream")
GROUP_NAME = "log-analyzers"
CONSUMER_NAME = f"worker-{socket.gethostname()}"
BLOCK_MS = 1000
BATCH_SIZE = 10
RECLAIM_IDLE_MS = 60000

process_log_batch = None


def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def ensure_consumer_group(r: redis.Redis):
    try:
        r.xgroup_create(STREAM_KEY, GROUP_NAME, id="0-0", mkstream=True)
        print(f"[WORKER] Created consumer group '{GROUP_NAME}'")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"[WORKER] Consumer group '{GROUP_NAME}' already exists — joining")
        else:
            raise


def reclaim_stuck_entries(r: redis.Redis):
    try:
        result = r.xautoclaim(
            STREAM_KEY,
            GROUP_NAME,
            CONSUMER_NAME,
            min_idle_time=RECLAIM_IDLE_MS,
            start_id="0-0",
            count=BATCH_SIZE,
        )
        reclaimed = result[1] if result else []
        if reclaimed:
            print(f"[WORKER] Reclaimed {len(reclaimed)} stuck entries")
        return reclaimed
    except Exception as e:
        print(f"[WORKER] reclaim skipped: {e}")
        return []


def process_entry(r: redis.Redis, entry_id: str, fields: dict):
    try:
        logs = json.loads(fields.get("logs", "[]"))
        payload = {
            "api_key": fields.get("api_key", ""),
            "source": fields.get("source", "log-server"),
            "environment": fields.get("environment", "prod"),
            "logs": logs,
        }
        process_log_batch(payload)
        r.xack(STREAM_KEY, GROUP_NAME, entry_id)
        print(f"[WORKER] ACKed {entry_id} ({len(logs)} logs)")
    except Exception as e:
        print(f"[WORKER] Failed {entry_id} — not ACKing, will retry: {e}")


def run():
    print(
        f"[WORKER] Starting — stream='{STREAM_KEY}' group='{GROUP_NAME}' consumer='{CONSUMER_NAME}'"
    )
    print("[WORKER] Importing tasks...")
    from worker.tasks import process_log_batch as _process_log_batch

    global process_log_batch
    process_log_batch = _process_log_batch
    print("[WORKER] Tasks imported OK")

    r = get_redis()
    print(f"[WORKER] Connecting to Redis...")
    try:
        r.ping()
        print("[WORKER] Redis connected")
    except Exception as e:
        print(f"[WORKER] Redis connection failed: {e}")
        return

    ensure_consumer_group(r)

    while True:
        try:
            for entry_id, fields in reclaim_stuck_entries(r):
                process_entry(r, entry_id, fields)

            results = r.xreadgroup(
                GROUP_NAME,
                CONSUMER_NAME,
                {STREAM_KEY: ">"},
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )
            if not results:
                continue

            for stream_name, entries in results:
                for entry_id, fields in entries:
                    process_entry(r, entry_id, fields)

        except redis.exceptions.ConnectionError as e:
            print(f"[WORKER] Redis lost: {e} — retrying in 5s")
            time.sleep(5)
        except KeyboardInterrupt:
            print("[WORKER] Shutting down")
            break
        except Exception as e:
            print(f"[WORKER] Error: {e} — retrying in 2s")
            time.sleep(2)


if __name__ == "__main__":
    run()
