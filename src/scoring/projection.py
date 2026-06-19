"""Weekly scenario projection from composite score + realized volatility.

This is deliberately simple and *honest*: a composite tilt maps to a small
expected weekly drift, and the bull/bear bands are volatility-driven. None of
this is a guaranteed price — confidence reflects cross-factor agreement and is
only trustworthy after the Phase 5 backtest validates the mapping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

# Max expected one-week drift at the extremes of the score (|score-50|=50).
_MAX_WEEKLY_DRIFT = 0.03   # +/-3%
_BULL_BEAR_K = 1.5          # band width in units of weekly vol


@dataclass
class Projection:
    ticker: str
    week: str
    last_close: float
    base: float
    bull: float
    bear: float
    prob_up: float
    confidence: str
    expected_return: float

    def as_row(self) -> dict:
        return {
            "ticker": self.ticker, "week": self.week, "base": self.base,
            "bull": self.bull, "bear": self.bear, "prob_up": self.prob_up,
            "confidence": self.confidence,
        }

    def to_dict(self) -> dict:
        return asdict(self)


def _confidence_label(agreement: float, weekly_vol: float) -> str:
    """High agreement + moderate vol -> higher confidence."""
    if math.isnan(weekly_vol):
        return "low"
    if agreement >= 0.85 and weekly_vol < 0.06:
        return "high"
    if agreement >= 0.65:
        return "medium"
    return "low"


def project_week(
    ticker: str,
    week: str,
    *,
    composite: float,
    weekly_vol: float,
    last_close: float,
    agreement: float = 0.5,
) -> Projection:
    """Build a one-week base/bull/bear projection.

    Args:
        composite: 0..100 composite score.
        weekly_vol: realized 1-week vol (fraction, e.g. 0.04 = 4%).
        last_close: latest close price.
        agreement: 0.5..1 cross-factor agreement (drives confidence).
    """
    tilt = (composite - 50.0) / 50.0            # -1..1
    drift = tilt * _MAX_WEEKLY_DRIFT
    wv = 0.0 if math.isnan(weekly_vol) else weekly_vol

    base = last_close * (1 + drift)
    bull = last_close * (1 + drift + _BULL_BEAR_K * wv)
    bear = last_close * (1 + drift - _BULL_BEAR_K * wv)

    # Probability the week closes up: logistic of (drift / vol) signal-to-noise.
    if wv > 0:
        prob_up = 1 / (1 + math.exp(-(drift / wv) * 1.5))
    else:
        prob_up = 0.5 + 0.5 * tilt
    prob_up = max(0.01, min(0.99, prob_up))

    return Projection(
        ticker=ticker, week=week, last_close=round(last_close, 1),
        base=round(base, 1), bull=round(bull, 1), bear=round(bear, 1),
        prob_up=round(prob_up, 3),
        confidence=_confidence_label(agreement, wv),
        expected_return=round(drift, 4),
    )
