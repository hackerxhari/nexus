"""
Structured logging for Nexus.
Every log entry is JSON — machine readable, queryable.
Never use print() anywhere in the codebase. Always use logger.
"""

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional
import structlog
from core.config import get_settings

# Context variable to track request ID across async calls
request_id_var: ContextVar[str] = ContextVar(
    "request_id",
    default="no-request"
)

# Context variable to track current user
user_id_var: ContextVar[str] = ContextVar(
    "user_id",
    default="anonymous"
)


def add_request_context(
    logger: Any,
    method: str,
    event_dict: Dict
) -> Dict:
    """Inject request context into every log entry."""
    event_dict["request_id"] = request_id_var.get()
    event_dict["user_id"] = user_id_var.get()
    return event_dict


def add_timestamp(
    logger: Any,
    method: str,
    event_dict: Dict
) -> Dict:
    """Add ISO timestamp to every log entry."""
    event_dict["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return event_dict


def setup_logging() -> None:
    """
    Configure structlog for the entire application.
    Call this once at application startup.
    """
    settings = get_settings()

    # Configure standard logging to file
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
        ]
    )

    # Suppress noisy third-party loggers
    for noisy_logger in ["httpx", "httpcore", "urllib3", "multipart"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Configure structlog processors
    shared_processors = [
        add_timestamp,
        add_request_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_development:
        # Pretty colored output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        # JSON output for production (queryable by log aggregators)
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a named logger instance.
    
    Usage:
        from core.logger import get_logger
        logger = get_logger(__name__)
        logger.info("ingestion_started", filename="report.pdf", chunks=24)
    """
    return structlog.get_logger(name)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> None:
    """Set context variables for the current request."""
    request_id_var.set(request_id or str(uuid.uuid4()))
    if user_id:
        user_id_var.set(user_id)


class TimedOperation:
    """
    Context manager for timing and logging operations.
    
    Usage:
        with TimedOperation(logger, "qdrant_search", query=question):
            results = client.search(...)
    """

    def __init__(
        self,
        logger: structlog.BoundLogger,
        operation: str,
        **kwargs
    ):
        self.logger = logger
        self.operation = operation
        self.kwargs = kwargs
        self.start_time: float = 0.0

    def __enter__(self) -> "TimedOperation":
        self.start_time = time.perf_counter()
        self.logger.debug(
            f"{self.operation}_started",
            **self.kwargs
        )
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any
    ) -> bool:
        duration_ms = (time.perf_counter() - self.start_time) * 1000

        if exc_type is not None:
            self.logger.error(
                f"{self.operation}_failed",
                duration_ms=round(duration_ms, 2),
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.kwargs
            )
        else:
            self.logger.info(
                f"{self.operation}_completed",
                duration_ms=round(duration_ms, 2),
                **self.kwargs
            )

        return False  # Never suppress exceptions