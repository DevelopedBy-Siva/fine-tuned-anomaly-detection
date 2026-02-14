"""
Clustering Module - Groups similar logs into incidents
Uses signature + time window for deduplication
"""

from datetime import datetime, timedelta
from app.core.parser import ParsedLog
from app.services.storage import Incident, SessionLocal
from sqlalchemy import and_

CLUSTER_WINDOW_MINUTES = 5
MAX_SAMPLES = 10


def cluster_log(
    project_id: str,
    source: str,
    environment: str,
    parsed_log: ParsedLog,
    signature: str,
) -> Incident:
    """
    Find or create an incident for this log based on signature clustering.

    Args:
        project_id: Project ID to scope incidents
        source: Log source identifier
        environment: Environment (dev/prod/etc)
        parsed_log: Parsed log entry
        signature: Unique signature for this error pattern

    Returns:
        Incident object (existing or newly created)
    """
    db = SessionLocal()

    try:
        cutoff = datetime.utcnow() - timedelta(minutes=CLUSTER_WINDOW_MINUTES)

        incident = (
            db.query(Incident)
            .filter(
                and_(
                    Incident.project_id == project_id,
                    Incident.signature == signature,
                    Incident.source == source,
                    Incident.last_seen >= cutoff,
                    Incident.status == "open",
                )
            )
            .first()
        )

        if incident:
            incident.count += 1
            incident.last_seen = datetime.utcnow()

            if len(incident.sample_lines) < MAX_SAMPLES:
                incident.sample_lines.append(parsed_log.raw)

            db.commit()
            db.refresh(incident)

            return incident

        else:
            new_incident = Incident(
                project_id=project_id,
                source=source,
                environment=environment,
                signature=signature,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                count=1,
                sample_lines=[parsed_log.raw],
                status="open",
            )

            db.add(new_incident)
            db.commit()
            db.refresh(new_incident)

            return new_incident

    finally:
        db.close()
