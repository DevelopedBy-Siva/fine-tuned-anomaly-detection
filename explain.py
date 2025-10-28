import subprocess

cache = {}


def explain_log(log_line, model="phi3"):
    if log_line in cache:
        return cache[log_line]

    prompt = f"""You are a senior DevOps engineer.
Analyze the following log and explain the likely root cause and possible fix in one paragraph:

{log_line}"""

    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=45,
        )
        output = result.stdout.strip()
        cache[log_line] = output
        return output or "No explanation returned."
    except Exception as e:
        return "Something went wrong: " + str(e)


if __name__ == "__main__":
    test_line = "ERROR Failed to connect to DB: timeout expired"
    print("Reason:-\n", explain_log(test_line))
