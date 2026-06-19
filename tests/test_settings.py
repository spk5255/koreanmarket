"""Tests for configuration invariants."""

from __future__ import annotations

import pytest

from config.settings import FactorWeights, Settings, settings
from config.universe import VERIFICATION_TICKERS, get_tickers, get_universe


def test_default_factor_weights_sum_to_one():
    assert pytest.approx(sum(settings.factor_weights.as_dict().values()), abs=1e-9) == 1.0


def test_invalid_factor_weights_rejected():
    with pytest.raises(ValueError):
        FactorWeights(fundamental=0.5, supply_demand=0.5, technical=0.5, sentiment=0.5)


def test_log_level_normalized():
    s = Settings(KMA_LOG_LEVEL="debug")
    assert s.log_level == "DEBUG"


def test_invalid_log_level_rejected():
    with pytest.raises(ValueError):
        Settings(KMA_LOG_LEVEL="verbose")


def test_resolved_db_url_is_absolute_for_relative_sqlite():
    s = Settings(KMA_DB_URL="sqlite:///data/market.db")
    assert s.resolved_db_url.startswith("sqlite:///")
    assert s.is_sqlite
    # relative path should have been resolved to an absolute one
    tail = s.resolved_db_url[len("sqlite:///") :]
    assert tail.endswith("data/market.db")
    assert "/" in tail and not tail.startswith("data/")


def test_universe_has_verification_tickers():
    tickers = set(get_tickers())
    for t in VERIFICATION_TICKERS:
        assert t in tickers
    assert len(get_universe("KOSPI")) > 0
    assert len(get_universe("KOSDAQ")) > 0
