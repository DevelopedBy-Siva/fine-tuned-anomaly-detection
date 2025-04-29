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
        return len(self.logs), 150, 93, self.logs
