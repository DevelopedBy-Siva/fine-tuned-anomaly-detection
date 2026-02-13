from fastapi import APIRouter
from app.models.schemas import IngestRequest, IngestResponse
from app.core.parser import ParsedLog
from app.core.signatures import generate_signature
from app.core.clustering import cluster_log

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest_logs(request: IngestRequest):
    """
    Receive logs, parse them, cluster into incidents.

    Flow:
    1. Parse each log line
    2. Filter to only ERROR/WARN levels
    3. Generate signature (dedupe key)
    4. Cluster into incident (find or create)
    """
    created = set()
    updated = set()
    processed = 0

    for log_line in request.logs:
        parsed = ParsedLog(log_line)
        processed += 1

        if parsed.level not in ["ERROR", "WARN", "WARNING", "CRITICAL"]:
            continue

        sig = generate_signature(request.source, parsed)

        incident = cluster_log(request.source, request.environment, parsed, sig)

        if incident.count == 1:
            created.add(incident.id)
        else:
            updated.add(incident.id)

    return IngestResponse(
        incidents_created=len(created),
        incidents_updated=len(updated),
        total_logs_processed=processed,
    )
