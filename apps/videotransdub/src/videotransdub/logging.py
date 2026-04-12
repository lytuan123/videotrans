from __future__ import annotations

import logging
from pathlib import Path


def build_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger(f"videotransdub:{log_path}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
