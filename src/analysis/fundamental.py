"""Fundamental analysis: profitability, growth, health, cash-flow quality.

Operates on the per-ticker fundamentals frame (one row per period, oldest
first) produced by storage.repository.get_fundamentals. Valuation-vs-sector is
handled in the scoring layer (it needs the cross-section); here we compute the
absolute per-company metrics.
"""

from __future__ import annotations

import pandas as pd


def _safe_div(a: float | None, b: float | None) -> float | None:
    try:
        if a is None or b is None or b == 0:
            return None
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def compute_fundamental_metrics(fund: pd.DataFrame) -> dict[str, float]:
    """Latest-period ratios + YoY growth. Returns {} if no data.

    Keys: roe, roa, op_margin, net_margin, debt_to_equity, ocf_to_ni (earnings
    quality), fcf, revenue_yoy, op_profit_yoy.
    """
    if fund is None or fund.empty:
        return {}
    fund = fund.reset_index(drop=True)
    latest = fund.iloc[-1]
    out: dict[str, float] = {}

    roe = _safe_div(latest.get("net_income"), latest.get("equity"))
    roa = _safe_div(latest.get("net_income"), latest.get("total_assets"))
    opm = _safe_div(latest.get("op_profit"), latest.get("revenue"))
    npm = _safe_div(latest.get("net_income"), latest.get("revenue"))
    dte = _safe_div(latest.get("total_liab"), latest.get("equity"))
    ocf_ni = _safe_div(latest.get("ocf"), latest.get("net_income"))

    for k, v in (("roe", roe), ("roa", roa), ("op_margin", opm),
                 ("net_margin", npm), ("debt_to_equity", dte), ("ocf_to_ni", ocf_ni)):
        if v is not None:
            out[k] = v

    ocf, capex = latest.get("ocf"), latest.get("capex")
    if ocf is not None and capex is not None:
        out["fcf"] = float(ocf) - float(capex)

    # YoY growth: compare latest to 4 quarters earlier when available.
    if len(fund) >= 5:
        prior = fund.iloc[-5]
        rev_yoy = _safe_div(
            (latest.get("revenue") or 0) - (prior.get("revenue") or 0), prior.get("revenue")
        )
        op_yoy = _safe_div(
            (latest.get("op_profit") or 0) - (prior.get("op_profit") or 0), prior.get("op_profit")
        )
        if rev_yoy is not None:
            out["revenue_yoy"] = rev_yoy
        if op_yoy is not None:
            out["op_profit_yoy"] = op_yoy
    return out
