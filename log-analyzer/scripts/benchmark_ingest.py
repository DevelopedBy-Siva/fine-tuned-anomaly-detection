#!/usr/bin/env python3
import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _raw_log(message: str, level: str = "ERROR") -> str:
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"[{ts}] {level}: {message}"


def _load_templates():
    with open(ROOT / "evals" / "clustering_cases.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


def _lookup_project(name: str):
    from app.services.storage import Project, SessionLocal

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == name).first()
        if not project:
            raise SystemExit(f"Project not found: {name}")
        db.expunge(project)
        return project
    finally:
        db.close()


def _batcher(items, size: int):
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _cluster_batch_bulk(project_id: str, source: str, environment: str, batch: list[str]):
    from app.core.parser import ParsedLog
    from app.core.signatures import generate_signature
    from app.services.storage import Incident, SessionLocal

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=2)
        grouped = defaultdict(list)

        for log_line in batch:
            parsed = ParsedLog(log_line)
            if parsed.level not in ["ERROR", "WARN", "WARNING", "CRITICAL"]:
                continue
            grouped[generate_signature(source, parsed)].append(parsed.raw)

        if not grouped:
            return

        existing_rows = (
            db.query(Incident)
            .filter(
                Incident.project_id == project_id,
                Incident.source == source,
                Incident.status == "open",
                Incident.signature.in_(list(grouped.keys())),
                Incident.last_seen >= window_start,
            )
            .all()
        )
        existing_by_signature = {row.signature: row for row in existing_rows}

        for signature, raw_lines in grouped.items():
            row = existing_by_signature.get(signature)
            if row:
                row.count += len(raw_lines)
                row.last_seen = now
                samples = list(row.sample_lines or [])
                remaining = max(0, 10 - len(samples))
                if remaining:
                    row.sample_lines = samples + raw_lines[:remaining]
            else:
                db.add(
                    Incident(
                        project_id=project_id,
                        source=source,
                        environment=environment,
                        signature=signature,
                        first_seen=now,
                        last_seen=now,
                        count=len(raw_lines),
                        sample_lines=raw_lines[:10],
                        status="open",
                    )
                )

        db.commit()
    finally:
        db.close()


def run_benchmark(project_name: str, mode: str, total_lines: int, batch_size: int):
    from app.services.storage import Analysis, Incident, SessionLocal
    from worker.tasks import process_log_batch

    project = _lookup_project(project_name)
    templates = _load_templates()
    source = f"benchmark-{mode}-{int(time.time())}"
    messages = [_raw_log(case["message"], case.get("level", "ERROR")) for case in templates]
    environment = "benchmark"

    generated = [messages[idx % len(messages)] for idx in range(total_lines)]
    latencies = []
    t0 = time.perf_counter()

    if mode == "cluster-only":
        for batch in _batcher(generated, batch_size):
            batch_start = time.perf_counter()
            _cluster_batch_bulk(project.id, source, environment, batch)
            latencies.append(time.perf_counter() - batch_start)
    else:
        for batch in _batcher(generated, batch_size):
            batch_start = time.perf_counter()
            process_log_batch(
                {
                    "project_id": project.id,
                    "source": source,
                    "environment": environment,
                    "logs": batch,
                    "_project": project,
                }
            )
            latencies.append(time.perf_counter() - batch_start)

    elapsed = time.perf_counter() - t0
    db = SessionLocal()
    try:
        incidents = db.query(Incident).filter(Incident.source == source).all()
        incident_ids = [incident.id for incident in incidents]
        analyses = []
        if incident_ids:
            analyses = db.query(Analysis).filter(Analysis.incident_id.in_(incident_ids)).all()
        analysis_latencies = []
        incident_by_id = {incident.id: incident for incident in incidents}
        for analysis in analyses:
            incident = incident_by_id.get(analysis.incident_id)
            if incident:
                analysis_latencies.append(
                    (analysis.created_at - incident.first_seen).total_seconds()
                )
    finally:
        db.close()

    print("Benchmark")
    print(f"project: {project_name}")
    print(f"mode: {mode}")
    print(f"source: {source}")
    print(f"lines processed: {total_lines}")
    print(f"batch size: {batch_size}")
    print(f"wall time: {elapsed:.2f}s")
    print(f"effective throughput: {total_lines / elapsed:.1f} lines/s")
    print(f"batch p50 latency: {statistics.median(latencies):.3f}s")
    print(f"batch p95 latency: {sorted(latencies)[int(0.95 * (len(latencies) - 1))]:.3f}s")
    print(f"incidents created: {len(incidents)}")
    if analysis_latencies:
        print(f"analysis latency p95: {sorted(analysis_latencies)[int(0.95 * (len(analysis_latencies) - 1))]:.3f}s")
    else:
        print("analysis latency p95: n/a")


def main():
    parser = argparse.ArgumentParser(description="IncidentLens ingest benchmark")
    parser.add_argument("--project", required=True, help="Project name to benchmark against")
    parser.add_argument(
        "--mode",
        choices=["cluster-only", "full-pipeline"],
        default="cluster-only",
        help="Benchmark clustering only or the full analysis pipeline",
    )
    parser.add_argument("--lines", type=int, default=1000, help="Total log lines to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")
    args = parser.parse_args()

    run_benchmark(args.project, args.mode, args.lines, args.batch_size)


if __name__ == "__main__":
    main()
