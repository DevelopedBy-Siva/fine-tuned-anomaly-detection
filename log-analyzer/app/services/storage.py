from sqlalchemy import Float, create_engine, Column, String, Integer, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
import os

os.makedirs("data", exist_ok=True)

DATABASE_URL = "sqlite:///data/app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    severity = Column(String)  # low/medium/high/critical
    disposition = Column(String)  # NO_ACTION/OBSERVE/NEEDS_DEV/NEEDS_ONCALL/ESCALATE
    confidence = Column(Float)
    summary = Column(String)
    next_steps = Column(JSON)  # Array of strings
    matched_runbook_id = Column(String)
    runbook_match_score = Column(Float)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String, nullable=False, index=True)
    environment = Column(String, default="dev")
    signature = Column(String, nullable=False, index=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    count = Column(Integer, default=1)
    sample_lines = Column(JSON)  # Array of log strings
    status = Column(String, default="open", index=True)  # open/closed/ignored


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("Database initialized")


def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
