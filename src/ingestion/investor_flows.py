"""pykrx ingestion: foreign/institutional net buying and short-selling balance.

A dominant signal in Korean markets. pykrx imported lazily; calls cached.

NOTE: live calls require network; not exercised offline. pykrx exposes
per-ticker investor trading via get_market_trading_value_by_date and short
balance via get_shorting_balance_by_date — column names are Korean and
normalized below.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.logging_setup import get_logger
from src.utils import read_cache, retry, write_cache, ymd

log = get_logger(__name__)

# Investor columns of interest (Korean -> internal)
_FOREIGN_COLS = ("외국인합계", "외국인")
_INST_COLS = ("기관합계",)


def _stock():
    try:
        from pykrx import stock
    except ImportError as exc:  # pragma: no cover
        raise ImportError("pykrx is required (pip install pykrx)") from exc
    return stock


def _first_present(df: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Series | None:
    for c in candidates:
        if c in df.columns:
            return df[c]
    return None


@retry(times=3)
def fetch_investor_flows(ticker: str, start: date | str, end: date | str, *, use_cache: bool = True) -> pd.DataFrame:
    """Daily foreign/institutional net-buy value + short balance for one ticker.

    Returns columns [date, ticker, foreign_net, inst_net, short_balance].
    """
    name = f"flows_{ticker}_{ymd(start)}_{ymd(end)}.csv"
    if use_cache and (cached := read_cache(name)) is not None:
        return cached

    stock = _stock()
    trade = stock.get_market_trading_value_by_date(ymd(start), ymd(end), ticker)
    trade.index.name = "date"
    trade = trade.reset_index()

    out = pd.DataFrame({"date": trade["date"]})
    out["ticker"] = ticker
    foreign = _first_present(trade, _FOREIGN_COLS)
    inst = _first_present(trade, _INST_COLS)
    out["foreign_net"] = foreign.values if foreign is not None else pd.NA
    out["inst_net"] = inst.values if inst is not None else pd.NA

    try:
        short = stock.get_shorting_balance_by_date(ymd(start), ymd(end), ticker)
        short.index.name = "date"
        short = short.reset_index()
        bal_col = next((c for c in ("잔고금액", "공매도잔고") if c in short.columns), None)
        if bal_col:
            out = out.merge(
                short[["date", bal_col]].rename(columns={bal_col: "short_balance"}),
                on="date", how="left",
            )
    except Exception as exc:  # pragma: no cover - short data may be unavailable
        log.warning("Short balance unavailable for %s: %s", ticker, exc)
    if "short_balance" not in out.columns:
        out["short_balance"] = pd.NA

    write_cache(out, name)
    log.info("Fetched %d investor-flow rows for %s", len(out), ticker)
    return out
