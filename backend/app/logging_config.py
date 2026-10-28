"""
backend/app/logging_config.py

Configures Python logging to write to both console and file with
structured formatting.
"""

import logging
import os
from app.config import settings


def setup_logging() -> None:
    """Configure root and scraper loggers."""
    log_dir = os.path.dirname(settings.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(file_handler)

    # Quieten noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
