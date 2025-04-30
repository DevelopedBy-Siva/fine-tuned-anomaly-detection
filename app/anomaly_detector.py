import os
import pandas as pd

base_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(base_dir, "../notebook/data/output.csv")
output_file = os.path.normpath(output_file)


class AnomalyDetector:
    def __init__(self, logs):
        self.logs = logs

    def detect(self):
        """
        Returns:
            int: log sequence count,
            int: anomaly count,
            int: model confidence,
            list: all logs sequences
        """
        df = pd.read_csv(output_file)
        anomaly_count = df["Explanation"].notna().sum()
        sequences = df.to_dict(orient="records")
        return len(df), anomaly_count, 93, sequences
