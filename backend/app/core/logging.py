"""
Structured logging configuration for FinSpectra.
Uses structlog for JSON-formatted log output.
Never logs secrets, credentials, or sensitive user data.
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for structured JSON logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
    ]

    if sys.stderr.isatty():
        # Pretty output for local development
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # JSON for production/Docker
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_logger(name: str = "finspectra") -> structlog.BoundLogger:
    """Get a bound logger instance."""
    return structlog.get_logger(name)
