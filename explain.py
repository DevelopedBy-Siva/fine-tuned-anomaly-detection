import subprocess
from typing import List

cache = {}


def explain_log_with_context(
    log_lines: List[str],
    anomaly_index: int,
    model: str = "phi3",
    context_window: int = 3,
) -> str:
    """
    Use a local Ollama model to generate a short RCA:
    Root cause + Possible Fix (one sentence each).
    """
    context = "\n".join(
        log_lines[max(0, anomaly_index - context_window) : anomaly_index + 2]
    )

    if context in cache:
        return cache[context]

    prompt = f"""
You are a senior DevOps engineer assisting with incident triage.

Summarize the issue **concisely**:
1. Root cause: one short sentence.
2. Possible Fix: one short sentence.

Format exactly:
Root cause: <...>
Possible Fix: <...>

Logs:
{context}
"""

    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=45,
        )
        output = result.stdout.strip()

        lines = [ln.strip() for ln in output.split("\n") if ln.strip()]
        if len(lines) > 3:
            output = "\n".join(lines[:3])

        cache[context] = output
        return output or "No explanation returned."
    except subprocess.TimeoutExpired:
        return "Model timeout."
    except Exception as e:
        return f"Model error: {e}"
