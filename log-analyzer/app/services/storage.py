from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    DateTime,
    JSON,
    Float,
    Boolean,
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

    # API Key for log ingestion
    api_key = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
        default=lambda: secrets.token_urlsafe(32),
    )

    # Log source
    log_source_url = Column(String, nullable=False)

    # User contact
    user_email = Column(String, nullable=False)

    # Discord webhooks
    discord_webhook_escalate = Column(String, nullable=False)
    discord_webhook_dev = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


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
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")


def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
