#!/usr/bin/env python3
import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _default_path(name: str) -> Path:
    return ROOT / "evals" / name


def _load_json(path: str | Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _pctl(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _raw_log(message: str, level: str) -> str:
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"[{ts}] {level}: {message}"


def run_clustering_eval(dataset_path: Path):
    from app.core.parser import ParsedLog
    from app.core.signatures import generate_signature

    cases = _load_json(dataset_path)
    predicted = []
    expected = []

    for case in cases:
        raw = _raw_log(case["message"], case.get("level", "ERROR"))
        signature = generate_signature(case["source"], ParsedLog(raw))
        predicted.append(signature)
        expected.append(case["label"])

    tp = fp = fn = 0
    for i in range(len(cases)):
        for j in range(i + 1, len(cases)):
            same_expected = expected[i] == expected[j]
            same_predicted = predicted[i] == predicted[j]
            if same_expected and same_predicted:
                tp += 1
            elif not same_expected and same_predicted:
                fp += 1
            elif same_expected and not same_predicted:
                fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    cluster_members = defaultdict(list)
    for predicted_label, expected_label in zip(predicted, expected):
        cluster_members[predicted_label].append(expected_label)
    purity_hits = sum(Counter(labels).most_common(1)[0][1] for labels in cluster_members.values())
    purity = purity_hits / len(cases) if cases else 0.0

    print("Clustering Eval")
    print(f"dataset: {dataset_path}")
    print(f"cases: {len(cases)}")
    print(f"expected clusters: {len(set(expected))}")
    print(f"predicted clusters: {len(set(predicted))}")
    print(f"pairwise precision: {_pct(precision)}")
    print(f"pairwise recall: {_pct(recall)}")
    print(f"pairwise f1: {_pct(f1)}")
    print(f"dominant-label purity: {_pct(purity)}")


def _project_filter(db, project_name: str | None):
    from app.services.storage import Project

    if not project_name:
        return None
    project = db.query(Project).filter(Project.name == project_name).first()
    if not project:
        raise SystemExit(f"Project not found: {project_name}")
    return project


def run_live_metrics(project_name: str | None):
    from app.services.storage import (
        ActionLog,
        Analysis,
        Incident,
        InvestigationRun,
        SessionLocal,
    )

    db = SessionLocal()
    try:
        project = _project_filter(db, project_name)

        incident_query = db.query(Incident)
        analysis_query = db.query(Analysis)
        action_query = db.query(ActionLog)
        run_query = db.query(InvestigationRun)

        if project:
            incident_query = incident_query.filter(Incident.project_id == project.id)
            incident_ids = [row.id for row in incident_query.all()]
            analysis_query = analysis_query.filter(Analysis.incident_id.in_(incident_ids))
            action_query = action_query.filter(ActionLog.project_id == project.id)
            run_query = run_query.filter(InvestigationRun.project_id == project.id)

        incidents = incident_query.all() if not project else []
        if project:
            incidents = db.query(Incident).filter(Incident.project_id == project.id).all()
        analyses = analysis_query.order_by(Analysis.created_at.desc()).all()
        actions = action_query.order_by(ActionLog.actioned_at.desc()).all()
        runs = run_query.order_by(InvestigationRun.started_at.desc()).all()

        latest_analysis_by_incident = {}
        for analysis in analyses:
            latest_analysis_by_incident.setdefault(analysis.incident_id, analysis)

        latency_seconds = []
        for incident in incidents:
            analysis = latest_analysis_by_incident.get(incident.id)
            if analysis:
                latency_seconds.append(
                    (analysis.created_at - incident.first_seen).total_seconds()
                )

        runtime_seconds = [
            (run.finished_at - run.started_at).total_seconds()
            for run in runs
            if run.started_at and run.finished_at
        ]

        verified = [log for log in actions if log.outcome != "pending"]
        auto_suppressed = [
            log for log in verified if "auto_suppress" in (log.actions_taken or [])
        ]
        incidents_by_id = {incident.id: incident for incident in incidents}
        runbook_hits = [
            analysis for analysis in latest_analysis_by_incident.values()
            if analysis.analysis_source == "runbook"
        ]

        print("Live Metrics")
        if project:
            print(f"project: {project.name}")
        print(f"incidents: {len(incidents)}")
        print(f"analyzed incidents: {len(latest_analysis_by_incident)}")
        print(
            "runbook hit rate: "
            + (
                _pct(len(runbook_hits) / len(latest_analysis_by_incident))
                if latest_analysis_by_incident
                else "n/a"
            )
        )
        if latency_seconds:
            print(
                f"investigation latency p50: {_pctl(latency_seconds, 0.5):.2f}s"
            )
            print(
                f"investigation latency p95: {_pctl(latency_seconds, 0.95):.2f}s"
            )
        else:
            print("investigation latency p50: n/a")
            print("investigation latency p95: n/a")
        if runtime_seconds:
            print(f"agent runtime p95: {_pctl(runtime_seconds, 0.95):.2f}s")
        else:
            print("agent runtime p95: n/a")
        if auto_suppressed:
            suppression_resolved = 0
            suppression_false_positive = 0
            for log in auto_suppressed:
                incident = incidents_by_id.get(log.incident_id)
                if incident is None:
                    continue
                reopened = (
                    db.query(Incident)
                    .filter(
                        Incident.project_id == log.project_id,
                        Incident.id != incident.id,
                        Incident.source == incident.source,
                        Incident.signature == incident.signature,
                        Incident.first_seen > log.actioned_at,
                    )
                    .first()
                )
                if reopened:
                    suppression_false_positive += 1
                else:
                    suppression_resolved += 1
            print(
                "auto-suppression success rate: "
                + _pct(suppression_resolved / len(auto_suppressed))
            )
            print(
                "auto-suppression false positive rate: "
                + _pct(suppression_false_positive / len(auto_suppressed))
            )
        else:
            print("auto-suppression success rate: n/a")
            print("auto-suppression false positive rate: n/a")
        if verified:
            resolved = sum(1 for log in verified if log.outcome == "resolved")
            print(f"verifier resolution rate: {_pct(resolved / len(verified))}")
        else:
            print("verifier resolution rate: n/a")
        print(f"pending verifier checks: {sum(1 for log in actions if log.outcome == 'pending')}")
    finally:
        db.close()


def _lookup_project(project_name: str | None):
    if not project_name:
        return None
    from app.services.storage import Project, SessionLocal

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            raise SystemExit(f"Project not found: {project_name}")
        db.expunge(project)
        return project
    finally:
        db.close()


def run_analysis_eval(dataset_path: Path, project_name: str | None):
    from app.core.decision_engine import get_decision_engine
    from app.core.parser import ParsedLog
    from app.core.signatures import generate_signature

    project = _lookup_project(project_name)
    cases = _load_json(dataset_path)
    engine = get_decision_engine()
    matches = 0
    scored = 0
    failures = []

    for case in cases:
        raw_lines = [_raw_log(message, "ERROR") for message in case["logs"]]
        parsed = ParsedLog(raw_lines[0])
        signature = generate_signature(case["source"], parsed)
        incident = SimpleNamespace(
            id=case["id"],
            source=case["source"],
            environment=case.get("environment", "prod"),
            count=len(raw_lines),
            first_seen=datetime.now(timezone.utc) - timedelta(minutes=1),
            last_seen=datetime.now(timezone.utc),
            signature=signature,
            sample_lines=raw_lines,
        )

        analysis = engine.analyze_incident(incident, project=project, evidence=None)
        if analysis is None:
            print("Analysis Eval")
            print("status: skipped")
            print("reason: no Groq key configured or LLM unavailable")
            return

        scored += 1
        predicted = (analysis.suspected_root_cause or "").lower()
        keywords = [keyword.lower() for keyword in case.get("acceptable_keywords", [])]
        is_match = bool(predicted) and any(keyword in predicted for keyword in keywords)
        if is_match:
            matches += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "expected": case["expected_root_cause"],
                    "predicted": analysis.suspected_root_cause,
                }
            )

    print("Analysis Eval")
    print(f"dataset: {dataset_path}")
    print(f"cases scored: {scored}")
    print(f"root-cause accuracy: {_pct(matches / scored) if scored else 'n/a'}")
    if failures:
        print("sample mismatches:")
        for failure in failures[:5]:
            print(
                f"- {failure['id']}: expected '{failure['expected']}', predicted '{failure['predicted']}'"
            )


def run_suppression_eval(dataset_path: Path, project_name: str):
    from app.services.storage import ActionLog, Incident, SessionLocal
    from worker import verifier
    from worker.tasks import process_log_batch

    project = _lookup_project(project_name)
    cases = _load_json(dataset_path)
    prefix = f"suppression-eval-{int(datetime.now(timezone.utc).timestamp())}"

    for idx, case in enumerate(cases, start=1):
        source = f"{prefix}-{case['source']}-{idx}"
        process_log_batch(
            {
                "project_id": project.id,
                "source": source,
                "environment": "eval",
                "logs": [_raw_log(message, "ERROR") for message in case["logs"]],
                "_project": project,
            }
        )

        db = SessionLocal()
        try:
            primary_incident = (
                db.query(Incident)
                .filter(Incident.project_id == project.id, Incident.source == source)
                .order_by(Incident.first_seen.asc())
                .first()
            )
            if not primary_incident:
                continue

            action = (
                db.query(ActionLog)
                .filter(ActionLog.incident_id == primary_incident.id)
                .order_by(ActionLog.actioned_at.desc())
                .first()
            )
            if action:
                action.actioned_at = datetime.utcnow() - timedelta(minutes=16)
                db.commit()
        finally:
            db.close()

        if case.get("replay_after_suppress"):
            replay_logs = [_raw_log(message, "ERROR") for message in case["logs"] for _ in range(3)]
            process_log_batch(
                {
                    "project_id": project.id,
                    "source": source,
                    "environment": "eval",
                    "logs": replay_logs,
                    "_project": project,
                }
            )

    verifier._sweep()

    db = SessionLocal()
    try:
        incidents = (
            db.query(Incident)
            .filter(Incident.project_id == project.id, Incident.source.like(f"{prefix}%"))
            .all()
        )
        grouped = defaultdict(list)
        for incident in incidents:
            grouped[incident.source].append(incident)

        expected_suppress = 0
        actual_suppress = 0
        correct_suppress = 0
        false_positive = 0
        non_suppress_total = 0
        non_suppress_correct = 0

        for idx, case in enumerate(cases, start=1):
            source = f"{prefix}-{case['source']}-{idx}"
            case_incidents = sorted(grouped.get(source, []), key=lambda row: row.first_seen)
            if not case_incidents:
                continue

            primary_incident = case_incidents[0]
            action = (
                db.query(ActionLog)
                .filter(ActionLog.incident_id == primary_incident.id)
                .order_by(ActionLog.actioned_at.desc())
                .first()
            )
            suppressed = bool(action and "auto_suppress" in (action.actions_taken or []))
            replayed = len(case_incidents) > 1

            if case["expected_suppress"]:
                expected_suppress += 1
                if suppressed:
                    actual_suppress += 1
                    if replayed:
                        false_positive += 1
                    else:
                        correct_suppress += 1
            else:
                non_suppress_total += 1
                if suppressed:
                    actual_suppress += 1
                    false_positive += 1
                else:
                    non_suppress_correct += 1

        print("Suppression Eval")
        print(f"dataset: {dataset_path}")
        print(f"cases scored: {len(cases)}")
        print(f"expected suppressions: {expected_suppress}")
        print(f"actual suppressions: {actual_suppress}")
        print(
            "suppression recall: "
            + (_pct(correct_suppress / expected_suppress) if expected_suppress else "n/a")
        )
        print(
            "suppression precision: "
            + (_pct(correct_suppress / actual_suppress) if actual_suppress else "n/a")
        )
        print(
            "suppression false positive rate: "
            + (_pct(false_positive / actual_suppress) if actual_suppress else "n/a")
        )
        print(
            "non-suppression correctness: "
            + (_pct(non_suppress_correct / non_suppress_total) if non_suppress_total else "n/a")
        )
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="IncidentLens metrics and eval runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    clustering = subparsers.add_parser("clustering", help="Run clustering eval")
    clustering.add_argument(
        "--dataset",
        default=str(_default_path("clustering_cases.json")),
        help="Path to clustering eval dataset",
    )

    live = subparsers.add_parser("live", help="Report live DB-backed metrics")
    live.add_argument("--project", default=None, help="Project name to filter on")

    analysis_eval = subparsers.add_parser(
        "analysis-eval", help="Run LLM root-cause eval on labeled incidents"
    )
    analysis_eval.add_argument(
        "--dataset",
        default=str(_default_path("analysis_eval_cases.json")),
        help="Path to analysis eval dataset",
    )
    analysis_eval.add_argument(
        "--project",
        default=None,
        help="Project name to load Groq credentials from",
    )

    suppression_eval = subparsers.add_parser(
        "suppression-eval", help="Run repeatable suppression/noise-policy eval"
    )
    suppression_eval.add_argument(
        "--dataset",
        default=str(_default_path("suppression_eval_cases.json")),
        help="Path to suppression eval dataset",
    )
    suppression_eval.add_argument(
        "--project",
        required=True,
        help="Project name to run suppression eval against",
    )

    args = parser.parse_args()
    if args.command == "clustering":
        run_clustering_eval(Path(args.dataset))
    elif args.command == "live":
        run_live_metrics(args.project)
    elif args.command == "analysis-eval":
        run_analysis_eval(Path(args.dataset), args.project)
    elif args.command == "suppression-eval":
        run_suppression_eval(Path(args.dataset), args.project)


if __name__ == "__main__":
    main()
