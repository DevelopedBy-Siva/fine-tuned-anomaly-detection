from fastapi import APIRouter
from app.models.schemas import IngestRequest, IngestResponse
from app.core.parser import ParsedLog
from app.core.signatures import generate_signature
from app.core.clustering import cluster_log
from app.core.runbook_matcher import match_runbook, should_escalate
from app.core.decision_engine import get_decision_engine
from app.services.storage import Analysis, SessionLocal

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest_logs(request: IngestRequest):
    """
    Receive logs, parse them, cluster into incidents, apply runbooks or LLM analysis.
    """
    created = set()
    updated = set()
    processed = 0

    decision_engine = get_decision_engine()

    for log_line in request.logs:
        # Parse
        parsed = ParsedLog(log_line)
        processed += 1

        # Only process errors/warnings
        if parsed.level not in ["ERROR", "WARN", "WARNING", "CRITICAL"]:
            continue

        # Generate signature
        sig = generate_signature(request.source, parsed)

        # Cluster
        incident = cluster_log(request.source, request.environment, parsed, sig)

        # Analyze incident (only for new or low-count incidents)
        if incident.count <= 3:
            db = SessionLocal()

            # Check if analysis already exists
            existing_analysis = (
                db.query(Analysis).filter(Analysis.incident_id == incident.id).first()
            )

            if not existing_analysis:
                # Try runbook match first
                runbook, score = match_runbook(incident)

                if runbook and score >= 0.5:
                    # High-confidence runbook match
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

                else:
                    # No runbook or low confidence - use LLM
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
            db.close()

        # Track created vs updated
        if incident.count == 1:
            created.add(incident.id)
        else:
            updated.add(incident.id)

    return IngestResponse(
        incidents_created=len(created),
        incidents_updated=len(updated),
        total_logs_processed=processed,
    )
