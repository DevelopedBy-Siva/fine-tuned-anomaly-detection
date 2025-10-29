from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from sklearn.ensemble import IsolationForest
import pandas as pd
from explain import explain_log_with_context


persistence = FilePersistence("drain3_state.bin")
template_miner = TemplateMiner(persistence)


def extract_log_features(log_lines):
    if not log_lines:
        return pd.DataFrame(columns=["template_id"])

    templates = []
    for line in log_lines:
        result = template_miner.add_log_message(line)
        cluster_id = result.get("cluster_id", -1) if isinstance(result, dict) else -1
        templates.append(cluster_id)
    df = pd.DataFrame(templates, columns=["template_id"])
    return df


def detect_anomalies(log_lines):
    critical = [l for l in log_lines if "CRITICAL" in l]
    errors = [l for l in log_lines if "ERROR" in l]
    warnings = [l for l in log_lines if "WARNING" in l]

    anomalies = critical + errors

    if len(warnings) >= 3:
        df = extract_log_features(warnings)

        if not df.empty:
            model = IsolationForest(contamination=0.2, random_state=42)
            model.fit(df)
            preds = model.predict(df)
            anomalies += [warnings[i] for i in range(len(preds)) if preds[i] == -1]

    if not anomalies:
        anomalies = [l for l in log_lines if "ERROR" in l or "CRITICAL" in l]

    return anomalies


if __name__ == "__main__":
    logs = open("sample_logs.txt").read().splitlines()
    anomalies = detect_anomalies(logs)

    print("Detected Anomalies:\n")
    if not anomalies:
        print("No anomalies found...")
    else:
        for i, log in enumerate(logs):
            if log in anomalies:
                explanation = explain_log_with_context(logs, i)
                print(f"{log}\n{explanation}\n")
