"""Backtest metrics: the numbers that tell you whether the scoring works.

Spearman rank-IC is computed as Pearson correlation of ranks so we avoid a hard
scipy dependency.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def information_coefficient(scores: pd.Series, fwd_returns: pd.Series) -> float:
    """Spearman rank correlation between scores and forward returns (-1..1)."""
    df = pd.concat([scores, fwd_returns], axis=1).dropna()
    if len(df) < 3:
        return float("nan")
    a = df.iloc[:, 0].rank()
    b = df.iloc[:, 1].rank()
    return float(a.corr(b))  # Pearson of ranks == Spearman; no scipy needed


def hit_rate(predicted_up: pd.Series, fwd_returns: pd.Series) -> float:
    """Fraction of names where the predicted direction matched realized sign."""
    df = pd.concat([predicted_up, fwd_returns], axis=1).dropna()
    if df.empty:
        return float("nan")
    correct = ((df.iloc[:, 0] > 0.5) & (df.iloc[:, 1] > 0)) | ((df.iloc[:, 0] <= 0.5) & (df.iloc[:, 1] <= 0))
    return float(correct.mean())


def long_short_spread(scores: pd.Series, fwd_returns: pd.Series, quantile: float = 0.2) -> float:
    """Mean forward return of top-quantile minus bottom-quantile by score."""
    df = pd.concat([scores, fwd_returns], axis=1).dropna()
    df.columns = ["score", "ret"]
    if len(df) < 5:
        return float("nan")
    hi = df["score"].quantile(1 - quantile)
    lo = df["score"].quantile(quantile)
    top = df.loc[df["score"] >= hi, "ret"].mean()
    bot = df.loc[df["score"] <= lo, "ret"].mean()
    return float(top - bot)


def sharpe(returns: pd.Series, periods_per_year: int = 52) -> float:
    """Annualized Sharpe of a return series (weekly by default, rf=0)."""
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))
