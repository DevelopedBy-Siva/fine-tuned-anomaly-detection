from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import logging
import os
from datetime import datetime
import requests
from collections import deque
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Log Server")


def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


ANALYZER_URL = os.getenv("ANALYZER_URL")
API_KEY = os.getenv("LOGSHIPPER_API_KEY")

cors_origins = os.getenv("CORS_ORIGINS")
origins = [origin.strip() for origin in cors_origins.split(",") if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log_generator = None


class ErrorPatterns:

    @staticmethod
    def database_timeout():
        timeout = random.choice([30, 45, 60])
        db_host = random.choice(["db-primary-1", "db-replica-2", "db-analytics"])
        return f"Database connection timeout after {timeout}s connecting to {db_host}"

    @staticmethod
    def null_pointer():
        user_id = random.randint(1000, 9999)
        line_num = random.randint(40, 120)
        classes = [
            "com.app.service.UserService",
            "com.app.repository.OrderRepository",
            "com.app.controller.PaymentController",
        ]
        cls = random.choice(classes)
        return f"NullPointerException: user_id={user_id} at {cls}.process({cls.split('.')[-1]}.java:{line_num})"

    @staticmethod
    def redis_connection():
        errors = [
            "Redis connection failed: Connection refused (localhost:6379)",
            "Redis timeout: Command timed out after 5000ms",
            "Redis READONLY: You can't write against a read only replica",
        ]
        return random.choice(errors)

    @staticmethod
    def api_rate_limit():
        user_id = random.randint(1000, 9999)
        api = random.choice(["stripe", "sendgrid", "twilio", "aws-s3"])
        return f"API rate limit exceeded for {api} (user_id={user_id})"

    @staticmethod
    def payment_failed():
        order_id = f"ORD-{random.randint(100000, 999999)}"
        reasons = [
            "InvalidCardException: Card declined",
            "InsufficientFundsException: Insufficient funds",
            "ExpiredCardException: Card expired",
            "SecurityCodeMismatch: CVV verification failed",
        ]
        error = random.choice(reasons)
        return f"Payment processing failed for {order_id}: {error}"

    @staticmethod
    def file_not_found():
        upload_id = random.randint(10000, 99999)
        ext = random.choice([".jpg", ".pdf", ".csv", ".xml"])
        return f"File not found: /tmp/upload_{upload_id}{ext}"

    @staticmethod
    def memory_error():
        heap_mb = random.randint(1800, 2048)
        return f"OutOfMemoryError: Java heap space (used: {heap_mb}MB / max: 2048MB)"

    @staticmethod
    def auth_failed():
        token = "".join(random.choices("abcdef0123456789", k=16))
        reason = random.choice(
            [
                "Token expired",
                "Invalid signature",
                "Token revoked",
                "Insufficient permissions",
            ]
        )
        return f"Authentication failed: {reason} (token={token})"

    @staticmethod
    def external_service_down():
        service = random.choice(
            [
                "email-service.internal:8080",
                "notification-service.internal:9000",
                "analytics-service.internal:8081",
            ]
        )
        code = random.choice([500, 502, 503, 504])
        return f"External service unavailable: {service} returned HTTP {code}"

    @staticmethod
    def sql_syntax_error():
        table = random.choice(["users", "orders", "products", "payments"])
        return f"SQLSyntaxError: Table '{table}_temp_{random.randint(1,999)}' doesn't exist"


ERROR_GENERATORS = [
    ErrorPatterns.database_timeout,
    ErrorPatterns.null_pointer,
    ErrorPatterns.redis_connection,
    ErrorPatterns.api_rate_limit,
    ErrorPatterns.payment_failed,
    ErrorPatterns.file_not_found,
    ErrorPatterns.memory_error,
    ErrorPatterns.auth_failed,
    ErrorPatterns.external_service_down,
    ErrorPatterns.sql_syntax_error,
]

ERROR_RATE = 0.15
SLOW_REQUEST_RATE = 0.05


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

    def __init__(self, analyzer_url, api_key):
        self.analyzer_url = analyzer_url
        self.api_key = api_key
        self.running = False
        self.log_buffer = deque(maxlen=20)

        self.stats = {
            "logs_generated": 0,
            "logs_shipped": 0,
            "incidents_created": 0,
            "incidents_updated": 0,
        }

        self.logger = self._setup_logger()

    def _setup_logger(self):
        logger = logging.getLogger("log-generator")
        logger.setLevel(logging.INFO)
        logger.handlers = []

        handler = InMemoryHandler(self.log_buffer)
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)

        return logger

    async def run(self, duration=300):
        self.running = True
        self.stats = {
            "logs_generated": 0,
            "logs_shipped": 0,
            "incidents_created": 0,
            "incidents_updated": 0,
        }

        print(f"[LOG-SERVER] Starting generation for {duration}s")

        start_time = asyncio.get_event_loop().time()

        try:
            while (
                self.running and asyncio.get_event_loop().time() - start_time < duration
            ):

                for _ in range(3):
                    self.generate_log()

                if len(self.log_buffer) >= 10:
                    await self.ship_logs()

                await asyncio.sleep(1)

            if self.log_buffer:
                await self.ship_logs()

            self.running = False
            print(f"[LOG-SERVER] Finished. Stats: {self.stats}")

        except asyncio.CancelledError:
            self.running = False
            print("[LOG-SERVER] Cancelled")

    def generate_log(self):
        self.stats["logs_generated"] += 1

        if random.random() < ERROR_RATE:
            self.logger.error(random.choice(ERROR_GENERATORS)())

        elif random.random() < SLOW_REQUEST_RATE:
            delay = random.uniform(2, 5)
            self.logger.warning(f"Slow request detected: {delay:.2f}s")

        else:
            endpoints = [
                "User lookup: user_id={}",
                "Order created: ORD-{}",
                "File uploaded: upload_id={}",
                "Cache hit: key=cache_key_{}",
                "Health check: OK",
            ]
            msg = random.choice(endpoints).format(random.randint(1000, 9999))
            self.logger.info(msg)

    async def ship_logs(self):
        if not self.log_buffer:
            return

        logs = list(self.log_buffer)
        self.log_buffer.clear()

        try:
            response = requests.post(
                self.analyzer_url,
                json={
                    "source": "log-server",
                    "environment": "prod",
                    "logs": logs,
                },
                headers={"X-API-Key": self.api_key} if self.api_key else {},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()

                self.stats["logs_shipped"] += data.get(
                    "total_logs_processed", len(logs)
                )
                self.stats["incidents_created"] += data.get("incidents_created", 0)
                self.stats["incidents_updated"] += data.get("incidents_updated", 0)

                print(f"[LOG-SERVER] Shipped {len(logs)} logs")

            else:
                self.log_buffer.extend(logs)

        except Exception as e:
            print(f"[LOG-SERVER] Ship failed: {e}")
            self.log_buffer.extend(logs)

    def stop(self):
        self.running = False
        print("[LOG-SERVER] Stopping...")


@app.on_event("startup")
async def startup_event():
    global log_generator
    log_generator = LogGenerator(ANALYZER_URL, API_KEY)
    print("[LOG-SERVER] Initialized")


@app.post("/api/start", dependencies=[Depends(verify_api_key)])
async def start_generation():
    if log_generator.running:
        return {"error": "Already running", "status": "running"}

    asyncio.create_task(log_generator.run(duration=300))

    return {"message": "Log generation started", "status": "running"}


@app.post("/api/stop", dependencies=[Depends(verify_api_key)])
async def stop_generation():
    if not log_generator.running:
        return {"error": "Not running", "status": "idle"}

    log_generator.stop()
    return {"message": "Stopped", "stats": log_generator.stats, "status": "idle"}


@app.get("/api/status", dependencies=[Depends(verify_api_key)])
async def get_status():
    return {
        "status": "running" if log_generator.running else "idle",
        "stats": log_generator.stats,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {
        "service": "log-server",
        "status": "running",
        "endpoints": {
            "start": "POST /api/start",
            "stop": "POST /api/stop",
            "status": "GET /api/status",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
