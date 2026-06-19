"""Technical analysis: trend / momentum / volatility / relative strength.

Indicators are implemented directly on pandas/numpy so there is no hard
dependency on pandas-ta (which is awkward on some platforms). Inputs are an
OHLCV DataFrame with a 'close' column (and 'high'/'low' for ATR), oldest first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window, min_periods=window).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    # Zero average loss over the window (pure uptrend) -> RSI 100, not NaN.
    out = out.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    """Annualization-free daily realized vol (std of log returns over a window)."""
    logret = np.log(close / close.shift(1))
    return logret.rolling(window, min_periods=window).std()


def weekly_vol(close: pd.Series, window: int = 20) -> float:
    """Most-recent daily realized vol scaled to a 1-week (5 trading day) horizon."""
    rv = realized_vol(close, window).iloc[-1]
    if pd.isna(rv):
        return float("nan")
    return float(rv) * np.sqrt(5.0)


def compute_technical_metrics(df: pd.DataFrame, index_close: pd.Series | None = None) -> dict[str, float]:
    """Return a flat dict of technical metrics for the latest bar.

    Keys: close, sma20/60/120, above_sma60, golden_cross, rsi14, macd_hist,
    atr14, realized_vol_20, weekly_vol, momentum_120 (close/sma120 - 1),
    rel_strength (stock vs index 60d return) when an index series is given.
    """
    if df is None or df.empty or "close" not in df:
        return {}
    close = df["close"].astype(float).reset_index(drop=True)
    out: dict[str, float] = {"close": float(close.iloc[-1])}

    for w in (20, 60, 120):
        val = sma(close, w).iloc[-1]
        out[f"sma{w}"] = float(val) if pd.notna(val) else float("nan")

    if pd.notna(out.get("sma60", float("nan"))):
        out["above_sma60"] = float(out["close"] > out["sma60"])
    if pd.notna(out.get("sma120", float("nan"))) and out["sma120"]:
        out["momentum_120"] = float(out["close"] / out["sma120"] - 1.0)

    s20, s60 = sma(close, 20), sma(close, 60)
    if len(close) > 2 and pd.notna(s20.iloc[-1]) and pd.notna(s60.iloc[-1]):
        out["golden_cross"] = float(s20.iloc[-1] > s60.iloc[-1] and s20.iloc[-2] <= s60.iloc[-2])

    r = rsi(close).iloc[-1]
    out["rsi14"] = float(r) if pd.notna(r) else float("nan")
    out["macd_hist"] = float(macd(close)["hist"].iloc[-1])
    if {"high", "low"}.issubset(df.columns):
        a = atr(df.reset_index(drop=True)).iloc[-1]
        out["atr14"] = float(a) if pd.notna(a) else float("nan")
    rv = realized_vol(close).iloc[-1]
    out["realized_vol_20"] = float(rv) if pd.notna(rv) else float("nan")
    out["weekly_vol"] = weekly_vol(close)

    if index_close is not None and len(index_close) >= 61 and len(close) >= 61:
        stock_ret = close.iloc[-1] / close.iloc[-61] - 1.0
        idx = index_close.astype(float).reset_index(drop=True)
        idx_ret = idx.iloc[-1] / idx.iloc[-61] - 1.0
        out["rel_strength"] = float(stock_ret - idx_ret)
    return out
