from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import random
import time
import os

from logger_config import setup_logger
from error_patterns import ERROR_GENERATORS, ErrorPatterns


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Log server starting...")
    logger.info(f"Error rate: {ERROR_RATE * 100}%")
    logger.info(f"Slow request rate: {SLOW_REQUEST_RATE * 100}%")
    logger.info("=" * 60)
    yield
    logger.info("Log server shutting down...")


app = FastAPI(title="log-server", lifespan=lifespan)

cors_origins = os.getenv("CORS_ORIGINS")
origins = [origin.strip() for origin in cors_origins.split(",") if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = setup_logger()

ERROR_RATE = 0.15
SLOW_REQUEST_RATE = 0.05


def maybe_error() -> bool:
    """Randomly trigger an error based on ERROR_RATE"""
    if random.random() < ERROR_RATE:
        error_gen = random.choice(ERROR_GENERATORS)
        error_msg = error_gen()
        logger.error(error_msg)
        return True
    return False


def maybe_slow() -> None:
    """Simulate slow requests"""
    if random.random() < SLOW_REQUEST_RATE:
        delay = random.uniform(2, 5)
        logger.warning(f"Slow request detected: {delay:.2f}s")
        time.sleep(delay)


@app.get("/")
def index():
    logger.info("Index page accessed")
    return {"service": "log-server", "status": "running"}


@app.get("/api/users/{user_id}")
def get_user(user_id: int):
    """Simulate user lookup"""
    maybe_slow()

    if maybe_error():
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    logger.info(f"User lookup: user_id={user_id}")
    return {"user_id": user_id, "name": f"User {user_id}"}


@app.post("/api/orders")
def create_order():
    """Simulate order creation"""
    maybe_slow()

    if random.random() < 0.25:
        error_msg = ErrorPatterns.payment_failed()
        logger.error(error_msg)
        return JSONResponse({"error": "Payment failed"}, status_code=400)

    if maybe_error():
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    order_id = f"ORD-{random.randint(100000, 999999)}"
    logger.info(f"Order created: {order_id}")
    return {"order_id": order_id, "status": "confirmed"}


@app.post("/api/upload")
def upload_file(file: UploadFile = File(None)):
    """Simulate file upload"""
    maybe_slow()

    if random.random() < 0.20:
        error_msg = ErrorPatterns.file_not_found()
        logger.error(error_msg)
        return JSONResponse({"error": "File processing failed"}, status_code=500)

    if maybe_error():
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    upload_id = random.randint(10000, 99999)
    logger.info(f"File uploaded: upload_id={upload_id}")
    return {"upload_id": upload_id, "status": "success"}


@app.get("/api/cache/{key}")
def cache_get(key: str):
    """Simulate cache lookup"""

    if random.random() < 0.10:
        error_msg = ErrorPatterns.redis_connection()
        logger.error(error_msg)
        return JSONResponse({"error": "Cache unavailable"}, status_code=503)

    logger.info(f"Cache hit: key={key}")
    return {"key": key, "value": "cached_data"}


@app.post("/api/external/notify")
def external_notify():
    """Simulate calling external service"""
    maybe_slow()

    if random.random() < 0.12:
        error_msg = ErrorPatterns.external_service_down()
        logger.error(error_msg)
        return JSONResponse({"error": "External service error"}, status_code=502)

    if maybe_error():
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    logger.info("External notification sent")
    return {"status": "sent"}


@app.get("/api/health")
def health():
    """Health check - mostly succeeds"""
    if random.random() < 0.02:
        logger.error("Health check failed: service degraded")
        return JSONResponse({"status": "unhealthy"}, status_code=503)

    logger.info("Health check: OK")
    return {"status": "healthy"}


@app.post("/internal/cron/cleanup")
def cleanup_job():
    """Simulate scheduled job"""

    if random.random() < 0.30:
        error_msg = random.choice(
            [
                ErrorPatterns.database_timeout(),
                ErrorPatterns.sql_syntax_error(),
                ErrorPatterns.memory_error(),
            ]
        )
        logger.error(f"Cleanup job failed: {error_msg}")
        return JSONResponse({"status": "failed"}, status_code=500)

    logger.info("Cleanup job completed successfully")
    return {"status": "success"}
