"""Walk-forward backtest of the scoring model.

At each weekly rebalance we score the universe using ONLY data available up to
that date (no look-ahead), form a top-decile long basket, and measure the
realized forward 1-week return. Aggregated metrics live in backtest.metrics.

The scoring function is injected so the same engine can validate any model. A
default momentum scorer is provided so the engine is runnable out of the box.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest.metrics import (
    information_coefficient,
    long_short_spread,
    sharpe,
)
from src.logging_setup import get_logger

log = get_logger(__name__)

# scorer(prices_up_to_t) -> Series[ticker -> score]; prices is {ticker: df(date,close)}
ScoreFn = Callable[[dict[str, pd.DataFrame]], "pd.Series"]


def momentum_scorer(prices: dict[str, pd.DataFrame], lookback: int = 60) -> pd.Series:
    """Default model: trailing `lookback`-day return as the score."""
    scores = {}
    for ticker, df in prices.items():
        c = df["close"].dropna()
        if len(c) > lookback:
            scores[ticker] = float(c.iloc[-1] / c.iloc[-lookback - 1] - 1.0)
    return pd.Series(scores)


@dataclass
class BacktestResult:
    per_week: pd.DataFrame          # week, basket_return, ic, ls_spread, n
    basket_sharpe: float
    mean_ic: float
    mean_basket_return: float
    mean_ls_spread: float
    n_weeks: int

    def summary(self) -> str:
        return (
            f"weeks={self.n_weeks} | basket_return/wk={self.mean_basket_return:+.4f} "
            f"| Sharpe={self.basket_sharpe:.2f} | mean_IC={self.mean_ic:+.3f} "
            f"| L/S spread={self.mean_ls_spread:+.4f}"
        )


def _align_calendar(prices: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    all_dates = sorted({pd.Timestamp(d) for df in prices.values() for d in df["date"]})
    return pd.DatetimeIndex(all_dates)


def walk_forward(
    prices: dict[str, pd.DataFrame],
    score_fn: ScoreFn = momentum_scorer,
    *,
    step_days: int = 5,
    warmup_days: int = 130,
    top_quantile: float = 0.2,
) -> BacktestResult:
    """Run the walk-forward backtest.

    Args:
        prices: {ticker: DataFrame[date, close]} sorted oldest-first.
        score_fn: maps the as-of price dict to per-ticker scores.
        step_days: trading days between rebalances (5 ≈ weekly).
        warmup_days: minimum history before the first score.
        top_quantile: long-basket cutoff (0.2 = top 20%).
    """
    calendar = _align_calendar(prices)
    # index each ticker frame by date for fast as-of slicing
    indexed = {t: df.assign(date=pd.to_datetime(df["date"])).set_index("date").sort_index()
               for t, df in prices.items()}

    rows = []
    for i in range(warmup_days, len(calendar) - step_days, step_days):
        asof = calendar[i]
        fwd = calendar[i + step_days]
        asof_prices = {t: d.loc[:asof].reset_index() for t, d in indexed.items()}
        asof_prices = {t: d for t, d in asof_prices.items() if len(d) >= 2}
        if len(asof_prices) < 5:
            continue
        scores = score_fn(asof_prices).dropna()
        if scores.empty:
            continue

        fwd_ret = {}
        for t in scores.index:
            d = indexed[t]
            p0 = d.loc[:asof, "close"]
            p1 = d.loc[:fwd, "close"]
            if len(p0) and len(p1):
                c0, c1 = p0.iloc[-1], p1.iloc[-1]
                if c0:
                    fwd_ret[t] = c1 / c0 - 1.0
        fwd_ret = pd.Series(fwd_ret)
        common = scores.index.intersection(fwd_ret.index)
        if len(common) < 5:
            continue
        scores, fwd_ret = scores[common], fwd_ret[common]

        cutoff = scores.quantile(1 - top_quantile)
        basket = fwd_ret[scores >= cutoff]
        rows.append({
            "week": asof.date().isoformat(),
            "basket_return": float(basket.mean()),
            "ic": information_coefficient(scores, fwd_ret),
            "ls_spread": long_short_spread(scores, fwd_ret, top_quantile),
            "n": int(len(common)),
        })

    per_week = pd.DataFrame(rows)
    if per_week.empty:
        log.warning("Backtest produced no weeks (insufficient history?)")
        return BacktestResult(per_week, float("nan"), float("nan"), float("nan"), float("nan"), 0)

    return BacktestResult(
        per_week=per_week,
        basket_sharpe=sharpe(per_week["basket_return"]),
        mean_ic=float(per_week["ic"].mean()),
        mean_basket_return=float(per_week["basket_return"].mean()),
        mean_ls_spread=float(per_week["ls_spread"].mean()),
        n_weeks=len(per_week),
    )
