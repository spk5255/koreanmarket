"""Committed real-data snapshot: ship real KRX/DART data with the repo.

KRX/DART often block cloud datacenter IPs, so live ingestion can fail on
Streamlit Cloud. To guarantee the hosted app shows REAL data, we export the
locally-ingested data to CSVs under data/real_snapshot/ (committed to git) and
load them on the host — no live call needed.

This is public market data (prices/fundamentals), not secrets.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select

from config.settings import DATA_DIR
from src.logging_setup import get_logger
from src.storage.db import init_db, session_scope
from src.storage.models import Company, Fundamental, InvestorFlow, Price

log = get_logger(__name__)

SNAPSHOT_DIR = DATA_DIR / "real_snapshot"
_TABLES = {
    "companies": Company,
    "prices": Price,
    "fundamentals": Fundamental,
    "investor_flows": InvestorFlow,
}
_STR_COLS = {"ticker", "corp_code", "period", "market", "sector", "name"}


def snapshot_exists() -> bool:
    return (SNAPSHOT_DIR / "prices.csv").exists()


def export_snapshot() -> dict[str, int]:
    """Dump current DB tables to data/real_snapshot/*.csv."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with session_scope() as s:
        for name, model in _TABLES.items():
            cols = [c.name for c in model.__table__.columns]
            rows = s.scalars(select(model)).all()
            df = pd.DataFrame([{c: getattr(r, c) for c in cols} for r in rows], columns=cols)
            df.to_csv(SNAPSHOT_DIR / f"{name}.csv", index=False)
            counts[name] = len(df)
    log.info("Exported snapshot: %s", counts)
    return counts


def load_snapshot() -> int:
    """Load data/real_snapshot/*.csv into the DB. Returns price-row count."""
    init_db()
    n_prices = 0
    for name, model in _TABLES.items():
        path = SNAPSHOT_DIR / f"{name}.csv"
        if not path.exists():
            continue
        present = pd.read_csv(path, nrows=0).columns
        dtypes = {c: str for c in _STR_COLS if c in present}
        df = pd.read_csv(path, dtype=dtypes)
        if df.empty:
            continue
        df = df.astype(object).where(pd.notna(df), None)
        recs = df.to_dict("records")
        for r in recs:
            if r.get("date") is not None:
                r["date"] = pd.to_datetime(r["date"]).date()
            if r.get("volume") is not None:
                r["volume"] = int(float(r["volume"]))
        with session_scope() as s:
            for r in recs:
                s.merge(model(**r))
        if name == "prices":
            n_prices = len(recs)
    log.info("Loaded snapshot: %d price rows", n_prices)
    return n_prices
