import asyncio
import base64
import json
import logging
import os
import random
import time
from collections import deque
from datetime import datetime, UTC

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

LOKI_URL = os.getenv("LOKI_URL", "")
LOKI_USERNAME = os.getenv("LOKI_USERNAME", "")
LOKI_API_KEY = os.getenv("LOKI_API_KEY", "")
SERVICE_NAME = os.getenv("LOG_SERVICE_NAME", "log-server")
print(LOKI_API_KEY)

cors_origins = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app = FastAPI(title="Log Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _loki_auth_header() -> str:
    """Basic auth header for Grafana Cloud Loki."""
    token = base64.b64encode(f"{LOKI_USERNAME}:{LOKI_API_KEY}".encode()).decode()
    return f"Basic {token}"


async def push_to_loki(lines: list[str], extra_labels: dict | None = None) -> bool:
    """
    Push a list of log lines to Loki in a single HTTP request
    """
    if not LOKI_URL or not LOKI_USERNAME or not LOKI_API_KEY:
        print("[LOKI] Credentials not set — dropping logs")
        return False

    labels = {"service": SERVICE_NAME, "env": "prod"}
    if extra_labels:
        labels.update(extra_labels)

    now_ns = str(int(time.time() * 1_000_000_000))
    values = [[now_ns, line] for line in lines]

    payload = {
        "streams": [
            {
                "stream": labels,
                "values": values,
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{LOKI_URL}/loki/api/v1/push",
                headers={
                    "Authorization": _loki_auth_header(),
                    "Content-Type": "application/json",
                },
                content=json.dumps(payload),
            )
            if response.status_code == 204:
                return True
            print(f"[LOKI] Push failed: {response.status_code} — {response.text}")
            return False
    except Exception as e:
        print(f"[LOKI] Push exception: {e}")
        return False


class ErrorPatterns:

    @staticmethod
    def db_connection_timeout():
        host = random.choice(["db-primary-1", "db-replica-2", "db-analytics-3"])
        return f"DatabaseConnectionError: Connection timeout after 30s to {host}:5432"

    @staticmethod
    def db_deadlock():
        table = random.choice(["orders", "payments", "inventory", "sessions"])
        return f"DeadlockException: Transaction deadlock detected on table '{table}' — rolled back"

    @staticmethod
    def db_pool_exhausted():
        return f"ConnectionPoolExhaustedError: All {random.choice([10, 20, 50])} connections in use — request queued"

    @staticmethod
    def db_replication_lag():
        lag = random.randint(5, 60)
        return f"ReplicationLagWarning: Replica is {lag}s behind primary — read consistency degraded"

    @staticmethod
    def auth_token_expired():
        return f"TokenExpiredError: JWT expired at {datetime.now(UTC).strftime('%H:%M:%S')} — user forced to re-login"

    @staticmethod
    def auth_invalid_signature():
        return "InvalidSignatureError: JWT signature verification failed — possible token tampering detected"

    @staticmethod
    def auth_rate_limited():
        ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
        return f"RateLimitExceeded: Too many login attempts from {ip} — blocked for 15 minutes"

    @staticmethod
    def session_store_unavailable():
        return "SessionStoreError: Redis session store unreachable — falling back to stateless mode"

    @staticmethod
    def payment_gateway_timeout():
        gateway = random.choice(["Stripe", "PayPal", "Braintree", "Adyen"])
        return f"PaymentGatewayTimeout: {gateway} did not respond within 10s — transaction aborted"

    @staticmethod
    def payment_card_declined():
        code = random.choice(
            ["insufficient_funds", "card_expired", "do_not_honor", "lost_card"]
        )
        return f"CardDeclinedError: Payment declined — reason: {code}"

    @staticmethod
    def payment_fraud_detected():
        return "FraudDetectionAlert: Transaction flagged by risk engine — score exceeded threshold"

    @staticmethod
    def payment_double_charge():
        return "IdempotencyViolation: Duplicate payment request detected — second charge blocked"

    @staticmethod
    def service_unavailable():
        svc = random.choice(
            [
                "email-service",
                "notification-service",
                "recommendation-engine",
                "search-service",
                "analytics-pipeline",
                "image-processor",
            ]
        )
        return f"ServiceUnavailableError: {svc} returned 503 after 3 retries — circuit breaker opened"

    @staticmethod
    def message_queue_full():
        queue = random.choice(
            ["email-queue", "sms-queue", "webhook-queue", "export-queue"]
        )
        depth = random.randint(10000, 99999)
        return f"QueueDepthCritical: {queue} has {depth} pending messages — consumer lag growing"

    @staticmethod
    def cache_stampede():
        key = random.choice(
            ["product-catalog", "user-permissions", "config-flags", "pricing-table"]
        )
        return f"CacheStampedeDetected: Cache miss storm on key '{key}' — {random.randint(50, 500)} simultaneous DB queries"

    @staticmethod
    def disk_space_critical():
        mount = random.choice(["/var/log", "/data", "/tmp", "/var/lib/postgresql"])
        pct = random.randint(90, 99)
        return f"DiskSpaceCritical: {mount} is {pct}% full — write operations may fail"

    @staticmethod
    def null_pointer():
        cls = random.choice(
            [
                "UserService.getProfile",
                "OrderRepository.findById",
                "PaymentController.process",
                "CartService.checkout",
                "NotificationService.send",
                "ReportGenerator.build",
            ]
        )
        return f"NullPointerException: Unexpected null reference in {cls}() at line {random.randint(40, 300)}"

    @staticmethod
    def stack_overflow():
        cls = random.choice(
            ["TreeParser", "RecursiveResolver", "XmlDeserializer", "GraphTraversal"]
        )
        return f"StackOverflowError: Maximum call depth exceeded in {cls} — possible circular reference"

    @staticmethod
    def out_of_memory():
        heap_mb = random.randint(1900, 2048)
        return f"OutOfMemoryError: Java heap space exhausted ({heap_mb}MB/2048MB) — GC overhead limit exceeded"

    @staticmethod
    def unhandled_exception():
        exc = random.choice(
            [
                "IndexOutOfBoundsException",
                "ClassCastException",
                "IllegalStateException",
                "ConcurrentModificationException",
                "NumberFormatException",
            ]
        )
        return f"UnhandledException: {exc} propagated to global handler — request returned 500"

    @staticmethod
    def data_validation_failed():
        field = random.choice(
            ["email", "phone_number", "postal_code", "tax_id", "iban"]
        )
        return (
            f"ValidationError: Field '{field}' failed schema validation — data rejected"
        )

    @staticmethod
    def api_schema_mismatch():
        api = random.choice(["Salesforce", "HubSpot", "Shopify", "Twilio", "SendGrid"])
        return f"SchemaMismatchError: {api} API response shape changed — expected field missing in response"

    @staticmethod
    def file_upload_failed():
        ext = random.choice([".pdf", ".csv", ".xlsx", ".zip", ".jpg"])
        return f"FileUploadError: Failed to write {ext} to object storage — S3 returned 500"

    @staticmethod
    def csv_parse_error():
        return f"CSVParseError: Malformed row at line {random.randint(100, 9999)} — unexpected column count"

    @staticmethod
    def sql_injection_attempt():
        return "SecurityAlert: SQL injection pattern detected in request — query blocked and IP flagged"

    @staticmethod
    def xss_attempt():
        return "SecurityAlert: XSS payload detected in user input — sanitization applied, incident logged"

    @staticmethod
    def brute_force_detected():
        endpoint = random.choice(
            ["/api/login", "/api/reset-password", "/api/verify-otp"]
        )
        return f"BruteForceDetected: {random.randint(50, 500)} failed attempts on {endpoint} in 60s"

    @staticmethod
    def kubernetes_oom_kill():
        pod = random.choice(
            ["api-server-7d9f", "worker-node-3b2c", "scheduler-pod-1a4e"]
        )
        return f"OOMKilled: Container {pod} exceeded memory limit and was killed by the kernel"

    @staticmethod
    def grpc_deadline_exceeded():
        svc = random.choice(["inventory-grpc", "pricing-grpc", "shipping-grpc"])
        return f"DeadlineExceeded: gRPC call to {svc} timed out after 5000ms — context cancelled by client"

    @staticmethod
    def elasticsearch_shard_failure():
        index = random.choice(["logs-2024", "products-v3", "users-search"])
        return f"ShardFailureException: Primary shard for index '{index}' unavailable — search results degraded"

    @staticmethod
    def websocket_connection_dropped():
        user_id = random.randint(10000, 99999)
        reason = random.choice(
            ["ping timeout", "transport close", "server namespace disconnect"]
        )
        return (
            f"WebSocketError: Connection dropped for user {user_id} — reason: {reason}"
        )

    @staticmethod
    def feature_flag_service_timeout():
        flag = random.choice(
            [
                "checkout-v2",
                "new-pricing-engine",
                "dark-mode-rollout",
                "ab-test-homepage",
            ]
        )
        return f"FeatureFlagTimeout: Failed to evaluate flag '{flag}' — defaulting to off, service unreachable"

    @staticmethod
    def cdn_origin_pull_failed():
        asset = random.choice(
            [
                "/static/js/main.chunk.js",
                "/static/css/app.css",
                "/images/hero-banner.webp",
            ]
        )
        return f"CDNOriginError: Origin pull failed for {asset} — 502 from origin, serving stale cache"


ERROR_GENERATORS = [
    ErrorPatterns.db_connection_timeout,
    ErrorPatterns.db_deadlock,
    ErrorPatterns.db_pool_exhausted,
    ErrorPatterns.db_replication_lag,
    ErrorPatterns.auth_token_expired,
    ErrorPatterns.auth_invalid_signature,
    ErrorPatterns.auth_rate_limited,
    ErrorPatterns.session_store_unavailable,
    ErrorPatterns.payment_gateway_timeout,
    ErrorPatterns.payment_card_declined,
    ErrorPatterns.payment_fraud_detected,
    ErrorPatterns.payment_double_charge,
    ErrorPatterns.service_unavailable,
    ErrorPatterns.message_queue_full,
    ErrorPatterns.cache_stampede,
    ErrorPatterns.disk_space_critical,
    ErrorPatterns.null_pointer,
    ErrorPatterns.stack_overflow,
    ErrorPatterns.out_of_memory,
    ErrorPatterns.unhandled_exception,
    ErrorPatterns.data_validation_failed,
    ErrorPatterns.api_schema_mismatch,
    ErrorPatterns.file_upload_failed,
    ErrorPatterns.csv_parse_error,
    ErrorPatterns.sql_injection_attempt,
    ErrorPatterns.xss_attempt,
    ErrorPatterns.brute_force_detected,
    ErrorPatterns.kubernetes_oom_kill,
    ErrorPatterns.grpc_deadline_exceeded,
    ErrorPatterns.elasticsearch_shard_failure,
    ErrorPatterns.websocket_connection_dropped,
    ErrorPatterns.feature_flag_service_timeout,
    ErrorPatterns.cdn_origin_pull_failed,
]

ERROR_RATE = 0.20
SLOW_REQUEST_RATE = 0.10


SCENARIOS = {
    "db_cascade": {
        "description": "DB pool exhaustion → payment timeout → NullPointerException → UnhandledException",
        "steps": [
            {
                "delay_seconds": 0,
                "level": "ERROR",
                "log": "ConnectionPoolExhaustedError: All 20 connections in use — request queued for >30s",
            },
            {
                "delay_seconds": 30,
                "level": "ERROR",
                "log": "PaymentGatewayTimeout: Stripe did not respond within 10s — no DB connection available to log transaction",
            },
            {
                "delay_seconds": 45,
                "level": "ERROR",
                "log": "NullPointerException: Unexpected null reference in PaymentController.process() at line 187 — response object was null after gateway timeout",
            },
            {
                "delay_seconds": 30,
                "level": "ERROR",
                "log": "UnhandledException: IllegalStateException propagated to global handler — order marked failed, request returned 500",
            },
        ],
    },
    "auth_cascade": {
        "description": "Session store failure → JWT invalid signature → rate limiter false positive",
        "steps": [
            {
                "delay_seconds": 0,
                "level": "ERROR",
                "log": "SessionStoreError: Redis session store unreachable — falling back to stateless mode",
            },
            {
                "delay_seconds": 40,
                "level": "ERROR",
                "log": "InvalidSignatureError: JWT signature verification failed — session store unavailable, token cannot be re-validated",
            },
            {
                "delay_seconds": 35,
                "level": "ERROR",
                "log": "RateLimitExceeded: Too many login attempts from 192.168.1.47 — rate limiter state lost, replaying from zero",
            },
        ],
    },
    "deployment_gone_wrong": {
        "description": "Simulates a bad deployment: config change causes memory pressure then OOM",
        "steps": [
            {
                "delay_seconds": 0,
                "level": "INFO",
                "log": "DeploymentStarted: Releasing v2.3.1 — connection pool size changed from 20 to 10",
            },
            {
                "delay_seconds": 20,
                "level": "WARN",
                "log": "ConnectionPoolExhaustedError: All 10 connections in use — request queued (pool was recently halved)",
            },
            {
                "delay_seconds": 30,
                "level": "ERROR",
                "log": "ConnectionPoolExhaustedError: All 10 connections in use — pool exhausted, requests failing",
            },
            {
                "delay_seconds": 20,
                "level": "ERROR",
                "log": "PaymentGatewayTimeout: Stripe did not respond within 10s — DB unavailable",
            },
            {
                "delay_seconds": 15,
                "level": "ERROR",
                "log": "OutOfMemoryError: Java heap space exhausted (2041MB/2048MB) — GC overhead limit exceeded",
            },
        ],
    },
    "memory_leak": {
        "description": "Gradual memory leak cycle — heap grows until OOM kill, then restarts",
        "steps": [
            {
                "delay_seconds": 0,
                "level": "WARN",
                "log": "MemoryPressureWarning: Heap at 71% — GC frequency increasing",
            },
            {
                "delay_seconds": 60,
                "level": "WARN",
                "log": "MemoryPressureWarning: Heap at 83% — GC pause times exceeding 500ms",
            },
            {
                "delay_seconds": 60,
                "level": "ERROR",
                "log": "MemoryPressureWarning: Heap at 94% — GC overhead critical, response times degraded",
            },
            {
                "delay_seconds": 60,
                "level": "ERROR",
                "log": "OOMKilled: Container api-server-7d9f exceeded memory limit and was killed by the kernel",
            },
            {
                "delay_seconds": 5,
                "level": "INFO",
                "log": "ServiceRestarted: api-server-7d9f restarted by orchestrator — heap reset to 0%",
            },
        ],
    },
}


async def _run_scenario(scenario_name: str):
    """Execute a scenario — push each step to Loki with controlled timing."""
    scenario = SCENARIOS[scenario_name]
    steps = scenario["steps"]
    print(f"[SCENARIO] Starting '{scenario_name}' — {len(steps)} steps")

    for i, step in enumerate(steps):
        delay = step["delay_seconds"]
        if delay > 0:
            print(f"[SCENARIO] Step {i+1}/{len(steps)} — waiting {delay}s")
            await asyncio.sleep(delay)

        ts = datetime.now(UTC).isoformat()
        level = step.get("level", "ERROR")
        log_line = f"[{ts}] {level}: {step['log']}"

        success = await push_to_loki(
            [log_line],
            extra_labels={"scenario": scenario_name, "step": str(i + 1)},
        )
        status = "pushed" if success else "FAILED"
        print(f"[SCENARIO] Step {i+1}/{len(steps)} {status}: {log_line[:80]}…")

    print(f"[SCENARIO] '{scenario_name}' complete")


class CustomFormatter(logging.Formatter):
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        return f"[{timestamp}] {record.levelname}: {record.getMessage()}"


class InMemoryHandler(logging.Handler):
    def __init__(self, buffer):
        super().__init__()
        self.buffer = buffer

    def emit(self, record):
        self.buffer.append(self.format(record))


class LogGenerator:

    def __init__(self):
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.log_buffer = deque(maxlen=50)
        self.stats = {
            "logs_generated": 0,
            "logs_shipped": 0,
            "batches_pushed": 0,
            "push_errors": 0,
        }
        self.last_push_at: str | None = None
        self.last_error: str | None = None
        self.logger = self._setup_logger()

    def _setup_logger(self):
        logger = logging.getLogger("log-generator")
        logger.setLevel(logging.INFO)
        logger.handlers = []
        handler = InMemoryHandler(self.log_buffer)
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)
        return logger

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, duration: int = 300):
        async with self._lock:
            if self.running:
                return False, "Already running"
            self._stop_event.clear()
            self.stats = {k: 0 for k in self.stats}
            self.last_error = None
            self._task = asyncio.create_task(self._run(duration))
            print(f"[LOG-SERVER] Started — {duration}s → Loki")
            return True, "started"

    async def stop(self):
        async with self._lock:
            if not self.running:
                return False, "Not running"
            self._stop_event.set()
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._task.cancel()
        print("[LOG-SERVER] Stopped")
        return True, "stopped"

    async def _run(self, duration: int = 300):
        print(f"[LOG-SERVER] Running for {duration}s")
        start_time = asyncio.get_event_loop().time()
        try:
            while not self._stop_event.is_set():
                if asyncio.get_event_loop().time() - start_time >= duration:
                    break
                self._generate_log()
                if self.log_buffer:
                    await self._flush_to_loki()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass

            if self.log_buffer:
                await self._flush_to_loki()

            print(f"[LOG-SERVER] Finished. Stats: {self.stats}")
        except asyncio.CancelledError:
            print("[LOG-SERVER] Task cancelled")

    def _generate_log(self):
        self.stats["logs_generated"] += 1
        rand = random.random()
        if rand < ERROR_RATE:
            self.logger.error(random.choice(ERROR_GENERATORS)())
        elif rand < ERROR_RATE + SLOW_REQUEST_RATE:
            svc = random.choice(["checkout", "search", "auth", "upload", "report"])
            delay = random.uniform(2, 8)
            self.logger.warning(
                f"SlowRequestWarning: {svc} endpoint took {delay:.2f}s — SLA breach"
            )
        else:
            endpoints = [
                "GET /api/users/{} 200 12ms",
                "POST /api/orders/{} 201 45ms",
                "GET /api/products/{} 200 8ms",
                "PUT /api/cart/{} 200 23ms",
                "GET /health 200 1ms",
            ]
            self.logger.info(
                random.choice(endpoints).format(random.randint(1000, 9999))
            )

    async def _flush_to_loki(self):
        if not self.log_buffer:
            return

        logs = list(self.log_buffer)
        self.log_buffer.clear()

        success = await push_to_loki(logs)
        if success:
            self.stats["logs_shipped"] += len(logs)
            self.stats["batches_pushed"] += 1
            self.last_push_at = datetime.now(UTC).isoformat()
            print(f"[LOG-SERVER] Pushed {len(logs)} logs to Loki")
        else:
            self.stats["push_errors"] += 1
            self.last_error = "Loki push failed"
            self.log_buffer.extendleft(reversed(logs))


log_generator: LogGenerator | None = None


@app.on_event("startup")
async def startup_event():
    global log_generator
    log_generator = LogGenerator()

    if not all([LOKI_URL, LOKI_USERNAME, LOKI_API_KEY]):
        print(
            "[LOG-SERVER] WARNING: LOKI_URL / LOKI_USERNAME / LOKI_API_KEY not fully set"
        )
    else:
        ok = await push_to_loki(["[startup] Log server connected to Loki"])
        if ok:
            print(f"[LOG-SERVER] Loki connected at {LOKI_URL}")
        else:
            print(
                "[LOG-SERVER] WARNING: Loki connection test failed — check credentials"
            )


@app.post("/api/start")
async def start_generation(duration: int = 300):
    ok, msg = await log_generator.start(duration=duration)
    return {
        "message": msg,
        "status": "running" if log_generator.running else "idle",
        "transport": "loki",
        "duration_seconds": duration,
    }


@app.post("/api/stop")
async def stop_generation():
    ok, msg = await log_generator.stop()
    return {
        "message": msg,
        "stats": log_generator.stats,
        "status": "idle",
    }


@app.get("/api/status")
async def get_status():
    return {
        "status": "running" if log_generator.running else "idle",
        "stats": log_generator.stats,
        "last_push_at": log_generator.last_push_at,
        "last_error": log_generator.last_error,
        "transport": "loki",
        "loki_url": LOKI_URL,
    }


@app.post("/api/scenario/{scenario_name}")
async def run_scenario(scenario_name: str):
    """
    Fire a correlated error scenario against Loki.
    """
    if scenario_name not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario '{scenario_name}'. Available: {list(SCENARIOS.keys())}",
        )

    asyncio.create_task(_run_scenario(scenario_name))

    scenario = SCENARIOS[scenario_name]
    steps = scenario["steps"]
    total_delay = sum(s["delay_seconds"] for s in steps)
    return {
        "scenario": scenario_name,
        "description": scenario["description"],
        "status": "started",
        "steps": len(steps),
        "estimated_duration_seconds": total_delay,
        "message": (
            f"Scenario '{scenario_name}' is running in the background. "
            f"{len(steps)} log entries will be pushed to Loki over ~{total_delay}s."
        ),
    }


@app.get("/api/scenario")
async def list_scenarios():
    """List all available test scenarios."""
    return {
        "scenarios": {
            name: {
                "description": scenario["description"],
                "steps": len(scenario["steps"]),
                "estimated_duration_seconds": sum(
                    s["delay_seconds"] for s in scenario["steps"]
                ),
            }
            for name, scenario in SCENARIOS.items()
        }
    }


@app.get("/health")
async def health():
    loki_ok = await push_to_loki(["[healthcheck] ping"])
    return {
        "status": "healthy",
        "loki": "connected" if loki_ok else "unreachable",
    }


@app.get("/")
async def root():
    return {
        "service": "log-server",
        "status": "running",
        "transport": "loki",
        "loki_url": LOKI_URL or "not configured",
        "scenarios": list(SCENARIOS.keys()),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
