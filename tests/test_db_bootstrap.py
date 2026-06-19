"""Tests for the storage schema and repository round-trip.

Uses an isolated in-memory SQLite engine so the test never touches the dev DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config.universe import get_universe
from src.storage.models import ALL_MODELS, Base
from src.storage.repository import get_company, list_companies, seed_companies

EXPECTED_TABLES = {
    "companies",
    "prices",
    "fundamentals",
    "investor_flows",
    "news",
    "factor_scores",
    "projections",
    "projection_outcomes",
}


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as s:
        yield s


def test_all_expected_tables_present():
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables))
    assert len(ALL_MODELS) == len(EXPECTED_TABLES)


def test_seed_and_read_companies(session: Session):
    n = seed_companies(session, get_universe())
    session.commit()

    assert n == len(get_universe())
    assert len(list_companies(session)) == n

    samsung = get_company(session, "005930")
    assert samsung is not None
    assert samsung.market == "KOSPI"


def test_seed_is_idempotent(session: Session):
    seed_companies(session, get_universe())
    session.commit()
    seed_companies(session, get_universe())  # second pass should update, not duplicate
    session.commit()
    assert len(list_companies(session)) == len(get_universe())


def test_market_filter(session: Session):
    seed_companies(session, get_universe())
    session.commit()
    kospi = list_companies(session, market="KOSPI")
    kosdaq = list_companies(session, market="KOSDAQ")
    assert all(c.market == "KOSPI" for c in kospi)
    assert all(c.market == "KOSDAQ" for c in kosdaq)
    assert len(kospi) + len(kosdaq) == len(list_companies(session))
