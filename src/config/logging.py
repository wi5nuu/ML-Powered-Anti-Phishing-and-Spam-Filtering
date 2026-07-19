"""
Logging configuration for CogniMail — Enterprise Edition.

Uses structlog for structured logging with:
- Colored console output for development
- JSON output for production (log aggregation)
- File rotation for persistent logs
- Request ID tracing
- Different log levels per module
"""
import os
import logging
import structlog
from pathlib import Path
from logging.handlers import RotatingFileHandler
from .settings import settings


def configure_logging():
    """Configure structured logging for the entire application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    log_file = getattr(settings, 'LOG_FILE', None)

    # ── Configure structlog ────────────────────────────────────────────
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if os.getenv("ENVIRONMENT") == "production":
        # JSON output for production log aggregation
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Colored console for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── Configure standard logging ─────────────────────────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root_logger.addHandler(console)

    # File handler (if configured)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            max_bytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s | %(pathname)s:%(lineno)d",
        ))
        root_logger.addHandler(file_handler)

    # Suppress verbose third-party loggers
    for noisy_logger in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    return structlog.get_logger()

