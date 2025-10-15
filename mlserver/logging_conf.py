
import logging
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class StructuredFormatter(logging.Formatter):
    def __init__(self, include_timestamp=False, show_tasks=False):
        """Initialize formatter with configurable options.

        Args:
            include_timestamp: Whether to include timestamp field
            show_tasks: Whether to include taskName field in output
        """
        super().__init__()
        self.include_timestamp = include_timestamp
        self.show_tasks = show_tasks

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Conditionally add timestamp
        if self.include_timestamp:
            log_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname",
                          "filename", "module", "lineno", "funcName", "created",
                          "msecs", "relativeCreated", "thread", "threadName",
                          "processName", "process", "getMessage"]:
                # Skip taskName if show_tasks is False
                if key == "taskName" and not self.show_tasks:
                    continue
                log_entry[key] = value

        return json.dumps(log_entry)


def configure_logging(level: str = "INFO", structured: bool = True,
                     include_timestamp: bool = False, show_tasks: bool = False,
                     custom_format: Optional[str] = None) -> None:
    """Configure logging with optional structured format.

    Args:
        level: Log level (INFO, DEBUG, WARNING, ERROR)
        structured: Whether to use structured JSON logging
        include_timestamp: Whether to include timestamps in logs
        show_tasks: Whether to show task names in logs
        custom_format: Custom format string (overrides other settings)
    """
    logger = logging.getLogger()
    logger.handlers.clear()

    handler = logging.StreamHandler()

    if custom_format:
        # Use custom format if provided
        handler.setFormatter(logging.Formatter(custom_format))
    elif structured:
        # Use structured formatter with configurable options
        handler.setFormatter(StructuredFormatter(
            include_timestamp=include_timestamp,
            show_tasks=show_tasks
        ))
    else:
        # Use default text format
        handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))

    logger.addHandler(handler)
    lvl = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(lvl)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for current context. Returns the correlation ID."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context"""
    return correlation_id_var.get()


def log_request(method: str, path: str, **kwargs):
    """Log structured request information"""
    logger = logging.getLogger("mlserver.request")
    logger.info("Request started", extra={
        "event": "request_start",
        "method": method,
        "path": path,
        **kwargs
    })


def log_response(status_code: int, duration_ms: float, **kwargs):
    """Log structured response information"""
    logger = logging.getLogger("mlserver.response")
    logger.info("Request completed", extra={
        "event": "request_complete",
        "status_code": status_code,
        "duration_ms": duration_ms,
        **kwargs
    })


def log_prediction(model_name: str, duration_ms: float, sample_count: int, **kwargs):
    """Log structured prediction information"""
    logger = logging.getLogger("mlserver.prediction")
    logger.info("Prediction completed", extra={
        "event": "prediction_complete",
        "model": model_name,
        "duration_ms": duration_ms,
        "sample_count": sample_count,
        **kwargs
    })
