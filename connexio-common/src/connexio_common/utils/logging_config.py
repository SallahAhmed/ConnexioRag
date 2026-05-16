"""Structured JSON logging configuration for both Connexio services."""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    logger_name: Optional[str] = None,
) -> logging.Logger:
    """Configure structured logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, use JSON formatter (requires python-json-logger).
        logger_name: Root logger name. Defaults to "connexio".

    Returns:
        Configured logger instance.
    """
    root_name = logger_name or "connexio"
    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_format:
        try:
            from pythonjsonlogger import jsonlogger

            handler = logging.StreamHandler(sys.stdout)
            formatter = jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            handler.setFormatter(formatter)
        except ImportError:
            json_format = False

    if not json_format:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

    logger = logging.getLogger(root_name)
    logger.setLevel(log_level)

    if not logger.handlers:
        logger.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger
