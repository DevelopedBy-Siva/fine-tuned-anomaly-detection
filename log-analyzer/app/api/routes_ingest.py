import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from app.services.storage import Project
from app.api.routes_auth import get_current_project

router = APIRouter()

LOG_SERVER_URL = os.getenv("LOG_SERVER_URL", "http://localhost:5001").rstrip("/")


def _url(path: str) -> str:
    return f"{LOG_SERVER_URL}{path}"


@router.post("/log-server/start")
def start_log_server(project: Project = Depends(get_current_project)):
    if not project.is_test:
        raise HTTPException(
            status_code=403, detail="Log server is only available for the demo project."
        )
    try:
        resp = requests.post(_url("/api/start"), timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")


@router.post("/log-server/stop")
def stop_log_server(project: Project = Depends(get_current_project)):
    if not project.is_test:
        raise HTTPException(
            status_code=403, detail="Log server is only available for the demo project."
        )
    try:
        resp = requests.post(_url("/api/stop"), timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")


@router.get("/log-server/status")
def log_server_status(project: Project = Depends(get_current_project)):
    if not project.is_test:
        raise HTTPException(
            status_code=403, detail="Log server is only available for the demo project."
        )
    try:
        resp = requests.get(_url("/api/status"), timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")
