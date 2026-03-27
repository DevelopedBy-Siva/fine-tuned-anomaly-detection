import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.services.storage import get_db, Project
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

router = APIRouter()
security = HTTPBearer()


class ProjectRegister(BaseModel):
    name: str
    password: str

    @validator("name")
    def validate_name(cls, v):
        if len(v) < 3:
            raise ValueError("Name must be at least 3 characters")
        if len(v) > 50:
            raise ValueError("Name must be less than 50 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Name can only contain letters, numbers, hyphens, underscores"
            )
        return v

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ProjectLogin(BaseModel):
    name: str
    password: str


class ProjectSettings(BaseModel):
    loki_url: Optional[str] = None
    loki_username: Optional[str] = None
    loki_api_key: Optional[str] = None
    loki_service: Optional[str] = None
    groq_api_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: Optional[str] = None
    user_email: Optional[str] = None
    discord_webhook_escalate: Optional[str] = None
    discord_webhook_dev: Optional[str] = None
    password: Optional[str] = None

    @validator("password")
    def validate_password(cls, v):
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


def _project_to_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "created_at": project.created_at.isoformat(),
        "is_test": project.is_test,
        "loki_url": project.loki_url,
        "loki_username": project.loki_username,
        "loki_api_key": "••••••" if project.loki_api_key else None,
        "loki_service": project.loki_service,
        "groq_api_key": "••••••" if project.groq_api_key else None,
        "langfuse_public_key": "••••••" if project.langfuse_public_key else None,
        "langfuse_secret_key": "••••••" if project.langfuse_secret_key else None,
        "langfuse_host": project.langfuse_host,
        "user_email": project.user_email,
        "discord_webhook_escalate": project.discord_webhook_escalate,
        "discord_webhook_dev": project.discord_webhook_dev,
        "setup_complete": all(
            [
                project.loki_url,
                project.loki_username,
                project.loki_api_key,
                project.groq_api_key,
            ]
        ),
    }


def get_current_project(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Project:
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    project = db.query(Project).filter(Project.id == payload.get("project_id")).first()
    if not project:
        raise HTTPException(status_code=401, detail="Project not found")
    return project


@router.post("/register")
def register_project(data: ProjectRegister, db: Session = Depends(get_db)):
    if db.query(Project).filter(Project.name == data.name).first():
        raise HTTPException(status_code=400, detail="Project name already exists")
    project = Project(name=data.name, password_hash=hash_password(data.password))
    try:
        db.add(project)
        db.commit()
        db.refresh(project)
        token = create_access_token(
            {"project_id": project.id, "project_name": project.name}
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "project": _project_to_dict(project),
            "message": "Project created. Go to Settings to configure Loki, Groq, and notification credentials.",
        }
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.post("/login")
def login_project(credentials: ProjectLogin, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.name == credentials.name).first()
    if not project or not verify_password(credentials.password, project.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect name or password")
    if not project.is_active:
        raise HTTPException(status_code=403, detail="Project is inactive")
    token = create_access_token(
        {"project_id": project.id, "project_name": project.name}
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "project": _project_to_dict(project),
    }


@router.get("/me")
def get_me(project: Project = Depends(get_current_project)):
    return _project_to_dict(project)


@router.put("/settings")
def update_settings(
    settings: ProjectSettings,
    project: Project = Depends(get_current_project),
    db: Session = Depends(get_db),
):
    if project.is_test:
        raise HTTPException(
            status_code=403, detail="Test project settings are read-only"
        )

    fields = [
        "loki_url",
        "loki_username",
        "loki_api_key",
        "loki_service",
        "groq_api_key",
        "langfuse_public_key",
        "langfuse_secret_key",
        "langfuse_host",
        "user_email",
        "discord_webhook_escalate",
        "discord_webhook_dev",
    ]
    for field in fields:
        value = getattr(settings, field)
        if value is not None:
            setattr(project, field, value)

    if settings.password:
        project.password_hash = hash_password(settings.password)

    try:
        db.commit()
        db.refresh(project)
        return {"message": "Settings updated", "project": _project_to_dict(project)}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/settings/status")
def settings_status(project: Project = Depends(get_current_project)):
    return {
        "loki": {
            "configured": all(
                [project.loki_url, project.loki_username, project.loki_api_key]
            )
        },
        "llm": {"configured": bool(project.groq_api_key)},
        "observability": {
            "configured": all(
                [project.langfuse_public_key, project.langfuse_secret_key]
            )
        },
        "notifications": {
            "configured": any(
                [
                    project.user_email,
                    project.discord_webhook_escalate,
                    project.discord_webhook_dev,
                ]
            )
        },
        "setup_complete": all(
            [
                project.loki_url,
                project.loki_username,
                project.loki_api_key,
                project.groq_api_key,
            ]
        ),
    }
