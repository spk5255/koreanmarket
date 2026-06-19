"""Tests for backtest metrics and the walk-forward engine."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import momentum_scorer, walk_forward
from src.backtest.metrics import hit_rate, information_coefficient, long_short_spread, sharpe


def test_ic_perfect_predictor():
    scores = pd.Series([1, 2, 3, 4, 5], dtype=float)
    fwd = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
    assert information_coefficient(scores, fwd) > 0.99


def test_ic_inverse_predictor_negative():
    scores = pd.Series([5, 4, 3, 2, 1], dtype=float)
    fwd = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
    assert information_coefficient(scores, fwd) < -0.99


def test_hit_rate_perfect():
    pred = pd.Series([0.9, 0.9, 0.1, 0.1])
    fwd = pd.Series([0.05, 0.02, -0.03, -0.01])
    assert hit_rate(pred, fwd) == 1.0


def test_long_short_spread_sign():
    scores = pd.Series(range(10), dtype=float)
    fwd = pd.Series(np.linspace(-0.05, 0.05, 10))
    assert long_short_spread(scores, fwd, 0.2) > 0


def test_sharpe_positive_for_positive_mean():
    r = pd.Series([0.01, 0.012, 0.009, 0.011, 0.013])
    assert sharpe(r) > 0


def _price_df(start, drift, n=200, seed=0):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.01, n)
    close = start * np.exp(np.cumsum(rets))
    dates = pd.bdate_range("2023-01-02", periods=n)
    return pd.DataFrame({"date": dates.date, "close": close})


def test_walk_forward_runs():
    prices = {f"T{i}": _price_df(1000 + i, drift=0.002 if i < 5 else -0.001, seed=i) for i in range(10)}
    res = walk_forward(prices, momentum_scorer, step_days=5, warmup_days=70)
    assert res.n_weeks > 0
    assert not res.per_week.empty
    assert "basket_return" in res.per_week.columns
