"""Generate synthetic but realistic market data so the full pipeline runs offline.

Creates ~3 years of business-day OHLCV (geometric random walk with per-ticker
drift/vol), daily investor flows, and 12 quarters of fundamentals for every name
in the universe, then writes them to the DB. Deterministic via a fixed seed so
tests and demos are reproducible.

Usage:  python scripts/seed_synthetic.py [--years 3] [--seed 42]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.universe import get_universe  # noqa: E402
from src.logging_setup import configure_logging, get_logger  # noqa: E402
from src.storage.db import init_db, session_scope  # noqa: E402
from src.storage.repository import (  # noqa: E402
    seed_companies,
    upsert_flows,
    upsert_fundamentals,
    upsert_prices,
)


def _business_days(years: int, end: date) -> list[date]:
    start = end - timedelta(days=int(years * 365.25))
    days = pd.bdate_range(start=start, end=end)
    return [d.date() for d in days]


def _synth_prices(ticker: str, days: list[date], rng: np.random.Generator) -> list[dict]:
    base = float(rng.uniform(20_000, 120_000))
    drift = float(rng.normal(0.0003, 0.0004))      # per-day drift, name-specific
    vol = float(rng.uniform(0.012, 0.032))          # daily vol
    rets = rng.normal(drift, vol, size=len(days))
    close = base * np.exp(np.cumsum(rets))
    rows: list[dict] = []
    for i, d in enumerate(days):
        c = float(close[i])
        o = c * float(np.exp(rng.normal(0, vol / 2)))
        hi = max(o, c) * float(np.exp(abs(rng.normal(0, vol / 2))))
        lo = min(o, c) * float(np.exp(-abs(rng.normal(0, vol / 2))))
        rows.append({
            "ticker": ticker, "date": d,
            "open": round(o, 1), "high": round(hi, 1), "low": round(lo, 1),
            "close": round(c, 1), "volume": int(rng.uniform(1e5, 5e6)),
        })
    return rows


def _synth_flows(ticker: str, days: list[date], rng: np.random.Generator) -> list[dict]:
    # Persistent (AR(1)) net-buy series so streak signals are meaningful.
    foreign = np.zeros(len(days))
    inst = np.zeros(len(days))
    fphi, iphi = 0.85, 0.8
    for i in range(1, len(days)):
        foreign[i] = fphi * foreign[i - 1] + rng.normal(0, 1)
        inst[i] = iphi * inst[i - 1] + rng.normal(0, 1)
    scale = float(rng.uniform(2e8, 2e9))
    short = np.cumsum(rng.normal(0, 1, len(days))) * scale / 50 + scale
    return [
        {"ticker": ticker, "date": d,
         "foreign_net": float(foreign[i] * scale),
         "inst_net": float(inst[i] * scale),
         "short_balance": float(max(0.0, short[i]))}
        for i, d in enumerate(days)
    ]


def _synth_fundamentals(ticker: str, n_quarters: int, end: date, rng: np.random.Generator) -> list[dict]:
    revenue = float(rng.uniform(5e11, 8e13))
    op_margin = float(rng.uniform(0.04, 0.22))
    net_margin = op_margin * float(rng.uniform(0.5, 0.9))
    assets = revenue * float(rng.uniform(1.2, 3.0))
    liab_ratio = float(rng.uniform(0.25, 0.65))
    growth = float(rng.normal(0.01, 0.03))
    rows: list[dict] = []
    y, q = end.year, (end.month - 1) // 3 + 1
    for k in range(n_quarters):
        rev = revenue * (1 + growth) ** (n_quarters - k)
        equity = assets * (1 - liab_ratio)
        rows.append({
            "ticker": ticker, "period": f"{y}Q{q}",
            "revenue": rev, "op_profit": rev * op_margin, "net_income": rev * net_margin,
            "total_assets": assets, "total_liab": assets * liab_ratio, "equity": equity,
            "ocf": rev * net_margin * float(rng.uniform(0.9, 1.4)),
            "capex": rev * float(rng.uniform(0.03, 0.10)),
        })
        q -= 1
        if q == 0:
            q = 4
            y -= 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic market data.")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--end", type=str, default=None, help="end date YYYY-MM-DD (default today)")
    args = parser.parse_args()

    configure_logging()
    log = get_logger("seed_synthetic")
    end = date.fromisoformat(args.end) if args.end else date.today()
    days = _business_days(args.years, end)
    log.info("Generating %.1fy synthetic data ending %s (%d business days)", args.years, end, len(days))

    init_db()
    universe = get_universe()
    with session_scope() as session:
        seed_companies(session, universe)

    total_prices = 0
    for idx, m in enumerate(universe):
        rng = np.random.default_rng(args.seed + idx)
        prices = _synth_prices(m.ticker, days, rng)
        flows = _synth_flows(m.ticker, days, rng)
        funds = _synth_fundamentals(m.ticker, 12, end, rng)
        with session_scope() as session:
            upsert_prices(session, prices)
            upsert_flows(session, flows)
            upsert_fundamentals(session, funds)
        total_prices += len(prices)
        log.info("  %s (%s): %d prices, %d flows, %d quarters",
                 m.ticker, m.name, len(prices), len(flows), len(funds))

    log.info("Done. Seeded %d price rows across %d tickers.", total_prices, len(universe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
