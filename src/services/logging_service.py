"""Логирование сервиса для проекта."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.core.config import config

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_is_configured = False

# Путь к папке логов
LOGS_DIR = Path("logs")


def _resolve_level(level: Optional[str]) -> int:
    """Преобразует строковый уровень в числовой."""
    name = (level or config.LOG_LEVEL or "INFO").upper()
    return getattr(logging, name, logging.INFO)


def setup_logging(level: Optional[str] = None, force: bool = False) -> None:
    """Инициализирует базовую конфигурацию логирования с сохранением в файлы."""
    global _is_configured
    if _is_configured and not force:
        return

    # Создаём папку для логов
    LOGS_DIR.mkdir(exist_ok=True)

    # Формат логов
    log_format = config.LOG_FORMAT or _DEFAULT_FORMAT
    date_format = config.LOG_DATE_FORMAT or _DEFAULT_DATE_FORMAT
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Получаем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(_resolve_level(level))

    # Удаляем существующие handlers (если force=True)
    if force:
        root_logger.handlers.clear()

    # Console handler (все уровни)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(_resolve_level(level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler для всех логов (INFO и выше)
    all_logs_handler = RotatingFileHandler(
        LOGS_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    all_logs_handler.setLevel(logging.INFO)
    all_logs_handler.setFormatter(formatter)
    root_logger.addHandler(all_logs_handler)

    # File handler только для ERROR и выше
    error_handler = RotatingFileHandler(
        LOGS_DIR / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # File handler для DEBUG (если уровень DEBUG)
    if _resolve_level(level) == logging.DEBUG:
        debug_handler = RotatingFileHandler(
            LOGS_DIR / "debug.log",
            maxBytes=20 * 1024 * 1024,  # 20 MB
            backupCount=3,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatter)
        root_logger.addHandler(debug_handler)

    _is_configured = True
    root_logger.info("Логирование настроено. Логи сохраняются в папку: %s", LOGS_DIR.absolute())


def get_logger(name: str) -> logging.Logger:
    """Возвращает настроенный логгер, гарантируя конфигурацию."""
    if not _is_configured:
        setup_logging()
    return logging.getLogger(name)


__all__ = ["get_logger", "setup_logging"]
