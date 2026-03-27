"""
app/main.py

Change from original:
  - start_worker() now imports from worker.loki_watcher instead of worker.stream
  - Everything else — routes, middleware, lifespan, CORS — UNCHANGED
"""

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.services.storage import init_db
from app.services.cleanup import cleanup_all_data
from app.api import routes_ingest, routes_incidents, routes_auth

load_dotenv()


def start_worker():
    import traceback

    print("[MAIN] Starting Loki watcher thread...")
    try:
        # ← Only change: stream → loki_watcher
        from worker.loki_watcher import run as run_worker

        print("[MAIN] loki_watcher imported OK, starting poll loop...")
        run_worker()
    except Exception as e:
        print(f"[MAIN] Loki watcher thread failed: {e}")
        traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Log Analyzer...")
    init_db()
    cleanup_all_data()

    worker_thread = threading.Thread(target=start_worker, daemon=True)
    worker_thread.start()
    print("[MAIN] Loki watcher thread started")

    yield
    print("Shutting down...")


app = FastAPI(title="Log Analyzer", lifespan=lifespan)

cors_origins = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes_ingest.router, prefix="/api", tags=["ingest"])
app.include_router(routes_incidents.router, prefix="/api", tags=["incidents"])


@app.get("/")
def root():
    return {
        "service": "log-analyzer",
        "status": "running",
        "version": "2.0.0",
        "frontend": origins,
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
