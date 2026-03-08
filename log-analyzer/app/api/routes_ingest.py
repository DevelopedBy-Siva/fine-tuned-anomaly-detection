from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
import requests

from app.services.storage import get_db, Project

router = APIRouter()


def get_project_by_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Project:
    if not x_api_key:
        project = db.query(Project).filter(Project.is_active == True).first()
        if not project:
            raise HTTPException(
                status_code=401,
                detail="No API key provided and no default project found.",
            )
        return project

    project = db.query(Project).filter(Project.api_key == x_api_key).first()
    if not project:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not project.is_active:
        raise HTTPException(status_code=403, detail="Project is inactive")
    return project


@router.post("/log-server/start")
def start_log_server(project: Project = Depends(get_project_by_api_key)):
    try:
        resp = requests.post(
            f"{project.log_source_url}/api/start",
            headers={"X-API-Key": project.api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")


@router.post("/log-server/stop")
def stop_log_server(project: Project = Depends(get_project_by_api_key)):
    try:
        resp = requests.post(
            f"{project.log_source_url}/api/stop",
            headers={"X-API-Key": project.api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")


@router.get("/log-server/status")
def log_server_status(project: Project = Depends(get_project_by_api_key)):
    try:
        resp = requests.get(
            f"{project.log_source_url}/api/status",
            headers={"X-API-Key": project.api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")
