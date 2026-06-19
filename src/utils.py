"""Shared utilities: retry/backoff, on-disk CSV caching, and date helpers.

Kept dependency-light (only pandas) so every layer can import it.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

from config.settings import RAW_DIR
from src.logging_setup import get_logger

log = get_logger(__name__)
T = TypeVar("T")


def retry(
    times: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: retry a call with exponential backoff. Re-raises the last error."""

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            last: BaseException | None = None
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203
                    last = exc
                    if attempt == times:
                        break
                    log.warning("%s failed (attempt %d/%d): %s; retrying in %.1fs",
                                fn.__name__, attempt, times, exc, delay)
                    time.sleep(delay)
                    delay *= backoff
            assert last is not None
            raise last

        return wrapper

    return deco


def ymd(d: date | datetime | str) -> str:
    """Normalize a date to KRX 'YYYYMMDD' string."""
    if isinstance(d, (date, datetime)):
        return d.strftime("%Y%m%d")
    return str(d).replace("-", "").replace("/", "")


def iso_week_label(d: date | datetime) -> str:
    """ISO week label, e.g. date(2026, 6, 19) -> '2026-W25'."""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def cache_path(name: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DIR / name


def read_cache(name: str) -> pd.DataFrame | None:
    """Return a cached DataFrame (CSV) or None if absent/unreadable."""
    p = cache_path(name)
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception as exc:  # pragma: no cover
        log.warning("Failed reading cache %s: %s", p, exc)
        return None


def write_cache(df: pd.DataFrame, name: str) -> Path:
    p = cache_path(name)
    df.to_csv(p, index=False)
    return p
