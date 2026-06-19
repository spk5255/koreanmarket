"""Convert raw metrics into 0..1 factor scores via cross-sectional ranking.

Percentile-rank within the universe makes scores relative, robust to outliers,
and comparable across factor groups. ``sector`` can be passed to rank within
sector instead of the whole market.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def percentile_rank(s: pd.Series, *, ascending: bool = True) -> pd.Series:
    """Rank to [0,1]. ascending=True -> higher raw value gets higher score."""
    x = pd.to_numeric(s, errors="coerce")
    if x.notna().sum() <= 1:
        return pd.Series(0.5, index=s.index)
    r = x.rank(pct=True, ascending=ascending)
    return r.fillna(0.5)


def zscore_to_unit(s: pd.Series) -> pd.Series:
    """Squash a z-score into (0,1) via logistic — alternative to percentile."""
    x = pd.to_numeric(s, errors="coerce")
    mu, sd = x.mean(), x.std(ddof=0)
    if not sd or np.isnan(sd):
        return pd.Series(0.5, index=s.index)
    z = (x - mu) / sd
    return (1 / (1 + np.exp(-z))).fillna(0.5)


# Which raw metric drives each factor group, and its direction (higher better?).
GROUP_SPECS: dict[str, list[tuple[str, bool]]] = {
    "fundamental": [("roe", True), ("op_margin", True), ("revenue_yoy", True),
                    ("ocf_to_ni", True), ("debt_to_equity", False)],
    "technical": [("momentum_120", True), ("rel_strength", True), ("rsi14", True)],
    "supply_demand": [("combined_net_sum_20", True), ("foreign_streak", True),
                      ("short_change_20", False)],
    "sentiment": [("sentiment", True)],
}


def build_factor_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Given a raw-metrics frame indexed by ticker, return a frame of 0..1 group scores.

    Columns: one per group in GROUP_SPECS. Each group score is the mean of the
    percentile ranks of its constituent metrics (present ones only).
    """
    out = pd.DataFrame(index=raw.index)
    for group, specs in GROUP_SPECS.items():
        parts: list[pd.Series] = []
        for metric, higher_better in specs:
            if metric in raw.columns:
                parts.append(percentile_rank(raw[metric], ascending=higher_better))
        out[group] = pd.concat(parts, axis=1).mean(axis=1) if parts else 0.5
    return out.fillna(0.5)
