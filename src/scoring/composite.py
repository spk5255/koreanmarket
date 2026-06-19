"""Blend the four factor-group scores into a 0..100 composite."""

from __future__ import annotations

import pandas as pd

from config.settings import FactorWeights, settings

GROUPS = ("fundamental", "supply_demand", "technical", "sentiment")


def composite_score(factor_table: pd.DataFrame, weights: FactorWeights | None = None) -> pd.Series:
    """Weighted blend of 0..1 group scores -> 0..100 composite, indexed by ticker.

    Missing groups default to a neutral 0.5 so a name is never punished for
    absent data beyond neutrality.
    """
    w = (weights or settings.factor_weights).as_dict()
    score = pd.Series(0.0, index=factor_table.index)
    for g in GROUPS:
        col = factor_table[g] if g in factor_table.columns else pd.Series(0.5, index=factor_table.index)
        score = score + w[g] * col.fillna(0.5)
    return (score * 100).clip(0, 100).round(2)


def signal_agreement(factor_table: pd.DataFrame) -> pd.Series:
    """Fraction of groups that agree with the overall tilt (0.5..1), per ticker.

    Used to label confidence: when most groups point the same way, trust is higher.
    """
    cols = [g for g in GROUPS if g in factor_table.columns]
    if not cols:
        return pd.Series(0.5, index=factor_table.index)
    sub = factor_table[cols]
    bullish = (sub > 0.5).sum(axis=1)
    bearish = (sub < 0.5).sum(axis=1)
    agree = pd.concat([bullish, bearish], axis=1).max(axis=1) / len(cols)
    return agree.clip(0.5, 1.0)
