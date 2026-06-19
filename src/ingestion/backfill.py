"""Live ingestion: pull REAL market data into the DB for the universe.

Uses pykrx for daily OHLCV (verified working) and DART for the latest annual
fundamentals (verified working). Each ticker is wrapped in try/except so one
failure never aborts the whole run. Flows/sentiment are left neutral for now.

Returns the number of price rows written (0 means nothing came back — caller
can fall back to synthetic).
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from config.settings import settings
from config.universe import get_universe
from src.ingestion.financials import (
    fetch_financial_statements,
    get_corp_code,
    normalize_statements,
)
from src.ingestion.market_data import fetch_ohlcv
from src.logging_setup import get_logger
from src.storage.db import init_db, session_scope
from src.storage.repository import seed_companies, upsert_fundamentals, upsert_prices

log = get_logger(__name__)


def _price_rows(ticker: str, df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        try:
            d = pd.to_datetime(r["date"]).date()
            rows.append({
                "ticker": ticker, "date": d,
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": int(r["volume"]) if pd.notna(r["volume"]) else None,
            })
        except (KeyError, ValueError, TypeError):
            continue
    return rows


def backfill_universe(years: float = 1.0, *, with_financials: bool = True) -> int:
    """Ingest real OHLCV (+ optional DART fundamentals) for the universe."""
    init_db()
    end = date.today()
    start = end - timedelta(days=int(years * 365.25))
    universe = get_universe()

    with session_scope() as s:
        seed_companies(s, universe)

    total = 0
    have_dart = with_financials and settings.dart_api_key is not None
    for m in universe:
        try:
            df = fetch_ohlcv(m.ticker, start, end, use_cache=False)
            rows = _price_rows(m.ticker, df)
            if rows:
                with session_scope() as s:
                    upsert_prices(s, rows)
                total += len(rows)
                log.info("  %s %s: %d real OHLCV rows", m.ticker, m.name, len(rows))
        except Exception as exc:  # noqa: BLE001 - one ticker must not kill the run
            log.warning("  OHLCV failed for %s: %s", m.ticker, exc)
            continue

        if have_dart:
            try:
                cc = get_corp_code(m.ticker)
                for yr in (end.year - 1, end.year - 2):
                    fs = fetch_financial_statements(cc, yr)
                    norm = normalize_statements(fs)
                    if norm:
                        with session_scope() as s:
                            upsert_fundamentals(s, [{"ticker": m.ticker, "period": str(yr), **norm}])
                        break
            except Exception as exc:  # noqa: BLE001
                log.warning("  DART failed for %s: %s", m.ticker, exc)

    log.info("Backfill complete: %d real price rows across %d tickers.", total, len(universe))
    return total
