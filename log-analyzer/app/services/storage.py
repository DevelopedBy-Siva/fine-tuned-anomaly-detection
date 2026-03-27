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
import uuid, os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://log_user:password@localhost:5432/log_analyzer"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Project(Base):
    """
    Registration: name + password only.
    All credentials set via PUT /api/auth/settings after registration.
    """

    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_test = Column(Boolean, default=False)

    # Loki
    loki_url = Column(String, nullable=True)
    loki_username = Column(String, nullable=True)
    loki_api_key = Column(String, nullable=True)
    loki_service = Column(String, nullable=True)

    # LLM
    groq_api_key = Column(String, nullable=True)

    # Observability
    langfuse_public_key = Column(String, nullable=True)
    langfuse_secret_key = Column(String, nullable=True)
    langfuse_host = Column(String, nullable=True, default="https://cloud.langfuse.com")

    # Notifications
    user_email = Column(String, nullable=True)
    discord_webhook_escalate = Column(String, nullable=True)
    discord_webhook_dev = Column(String, nullable=True)


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, index=True)
    environment = Column(String, default="prod")
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
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables initialised")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
