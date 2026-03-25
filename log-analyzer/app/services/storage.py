from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    DateTime,
    JSON,
    Float,
    Boolean,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://log_user:password@localhost:5432/log_analyzer"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Project(Base):
    """Project with credentials and notification settings"""

    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    api_key = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
        default=lambda: secrets.token_urlsafe(32),
    )
    log_source_url = Column(String, nullable=False)
    user_email = Column(String, nullable=False)
    discord_webhook_escalate = Column(String, nullable=False)
    discord_webhook_dev = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_test = Column(Boolean, default=False)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, index=True)
    environment = Column(String, default="dev")
    signature = Column(String, nullable=False, index=True)
    first_seen = Column(DateTime, default=datetime.utcnow, index=True)
    last_seen = Column(DateTime, default=datetime.utcnow, index=True)
    count = Column(Integer, default=1)
    sample_lines = Column(JSON)
    status = Column(String, default="open", index=True)

    root_cause_incident_id = Column(String, nullable=True, index=True)
    cause_explanation = Column(Text, nullable=True)


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    severity = Column(String)
    disposition = Column(String)
    confidence = Column(Float)
    summary = Column(String)
    next_steps = Column(JSON)
    matched_runbook_id = Column(String)
    runbook_match_score = Column(Float)
    ticket_title = Column(String)
    ticket_body = Column(String)
    analysis_source = Column(String)


def init_db():
    """Initialize database tables (creates new columns via CREATE TABLE IF NOT EXISTS)."""
    Base.metadata.create_all(bind=engine)
    print("Database initialized")


def migrate_add_root_cause_columns():
    """
    Safe migration for existing deployments — adds the two new columns if they
    don't already exist.  Call this once from your startup script or run it
    manually before deploying the new worker.

    Usage:
        python -c "from app.services.storage import migrate_add_root_cause_columns; migrate_add_root_cause_columns()"
    """
    with engine.connect() as conn:
        for col, col_type in [
            ("root_cause_incident_id", "VARCHAR"),
            ("cause_explanation", "TEXT"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE incidents ADD COLUMN IF NOT EXISTS {col} {col_type};"
                )
                print(f"[MIGRATION] Column '{col}' ensured on incidents table.")
            except Exception as e:
                print(f"[MIGRATION] Could not add column '{col}': {e}")
        conn.commit()


def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
