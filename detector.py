from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from sklearn.ensemble import IsolationForest
import pandas as pd

persistence = FilePersistence("drain3_state.bin")
template_miner = TemplateMiner(persistence)


def extract_log_features(log_lines):
    templates = []
    for line in log_lines:
        result = template_miner.add_log_message(line)
        cluster_id = result.get("cluster_id", -1) if isinstance(result, dict) else -1
        templates.append(cluster_id)
    df = pd.DataFrame(templates, columns=["template_id"])
    return df


def detect_anomalies(log_lines):
    interesting = [
        l for l in log_lines if any(x in l for x in ["WARNING", "ERROR", "CRITICAL"])
    ]

    if not interesting:
        df = extract_log_features(log_lines)
        model = IsolationForest(contamination=0.1, random_state=42)
        model.fit(df)
        preds = model.predict(df)
        anomalies = [log_lines[i] for i in range(len(preds)) if preds[i] == -1]
        return anomalies

    df = extract_log_features(interesting)
    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(df)
    preds = model.predict(df)
    anomalies = [interesting[i] for i in range(len(preds)) if preds[i] == -1]

    if not anomalies:
        anomalies = [l for l in interesting if "ERROR" in l or "CRITICAL" in l]

    return anomalies


if __name__ == "__main__":

    logs = open("sample_logs.txt").read().splitlines()
    anomalies = detect_anomalies(logs)
    print("Anomalies:")
    for a in anomalies:
        print(" -", a)
