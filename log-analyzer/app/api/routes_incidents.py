from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from app.services.storage import get_db, Incident, Analysis
from app.models.schemas import IncidentResponse

router = APIRouter()


@router.get("/incidents")
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
        query = query.filter(Incident.source.contains(source))

    incidents = query.order_by(Incident.last_seen.desc()).limit(limit).all()

    # Format response with analyses
    result = []
    for inc in incidents:
        analysis = (
            db.query(Analysis)
            .filter(Analysis.incident_id == inc.id)
            .order_by(Analysis.created_at.desc())
            .first()
        )

        incident_dict = {
            "id": inc.id,
            "source": inc.source,
            "environment": inc.environment,
            "signature": inc.signature,
            "first_seen": inc.first_seen.isoformat(),
            "last_seen": inc.last_seen.isoformat(),
            "count": inc.count,
            "status": inc.status,
            "sample_lines": inc.sample_lines,
        }

        if analysis:
            incident_dict["analysis"] = {
                "severity": analysis.severity,
                "disposition": analysis.disposition,
                "confidence": analysis.confidence,
                "summary": analysis.summary,
                "next_steps": analysis.next_steps,
                "ticket_title": analysis.ticket_title,
                "ticket_body": analysis.ticket_body,
                "analysis_source": analysis.analysis_source,
            }

        result.append(incident_dict)

    return result


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """Get single incident by ID"""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        return {"error": "Incident not found"}

    analysis = (
        db.query(Analysis)
        .filter(Analysis.incident_id == incident_id)
        .order_by(Analysis.created_at.desc())
        .first()
    )

    result = {
        "id": incident.id,
        "source": incident.source,
        "environment": incident.environment,
        "signature": incident.signature,
        "first_seen": incident.first_seen.isoformat(),
        "last_seen": incident.last_seen.isoformat(),
        "count": incident.count,
        "status": incident.status,
        "sample_lines": incident.sample_lines,
    }

    if analysis:
        result["analysis"] = {
            "severity": analysis.severity,
            "disposition": analysis.disposition,
            "confidence": analysis.confidence,
            "summary": analysis.summary,
            "next_steps": analysis.next_steps,
            "ticket_title": analysis.ticket_title,
            "ticket_body": analysis.ticket_body,
            "analysis_source": analysis.analysis_source,
        }

    return result


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
