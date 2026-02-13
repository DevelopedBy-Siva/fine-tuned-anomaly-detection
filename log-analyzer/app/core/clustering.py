from datetime import datetime, timedelta
from app.services.storage import Incident, SessionLocal

CLUSTER_WINDOW_MINUTES = 5

MAX_SAMPLES = 10


def cluster_log(source: str, environment: str, parsed_log, signature: str) -> Incident:
    """
    Find or create incident for this log.

    Logic:
    1. Look for recent incident with same signature
    2. If found: increment count, update timestamp
    3. If not found: create new incident
    """
    db = SessionLocal()

    cutoff = datetime.utcnow() - timedelta(minutes=CLUSTER_WINDOW_MINUTES)

    incident = (
        db.query(Incident)
        .filter(
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
