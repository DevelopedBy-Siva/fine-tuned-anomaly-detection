from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import logging
import os
import json
from datetime import datetime
from collections import deque
from dotenv import load_dotenv
import redis.asyncio as aioredis

load_dotenv()

app = FastAPI(title="Log Server")

API_KEY = os.getenv("LOGSHIPPER_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")
STREAM_KEY = os.getenv("STREAM_KEY", "logs:stream")
STREAM_MAXLEN = 10_000

cors_origins = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_redis_client = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        if not REDIS_URL:
            raise RuntimeError("REDIS_URL environment variable not set")
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Error patterns — each class/method name is DISTINCT so the signature
# generator produces a different signature per error type, creating more
# unique incidents instead of collapsing everything into 1.
# ---------------------------------------------------------------------------

class ErrorPatterns:

    # --- Database errors (distinct subtypes) ---
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
        return f"ConnectionPoolExhaustedError: All {random.choice([10,20,50])} connections in use — request queued"

    @staticmethod
    def db_replication_lag():
        lag = random.randint(5, 60)
        return f"ReplicationLagWarning: Replica is {lag}s behind primary — read consistency degraded"

    # --- Auth / Session errors ---
    @staticmethod
    def auth_token_expired():
        return f"TokenExpiredError: JWT expired at {datetime.utcnow().strftime('%H:%M:%S')} — user forced to re-login"

    @staticmethod
    def auth_invalid_signature():
        return f"InvalidSignatureError: JWT signature verification failed — possible token tampering detected"

    @staticmethod
    def auth_rate_limited():
        ip = f"192.168.{random.randint(1,254)}.{random.randint(1,254)}"
        return f"RateLimitExceeded: Too many login attempts from {ip} — blocked for 15 minutes"

    @staticmethod
    def session_store_unavailable():
        return f"SessionStoreError: Redis session store unreachable — falling back to stateless mode"

    # --- Payment errors ---
    @staticmethod
    def payment_gateway_timeout():
        gateway = random.choice(["Stripe", "PayPal", "Braintree", "Adyen"])
        return f"PaymentGatewayTimeout: {gateway} did not respond within 10s — transaction aborted"

    @staticmethod
    def payment_card_declined():
        code = random.choice(["insufficient_funds", "card_expired", "do_not_honor", "lost_card"])
        return f"CardDeclinedError: Payment declined — reason: {code}"

    @staticmethod
    def payment_fraud_detected():
        return f"FraudDetectionAlert: Transaction flagged by risk engine — score exceeded threshold"

    @staticmethod
    def payment_double_charge():
        return f"IdempotencyViolation: Duplicate payment request detected — second charge blocked"

    # --- Service / infra errors ---
    @staticmethod
    def service_unavailable():
        svc = random.choice([
            "email-service", "notification-service",
            "recommendation-engine", "search-service",
            "analytics-pipeline", "image-processor",
        ])
        return f"ServiceUnavailableError: {svc} returned 503 after 3 retries — circuit breaker opened"

    @staticmethod
    def message_queue_full():
        queue = random.choice(["email-queue", "sms-queue", "webhook-queue", "export-queue"])
        depth = random.randint(10000, 99999)
        return f"QueueDepthCritical: {queue} has {depth} pending messages — consumer lag growing"

    @staticmethod
    def cache_stampede():
        key = random.choice(["product-catalog", "user-permissions", "config-flags", "pricing-table"])
        return f"CacheStampedeDetected: Cache miss storm on key '{key}' — {random.randint(50,500)} simultaneous DB queries"

    @staticmethod
    def disk_space_critical():
        mount = random.choice(["/var/log", "/data", "/tmp", "/var/lib/postgresql"])
        pct = random.randint(90, 99)
        return f"DiskSpaceCritical: {mount} is {pct}% full — write operations may fail"

    # --- Application errors ---
    @staticmethod
    def null_pointer():
        cls = random.choice([
            "UserService.getProfile",
            "OrderRepository.findById",
            "PaymentController.process",
            "CartService.checkout",
            "NotificationService.send",
            "ReportGenerator.build",
        ])
        return f"NullPointerException: Unexpected null reference in {cls}() at line {random.randint(40, 300)}"

    @staticmethod
    def stack_overflow():
        cls = random.choice(["TreeParser", "RecursiveResolver", "XmlDeserializer", "GraphTraversal"])
        return f"StackOverflowError: Maximum call depth exceeded in {cls} — possible circular reference"

    @staticmethod
    def out_of_memory():
        heap_mb = random.randint(1900, 2048)
        return f"OutOfMemoryError: Java heap space exhausted ({heap_mb}MB/2048MB) — GC overhead limit exceeded"

    @staticmethod
    def unhandled_exception():
        exc = random.choice([
            "IndexOutOfBoundsException",
            "ClassCastException",
            "IllegalStateException",
            "ConcurrentModificationException",
            "NumberFormatException",
        ])
        return f"UnhandledException: {exc} propagated to global handler — request returned 500"

    # --- Data / integration errors ---
    @staticmethod
    def data_validation_failed():
        field = random.choice(["email", "phone_number", "postal_code", "tax_id", "iban"])
        return f"ValidationError: Field '{field}' failed schema validation — data rejected"

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
        return f"CSVParseError: Malformed row at line {random.randint(100,9999)} — unexpected column count"

    # --- Security ---
    @staticmethod
    def sql_injection_attempt():
        return f"SecurityAlert: SQL injection pattern detected in request — query blocked and IP flagged"

    @staticmethod
    def xss_attempt():
        return f"SecurityAlert: XSS payload detected in user input — sanitization applied, incident logged"

    @staticmethod
    def brute_force_detected():
        endpoint = random.choice(["/api/login", "/api/reset-password", "/api/verify-otp"])
        return f"BruteForceDetected: {random.randint(50,500)} failed attempts on {endpoint} in 60s"

        # --- Unknown / no runbook — triggers LLM analysis ---
    @staticmethod
    def kubernetes_oom_kill():
        pod = random.choice(["api-server-7d9f", "worker-node-3b2c", "scheduler-pod-1a4e"])
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
        reason = random.choice(["ping timeout", "transport close", "server namespace disconnect"])
        return f"WebSocketError: Connection dropped for user {user_id} — reason: {reason}"

    @staticmethod
    def feature_flag_service_timeout():
        flag = random.choice(["checkout-v2", "new-pricing-engine", "dark-mode-rollout", "ab-test-homepage"])
        return f"FeatureFlagTimeout: Failed to evaluate flag '{flag}' — defaulting to off, service unreachable"

    @staticmethod
    def cdn_origin_pull_failed():
        asset = random.choice(["/static/js/main.chunk.js", "/static/css/app.css", "/images/hero-banner.webp"])
        return f"CDNOriginError: Origin pull failed for {asset} — 502 from origin, serving stale cache"

ERROR_GENERATORS = [
    # database
    ErrorPatterns.db_connection_timeout,
    ErrorPatterns.db_deadlock,
    ErrorPatterns.db_pool_exhausted,
    ErrorPatterns.db_replication_lag,
    # auth
    ErrorPatterns.auth_token_expired,
    ErrorPatterns.auth_invalid_signature,
    ErrorPatterns.auth_rate_limited,
    ErrorPatterns.session_store_unavailable,
    # payment
    ErrorPatterns.payment_gateway_timeout,
    ErrorPatterns.payment_card_declined,
    ErrorPatterns.payment_fraud_detected,
    ErrorPatterns.payment_double_charge,
    # infra
    ErrorPatterns.service_unavailable,
    ErrorPatterns.message_queue_full,
    ErrorPatterns.cache_stampede,
    ErrorPatterns.disk_space_critical,
    # app
    ErrorPatterns.null_pointer,
    ErrorPatterns.stack_overflow,
    ErrorPatterns.out_of_memory,
    ErrorPatterns.unhandled_exception,
    # data
    ErrorPatterns.data_validation_failed,
    ErrorPatterns.api_schema_mismatch,
    ErrorPatterns.file_upload_failed,
    ErrorPatterns.csv_parse_error,
    # security
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

# high rates for demo — lots of visible incidents quickly
ERROR_RATE = 0.20
SLOW_REQUEST_RATE = 0.10


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
        self.log_buffer = deque(maxlen=20)
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

    async def start(self, duration=300):
        async with self._lock:
            if self.running:
                return False, "Already running"
            self._stop_event.clear()
            self.stats = {k: 0 for k in self.stats}
            self.last_error = None
            self._task = asyncio.create_task(self._run(duration))
            print(f"[LOG-SERVER] Started — {duration}s → '{STREAM_KEY}'")
            return True, "started"

    async def stop(self):
        async with self._lock:
            if not self.running:
                return False, "Not running"
            self._stop_event.set()
        # wait up to 5s for the task to exit cleanly, then cancel
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._task.cancel()
        print("[LOG-SERVER] Stopped")
        return True, "stopped"

    async def _run(self, duration=300):
        print(f"[LOG-SERVER] Running for {duration}s")
        start_time = asyncio.get_event_loop().time()
        try:
            while not self._stop_event.is_set():
                if asyncio.get_event_loop().time() - start_time >= duration:
                    break
                self._generate_log()
                if self.log_buffer:
                    await self._push_to_stream()
                # sleep 3s but wake immediately if stop_event fires
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass

            # flush remaining buffer on clean exit
            if self.log_buffer and not self._stop_event.is_set():
                await self._push_to_stream()

            print(f"[LOG-SERVER] Finished. Stats: {self.stats}")
        except asyncio.CancelledError:
            print("[LOG-SERVER] Task cancelled")

    def _generate_log(self):
        self.stats["logs_generated"] += 1
        if random.random() < ERROR_RATE:
            self.logger.error(random.choice(ERROR_GENERATORS)())
        elif random.random() < SLOW_REQUEST_RATE:
            svc = random.choice(["checkout", "search", "auth", "upload", "report"])
            delay = random.uniform(2, 8)
            self.logger.warning(f"SlowRequestWarning: {svc} endpoint took {delay:.2f}s — SLA breach")
        else:
            endpoints = [
                "GET /api/users/{} 200 12ms",
                "POST /api/orders/{} 201 45ms",
                "GET /api/products/{} 200 8ms",
                "PUT /api/cart/{} 200 23ms",
                "GET /health 200 1ms",
            ]
            self.logger.info(random.choice(endpoints).format(random.randint(1000, 9999)))

    async def _push_to_stream(self):
        if not self.log_buffer:
            return

        logs = list(self.log_buffer)
        self.log_buffer.clear()

        try:
            r = await get_redis()
            await r.xadd(
                STREAM_KEY,
                {
                    "api_key": API_KEY or "",
                    "source": "log-server",
                    "environment": "prod",
                    "logs": json.dumps(logs),
                },
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
            self.stats["logs_shipped"] += len(logs)
            self.stats["batches_pushed"] += 1
            self.last_push_at = datetime.utcnow().isoformat()
            print(f"[LOG-SERVER] Pushed {len(logs)} logs to stream")

        except Exception as e:
            err = str(e)
            print(f"[LOG-SERVER] Stream push failed: {err}")
            self.last_error = err
            self.stats["push_errors"] += 1
            self.log_buffer.extendleft(reversed(logs))


log_generator = None


@app.on_event("startup")
async def startup_event():
    global log_generator
    log_generator = LogGenerator()
    try:
        r = await get_redis()
        await r.ping()
        print(f"[LOG-SERVER] Redis connected. Stream key: '{STREAM_KEY}'")
    except Exception as e:
        print(f"[LOG-SERVER] WARNING: Redis not reachable on startup: {e}")


@app.post("/api/start", dependencies=[Depends(verify_api_key)])
async def start_generation():
    ok, msg = await log_generator.start(duration=300)
    status = "running" if ok else "running"  # already running is still running
    return {"message": msg, "status": log_generator.running and "running" or "idle", "stream": STREAM_KEY}


@app.post("/api/stop", dependencies=[Depends(verify_api_key)])
async def stop_generation():
    ok, msg = await log_generator.stop()
    return {"message": msg, "stats": log_generator.stats, "status": "idle"}


@app.get("/api/status", dependencies=[Depends(verify_api_key)])
async def get_status():
    return {
        "status": "running" if log_generator.running else "idle",
        "stats": log_generator.stats,
        "last_push_at": log_generator.last_push_at,
        "last_error": log_generator.last_error,
        "stream": STREAM_KEY,
    }


@app.get("/health")
async def health():
    redis_ok = False
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass
    return {"status": "healthy", "redis": "connected" if redis_ok else "disconnected"}


@app.get("/")
async def root():
    return {
        "service": "log-server",
        "status": "running",
        "transport": "redis-stream",
        "stream_key": STREAM_KEY,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)