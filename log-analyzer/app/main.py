from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.services.storage import init_db
from app.api import routes_ingest, routes_incidents
from app.api import routes_ingest, routes_incidents, routes_dashboard  # Add this


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Log Analyzer...")
    init_db()
    yield
    print("Shutting down...")


app = FastAPI(title="Log Analyzer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_ingest.router, prefix="/api", tags=["ingest"])
app.include_router(routes_incidents.router, prefix="/api", tags=["incidents"])
app.include_router(routes_dashboard.router, prefix="/api", tags=["dashboard"])


@app.get("/")
def root():
    return {
        "service": "log-analyzer",
        "status": "running",
        "dashboard": "http://localhost:8000/api/dashboard",
        "endpoints": [
            "POST /api/ingest",
            "GET /api/incidents",
            "GET /api/incidents/{id}",
            "GET /api/dashboard",
        ],
    }
