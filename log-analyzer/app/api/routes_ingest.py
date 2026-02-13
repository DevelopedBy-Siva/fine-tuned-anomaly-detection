from fastapi import APIRouter
from app.models.schemas import IngestRequest, IngestResponse
from app.core.parser import ParsedLog
from app.core.signatures import generate_signature
from app.core.clustering import cluster_log
from app.core.runbook_matcher import match_runbook, should_escalate
from app.services.storage import Analysis, SessionLocal

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest_logs(request: IngestRequest):
    """
    Receive logs, parse them, cluster into incidents, apply runbooks.
    """
    created = set()
    updated = set()
    processed = 0

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

        # Apply runbook matching (only for new incidents or first few occurrences)
        if incident.count <= 3:
            runbook, score = match_runbook(incident)

            if runbook:
                # Check if we should escalate
                disposition = runbook.disposition
                if disposition == "OBSERVE" and should_escalate(incident, runbook):
                    disposition = runbook.observe_threshold.get(
                        "escalate_to", "ESCALATE"
                    )

                # Create analysis
                db = SessionLocal()
                analysis = Analysis(
                    incident_id=incident.id,
                    severity=runbook.default_severity,
                    disposition=disposition,
                    confidence=score,
                    summary=f"{runbook.name}: {runbook.description}",
                    next_steps=runbook.steps,
                    matched_runbook_id=runbook.id,
                    runbook_match_score=score,
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
