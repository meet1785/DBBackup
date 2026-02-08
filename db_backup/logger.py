"""Logging configuration for the backup utility."""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(log_dir: str = "logs") -> logging.Logger:
    """Configure and return the application logger.

    Logs to both console and a timestamped file in the log directory.
    """
    logger = logging.getLogger("db_backup")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    # File handler
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = os.path.join(log_dir, f"db_backup_{datetime.now():%Y%m%d_%H%M%S}.log")
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
    fh.setFormatter(file_fmt)
    logger.addHandler(fh)

    return logger


logger = setup_logger()
