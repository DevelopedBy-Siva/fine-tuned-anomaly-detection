from flask import Flask, request, jsonify
from detector import detect_anomalies
from explain import explain_log_with_context
from code_context import generate_code_impact_summary
from memory import remember_incident, retrieve_similar

app = Flask(__name__)


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    logs = data.get("logs", [])

    if not isinstance(logs, list) or not logs:
        return jsonify({"error": "send { 'logs': [ ... ] }"}), 400

    anomalies = detect_anomalies(logs)

    enriched = []
    for a in anomalies:
        idx = a["index"]
        line = a["log_line"]
        template_id = a["template_id"]
        severity = a["severity"]

        rca_text = explain_log_with_context(logs, idx)
        root_cause = ""
        fix = ""
        for rline in rca_text.split("\n"):
            if rline.lower().startswith("root cause:"):
                root_cause = rline.replace("Root cause:", "").strip()
            elif rline.lower().startswith("possible fix:") or rline.lower().startswith(
                "fix:"
            ):
                fix = rline.split(":", 1)[-1].strip()

        if not root_cause:
            root_cause = rca_text

        code_hint = generate_code_impact_summary(line)

        prev = retrieve_similar(template_id)
        if prev:
            seen_before = True
            prev_fix = prev.get("fix", "")
            prev_root = prev.get("root_cause", "")
            prev_when = prev.get("timestamp", "")
        else:
            seen_before = False
            prev_fix = ""
            prev_root = ""
            prev_when = ""

        remember_incident(
            template_id=template_id,
            log_line=line,
            root_cause=root_cause,
            fix=fix or prev_fix or "n/a",
            code_hint=code_hint,
        )

        enriched.append(
            {
                "line_index": idx,
                "log_line": line,
                "severity": severity,
                "template_id": template_id,
                "root_cause": root_cause,
                "fix": fix,
                "code_hint": code_hint,
                "seen_before": seen_before,
                "previous_incident": {
                    "timestamp": prev_when,
                    "root_cause": prev_root,
                    "fix": prev_fix,
                },
            }
        )

    return jsonify(enriched), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
