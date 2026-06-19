"""pykrx ingestion: OHLCV, index series, and market fundamentals (PER/PBR/...).

pykrx is imported lazily so the rest of the system runs without it. All network
calls are cached to data/raw/ and retried with backoff. Column names returned by
pykrx are Korean; we normalize to a stable English schema.

NOTE: the live pykrx calls below require network access to KRX and are not
exercised in the offline/synthetic path. Signatures follow the pykrx API; verify
against the installed pykrx version when wiring real ingestion.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.logging_setup import get_logger
from src.utils import read_cache, retry, write_cache, ymd

log = get_logger(__name__)

KOSPI_INDEX = "1001"
KOSDAQ_INDEX = "2001"

_OHLCV_COLS = {
    "시가": "open", "고가": "high", "저가": "low", "종가": "close",
    "거래량": "volume", "거래대금": "value", "등락률": "change_pct",
}


def _stock():  # lazy import
    try:
        from pykrx import stock
    except ImportError as exc:  # pragma: no cover
        raise ImportError("pykrx is required for live market data (pip install pykrx)") from exc
    return stock


@retry(times=3)
def fetch_ohlcv(ticker: str, start: date | str, end: date | str, *, use_cache: bool = True) -> pd.DataFrame:
    """Daily OHLCV for one ticker -> columns [date, open, high, low, close, volume, ticker]."""
    name = f"ohlcv_{ticker}_{ymd(start)}_{ymd(end)}.csv"
    if use_cache and (cached := read_cache(name)) is not None:
        return cached
    df = _stock().get_market_ohlcv(ymd(start), ymd(end), ticker)
    df = df.rename(columns=_OHLCV_COLS)
    df.index.name = "date"
    out = df.reset_index()
    out["ticker"] = ticker
    keep = ["date", "open", "high", "low", "close", "volume", "ticker"]
    out = out[[c for c in keep if c in out.columns]]
    write_cache(out, name)
    log.info("Fetched %d OHLCV rows for %s", len(out), ticker)
    return out


@retry(times=3)
def fetch_market_fundamentals(d: date | str, market: str = "ALL") -> pd.DataFrame:
    """PER/PBR/EPS/BPS/DIV/DPS for all tickers on a date -> columns incl. 'ticker'."""
    df = _stock().get_market_fundamental(ymd(d), market=market)
    df.index.name = "ticker"
    return df.reset_index()


@retry(times=3)
def fetch_index_ohlcv(index_code: str, start: date | str, end: date | str) -> pd.DataFrame:
    """Index OHLCV series (for relative-strength) -> columns [date, open, high, low, close, ...]."""
    df = _stock().get_index_ohlcv(ymd(start), ymd(end), index_code).rename(columns=_OHLCV_COLS)
    df.index.name = "date"
    return df.reset_index()
