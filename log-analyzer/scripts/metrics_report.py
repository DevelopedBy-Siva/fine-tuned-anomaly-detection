#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")
except Exception:
    pass


DISPOSITION_RANK = {
    "NO_ACTION": 0,
    "OBSERVE": 1,
    "NEEDS_DEV": 2,
    "NEEDS_ONCALL": 3,
    "ESCALATE": 4,
}

RUNBOOK_FAST_PATH_THRESHOLD = 0.5
AUTO_SUPPRESS_MIN_CONFIDENCE = 0.80
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_incident_logs",
            "description": "Return the raw log samples for the incident.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_runbook_candidates",
            "description": "Return the best matching deterministic runbooks and scores.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_safety_rubric",
            "description": "Return the project safety rules for automated actions.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


@dataclass
class EvalResult:
    case_id: str
    source: str
    analysis_source: str
    severity: str
    disposition: str
    effective_disposition: str
    confidence: float
    matched_runbook_id: Optional[str]
    suspected_root_cause: Optional[str]
    summary: str
    ticket_title: str
    ticket_body: str
    policy_tags: list[str]
    tool_calls: list[str]
    skipped_reason: Optional[str] = None

    @property
    def would_auto_suppress(self) -> bool:
        return (
            self.effective_disposition == "NO_ACTION"
            and self.confidence >= AUTO_SUPPRESS_MIN_CONFIDENCE
        )


def _default_dataset() -> Path:
    return ROOT / "evals" / "incident_triage_cases.json"


def _load_json(path: str | Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{(numerator / denominator) * 100:.1f}%"


def _rank(disposition: str) -> int:
    return DISPOSITION_RANK.get((disposition or "").upper(), 0)


def _raw_log(log_entry) -> str:
    if isinstance(log_entry, str):
        level = "ERROR"
        message = log_entry
    else:
        level = log_entry.get("level", "ERROR")
        message = log_entry["message"]
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"[{ts}] {level}: {message}"


def _make_incident(case: dict):
    from app.core.parser import ParsedLog
    from app.core.signatures import generate_signature

    raw_lines = [_raw_log(entry) for entry in case["logs"]]
    parsed = ParsedLog(raw_lines[0])
    signature = generate_signature(case["source"], parsed)
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=case["id"],
        source=case["source"],
        environment=case.get("environment", "prod"),
        count=int(case.get("count") or len(raw_lines)),
        first_seen=now - timedelta(minutes=1),
        last_seen=now,
        signature=signature,
        sample_lines=raw_lines,
        status="open",
        last_actioned_at=None,
        root_cause_incident_id=None,
        cause_explanation=None,
    )


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


def _runbook_analysis(incident, runbook, score: float):
    from app.core.runbook_matcher import should_escalate

    disposition = runbook.disposition
    if disposition == "OBSERVE" and should_escalate(incident, runbook):
        disposition = runbook.observe_threshold.get("escalate_to", "ESCALATE")

    return SimpleNamespace(
        severity=runbook.default_severity,
        disposition=disposition,
        confidence=score,
        summary=f"{runbook.name}: {runbook.description}",
        suspected_root_cause=None,
        next_steps=runbook.steps,
        ticket_title=runbook.name,
        ticket_body="\n".join(runbook.steps),
        analysis_source="runbook",
        matched_runbook_id=runbook.id,
        runbook_match_score=score,
        tool_calls=[],
    )


def _llm_analysis(incident, project):
    api_key = _groq_api_key(project)
    if not api_key:
        return None, "GROQ_API_KEY is not visible to this shell or .env"

    try:
        from groq import Groq
    except ImportError as exc:
        return None, f"groq package unavailable: {_short_error(exc)}"

    client = Groq(api_key=api_key)
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    messages = _agent_messages(incident)
    tool_calls = []
    final_text = ""

    try:
        for iteration in range(3):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=AGENT_TOOLS if iteration < 2 else None,
                tool_choice="auto" if iteration < 2 else None,
                temperature=0.1,
                max_tokens=1200,
            )
            message = response.choices[0].message

            if not getattr(message, "tool_calls", None):
                final_text = message.content or ""
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in message.tool_calls
                    ],
                }
            )

            for call in message.tool_calls:
                args = _json_object(call.function.arguments or "{}")
                tool_calls.append(call.function.name)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": _agent_tool_result(
                            incident,
                            call.function.name,
                            args,
                        ),
                    }
                )

        if not final_text:
            response = client.chat.completions.create(
                model=model,
                messages=messages
                + [
                    {
                        "role": "user",
                        "content": "Return only the final JSON analysis now.",
                    }
                ],
                temperature=0.1,
                max_tokens=1200,
            )
            final_text = response.choices[0].message.content or ""
    except Exception as exc:
        return None, f"Groq request failed: {_short_error(exc)}"

    data = _json_object_from_text(final_text)
    if not data:
        return None, "Groq response did not contain parseable JSON"

    severity = str(data.get("severity", "medium")).lower().strip()
    disposition = str(data.get("disposition", "OBSERVE")).upper().strip()
    confidence = _clamp_float(data.get("confidence", 0.6))
    severity, disposition = _normalize_agent_triage(incident, severity, disposition)
    confidence = max(confidence, _evidence_confidence_floor(incident))
    next_steps = data.get("next_steps") or []
    if not isinstance(next_steps, list):
        next_steps = [str(next_steps)]

    return (
        SimpleNamespace(
            severity=severity,
            disposition=disposition,
            confidence=confidence,
            summary=str(data.get("summary") or ""),
            suspected_root_cause=data.get("suspected_root_cause"),
            next_steps=next_steps,
            ticket_title=str(data.get("ticket_title") or incident.source)[:100],
            ticket_body=str(data.get("ticket_body") or ""),
            analysis_source="llm-agent",
            matched_runbook_id=None,
            runbook_match_score=None,
            tool_calls=tool_calls,
        ),
        None,
    )


def _groq_api_key(project) -> str:
    project_key = (getattr(project, "groq_api_key", None) or "").strip()
    if project_key:
        return project_key

    for name in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"):
        key = os.getenv(name, "").strip()
        if key:
            return key
    return ""


def _agent_messages(incident) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are an SRE incident triage agent. Use available tools before "
                "your final answer. Return only JSON with keys: severity, disposition, "
                "confidence, suspected_root_cause, summary, next_steps, ticket_title, "
                "ticket_body. Severity must be low, medium, high, or critical. "
                "Disposition must be NO_ACTION, OBSERVE, NEEDS_DEV, NEEDS_ONCALL, "
                "or ESCALATE. Use ESCALATE only for immediate paging situations "
                "such as OOM, disk full, service down, data loss, or active severe "
                "security incidents. A bad production deploy with failed health checks "
                "is high/NEEDS_ONCALL. An expired TLS certificate breaking partner "
                "webhooks is high/NEEDS_DEV unless there is evidence of service-wide "
                "outage or data loss. Confidence must be a number from 0.0 to 1.0."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Incident {incident.id}\n"
                f"Source: {incident.source}\n"
                f"Environment: {incident.environment}\n"
                f"Count: {incident.count}\n"
                f"First seen: {incident.first_seen}\n"
                f"Last seen: {incident.last_seen}\n"
                "Investigate the incident, decide severity/disposition, and explain "
                "the most likely root cause."
            ),
        },
    ]


def _agent_tool_result(incident, tool_name: str, args: dict) -> str:
    if tool_name == "get_incident_logs":
        return json.dumps(
            {
                "incident_id": incident.id,
                "logs": incident.sample_lines,
            }
        )

    if tool_name == "get_runbook_candidates":
        from app.core.runbook_matcher import score_runbook
        from app.core.runbook_loader import get_runbooks

        text = " ".join(incident.sample_lines or [])
        candidates = []
        for runbook in get_runbooks():
            score = score_runbook(runbook, text)
            if score > 0:
                candidates.append(
                    {
                        "id": runbook.id,
                        "name": runbook.name,
                        "score": round(score, 2),
                        "severity": runbook.default_severity,
                        "disposition": runbook.disposition,
                    }
                )
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return json.dumps({"candidates": candidates[:5]})

    if tool_name == "get_safety_rubric":
        return json.dumps(
            {
                "automation_boundary": "No infra mutation, no database mutation, no service restarts.",
                "allowed_actions": ["notify", "auto_enrich", "auto_suppress"],
                "suppression_rule": "Only NO_ACTION incidents with high confidence can be suppressed.",
                "critical_rule": "Critical incidents must not be downgraded just because count is low.",
            }
        )

    return json.dumps({"error": f"unknown tool: {tool_name}", "args": args})


def _json_object(text: str) -> dict:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _json_object_from_text(text: str) -> dict:
    clean = re.sub(r"```(?:json)?", "", text or "").strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        return {}
    return _json_object(match.group(0))


def _clamp_float(value) -> float:
    if isinstance(value, str):
        text = value.strip().lower()
        word_values = {
            "very high": 0.9,
            "high": 0.8,
            "medium": 0.6,
            "moderate": 0.6,
            "low": 0.4,
            "very low": 0.2,
        }
        if text in word_values:
            return word_values[text]

        match = re.search(r"\d+(?:\.\d+)?", text)
        if match:
            value = match.group(0)

    try:
        parsed = float(value)
    except Exception:
        parsed = 0.6
    if parsed > 1.0 and parsed <= 100.0:
        parsed = parsed / 100.0
    return max(0.0, min(1.0, parsed))


def _short_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    return text[:180] if text else exc.__class__.__name__


def _normalize_agent_triage(incident, severity: str, disposition: str) -> tuple[str, str]:
    text = " ".join(incident.sample_lines or []).lower()

    critical_patterns = [
        "outofmemoryerror",
        "oomkilled",
        "heap space exhausted",
        "diskspacecritical",
        "write operations may fail",
        "stackoverflowerror",
        "segmentation fault",
        "data loss",
        "service down",
    ]
    if any(pattern in text for pattern in critical_patterns):
        return "critical", "ESCALATE"

    if any(
        pattern in text
        for pattern in ["certificate expired", "x509", "tlshandshakeerror"]
    ):
        return "high", "NEEDS_DEV"

    if any(
        pattern in text
        for pattern in [
            "deployconfigerror",
            "rollbackrequired",
            "failing health checks",
            "availabilitydrop",
            "successful checkout rate fell below",
        ]
    ):
        return "high", "NEEDS_ONCALL"

    if severity == "critical":
        severity = "high"
        if disposition == "ESCALATE":
            disposition = "NEEDS_ONCALL"

    if disposition not in DISPOSITION_RANK:
        disposition = "OBSERVE"

    return severity, disposition


def _evidence_confidence_floor(incident) -> float:
    text = " ".join(incident.sample_lines or []).lower()
    strong_patterns = [
        "certificate expired",
        "x509",
        "tlshandshakeerror",
        "deployconfigerror",
        "rollbackrequired",
        "failing health checks",
        "availabilitydrop",
        "outofmemoryerror",
        "oomkilled",
        "diskspacecritical",
    ]
    if any(pattern in text for pattern in strong_patterns):
        return 0.75
    return 0.0


def _analyze_case(case: dict, project) -> EvalResult:
    from app.core.policy import evaluate as evaluate_policy
    from app.core.runbook_matcher import match_runbook

    incident = _make_incident(case)
    runbook, score = match_runbook(incident)

    if runbook and score >= RUNBOOK_FAST_PATH_THRESHOLD:
        analysis = _runbook_analysis(incident, runbook, score)
    else:
        analysis, skipped_reason = _llm_analysis(incident, project)
        if analysis is None:
            return EvalResult(
                case_id=case["id"],
                source=case["source"],
                analysis_source="llm",
                severity="",
                disposition="",
                effective_disposition="",
                confidence=0.0,
                matched_runbook_id=None,
                suspected_root_cause=None,
                summary="",
                ticket_title="",
                ticket_body="",
                policy_tags=[],
                tool_calls=[],
                skipped_reason=skipped_reason or "LLM unavailable",
            )

    policy = evaluate_policy(incident, analysis)
    effective = policy.effective_disposition or analysis.disposition

    return EvalResult(
        case_id=case["id"],
        source=case["source"],
        analysis_source=analysis.analysis_source,
        severity=(analysis.severity or "").lower(),
        disposition=(analysis.disposition or "").upper(),
        effective_disposition=(effective or "").upper(),
        confidence=float(analysis.confidence or 0.0),
        matched_runbook_id=analysis.matched_runbook_id,
        suspected_root_cause=analysis.suspected_root_cause,
        summary=analysis.summary or "",
        ticket_title=analysis.ticket_title or "",
        ticket_body=analysis.ticket_body or "",
        policy_tags=policy.tags or [],
        tool_calls=getattr(analysis, "tool_calls", []),
    )


def _root_or_runbook_matches(expected: dict, result: EvalResult) -> bool:
    expected_runbook = expected.get("runbook_id")
    if expected_runbook:
        return result.matched_runbook_id == expected_runbook

    keywords = [kw.lower() for kw in expected.get("root_cause_keywords", [])]
    if not keywords:
        return True

    haystack = " ".join(
        [
            result.suspected_root_cause or "",
            result.summary,
            result.ticket_title,
            result.ticket_body,
        ]
    ).lower()
    return any(keyword in haystack for keyword in keywords)


def _triage_failures(case: dict, result: EvalResult) -> list[str]:
    expected = case["expected"]
    failures = []

    expected_severity = expected["severity"].lower()
    if result.severity != expected_severity:
        failures.append(f"severity expected {expected_severity}, got {result.severity}")

    expected_disposition = expected["disposition"].upper()
    if result.effective_disposition != expected_disposition:
        failures.append(
            f"disposition expected {expected_disposition}, got {result.effective_disposition}"
        )

    if not _root_or_runbook_matches(expected, result):
        expected_root = expected.get("runbook_id") or ", ".join(
            expected.get("root_cause_keywords", [])
        )
        actual_root = result.matched_runbook_id or result.suspected_root_cause or "none"
        failures.append(f"root/runbook expected {expected_root}, got {actual_root}")

    return failures


def _unsafe_reasons(case: dict, result: EvalResult) -> list[str]:
    expected_disposition = case["expected"]["disposition"].upper()
    expected_rank = _rank(expected_disposition)
    actual_rank = _rank(result.effective_disposition)
    reasons = []

    if expected_disposition != "NO_ACTION" and result.would_auto_suppress:
        reasons.append("would auto-suppress an actionable incident")

    if expected_rank >= _rank("NEEDS_DEV"):
        if result.effective_disposition != expected_disposition:
            if actual_rank < expected_rank:
                reasons.append("under-triaged an actionable incident")
            else:
                reasons.append("would notify the wrong severity/channel")

    if expected_disposition == "NO_ACTION" and actual_rank >= _rank("NEEDS_DEV"):
        reasons.append("would escalate known noise")

    return reasons


def run_triage_eval(dataset_path: Path, project_name: str | None):
    project = _lookup_project(project_name)
    cases = _load_json(dataset_path)

    scored = []
    skipped = []
    triage_mismatches = []
    unsafe = []

    for case in cases:
        result = _analyze_case(case, project)
        if result.skipped_reason:
            skipped.append((case, result))
            continue

        scored.append((case, result))

        failures = _triage_failures(case, result)
        if failures:
            triage_mismatches.append((case, result, failures))

        unsafe_reasons = _unsafe_reasons(case, result)
        if unsafe_reasons:
            unsafe.append((case, result, unsafe_reasons))

    correct = len(scored) - len(triage_mismatches)
    print("IncidentLens Triage Eval")
    print(f"dataset: {dataset_path}")
    if project_name:
        print(f"project: {project_name}")
    print(f"cases scored: {len(scored)}")
    if skipped:
        print(f"cases skipped: {len(skipped)}")
    paths = {}
    tool_call_count = 0
    for _case, result in scored:
        paths[result.analysis_source] = paths.get(result.analysis_source, 0) + 1
        tool_call_count += len(result.tool_calls)
    print(
        "analysis paths: "
        + ", ".join(f"{name}={count}" for name, count in sorted(paths.items()))
    )
    if tool_call_count:
        print(f"agent tool calls: {tool_call_count}")
    print(f"correct triage rate: {correct}/{len(scored)} ({_pct(correct, len(scored))})")
    print(
        f"unsafe automation rate: {len(unsafe)}/{len(scored)} "
        f"({_pct(len(unsafe), len(scored))})"
    )

    if triage_mismatches:
        print()
        print("triage mismatches:")
        for case, result, failures in triage_mismatches:
            print(
                f"- {case['id']} ({case['name']}): "
                f"{'; '.join(failures)} "
                f"[source={result.analysis_source}, confidence={result.confidence:.2f}]"
            )

    if unsafe:
        print()
        print("unsafe automation cases:")
        for case, result, reasons in unsafe:
            print(
                f"- {case['id']} ({case['name']}): "
                f"{'; '.join(reasons)} "
                f"[effective={result.effective_disposition}]"
            )

    if skipped:
        print()
        print("skipped cases:")
        for case, result in skipped:
            print(f"- {case['id']} ({case['name']}): {result.skipped_reason}")

    return 0 if not triage_mismatches and not unsafe else 1


def main():
    parser = argparse.ArgumentParser(description="IncidentLens triage eval runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    triage_eval = subparsers.add_parser(
        "triage-eval",
        aliases=["eval"],
        help="Run the labeled incident triage eval",
    )
    triage_eval.add_argument(
        "--dataset",
        default=str(_default_dataset()),
        help="Path to incident triage eval dataset",
    )
    triage_eval.add_argument(
        "--project",
        default=None,
        help="Project name to load Groq credentials from for LLM-only cases",
    )

    args = parser.parse_args()
    if args.command in {"triage-eval", "eval"}:
        raise SystemExit(run_triage_eval(Path(args.dataset), args.project))


if __name__ == "__main__":
    main()
