from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.services.storage import get_db, Incident, Analysis, Project
from app.api.routes_auth import get_current_project

router = APIRouter()


@router.get("/incidents")
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    ticket_title: Optional[str] = None,
    limit: int = 50,
    project: Project = Depends(get_current_project),
    db: Session = Depends(get_db),
):
    """List incidents with optional filters"""
    query = db.query(Incident).filter(Incident.project_id == project.id)

    if status:
        status = status.strip().lower()
        query = query.filter(func.lower(Incident.status) == status)

    if severity or ticket_title:
        query = query.join(Analysis, Incident.id == Analysis.incident_id)

        if severity:
            severity = severity.strip().lower()
            query = query.filter(func.lower(Analysis.severity) == severity)

        if ticket_title:
            ticket_title = ticket_title.strip()
            query = query.filter(
                func.lower(Analysis.ticket_title).contains(ticket_title.lower())
            )

        subquery = (
            db.query(
                Analysis.incident_id, func.max(Analysis.created_at).label("max_created")
            )
            .group_by(Analysis.incident_id)
            .subquery()
        )
        query = query.join(
            subquery,
            (Analysis.incident_id == subquery.c.incident_id)
            & (Analysis.created_at == subquery.c.max_created),
        )

    incidents = query.order_by(Incident.last_seen.desc()).limit(limit).all()

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
def get_incident(
    incident_id: str,
    project: Project = Depends(get_current_project),
    db: Session = Depends(get_db),
):
    """Get single incident by ID"""
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id, Incident.project_id == project.id)
        .first()
    )

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

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
def close_incident(
    incident_id: str,
    project: Project = Depends(get_current_project),
    db: Session = Depends(get_db),
):
    """Mark incident as closed"""
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id, Incident.project_id == project.id)
        .first()
    )

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "closed"
    db.commit()
    return {"status": "closed"}


@router.post("/incidents/{incident_id}/ignore")
def ignore_incident(
    incident_id: str,
    project: Project = Depends(get_current_project),
    db: Session = Depends(get_db),
):
    """Mark incident as ignored"""
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id, Incident.project_id == project.id)
        .first()
    )

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "ignored"
    db.commit()
    return {"status": "ignored"}
