from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
import requests
from app.models.schemas import IngestRequest, IngestResponse
from app.core.parser import ParsedLog
from app.core.signatures import generate_signature
from app.core.clustering import cluster_log
from app.core.runbook_matcher import match_runbook, should_escalate
from app.core.decision_engine import get_decision_engine
from app.services.storage import Analysis, SessionLocal, get_db, Project
from app.services.notifications import get_notification_service

router = APIRouter()


def get_project_by_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Optional[Project]:
    """
    Authenticate request using API key
    Returns None if no API key provided (for backward compatibility with log server)
    """
    if not x_api_key:
        project = db.query(Project).filter(Project.is_active == True).first()
        if not project:
            raise HTTPException(
                status_code=401,
                detail="No API key provided and no default project found. Please register a project first.",
            )
        return project

    project = db.query(Project).filter(Project.api_key == x_api_key).first()

    if not project:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not project.is_active:
        raise HTTPException(status_code=403, detail="Project is inactive")

    return project


@router.post("/ingest", response_model=IngestResponse)
def ingest_logs(
    request: IngestRequest,
    project: Project = Depends(get_project_by_api_key),
):
    """
    Receive logs, parse them, cluster into incidents, apply runbooks or LLM analysis.

    Authentication:
    - With X-API-Key header: Uses the specified project
    - Without X-API-Key: Uses first active project (for demo/testing)
    """
    created = set()
    updated = set()
    processed = 0

    decision_engine = get_decision_engine()
    notification_service = get_notification_service(project=project)

    for log_line in request.logs:
        parsed = ParsedLog(log_line)
        processed += 1

        if parsed.level not in ["ERROR", "WARN", "WARNING", "CRITICAL"]:
            continue

        sig = generate_signature(request.source, parsed)

        incident = cluster_log(
            project_id=project.id,
            source=request.source,
            environment=request.environment,
            parsed_log=parsed,
            signature=sig,
        )

        if incident.count <= 3:
            db = SessionLocal()

            existing_analysis = (
                db.query(Analysis).filter(Analysis.incident_id == incident.id).first()
            )

            if not existing_analysis:
                runbook, score = match_runbook(incident)

                if runbook and score >= 0.5:
                    disposition = runbook.disposition

                    if disposition == "OBSERVE" and should_escalate(incident, runbook):
                        disposition = runbook.observe_threshold.get(
                            "escalate_to", "ESCALATE"
                        )

                    analysis = Analysis(
                        incident_id=incident.id,
                        severity=runbook.default_severity,
                        disposition=disposition,
                        confidence=score,
                        summary=f"{runbook.name}: {runbook.description}",
                        next_steps=runbook.steps,
                        matched_runbook_id=runbook.id,
                        runbook_match_score=score,
                        analysis_source="runbook",
                    )
                    db.add(analysis)
                    db.commit()
                    db.refresh(analysis)

                    notification_service.route_notification(incident, analysis)

                else:
                    llm_analysis = decision_engine.analyze_incident(incident)

                    if llm_analysis:
                        analysis = Analysis(
                            incident_id=incident.id,
                            severity=llm_analysis.severity,
                            disposition=llm_analysis.disposition,
                            confidence=llm_analysis.confidence,
                            summary=llm_analysis.summary,
                            next_steps=llm_analysis.next_steps,
                            ticket_title=llm_analysis.ticket_title,
                            ticket_body=llm_analysis.ticket_body,
                            analysis_source="llm",
                        )
                        db.add(analysis)
                        db.commit()
                        db.refresh(analysis)

                        notification_service.route_notification(incident, analysis)

            db.close()

        if incident.count == 1:
            created.add(incident.id)
        else:
            updated.add(incident.id)

    return IngestResponse(
        incidents_created=len(created),
        incidents_updated=len(updated),
        total_logs_processed=processed,
    )


@router.post("/log-server/start")
def start_log_server(
    project: Project = Depends(get_project_by_api_key),
):

    try:
        resp = requests.post(
            f"{project.log_source_url}/api/start",
            headers={"X-API-Key": project.api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")


@router.post("/log-server/stop")
def stop_log_server(
    project: Project = Depends(get_project_by_api_key),
):

    try:
        resp = requests.post(
            f"{project.log_source_url}/api/stop",
            headers={"X-API-Key": project.api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")


@router.get("/log-server/status")
def log_server_status(
    project: Project = Depends(get_project_by_api_key),
):
    try:
        resp = requests.get(
            f"{project.log_source_url}/api/status",
            headers={"X-API-Key": project.api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Log server unreachable: {e}")
