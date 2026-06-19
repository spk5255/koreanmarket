"""Tests for the scoring layer: factors, composite, projection."""
from __future__ import annotations

import pandas as pd

from config.settings import FactorWeights
from src.scoring.composite import composite_score, signal_agreement
from src.scoring.factors import build_factor_table, percentile_rank
from src.scoring.projection import project_week


def test_percentile_rank_orders():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    r = percentile_rank(s, ascending=True)
    assert r.iloc[0] < r.iloc[-1]
    rd = percentile_rank(s, ascending=False)
    assert rd.iloc[0] > rd.iloc[-1]


def test_build_factor_table_shape():
    raw = pd.DataFrame({
        "roe": [0.1, 0.2, 0.05],
        "momentum_120": [0.1, -0.05, 0.2],
        "combined_net_sum_20": [1e9, -1e9, 5e8],
        "sentiment": [0.5, -0.5, 0.0],
    }, index=["A", "B", "C"])
    ft = build_factor_table(raw)
    assert set(ft.columns) == {"fundamental", "technical", "supply_demand", "sentiment"}
    assert ((ft >= 0) & (ft <= 1)).all().all()


def test_composite_strong_name_scores_higher():
    ft = pd.DataFrame({
        "fundamental": [0.9, 0.1],
        "technical": [0.9, 0.1],
        "supply_demand": [0.9, 0.1],
        "sentiment": [0.9, 0.1],
    }, index=["strong", "weak"])
    cs = composite_score(ft, FactorWeights())
    assert cs["strong"] > cs["weak"]
    assert 0 <= cs.min() <= cs.max() <= 100


def test_signal_agreement_range():
    ft = pd.DataFrame({
        "fundamental": [0.9], "technical": [0.8], "supply_demand": [0.7], "sentiment": [0.6]
    }, index=["X"])
    a = signal_agreement(ft)
    assert 0.5 <= a.iloc[0] <= 1.0


def test_projection_monotonic_in_composite():
    lo = project_week("T", "2026-W25", composite=20, weekly_vol=0.04, last_close=1000, agreement=0.8)
    hi = project_week("T", "2026-W25", composite=80, weekly_vol=0.04, last_close=1000, agreement=0.8)
    assert hi.base > lo.base
    assert hi.prob_up > lo.prob_up
    assert 0.01 <= hi.prob_up <= 0.99
    assert lo.bear < lo.base < lo.bull
