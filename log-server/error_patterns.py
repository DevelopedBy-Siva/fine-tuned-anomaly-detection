import random


class ErrorPatterns:
    """Realistic error patterns that occur in production systems"""

    @staticmethod
    def database_timeout():
        """Simulates DB connection issues"""
        timeout = random.choice([30, 45, 60])
        db_host = random.choice(["db-primary-1", "db-replica-2", "db-analytics"])
        return f"Database connection timeout after {timeout}s connecting to {db_host}"

    @staticmethod
    def null_pointer():
        """Java-style NPE with stack traces"""
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
        """Cache layer failures"""
        errors = [
            "Redis connection failed: Connection refused (localhost:6379)",
            "Redis timeout: Command timed out after 5000ms",
            "Redis READONLY: You can't write against a read only replica",
        ]
        return random.choice(errors)

    @staticmethod
    def api_rate_limit():
        """External API quota issues"""
        user_id = random.randint(1000, 9999)
        api = random.choice(["stripe", "sendgrid", "twilio", "aws-s3"])
        return f"API rate limit exceeded for {api} (user_id={user_id})"

    @staticmethod
    def payment_failed():
        """Payment processing errors"""
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
        """File I/O errors"""
        upload_id = random.randint(10000, 99999)
        extensions = [".jpg", ".pdf", ".csv", ".xml"]
        ext = random.choice(extensions)
        return f"File not found: /tmp/upload_{upload_id}{ext}"

    @staticmethod
    def memory_error():
        """Out of memory issues"""
        heap_mb = random.randint(1800, 2048)
        return f"OutOfMemoryError: Java heap space (used: {heap_mb}MB / max: 2048MB)"

    @staticmethod
    def auth_failed():
        """Authentication failures"""
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
        """Dependency failures"""
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
        """Database query issues"""
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
