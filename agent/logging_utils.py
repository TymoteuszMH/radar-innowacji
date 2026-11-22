import logging
import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


def get_logger(name: str, *, console: bool = True) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        log_path = Path(os.getenv("LOG_FILE", "logs/logs.txt"))
        if not log_path.is_absolute():
            log_path = PROJECT_DIR / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        if console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
    return logger