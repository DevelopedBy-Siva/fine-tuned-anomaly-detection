from datetime import datetime, timedelta

CLUSTER_WINDOW_MINUTES = 2
MAX_SAMPLES = 10
ROOT_CAUSE_LOOKBACK_MINUTES = 10


def cluster_log_db(project_id, source, environment, parsed_log, signature):
    from app.services.storage import Incident, SessionLocal

    db = SessionLocal()
    try:
        window_start = datetime.utcnow() - timedelta(minutes=CLUSTER_WINDOW_MINUTES)
        incident = (
            db.query(Incident)
            .filter(
                Incident.project_id == project_id,
                Incident.signature == signature,
                Incident.status == "open",
                Incident.last_seen >= window_start,
            )
            .order_by(Incident.last_seen.desc())
            .first()
        )

        if incident:
            incident.count += 1
            incident.last_seen = datetime.utcnow()
            if len(incident.sample_lines or []) < MAX_SAMPLES:
                lines = list(incident.sample_lines or [])
                lines.append(parsed_log.raw)
                incident.sample_lines = lines
            db.commit()
            db.refresh(incident)
            return incident, False

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
        return new_incident, True
    finally:
        db.close()


def _fetch_recent_root_cause_candidates(project_id, new_incident_id):
    from app.services.storage import Incident, SessionLocal

    cutoff = datetime.utcnow() - timedelta(minutes=ROOT_CAUSE_LOOKBACK_MINUTES)
    db = SessionLocal()
    try:
        candidates = (
            db.query(Incident)
            .filter(
                Incident.project_id == project_id,
                Incident.id != new_incident_id,
                Incident.status == "open",
                Incident.first_seen >= cutoff,
                Incident.root_cause_incident_id == None,
            )
            .order_by(Incident.first_seen.asc())
            .all()
        )
        for c in candidates:
            db.expunge(c)
        return candidates
    finally:
        db.close()


def _apply_root_cause_chain(new_incident_id, cause_incident_id, explanation):
    from app.services.storage import Incident, SessionLocal

    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == new_incident_id).first()
        if incident:
            incident.root_cause_incident_id = cause_incident_id
            incident.cause_explanation = explanation
            db.commit()
            print(f"[CHAIN] {new_incident_id} linked → {cause_incident_id}")
    except Exception as e:
        print(f"[CHAIN] Failed to persist root cause link: {e}")
        db.rollback()
    finally:
        db.close()


def analyze_incident(incident, project, force=False):
    """
    project is the full Project ORM object — used for per-project
    Groq key, Langfuse keys, and notification webhooks.
    """
    from app.services.storage import Analysis, SessionLocal
    from app.core.runbook_matcher import match_runbook, should_escalate
    from app.core.decision_engine import get_decision_engine
    from app.services.notifications import get_notification_service

    db = SessionLocal()
    try:
        existing = (
            db.query(Analysis).filter(Analysis.incident_id == incident.id).first()
        )
        if existing and not force:
            return None

        notification_service = get_notification_service(project=project)
        runbook, score = match_runbook(incident)

        if runbook and score >= 0.5:
            disposition = runbook.disposition
            if disposition == "OBSERVE" and should_escalate(incident, runbook):
                disposition = runbook.observe_threshold.get("escalate_to", "ESCALATE")

            new_severity = runbook.default_severity
            new_disposition = disposition
            new_confidence = score
            new_summary = f"{runbook.name}: {runbook.description}"
            new_next_steps = runbook.steps
            new_ticket_title = runbook.name
            new_ticket_body = "\n".join(runbook.steps)
            new_source = "runbook"
            matched_runbook_id = runbook.id
            runbook_match_score = score
        else:
            decision_engine = get_decision_engine()
            llm_analysis = decision_engine.analyze_incident(incident, project=project)
            if not llm_analysis:
                print(f"[WORKER] LLM returned None for incident {incident.id}")
                return None
            new_severity = llm_analysis.severity
            new_disposition = llm_analysis.disposition
            new_confidence = llm_analysis.confidence
            new_summary = llm_analysis.summary
            new_next_steps = llm_analysis.next_steps
            new_ticket_title = llm_analysis.ticket_title
            new_ticket_body = llm_analysis.ticket_body
            new_source = "llm"
            matched_runbook_id = None
            runbook_match_score = None

        if existing and force:
            existing.severity = new_severity
            existing.disposition = new_disposition
            existing.confidence = new_confidence
            existing.summary = new_summary
            existing.next_steps = new_next_steps
            existing.ticket_title = new_ticket_title
            existing.ticket_body = new_ticket_body
            existing.analysis_source = new_source
            existing.created_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            analysis = existing
        else:
            analysis = Analysis(
                incident_id=incident.id,
                severity=new_severity,
                disposition=new_disposition,
                confidence=new_confidence,
                summary=new_summary,
                next_steps=new_next_steps,
                ticket_title=new_ticket_title,
                ticket_body=new_ticket_body,
                analysis_source=new_source,
                matched_runbook_id=matched_runbook_id,
                runbook_match_score=runbook_match_score,
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)

        notification_service.route_notification(incident, analysis)
        print(
            f"[WORKER] Analysis {'updated' if force else 'created'} for "
            f"{incident.id} — {analysis.severity}/{analysis.disposition}"
        )
        return analysis

    except Exception as e:
        print(f"[WORKER] analyze_incident failed for {incident.id}: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def run_root_cause_chaining(new_incident, project_id, project):
    from app.core.decision_engine import get_decision_engine

    try:
        candidates = _fetch_recent_root_cause_candidates(project_id, new_incident.id)
        if not candidates:
            return

        print(
            f"[CHAIN] Checking {new_incident.id} against {len(candidates)} candidate(s)"
        )
        decision_engine = get_decision_engine()
        result = decision_engine.chain_root_cause(
            new_incident, candidates, project=project
        )

        if result and result.has_cause and result.cause_incident_id:
            _apply_root_cause_chain(
                new_incident_id=new_incident.id,
                cause_incident_id=result.cause_incident_id,
                explanation=result.cause_explanation or "",
            )
        else:
            print(f"[CHAIN] No causal link found for {new_incident.id}")

    except Exception as e:
        print(f"[CHAIN] run_root_cause_chaining failed for {new_incident.id}: {e}")


def process_log_batch(payload: dict):
    """
    Entry point called by loki_watcher.

    payload keys:
      project_id  — str UUID (direct, no api_key lookup needed)
      source      — str
      environment — str
      logs        — list[str]
      _project    — Project ORM object (passed through for creds)
    """
    from app.core.parser import ParsedLog
    from app.core.signatures import generate_signature
    from app.services.storage import SessionLocal, Project

    project_id = payload.get("project_id")
    source = payload["source"]
    environment = payload["environment"]
    logs = payload["logs"]
    project = payload.get("_project")

    if project is None:
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                db.expunge(project)
            else:
                print(f"[WORKER] Project {project_id} not found — skipping batch")
                return
        finally:
            db.close()

    print(f"[WORKER] Processing {len(logs)} logs for project '{project.name}'")

    created = 0
    updated = 0
    failed = 0

    for log_line in logs:
        try:
            parsed = ParsedLog(log_line)
            if parsed.level not in ["ERROR", "WARN", "WARNING", "CRITICAL"]:
                continue

            sig = generate_signature(source, parsed)
            incident, is_new = cluster_log_db(
                project_id=project_id,
                source=source,
                environment=environment,
                parsed_log=parsed,
                signature=sig,
            )

            if is_new:
                analyze_incident(incident, project=project, force=False)
                run_root_cause_chaining(incident, project_id, project=project)
                created += 1
            else:
                if incident.count in {5, 10, 20}:
                    analyze_incident(incident, project=project, force=True)
                updated += 1

        except Exception as e:
            print(f"[WORKER] Failed to process log line: {e} | line: {log_line[:100]}")
            failed += 1
            continue

    print(
        f"[WORKER] Batch done — created: {created}, updated: {updated}, failed: {failed}"
    )

    if failed > 0 and created == 0 and updated == 0:
        raise RuntimeError(f"Batch entirely failed — {failed} lines errored")

    return {
        "incidents_created": created,
        "incidents_updated": updated,
        "failed": failed,
    }
