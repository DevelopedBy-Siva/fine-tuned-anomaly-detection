from datetime import datetime, timedelta
from app.services.storage import Incident, SessionLocal

CLUSTER_WINDOW_MINUTES = 5
MAX_SAMPLES = 10


def cluster_log(
    project_id: str, source: str, environment: str, parsed_log, signature: str
) -> Incident:
    """
    Find or create incident for this log.
    """
    db = SessionLocal()

    cutoff = datetime.utcnow() - timedelta(minutes=CLUSTER_WINDOW_MINUTES)

    incident = (
        db.query(Incident)
        .filter(
            Incident.project_id == project_id,
            Incident.signature == signature,
            Incident.source == source,
            Incident.last_seen >= cutoff,
            Incident.status == "open",
        )
        .first()
    )

    if incident:
        incident.count += 1
        incident.last_seen = datetime.utcnow()

        samples = incident.sample_lines or []
        if len(samples) < MAX_SAMPLES:
            samples.append(parsed_log.raw)
            incident.sample_lines = samples
    else:
        incident = Incident(
            project_id=project_id,
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
