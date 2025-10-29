import json
import os
from typing import List, Dict, Optional
from datetime import datetime

INCIDENT_MEMORY_FILE = "incidents.json"


def _load_memory() -> List[Dict]:
    if not os.path.exists(INCIDENT_MEMORY_FILE):
        return []
    with open(INCIDENT_MEMORY_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_memory(all_incidents: List[Dict]):
    with open(INCIDENT_MEMORY_FILE, "w") as f:
        json.dump(all_incidents, f, indent=2)


def remember_incident(
    template_id: str, log_line: str, root_cause: str, fix: str, code_hint: str
):
    all_incidents = _load_memory()
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "template_id": template_id,
        "log_line": log_line,
        "root_cause": root_cause,
        "fix": fix,
        "code_hint": code_hint,
    }
    all_incidents.append(entry)
    _save_memory(all_incidents)


def retrieve_similar(template_id: str) -> Optional[Dict]:
    all_incidents = _load_memory()
    matches = [i for i in all_incidents if i["template_id"] == template_id]
    if not matches:
        return None
    matches.sort(key=lambda x: x["timestamp"], reverse=True)
    return matches[0]
