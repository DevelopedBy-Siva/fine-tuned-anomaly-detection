from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.services.storage import get_db, Project
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

router = APIRouter()
security = HTTPBearer()


class ProjectCreate(BaseModel):
    name: str
    password: str
    discord_webhook_escalate: str = ""
    discord_webhook_dev: str = ""
    smtp_user: str = ""
    smtp_password: str = ""
    oncall_email: str = ""


class ProjectLogin(BaseModel):
    name: str
    password: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    discord_webhook_escalate: str
    discord_webhook_dev: str
    smtp_user: str
    oncall_email: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("/register")
def register_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project"""
    # Check if project name already exists
    existing = db.query(Project).filter(Project.name == project.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project name already exists")

    # Create project
    new_project = Project(
        name=project.name,
        password_hash=hash_password(project.password),
        discord_webhook_escalate=project.discord_webhook_escalate,
        discord_webhook_dev=project.discord_webhook_dev,
        smtp_user=project.smtp_user,
        smtp_password=project.smtp_password,
        oncall_email=project.oncall_email,
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    # Generate token
    token = create_access_token(
        {"project_id": new_project.id, "project_name": new_project.name}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "project": ProjectResponse.from_orm(new_project),
    }


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

    # Generate token
    token = create_access_token(
        {"project_id": project.id, "project_name": project.name}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "project": ProjectResponse.from_orm(new_project),
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


@router.get("/me", response_model=ProjectResponse)
def get_current_project_info(project: Project = Depends(get_current_project)):
    """Get current project info"""
    return project


@router.put("/settings")
def update_project_settings(
    settings: ProjectCreate,
    project: Project = Depends(get_current_project),
    db: Session = Depends(get_db),
):
    """Update project notification settings"""
    project.discord_webhook_escalate = settings.discord_webhook_escalate
    project.discord_webhook_dev = settings.discord_webhook_dev
    project.smtp_user = settings.smtp_user
    project.smtp_password = settings.smtp_password
    project.oncall_email = settings.oncall_email

    # Update password if provided
    if settings.password:
        project.password_hash = hash_password(settings.password)

    db.commit()

    return {"message": "Settings updated successfully"}
