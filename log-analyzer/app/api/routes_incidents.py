from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from app.services.storage import get_db, Incident
from app.models.schemas import IncidentResponse

router = APIRouter()


@router.get("/incidents", response_model=List[IncidentResponse])
def list_incidents(
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List incidents with optional filters"""
    query = db.query(Incident)

    if status:
        query = query.filter(Incident.status == status)
    if source:
        query = query.filter(Incident.source == source)

    incidents = query.order_by(Incident.last_seen.desc()).limit(limit).all()
    return incidents


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """Get single incident by ID"""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        return {"error": "Incident not found"}
    return incident


@router.post("/incidents/{incident_id}/close")
def close_incident(incident_id: str, db: Session = Depends(get_db)):
    """Mark incident as closed"""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.status = "closed"
        db.commit()
        return {"status": "closed"}
    return {"error": "Incident not found"}


@router.post("/incidents/{incident_id}/ignore")
def ignore_incident(incident_id: str, db: Session = Depends(get_db)):
    """Mark incident as ignored"""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.status = "ignored"
        db.commit()
        return {"status": "ignored"}
    return {"error": "Incident not found"}
