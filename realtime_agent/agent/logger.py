from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("monitoring_agent")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    stream_handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
