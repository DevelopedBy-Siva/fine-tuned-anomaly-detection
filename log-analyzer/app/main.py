import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.services.storage import init_db
from app.api import routes_ingest, routes_incidents, routes_auth

from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Log Analyzer...")
    init_db()
    yield
    print("Shutting down...")


app = FastAPI(title="Log Analyzer", lifespan=lifespan)


cors_origins = os.getenv("CORS_ORIGINS")
origins = [origin.strip() for origin in cors_origins.split(",") if origin]

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
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}
