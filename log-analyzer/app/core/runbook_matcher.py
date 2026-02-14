import re
from typing import Optional, Tuple
from app.core.runbook_loader import Runbook, get_runbooks


def score_runbook(runbook: Runbook, incident_text: str) -> float:
    """
    Score how well a runbook matches an incident.
    Returns a score between 0.0 and 1.0
    """
    incident_lower = incident_text.lower()
    matches = 0

    for pattern in runbook.patterns:
        if pattern.startswith("regex:"):
            regex_pattern = pattern[6:]
            if re.search(regex_pattern, incident_lower, re.IGNORECASE):
                matches += 1
        else:
            if pattern.lower() in incident_lower:
                matches += 1

    if not runbook.patterns:
        return 0.0

    score = matches / len(runbook.patterns)
    return score


def match_runbook(incident) -> Tuple[Optional[Runbook], float]:
    """
    Find the best matching runbook for an incident.

    Returns:
        (matched_runbook, confidence_score) or (None, 0.0)
    """
    runbooks = get_runbooks()

    if not runbooks:
        return None, 0.0

    sample_text = " ".join(incident.sample_lines or [])

    scored_runbooks = [
        (runbook, score_runbook(runbook, sample_text)) for runbook in runbooks
    ]

    scored_runbooks.sort(key=lambda x: x[1], reverse=True)

    best_runbook, best_score = scored_runbooks[0]

    if best_score < 0.3:
        return None, 0.0

    return best_runbook, best_score


def should_escalate(incident, runbook: Runbook) -> bool:
    """
    Check if incident should be escalated based on runbook threshold.
    """
    if not runbook.observe_threshold:
        return False

    threshold = runbook.observe_threshold
    required_count = threshold.get("count", 10)

    return incident.count >= required_count
