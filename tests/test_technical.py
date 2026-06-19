"""Tests for technical indicators."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.technical import compute_technical_metrics, realized_vol, rsi, sma


def _series(n=200, drift=0.001, vol=0.02, seed=0):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    return pd.Series(100 * np.exp(np.cumsum(rets)))


def test_rsi_bounds():
    r = rsi(_series()).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_rsi_uptrend_high():
    up = pd.Series(np.linspace(100, 200, 100))
    assert rsi(up).iloc[-1] > 70


def test_sma_matches_mean():
    s = pd.Series(range(10), dtype=float)
    assert sma(s, 3).iloc[-1] == np.mean([7, 8, 9])


def test_realized_vol_positive():
    rv = realized_vol(_series(vol=0.03)).iloc[-1]
    assert rv > 0


def test_compute_metrics_keys():
    df = pd.DataFrame({"close": _series(), "high": _series(seed=1) + 1, "low": _series(seed=2) - 1})
    df["high"] = df[["high", "close"]].max(axis=1)
    df["low"] = df[["low", "close"]].min(axis=1)
    m = compute_technical_metrics(df)
    for k in ("close", "sma60", "rsi14", "weekly_vol", "momentum_120"):
        assert k in m
