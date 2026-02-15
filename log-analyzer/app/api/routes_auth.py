from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from app.services.storage import get_db, Project
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.services.validators import (
    validate_url,
    validate_discord_webhook,
    validate_email,
    validate_log_source_url,
)

import re

router = APIRouter()
security = HTTPBearer()


class ProjectCreate(BaseModel):
    name: str
    password: str
    log_source_url: str
    user_email: str
    discord_webhook_escalate: str
    discord_webhook_dev: str

    @validator("name")
    def validate_name(cls, v):
        if len(v) < 3:
            raise ValueError("Project name must be at least 3 characters")
        if len(v) > 50:
            raise ValueError("Project name must be less than 50 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Project name can only contain letters, numbers, hyphens, and underscores"
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


class ProjectResponse(BaseModel):
    id: str
    name: str
    api_key: str
    log_source_url: str
    user_email: str
    discord_webhook_escalate: str
    discord_webhook_dev: str
    created_at: str

    class Config:
        from_attributes = True


class ValidationResponse(BaseModel):
    field: str
    is_valid: bool
    message: str


@router.post("/validate/url", response_model=ValidationResponse)
def validate_log_url(data: dict):
    """Validate log source URL by actually connecting to it"""
    url = data.get("url", "")
    is_valid, message = validate_log_source_url(url)

    return {"field": "log_source_url", "is_valid": is_valid, "message": message}


@router.post("/validate/discord-escalate", response_model=ValidationResponse)
def validate_discord_escalate_webhook(data: dict):
    """Validate Discord ESCALATE webhook"""
    webhook_url = data.get("webhook_url", "")
    is_valid, message = validate_discord_webhook(webhook_url)

    return {
        "field": "discord_webhook_escalate",
        "is_valid": is_valid,
        "message": message if not is_valid else "Discord webhook verified successfully",
    }


@router.post("/validate/discord-dev", response_model=ValidationResponse)
def validate_discord_dev_webhook(data: dict):
    """Validate Discord DEV webhook"""
    webhook_url = data.get("webhook_url", "")
    is_valid, message = validate_discord_webhook(webhook_url)

    return {
        "field": "discord_webhook_dev",
        "is_valid": is_valid,
        "message": message if not is_valid else "Discord webhook verified successfully",
    }


@router.post("/validate/email", response_model=ValidationResponse)
def validate_user_email(data: dict):
    """Validate user email"""
    email = data.get("email", "")
    is_valid, message = validate_email(email)

    return {
        "field": "user_email",
        "is_valid": is_valid,
        "message": message if not is_valid else "Email format is valid",
    }


@router.post("/register")
def register_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project with full validation"""

    existing = db.query(Project).filter(Project.name == project.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project name already exists")

    errors = []

    url_valid, url_msg = validate_log_source_url(project.log_source_url)
    if not url_valid:
        errors.append({"field": "log_source_url", "message": url_msg})

    email_valid, email_msg = validate_email(project.user_email)
    if not email_valid:
        errors.append({"field": "user_email", "message": email_msg})

    escalate_valid, escalate_msg = validate_discord_webhook(
        project.discord_webhook_escalate
    )
    if not escalate_valid:
        errors.append({"field": "discord_webhook_escalate", "message": escalate_msg})

    dev_valid, dev_msg = validate_discord_webhook(project.discord_webhook_dev)
    if not dev_valid:
        errors.append({"field": "discord_webhook_dev", "message": dev_msg})

    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    new_project = Project(
        name=project.name,
        password_hash=hash_password(project.password),
        log_source_url=project.log_source_url,
        user_email=project.user_email,
        discord_webhook_escalate=project.discord_webhook_escalate,
        discord_webhook_dev=project.discord_webhook_dev,
    )

    try:
        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        token = create_access_token(
            {"project_id": new_project.id, "project_name": new_project.name}
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "project": {
                "id": new_project.id,
                "name": new_project.name,
                "api_key": new_project.api_key,
                "log_source_url": new_project.log_source_url,
                "user_email": new_project.user_email,
                "discord_webhook_escalate": new_project.discord_webhook_escalate,
                "discord_webhook_dev": new_project.discord_webhook_dev,
                "created_at": new_project.created_at.isoformat(),
            },
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.post("/login")
def login_project(credentials: ProjectLogin, db: Session = Depends(get_db)):
    """Login to a project"""
    project = db.query(Project).filter(Project.name == credentials.name).first()

    if not project or not verify_password(credentials.password, project.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect project name or password",
        )

    if not project.is_active:
        raise HTTPException(status_code=403, detail="Project is inactive")

    token = create_access_token(
        {"project_id": project.id, "project_name": project.name}
    )

    webhook_1 = (
        "HIDDEN: TEST DATA NOT ALLOWED TO EDIT"
        if project.is_test
        else project.discord_webhook_escalate
    )

    webhook_2 = (
        "HIDDEN: TEST DATA NOT ALLOWED TO EDIT"
        if project.is_test
        else project.discord_webhook_dev
    )

    api_key = "HIDDEN: TEST API KEY" if project.is_test else project.api_key

    return {
        "access_token": token,
        "token_type": "bearer",
        "project": {
            "id": project.id,
            "name": project.name,
            "api_key": api_key,
            "log_source_url": project.log_source_url,
            "user_email": project.user_email,
            "discord_webhook_escalate": webhook_1,
            "discord_webhook_dev": webhook_2,
            "created_at": project.created_at.isoformat(),
            "is_test": project.is_test,
        },
    }


def get_current_project(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Project:
    """Dependency to get current authenticated project"""
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    project_id = payload.get("project_id")
    if not project_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=401, detail="Project not found")

    return project


@router.get("/me")
def get_current_project_info(project: Project = Depends(get_current_project)):
    """Get current project info"""
    webhook_1 = (
        "HIDDEN: TEST DATA NOT ALLOWED TO EDIT"
        if project.is_test
        else project.discord_webhook_escalate
    )

    webhook_2 = (
        "HIDDEN: TEST DATA NOT ALLOWED TO EDIT"
        if project.is_test
        else project.discord_webhook_dev
    )

    api_key = "HIDDEN: TEST API KEY" if project.is_test else project.api_key

    return {
        "id": project.id,
        "name": project.name,
        "api_key": api_key,
        "log_source_url": project.log_source_url,
        "user_email": project.user_email,
        "discord_webhook_escalate": webhook_1,
        "discord_webhook_dev": webhook_2,
        "created_at": project.created_at.isoformat(),
        "is_test": project.is_test,
    }


@router.put("/settings")
def update_project_settings(
    settings: ProjectCreate,
    project: Project = Depends(get_current_project),
    db: Session = Depends(get_db),
):
    """Update project settings"""
    if project.is_test:
        return {"message": "Test server is not allowed to edit"}

    errors = []

    url_valid, url_msg = validate_url(settings.log_source_url)
    if not url_valid:
        errors.append({"field": "log_source_url", "message": url_msg})

    email_valid, email_msg = validate_email(settings.user_email)
    if not email_valid:
        errors.append({"field": "user_email", "message": email_msg})

    escalate_valid, escalate_msg = validate_discord_webhook(
        settings.discord_webhook_escalate
    )
    if not escalate_valid:
        errors.append({"field": "discord_webhook_escalate", "message": escalate_msg})

    dev_valid, dev_msg = validate_discord_webhook(settings.discord_webhook_dev)
    if not dev_valid:
        errors.append({"field": "discord_webhook_dev", "message": dev_msg})

    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    project.log_source_url = settings.log_source_url
    project.user_email = settings.user_email
    project.discord_webhook_escalate = settings.discord_webhook_escalate
    project.discord_webhook_dev = settings.discord_webhook_dev

    if settings.password:
        project.password_hash = hash_password(settings.password)

    db.commit()

    return {"message": "Settings updated successfully"}
