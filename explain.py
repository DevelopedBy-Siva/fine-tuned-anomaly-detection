import subprocess

cache = {}


def explain_log_with_context(log_lines, anomaly_index, model="phi3"):
    context_window = 3
    context = "\n".join(
        log_lines[max(0, anomaly_index - context_window) : anomaly_index + 2]
    )

    if context in cache:
        return cache[context]

    prompt = f"""
    You are a senior DevOps engineer assisting with incident triage.

    Summarize the following logs **concisely**:
    1. Identify the most likely root cause (one short sentence).
    2. Suggest one direct fix or next step (one short sentence).

    Keep the answer brief, in this format:
    Root cause: <one sentence>
    Possible Fix: <one sentence>

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
        cache[context] = output
        return output or "No explanation returned."
    except subprocess.TimeoutExpired:
        return "Timed out..."
    except Exception as e:
        return f"Something went wrong: {e}"
