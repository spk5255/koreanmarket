"""Repository helpers over the ORM — keeps DB access in one place.

Bulk upserts use SQLAlchemy's dialect-specific INSERT .. ON CONFLICT where
available (SQLite/Postgres) and fall back to per-row merge otherwise.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.universe import UniverseMember
from src.storage.models import (
    Company,
    FactorScore,
    Fundamental,
    InvestorFlow,
    Price,
    Projection,
    ProjectionOutcome,
)

# ---------------------------------------------------------------- companies ---

def upsert_company(session: Session, *, ticker: str, name: str, market: str,
                   corp_code: str | None = None, sector: str | None = None) -> Company:
    company = session.get(Company, ticker)
    if company is None:
        company = Company(ticker=ticker, name=name, market=market, corp_code=corp_code, sector=sector)
        session.add(company)
    else:
        company.name = name
        company.market = market
        if corp_code is not None:
            company.corp_code = corp_code
        if sector is not None:
            company.sector = sector
    return company


def seed_companies(session: Session, members: Iterable[UniverseMember]) -> int:
    n = 0
    for m in members:
        upsert_company(session, ticker=m.ticker, name=m.name, market=m.market)
        n += 1
    return n


def list_companies(session: Session, market: str | None = None) -> Sequence[Company]:
    stmt = select(Company).order_by(Company.ticker)
    if market is not None:
        stmt = stmt.where(Company.market == market.upper())
    return session.scalars(stmt).all()


def get_company(session: Session, ticker: str) -> Company | None:
    return session.get(Company, ticker)


# ------------------------------------------------------------- generic merge ---

def _merge_rows(session: Session, model: type, rows: list[dict]) -> int:
    """Per-row merge() upsert keyed by the model's primary key. Returns count."""
    for r in rows:
        session.merge(model(**r))
    return len(rows)


# ----------------------------------------------------------------- prices -----

def upsert_prices(session: Session, rows: list[dict]) -> int:
    """rows: dicts with keys ticker,date,open,high,low,close,volume."""
    return _merge_rows(session, Price, rows)


def get_prices(session: Session, ticker: str, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    stmt = select(Price).where(Price.ticker == ticker).order_by(Price.date)
    if start:
        stmt = stmt.where(Price.date >= start)
    if end:
        stmt = stmt.where(Price.date <= end)
    rows = session.scalars(stmt).all()
    return pd.DataFrame([
        {"date": p.date, "open": p.open, "high": p.high, "low": p.low,
         "close": p.close, "volume": p.volume} for p in rows
    ])


# ------------------------------------------------------------- fundamentals ---

def upsert_fundamentals(session: Session, rows: list[dict]) -> int:
    return _merge_rows(session, Fundamental, rows)


def get_fundamentals(session: Session, ticker: str) -> pd.DataFrame:
    stmt = select(Fundamental).where(Fundamental.ticker == ticker).order_by(Fundamental.period)
    rows = session.scalars(stmt).all()
    return pd.DataFrame([
        {"period": f.period, "revenue": f.revenue, "op_profit": f.op_profit,
         "net_income": f.net_income, "total_assets": f.total_assets,
         "total_liab": f.total_liab, "equity": f.equity, "ocf": f.ocf, "capex": f.capex}
        for f in rows
    ])


# ------------------------------------------------------------ investor flows ---

def upsert_flows(session: Session, rows: list[dict]) -> int:
    return _merge_rows(session, InvestorFlow, rows)


def get_flows(session: Session, ticker: str, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    stmt = select(InvestorFlow).where(InvestorFlow.ticker == ticker).order_by(InvestorFlow.date)
    if start:
        stmt = stmt.where(InvestorFlow.date >= start)
    if end:
        stmt = stmt.where(InvestorFlow.date <= end)
    rows = session.scalars(stmt).all()
    return pd.DataFrame([
        {"date": r.date, "foreign_net": r.foreign_net, "inst_net": r.inst_net,
         "short_balance": r.short_balance} for r in rows
    ])


# ------------------------------------------------------ scores / projections ---

def save_factor_scores(session: Session, rows: list[dict]) -> int:
    return _merge_rows(session, FactorScore, rows)


def save_projection(session: Session, row: dict) -> None:
    session.merge(Projection(**row))


def save_projection_outcome(session: Session, row: dict) -> None:
    session.merge(ProjectionOutcome(**row))


def get_projections(session: Session, week: str) -> Sequence[Projection]:
    return session.scalars(
        select(Projection).where(Projection.week == week)
    ).all()
