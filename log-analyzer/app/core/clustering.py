from datetime import datetime, timedelta
from app.services.storage import Incident, SessionLocal

CLUSTER_WINDOW_MINUTES = 5
MAX_SAMPLES = 10


def cluster_log(
    project_id: str, source: str, environment: str, parsed_log, signature: str
) -> Incident:  # CHANGED
    """
    Find or create incident for this log.
    """
    db = SessionLocal()

    # Look for recent incident with same signature and project
    cutoff = datetime.utcnow() - timedelta(minutes=CLUSTER_WINDOW_MINUTES)

    incident = (
        db.query(Incident)
        .filter(
            Incident.project_id == project_id,  # ADD THIS
            Incident.signature == signature,
            Incident.source == source,
            Incident.last_seen >= cutoff,
            Incident.status == "open",
        )
        .first()
    )

    if incident:
        # Update existing incident
        incident.count += 1
        incident.last_seen = datetime.utcnow()

        # Add sample if we don't have too many
        samples = incident.sample_lines or []
        if len(samples) < MAX_SAMPLES:
            samples.append(parsed_log.raw)
            incident.sample_lines = samples
    else:
        # Create new incident
        incident = Incident(
            project_id=project_id,  # ADD THIS
            source=source,
            environment=environment,
            signature=signature,
            sample_lines=[parsed_log.raw],
        )
        db.add(incident)

    db.commit()
    db.refresh(incident)
    db.close()

    return incident
