import time
import requests
from pathlib import Path
from collections import deque
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LOG_FILE = "logs/app.log"
ANALYZER_URL = os.getenv("ANALYZER_URL")
API_KEY = os.getenv("LOGSHIPPER_API_KEY")
BATCH_SIZE = 10
POLL_INTERVAL = 2


class LogTailer:
    """Tail a log file and ship lines to the analyzer"""

    def __init__(self, filepath: str, analyzer_url: str, api_key: str):
        self.filepath = Path(filepath)
        self.analyzer_url = analyzer_url
        self.api_key = api_key
        self.position = 0
        self.buffer = deque(maxlen=BATCH_SIZE * 2)

    def tail_and_ship(self):
        """Continuously tail the log file and send batches"""
        print(f"Tailing {self.filepath} → {self.analyzer_url}")
        print(f"Batch size: {BATCH_SIZE}, Poll interval: {POLL_INTERVAL}s\n")

        if self.filepath.exists():
            self.position = self.filepath.stat().st_size

        while True:
            try:
                self._read_new_lines()
                if len(self.buffer) >= BATCH_SIZE:
                    self._ship_batch()
                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                print("\n\nStopping log shipper...")
                if self.buffer:
                    self._ship_batch()
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)

    def _read_new_lines(self):
        """Read new lines from log file"""
        if not self.filepath.exists():
            return

        with open(self.filepath, "r") as f:
            f.seek(self.position)
            for line in f:
                line = line.strip()
                if line:
                    self.buffer.append(line)
            self.position = f.tell()

    def _ship_batch(self):
        """Send buffered logs to analyzer"""
        if not self.buffer:
            return

        logs = list(self.buffer)
        self.buffer.clear()

        try:
            response = requests.post(
                self.analyzer_url,
                json={"source": "log-server", "environment": "prod", "logs": logs},
                headers={"X-API-Key": self.api_key},  # ADD THIS
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                print(
                    f"✅ Shipped {data['total_logs_processed']} logs | "
                    f"Created: {data['incidents_created']} | "
                    f"Updated: {data['incidents_updated']}"
                )
            else:
                print(f"⚠️  Analyzer returned {response.status_code}: {response.text}")

        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to analyzer. Is it running on port 8000?")
            self.buffer.extendleft(reversed(logs))
        except Exception as e:
            print(f"❌ Ship failed: {e}")
            self.buffer.extendleft(reversed(logs))


if __name__ == "__main__":
    if API_KEY == "YOUR_API_KEY_HERE":
        print("❌ Please set your API_KEY in the script first!")
        print("   Get it from the React app after registration.")
        exit(1)

    tailer = LogTailer(LOG_FILE, ANALYZER_URL, API_KEY)
    tailer.tail_and_ship()
