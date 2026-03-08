import os
import json
import redis
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CLUSTER_WINDOW_MINUTES = 5
MAX_SAMPLES = 10

_redis_client = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    return _redis_client


def cluster_log_redis(
    project_id: str,
    source: str,
    environment: str,
    parsed_log,
    signature: str,
):
    from app.services.storage import Incident, SessionLocal

    """
    Find or create an incident using Redis as the clustering cache.

    Redis key: cluster:{project_id}:{signature}
    Value: incident_id (string)
    TTL: CLUSTER_WINDOW_MINUTES

    This replaces the DB-query-based clustering in clustering.py.
    Workers share the same Redis so there are no race conditions from
    multiple worker processes using separate in-memory dicts.
    """
    r = get_redis()
    cache_key = f"cluster:{project_id}:{signature}"
    ttl_seconds = CLUSTER_WINDOW_MINUTES * 60

    cached = r.get(cache_key)

    db = SessionLocal()
    try:
        if cached:
            incident_id = cached.decode()
            incident = db.query(Incident).filter(Incident.id == incident_id).first()

            if incident and incident.status == "open":
                incident.count += 1
                incident.last_seen = datetime.utcnow()
                if len(incident.sample_lines or []) < MAX_SAMPLES:
                    lines = list(incident.sample_lines or [])
                    lines.append(parsed_log.raw)
                    incident.sample_lines = lines
                db.commit()
                db.refresh(incident)

                r.expire(cache_key, ttl_seconds)
                return incident

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

        r.setex(cache_key, ttl_seconds, new_incident.id)
        return new_incident

    finally:
        db.close()


def analyze_incident(incident, project):
    from app.services.storage import Analysis, SessionLocal
    from app.core.runbook_matcher import match_runbook, should_escalate
    from app.core.decision_engine import get_decision_engine
    from app.services.notifications import get_notification_service

    """
    Run runbook matching or LLM analysis on an incident, save result to DB,
    and send notifications. Called only for new/low-count incidents.
    """
    db = SessionLocal()
    try:
        existing = (
            db.query(Analysis).filter(Analysis.incident_id == incident.id).first()
        )
        if existing:
            return

        notification_service = get_notification_service(project=project)
        decision_engine = get_decision_engine()

        runbook, score = match_runbook(incident)

        if runbook and score >= 0.5:
            disposition = runbook.disposition

            if disposition == "OBSERVE" and should_escalate(incident, runbook):
                disposition = runbook.observe_threshold.get("escalate_to", "ESCALATE")

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
        else:
            llm_analysis = decision_engine.analyze_incident(incident)

            if not llm_analysis:
                print(f"[WORKER] LLM analysis returned None for incident {incident.id}")
                return

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
        print(
            f"[WORKER] Analysis complete for incident {incident.id} — {analysis.severity}/{analysis.disposition}"
        )

        try:
            import redis as _redis
            import os

            r_pub = _redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            channel = f"incidents:{incident.project_id}"
            payload = json.dumps(
                {
                    "id": incident.id,
                    "source": incident.source,
                    "environment": incident.environment,
                    "signature": incident.signature,
                    "count": incident.count,
                    "status": incident.status,
                    "first_seen": incident.first_seen.isoformat(),
                    "last_seen": incident.last_seen.isoformat(),
                    "severity": analysis.severity,
                    "disposition": analysis.disposition,
                    "summary": analysis.summary,
                }
            )
            r_pub.publish(channel, payload)
            print(f"[WORKER] Published to channel '{channel}'")
        except Exception as pub_err:
            print(f"[WORKER] Pub/sub publish failed (non-critical): {pub_err}")

    except Exception as e:
        print(f"[WORKER] analyze_incident failed for {incident.id}: {e}")
        db.rollback()
        raise

    finally:
        db.close()


def process_log_batch(payload: dict):
    from app.core.parser import ParsedLog
    from app.core.signatures import generate_signature
    from app.services.storage import SessionLocal, Project

    """
    RQ job entry point.

    payload = {
        "project_id": str,
        "project_name": str,          # for logging
        "source": str,
        "environment": str,
        "logs": [str, ...],

        # Project notification config passed directly so worker
        # doesn't need to re-query DB for every batch
        "log_source_url": str,
        "user_email": str,
        "discord_webhook_escalate": str,
        "discord_webhook_dev": str,
    }
    """
    api_key = payload.get("api_key", "")
    source = payload["source"]
    environment = payload["environment"]
    logs = payload["logs"]

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.api_key == api_key).first()
        if not project:
            print(f"[WORKER] No project found for api_key — skipping batch")
            return
        project_id = project.id
        print(f"[WORKER] Processing {len(logs)} logs for project '{project.name}'")
    finally:
        db.close()

    created = 0
    updated = 0

    for log_line in logs:
        try:
            parsed = ParsedLog(log_line)

            if parsed.level not in ["ERROR", "WARN", "WARNING", "CRITICAL"]:
                continue

            sig = generate_signature(source, parsed)

            incident = cluster_log_redis(
                project_id=project_id,
                source=source,
                environment=environment,
                parsed_log=parsed,
                signature=sig,
            )

            if incident.count <= 3:
                analyze_incident(incident, project)

            if incident.count == 1:
                created += 1
            else:
                updated += 1

        except Exception as e:
            print(f"[WORKER] Failed to process log line: {e} | line: {log_line[:100]}")
            continue

    print(f"[WORKER] Batch done — created: {created}, updated: {updated}")
    return {"incidents_created": created, "incidents_updated": updated}
