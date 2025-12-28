import requests
import time
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:8000"
COLORS = {
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "END": "\033[0m",
}


def print_header(text):
    print(f"\n{'='*70}")
    print(f"{COLORS['BLUE']}{text}{COLORS['END']}")
    print(f"{'='*70}")


def print_success(text):
    print(f"{COLORS['GREEN']}✓ {text}{COLORS['END']}")


def print_error(text):
    print(f"{COLORS['RED']}✗ {text}{COLORS['END']}")


def print_info(text):
    print(f"{COLORS['YELLOW']}ℹ {text}{COLORS['END']}")


class APITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.results = {"passed": 0, "failed": 0, "total": 0}

    def test_endpoint(self, name, func):
        self.results["total"] += 1
        print(f"\n{COLORS['YELLOW']}Testing: {name}{COLORS['END']}")
        try:
            func()
            self.results["passed"] += 1
            print_success(f"{name} - PASSED")
            return True
        except AssertionError as e:
            self.results["failed"] += 1
            print_error(f"{name} - FAILED: {e}")
            return False
        except Exception as e:
            self.results["failed"] += 1
            print_error(f"{name} - ERROR: {e}")
            return False

    def print_summary(self):
        print_header("TEST SUMMARY")
        print(f"Total Tests: {self.results['total']}")
        print(f"{COLORS['GREEN']}Passed: {self.results['passed']}{COLORS['END']}")
        print(f"{COLORS['RED']}Failed: {self.results['failed']}{COLORS['END']}")

        success_rate = (
            (self.results["passed"] / self.results["total"] * 100)
            if self.results["total"] > 0
            else 0
        )
        print(f"\nSuccess Rate: {success_rate:.1f}%")

        if self.results["failed"] == 0:
            print(f"\n{COLORS['GREEN']} All tests passed!{COLORS['END']}")
        else:
            print(f"\n{COLORS['RED']} Some tests failed{COLORS['END']}")


tester = APITester(BASE_URL)


def test_root():
    print_info(f"GET {BASE_URL}/")
    response = requests.get(f"{BASE_URL}/")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    assert "service" in data, "Missing 'service' field"
    assert data["service"] == "LogAnomaly API", "Incorrect service name"
    assert "version" in data, "Missing 'version' field"
    assert "endpoints" in data, "Missing 'endpoints' field"


tester.test_endpoint("Root Endpoint", test_root)


def test_health():
    print_info(f"GET {BASE_URL}/health")
    response = requests.get(f"{BASE_URL}/health")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    assert data["status"] == "healthy", "Status is not healthy"
    assert data["models_loaded"] == True, "Models not loaded"
    assert "device" in data, "Missing device info"
    assert "timestamp" in data, "Missing timestamp"

    print_info(f"Device: {data['device']}")
    print_info(f"Models Loaded: {data['models_loaded']}")


tester.test_endpoint("Health Check", test_health)


def test_stats():
    print_info(f"GET {BASE_URL}/stats")
    response = requests.get(f"{BASE_URL}/stats")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    assert "model_info" in data, "Missing model_info"
    assert "config" in data, "Missing config"

    classifier = data["model_info"]["classifier"]
    print_info(f"Classifier F1: {classifier['f1_score']}")
    print_info(f"Classifier Precision: {classifier['precision']}")
    print_info(f"Classifier Recall: {classifier['recall']}")


tester.test_endpoint("Stats Endpoint", test_stats)


def test_analyze_normal():
    print_info("Testing with small normal log file")

    log_content = "\n".join(
        [
            f"2024-12-28 10:00:{i:02d},000 INFO org.apache.hadoop.hdfs: Processing block {i}"
            for i in range(20)
        ]
    )

    files = {"file": ("test_normal.log", log_content, "text/plain")}

    print_info(f"POST {BASE_URL}/analyze")
    start = time.time()
    response = requests.post(f"{BASE_URL}/analyze", files=files)
    duration = time.time() - start

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"\nResponse Summary:")
    print(f"  Status: {data['status']}")
    print(f"  Total Sequences: {data['total_sequences']}")
    print(f"  Anomalies Detected: {data['anomalies_detected']}")
    print(f"  Anomaly Rate: {data['anomaly_rate']:.2%}")
    print(f"  Processing Time: {data['processing_time']:.3f}s")
    print(f"  API Response Time: {duration:.3f}s")
    print(f"  Summary: {data['summary']}")

    assert data["status"] == "success", "Analysis failed"
    assert data["total_sequences"] > 0, "No sequences created"
    assert "results" in data, "Missing results"

    print_info(f"Performance: {duration:.3f}s for {data['total_sequences']} sequences")


tester.test_endpoint("Analyze Normal Logs", test_analyze_normal)


def test_analyze_anomalies():
    print_info("Testing with logs containing anomalies")

    log_content = "\n".join(
        [
            "2024-12-28 10:00:00,000 INFO org.apache.hadoop.hdfs: Starting service",
            "2024-12-28 10:00:01,000 INFO org.apache.hadoop.hdfs: Processing request",
            "2024-12-28 10:00:02,000 ERROR org.apache.hadoop.hdfs: Connection timeout",
            "2024-12-28 10:00:03,000 ERROR org.apache.hadoop.hdfs: Failed to connect to datanode",
            "2024-12-28 10:00:04,000 FATAL org.apache.hadoop.hdfs: System crash detected",
            "2024-12-28 10:00:05,000 ERROR org.apache.hadoop.hdfs: Unable to recover",
            "2024-12-28 10:00:06,000 INFO org.apache.hadoop.hdfs: Attempting restart",
            "2024-12-28 10:00:07,000 ERROR org.apache.hadoop.hdfs: Restart failed",
            "2024-12-28 10:00:08,000 ERROR org.apache.hadoop.hdfs: Data corruption detected",
            "2024-12-28 10:00:09,000 FATAL org.apache.hadoop.hdfs: Emergency shutdown",
            "2024-12-28 10:00:10,000 INFO org.apache.hadoop.hdfs: Service stopped",
        ]
        * 2
    )

    files = {"file": ("test_anomaly.log", log_content, "text/plain")}

    print_info(f"POST {BASE_URL}/analyze")
    start = time.time()
    response = requests.post(f"{BASE_URL}/analyze", files=files)
    duration = time.time() - start

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"\nResponse Summary:")
    print(f"  Status: {data['status']}")
    print(f"  Total Sequences: {data['total_sequences']}")
    print(f"  Anomalies Detected: {data['anomalies_detected']}")
    print(f"  Anomaly Rate: {data['anomaly_rate']:.2%}")
    print(f"  Processing Time: {data['processing_time']:.3f}s")
    print(f"  Summary: {data['summary']}")

    if data["anomalies_detected"] > 0:
        print(f"\n{COLORS['YELLOW']}Detected Anomalies:{COLORS['END']}")
        for i, anomaly in enumerate(data["results"][:3], 1):
            print(f"\n  Anomaly {i}:")
            print(f"    Confidence: {anomaly['confidence']:.2%}")
            print(f"    Severity: {anomaly['severity']}")
            print(f"    Explanation: {anomaly['explanation']}")
            print(f"    Snippet: {anomaly['log_snippet'][:100]}...")

    assert data["status"] == "success", "Analysis failed"
    print_info(f"Detected {data['anomalies_detected']} anomalies")


tester.test_endpoint("Analyze Anomaly Logs", test_analyze_anomalies)


def test_analyze_medium():
    print_info("Testing with medium-sized log file (500 lines)")

    log_content = "\n".join(
        [
            f"2024-12-28 {i//3600:02d}:{(i%3600)//60:02d}:{i%60:02d},000 INFO org.apache.hadoop: Log entry {i}"
            for i in range(500)
        ]
    )

    anomaly_lines = [
        "2024-12-28 10:15:00,000 ERROR org.apache.hadoop: Connection timeout",
        "2024-12-28 10:15:01,000 FATAL org.apache.hadoop: System failure",
    ] * 5

    log_content += "\n" + "\n".join(anomaly_lines)

    files = {"file": ("test_medium.log", log_content, "text/plain")}

    print_info(f"POST {BASE_URL}/analyze")
    start = time.time()
    response = requests.post(f"{BASE_URL}/analyze", files=files)
    duration = time.time() - start

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"\nResponse Summary:")
    print(f"  Total Sequences: {data['total_sequences']}")
    print(f"  Anomalies: {data['anomalies_detected']}")
    print(f"  Rate: {data['anomaly_rate']:.2%}")
    print(f"  Processing Time: {data['processing_time']:.3f}s")
    print(f"  API Response Time: {duration:.3f}s")

    throughput = data["total_sequences"] / duration
    print_info(f"Throughput: {throughput:.1f} sequences/second")

    assert duration < 30, f"Too slow for medium file: {duration:.2f}s"


tester.test_endpoint("Analyze Medium File", test_analyze_medium)


def test_invalid_file_type():
    print_info("Testing invalid file type rejection")

    files = {"file": ("test.pdf", b"fake pdf content", "application/pdf")}

    print_info(f"POST {BASE_URL}/analyze (expecting 400)")
    response = requests.post(f"{BASE_URL}/analyze", files=files)

    print(f"Response Code: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    assert "Only .log and .txt files are supported" in response.json()["detail"]


tester.test_endpoint("Invalid File Type", test_invalid_file_type)


def test_insufficient_logs():
    print_info("Testing insufficient log lines")

    log_content = "\n".join(
        [f"2024-12-28 10:00:{i:02d},000 INFO test: Log {i}" for i in range(5)]
    )

    files = {"file": ("test_small.log", log_content, "text/plain")}

    print_info(f"POST {BASE_URL}/analyze (expecting 400)")
    response = requests.post(f"{BASE_URL}/analyze", files=files)

    print(f"Response Code: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 400, f"Expected 400, got {response.status_code}"


tester.test_endpoint("Insufficient Logs", test_insufficient_logs)


def test_response_time():
    print_info("Benchmarking response times")

    log_content = "\n".join(
        [f"2024-12-28 10:00:{i:02d},000 INFO test: Log entry {i}" for i in range(50)]
    )

    times = []
    num_requests = 5

    print_info(f"Making {num_requests} requests...")
    for i in range(num_requests):
        files = {"file": ("test.log", log_content, "text/plain")}
        start = time.time()
        response = requests.post(f"{BASE_URL}/analyze", files=files)
        duration = time.time() - start
        times.append(duration)
        print(f"  Request {i+1}: {duration:.3f}s")

        assert response.status_code == 200

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    print(f"\nBenchmark Results:")
    print(f"  Average: {avg_time:.3f}s")
    print(f"  Min: {min_time:.3f}s")
    print(f"  Max: {max_time:.3f}s")

    assert avg_time < 10, f"Average response time too high: {avg_time:.2f}s"


tester.test_endpoint("Response Time Benchmark", test_response_time)


def test_real_world_format():
    print_info("Testing with real HDFS log format")

    log_content = """2024-12-28 10:00:00,123 INFO org.apache.hadoop.hdfs.server.namenode.FSNamesystem: Roll Edit Log from 192.168.1.1
2024-12-28 10:00:01,456 INFO org.apache.hadoop.hdfs.server.namenode.FSNamesystem: Number of transactions: 1234
2024-12-28 10:00:02,789 INFO org.apache.hadoop.hdfs.StateChange: BLOCK* allocate blk_1234567890
2024-12-28 10:00:03,012 ERROR org.apache.hadoop.hdfs.server.datanode.DataNode: Error processing write
2024-12-28 10:00:04,345 ERROR org.apache.hadoop.hdfs.server.datanode.DataNode: java.net.SocketTimeoutException: 60000 millis timeout
2024-12-28 10:00:05,678 FATAL org.apache.hadoop.hdfs.server.namenode.FSNamesystem: Encountered exception during block recovery
2024-12-28 10:00:06,901 ERROR org.apache.hadoop.hdfs.server.namenode.FSNamesystem: Failed to recover block
2024-12-28 10:00:07,234 INFO org.apache.hadoop.hdfs.StateChange: BLOCK* InvalidateBlocks: add blk_1234567890
2024-12-28 10:00:08,567 INFO org.apache.hadoop.hdfs.server.namenode.FSNamesystem: Removing unreachable blocks
2024-12-28 10:00:09,890 ERROR org.apache.hadoop.hdfs.server.namenode.FSNamesystem: Failed to remove blocks
2024-12-28 10:00:10,123 INFO org.apache.hadoop.hdfs.StateChange: BLOCK* NameSystem.addStoredBlock: node deleted
2024-12-28 10:00:11,456 INFO org.apache.hadoop.hdfs.server.namenode.FSNamesystem: Saving namespace"""

    files = {"file": ("hdfs_sample.log", log_content, "text/plain")}

    print_info(f"POST {BASE_URL}/analyze")
    response = requests.post(f"{BASE_URL}/analyze", files=files)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"\nReal-world Format Results:")
    print(f"  Sequences: {data['total_sequences']}")
    print(f"  Anomalies: {data['anomalies_detected']}")
    print(f"  Summary: {data['summary']}")

    if data["anomalies_detected"] > 0:
        print(f"\n  Sample Anomaly:")
        anomaly = data["results"][0]
        print(f"    Confidence: {anomaly['confidence']:.2%}")
        print(f"    Severity: {anomaly['severity']}")
        print(f"    Explanation: {anomaly['explanation']}")


tester.test_endpoint("Real-world Log Format", test_real_world_format)

print_header("FINAL RESULTS")
tester.print_summary()

results_file = Path("test_results.json")
with open(results_file, "w") as f:
    json.dump(
        {
            "timestamp": datetime.now().isoformat(),
            "results": tester.results,
            "base_url": BASE_URL,
        },
        f,
        indent=2,
    )

print(f"\n{COLORS['BLUE']}Results saved to: {results_file}{COLORS['END']}")
