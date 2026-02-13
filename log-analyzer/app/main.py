from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.services.storage import init_db
from app.api import routes_ingest, routes_incidents, routes_dashboard, routes_auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Log Analyzer...")
    init_db()
    yield
    # Shutdown
    print("🛑 Shutting down...")


app = FastAPI(title="Log Analyzer", lifespan=lifespan)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(routes_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes_ingest.router, prefix="/api", tags=["ingest"])
app.include_router(routes_incidents.router, prefix="/api", tags=["incidents"])
app.include_router(routes_dashboard.router, prefix="/api", tags=["dashboard"])


@app.get("/")
def root():
    return {
        "service": "log-analyzer",
        "status": "running",
        "version": "2.0.0",
        "dashboard": "http://localhost:8000/api/dashboard",
        "frontend": "http://localhost:3000",
    }
