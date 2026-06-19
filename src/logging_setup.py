"""Logging configuration.

Call :func:`configure_logging` once at process start (CLI, scheduler job,
tests). Uses Rich for readable colored console output when available and falls
back to the stdlib formatter otherwise. Honors ``settings.log_level``.
"""

from __future__ import annotations

import logging

from config.settings import settings

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configure root logging. Idempotent — safe to call more than once.

    Args:
        level: override log level (e.g. "DEBUG"); defaults to settings.log_level.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = (level or settings.log_level).upper()

    handler: logging.Handler
    try:
        from rich.logging import RichHandler

        handler = RichHandler(rich_tracebacks=True, show_path=False, markup=False)
        fmt = "%(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
    except Exception:  # pragma: no cover - rich is a declared dep, this is a safety net
        handler = logging.StreamHandler()
        fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"

    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Quiet noisy third-party loggers a notch.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring logging is configured first."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
