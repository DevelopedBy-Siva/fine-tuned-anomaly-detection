from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class IngestRequest(BaseModel):
    source: str
    environment: str = "dev"
    logs: List[str]


class IngestResponse(BaseModel):
    incidents_created: int
    incidents_updated: int
    total_logs_processed: int


class IncidentResponse(BaseModel):
    id: str
    source: str
    environment: str
    signature: str
    first_seen: datetime
    last_seen: datetime
    count: int
    status: str
    sample_lines: Optional[List[str]] = None

    class Config:
        from_attributes = True
