import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:5001"

ENDPOINTS = [
    ("GET", "/api/users/{user_id}"),
    ("POST", "/api/orders"),
    ("POST", "/api/upload"),
    ("GET", "/api/cache/{key}"),
    ("POST", "/api/external/notify"),
    ("GET", "/api/health"),
    ("POST", "/internal/cron/cleanup"),
]


def make_request():
    """Make a random request to the server"""
    method, path = random.choice(ENDPOINTS)

    url = path.replace("{user_id}", str(random.randint(1, 100)))
    url = url.replace("{key}", f"cache_key_{random.randint(1, 50)}")
    url = BASE_URL + url

    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        else:
            response = requests.post(url, json={}, timeout=10)

    except Exception as e:
        print(f"Request failed: {e}")


def generate_traffic(duration_seconds=300, requests_per_second=2):
    """
    Generate continuous traffic to the log server

    Args:
        duration_seconds: How long to run (default: 5 minutes)
        requests_per_second: Request rate (default: 2/sec)
    """
    print(f"Generating traffic for {duration_seconds}s at {requests_per_second} req/s")
    print("Press Ctrl+C to stop\n")

    with ThreadPoolExecutor(max_workers=10) as executor:
        start_time = time.time()
        request_count = 0

        try:
            while time.time() - start_time < duration_seconds:
                for _ in range(requests_per_second):
                    executor.submit(make_request)
                    request_count += 1

                time.sleep(1)

                if request_count % 20 == 0:
                    elapsed = time.time() - start_time
                    print(f"[{elapsed:.0f}s] Sent {request_count} requests")

        except KeyboardInterrupt:
            print("\n\nStopping traffic generator...")

    print(f"\nTotal requests sent: {request_count}")


if __name__ == "__main__":
    generate_traffic(duration_seconds=300, requests_per_second=3)
