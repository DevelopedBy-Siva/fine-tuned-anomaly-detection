from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import logging
import os
from datetime import datetime
from typing import Set
import requests
from collections import deque

app = FastAPI(title="Log Server")


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
connected_clients: Set[WebSocket] = set()


class ErrorPatterns:
    """Realistic error patterns that occur in production systems"""

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
        extensions = [".jpg", ".pdf", ".csv", ".xml"]
        ext = random.choice(extensions)
        return f"File not found: /tmp/upload_{upload_id}{ext}"

    @staticmethod
    def memory_error():
        heap_mb = random.randint(1800, 2048)
        return f"OutOfMemoryError: Java heap space (used: {heap_mb}MB / max: 2048MB)"

    @staticmethod
    def auth_failed():
        token = "".join(random.choices("abcdef0123456789", k=16))
        reasons = [
            "Token expired",
            "Invalid signature",
            "Token revoked",
            "Insufficient permissions",
        ]
        reason = random.choice(reasons)
        return f"Authentication failed: {reason} (token={token})"

    @staticmethod
    def external_service_down():
        services = [
            "email-service.internal:8080",
            "notification-service.internal:9000",
            "analytics-service.internal:8081",
        ]
        service = random.choice(services)
        codes = [500, 502, 503, 504]
        code = random.choice(codes)
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
    """Custom formatter with ISO timestamps"""

    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        log_line = f"[{timestamp}] {record.levelname}: {record.getMessage()}"
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"
        return log_line


class LogGenerator:
    """
    Generates logs and ships them to analyzer
    All in one process
    """

    def __init__(self, analyzer_url: str, api_key: str):
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
        """Setup in-memory logger"""
        logger = logging.getLogger("log-generator")
        logger.setLevel(logging.INFO)
        logger.handlers = []

        handler = InMemoryHandler(self.log_buffer)
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)

        return logger

    async def run(self, duration: int = 300):
        """
        Generate logs for specified duration
        3 requests per second, ships logs every 10
        """
        self.running = True
        self.stats = {
            "logs_generated": 0,
            "logs_shipped": 0,
            "incidents_created": 0,
            "incidents_updated": 0,
        }

        print(f"[LOG-SERVER] Starting log generation for {duration}s")
        await broadcast_to_clients(
            {"type": "status", "status": "running", "message": "Log generation started"}
        )

        start_time = asyncio.get_event_loop().time()

        try:
            while (
                self.running and asyncio.get_event_loop().time() - start_time < duration
            ):
                for _ in range(3):
                    await self.generate_log()

                if len(self.log_buffer) >= 10:
                    await self.ship_logs()

                await asyncio.sleep(1)

            if self.log_buffer:
                await self.ship_logs()

            self.running = False

            print(f"[LOG-SERVER] Generation complete. Stats: {self.stats}")
            await broadcast_to_clients({"type": "complete", "stats": self.stats})

        except asyncio.CancelledError:
            print(f"[LOG-SERVER] Stopped by user")
            self.running = False

            await broadcast_to_clients(
                {
                    "type": "stopped",
                    "message": "Log generation stopped",
                    "stats": self.stats,
                }
            )

    async def generate_log(self):
        """Generate a single log entry"""
        self.stats["logs_generated"] += 1

        if random.random() < ERROR_RATE:
            error_gen = random.choice(ERROR_GENERATORS)
            error_msg = error_gen()
            self.logger.error(error_msg)

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

        if self.stats["logs_generated"] % 10 == 0:
            await broadcast_to_clients({"type": "stats", "stats": self.stats})

    async def ship_logs(self):
        """Ship buffered logs to analyzer"""
        if not self.log_buffer:
            return

        logs = list(self.log_buffer)
        self.log_buffer.clear()

        try:
            response = requests.post(
                self.analyzer_url,
                json={"source": "log-server", "environment": "prod", "logs": logs},
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

                print(
                    f"[LOG-SERVER] Shipped {len(logs)} logs | "
                    f"Created: {data.get('incidents_created', 0)} | "
                    f"Updated: {data.get('incidents_updated', 0)}"
                )
            else:
                print(f"[LOG-SERVER] Analyzer returned {response.status_code}")
                self.log_buffer.extend(logs)

        except requests.exceptions.ConnectionError:
            print(f"[LOG-SERVER] Cannot connect to analyzer: {self.analyzer_url}")
            self.log_buffer.extend(logs)

        except Exception as e:
            print(f"[LOG-SERVER] Ship failed: {e}")
            self.log_buffer.extend(logs)

    def stop(self):
        """Stop log generation"""
        self.running = False
        print(f"[LOG-SERVER] Stopping...")


class InMemoryHandler(logging.Handler):
    """Logging handler that captures logs in memory"""

    def __init__(self, buffer: deque):
        super().__init__()
        self.buffer = buffer

    def emit(self, record):
        log_entry = self.format(record)
        self.buffer.append(log_entry)


async def broadcast_to_clients(message: dict):
    """Send message to all connected WebSocket clients"""
    disconnected = set()

    for client in connected_clients:
        try:
            await client.send_json(message)
        except:
            disconnected.add(client)

    for client in disconnected:
        connected_clients.discard(client)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    global log_generator
    log_generator = LogGenerator(ANALYZER_URL, API_KEY)
    print(f"[LOG-SERVER] Initialized")
    print(f"[LOG-SERVER] Analyzer URL: {ANALYZER_URL}")


@app.post("/api/start")
async def start_generation():
    """Start log generation"""
    global log_generator

    if log_generator.running:
        return {"error": "Log generation is already running", "status": "running"}, 409

    asyncio.create_task(log_generator.run(duration=300))

    return {
        "message": "Log generation started",
        "duration": "5 minutes",
        "analyzer_url": ANALYZER_URL,
    }


@app.post("/api/stop")
async def stop_generation():
    """Stop log generation"""
    global log_generator

    if not log_generator.running:
        return {"error": "No log generation is running", "status": "idle"}, 400

    log_generator.stop()

    return {"message": "Log generation stopped", "stats": log_generator.stats}


@app.get("/api/status")
async def get_status():
    """Get current status"""
    global log_generator

    return {
        "status": "running" if log_generator.running else "idle",
        "stats": log_generator.stats,
        "analyzer_url": ANALYZER_URL,
        "error_rate": f"{ERROR_RATE * 100}%",
        "slow_request_rate": f"{SLOW_REQUEST_RATE * 100}%",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    connected_clients.add(websocket)

    global log_generator

    try:
        await websocket.send_json(
            {
                "type": "status",
                "status": "running" if log_generator.running else "idle",
                "stats": log_generator.stats,
            }
        )

        while True:
            await asyncio.sleep(1)

            if log_generator.running:
                await websocket.send_json(
                    {"type": "stats", "stats": log_generator.stats}
                )

    except WebSocketDisconnect:
        print("[LOG-SERVER] Client disconnected")
    except Exception as e:
        print(f"[LOG-SERVER] WebSocket error: {e}")
    finally:
        connected_clients.discard(websocket)
        try:
            await websocket.close()
        except:
            pass


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "Log Server",
        "running": log_generator.running if log_generator else False,
    }


@app.get("/")
async def root():
    """Service info"""
    return {
        "service": "log-server",
        "status": "running",
        "endpoints": {
            "start": "POST /api/start",
            "stop": "POST /api/stop",
            "status": "GET /api/status",
            "websocket": "WS /ws",
        },
        "config": {
            "analyzer_url": ANALYZER_URL,
            "error_rate": f"{ERROR_RATE * 100}%",
            "slow_request_rate": f"{SLOW_REQUEST_RATE * 100}%",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
