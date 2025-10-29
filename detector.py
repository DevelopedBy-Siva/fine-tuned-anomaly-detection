from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from sklearn.ensemble import IsolationForest
import pandas as pd
from typing import List, Dict

persistence = FilePersistence("drain3_state.bin")
template_miner = TemplateMiner(persistence)


def extract_log_templates(log_lines: List[str]) -> List[Dict]:
    """
    For each line, return { "line": str, "template_id": "...", "severity": "INFO"/"ERROR"/... }
    """
    results = []
    for line in log_lines:
        parsed = template_miner.add_log_message(line)
        template_id = (
            parsed.get("cluster_id", "unknown")
            if isinstance(parsed, dict)
            else "unknown"
        )

        if "CRITICAL" in line:
            sev = "CRITICAL"
        elif "ERROR" in line:
            sev = "ERROR"
        elif "WARNING" in line:
            sev = "WARNING"
        else:
            sev = "INFO"

        results.append({"line": line, "template_id": template_id, "severity": sev})
    return results


def detect_anomalies(log_lines: List[str]) -> List[Dict]:
    """
    Return list of anomaly dicts:
    {
      "index": int,
      "log_line": str,
      "template_id": str,
      "severity": str
    }
    """
    annotated = extract_log_templates(log_lines)

    anomalies = [
        {
            "index": i,
            "log_line": row["line"],
            "template_id": row["template_id"],
            "severity": row["severity"],
        }
        for i, row in enumerate(annotated)
        if row["severity"] in ["CRITICAL", "ERROR"]
    ]

    warning_rows = [
        (i, row) for i, row in enumerate(annotated) if row["severity"] == "WARNING"
    ]

    if len(warning_rows) >= 3:
        df = pd.DataFrame(
            [row["template_id"] for (_, row) in warning_rows], columns=["template_id"]
        )

        model = IsolationForest(contamination=0.2, random_state=42)
        model.fit(df)
        preds = model.predict(df)

        for pred_idx, (i, row) in enumerate(warning_rows):
            if preds[pred_idx] == -1:
                anomalies.append(
                    {
                        "index": i,
                        "log_line": row["line"],
                        "template_id": row["template_id"],
                        "severity": row["severity"],
                    }
                )

    dedup = {}
    for a in anomalies:
        dedup[a["index"]] = a
    final_list = [dedup[k] for k in sorted(dedup.keys())]

    return final_list
