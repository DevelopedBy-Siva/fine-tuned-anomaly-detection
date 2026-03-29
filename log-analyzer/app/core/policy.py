from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


MIN_CONFIDENCE_TO_ACT = 0.55

MIN_CONFIDENCE_RUNBOOK = 0.40

COOLDOWN_MINUTES = 20

ALLOWED_AUTO_DISPOSITIONS = {"ESCALATE", "NEEDS_ONCALL", "NEEDS_DEV", "NO_ACTION"}

MIN_COUNT_TO_ESCALATE = 3

SEVERITY_DISPOSITION_FLOOR = {
    "critical": "NEEDS_ONCALL",
    "high": "NEEDS_DEV",
    "medium": "OBSERVE",
    "low": "OBSERVE",
}

DISPOSITION_RANK = {
    "NO_ACTION": 0,
    "OBSERVE": 1,
    "NEEDS_DEV": 2,
    "NEEDS_ONCALL": 3,
    "ESCALATE": 4,
}


@dataclass
class PolicyDecision:
    allow: bool
    reason: str
    effective_disposition: Optional[str] = None
    tags: list[str] = field(default_factory=list)


def _rank(disposition: str) -> int:
    return DISPOSITION_RANK.get(disposition.upper(), 0)


def _floor_disposition(severity: str, proposed: str) -> str:
    """Ensure disposition is at least the floor for this severity."""
    floor = SEVERITY_DISPOSITION_FLOOR.get(severity.lower(), "OBSERVE")
    if _rank(proposed) < _rank(floor):
        return floor
    return proposed


def _was_recently_acted_on(incident, cooldown_minutes: int) -> bool:
    """
    Check whether this incident already had an action fired recently.
    Uses incident.last_seen as a proxy until ActionLog is introduced in Phase 4.
    Falls back gracefully if the field doesn't exist yet.
    """
    acted_at: Optional[datetime] = getattr(incident, "last_actioned_at", None)
    if acted_at is None:
        return False
    cutoff = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
    return acted_at > cutoff


def evaluate(incident, analysis) -> PolicyDecision:
    """
    Evaluate whether the analysis warrants immediate action.

    Args:
        incident:  Incident ORM object (needs .count, .status, optionally .last_actioned_at)
        analysis:  Analysis ORM object OR IncidentAnalysis pydantic model
                   (needs .severity, .disposition, .confidence, .analysis_source)

    Returns:
        PolicyDecision — always returned, never raises.
    """
    tags: list[str] = []

    severity = (analysis.severity or "low").lower().strip()
    disposition = (analysis.disposition or "OBSERVE").upper().strip()
    confidence = float(analysis.confidence or 0.0)
    source = getattr(analysis, "analysis_source", "llm") or "llm"

    if incident.status in ("closed", "ignored"):
        return PolicyDecision(
            allow=False,
            reason=f"Incident is {incident.status} — no action",
            effective_disposition=disposition,
            tags=["blocked:status"],
        )

    min_conf = MIN_CONFIDENCE_RUNBOOK if source == "runbook" else MIN_CONFIDENCE_TO_ACT
    if confidence < min_conf:
        tags.append("blocked:low_confidence")
        logger.info(
            "[POLICY] Blocked — confidence %.2f < %.2f for incident %s",
            confidence,
            min_conf,
            incident.id,
        )
        return PolicyDecision(
            allow=False,
            reason=f"Confidence {confidence:.2f} below threshold {min_conf:.2f} ({source})",
            effective_disposition="OBSERVE",
            tags=tags,
        )

    if _was_recently_acted_on(incident, COOLDOWN_MINUTES):
        tags.append("blocked:cooldown")
        return PolicyDecision(
            allow=False,
            reason=f"Incident actioned within last {COOLDOWN_MINUTES}min — cooldown active",
            effective_disposition=disposition,
            tags=tags,
        )

    if disposition == "ESCALATE" and incident.count < MIN_COUNT_TO_ESCALATE:
        tags.append("downgraded:count_too_low")
        disposition = "NEEDS_DEV"
        logger.info(
            "[POLICY] Downgraded ESCALATE → NEEDS_DEV — count %d < %d for incident %s",
            incident.count,
            MIN_COUNT_TO_ESCALATE,
            incident.id,
        )

    floored = _floor_disposition(severity, disposition)
    if floored != disposition:
        tags.append(f"floored:{disposition}→{floored}")
        disposition = floored

    if disposition not in ALLOWED_AUTO_DISPOSITIONS:
        tags.append("unknown_disposition")

    logger.info(
        "[POLICY] Allowed — %s/%s conf=%.2f src=%s incident=%s",
        severity,
        disposition,
        confidence,
        source,
        incident.id,
    )

    return PolicyDecision(
        allow=True,
        reason="All policy checks passed",
        effective_disposition=disposition,
        tags=tags,
    )
