import logging
import os
from datetime import datetime

os.makedirs("logs", exist_ok=True)


class CustomFormatter(logging.Formatter):
    """Custom formatter with timestamps"""

    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).isoformat()

        log_line = f"[{timestamp}] {record.levelname}: {record.getMessage()}"

        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"

        return log_line


def setup_logger(name="app"):
    """Configure application logger"""

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler("logs/app.log")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(CustomFormatter())

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CustomFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
