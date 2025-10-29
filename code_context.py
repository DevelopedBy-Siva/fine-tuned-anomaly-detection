import subprocess
import re
from typing import Dict, Optional


def get_recent_git_diff() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except Exception:
        return ""


def guess_related_code(log_line: str, diff_text: str) -> str:
    if not diff_text:
        return "No recent code changes available."

    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]+", log_line)
    tokens = [t for t in tokens if len(t) > 3]
    tokens = tokens[:10]

    matches = []
    for t in tokens:
        if t in diff_text:
            matches.append(t)

    if matches:
        return (
            "Recent change may be related to: "
            + ", ".join(sorted(set(matches))[:5])
            + ". Check recent commit diff."
        )
    else:
        return "Log terms not clearly mapped to the last commit diff."


def generate_code_impact_summary(log_line: str) -> str:
    diff_text = get_recent_git_diff()
    if not diff_text:
        return "No git context available."

    hint = guess_related_code(log_line, diff_text)

    return hint
