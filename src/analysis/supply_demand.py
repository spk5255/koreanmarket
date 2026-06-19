"""Supply/demand analysis from investor flows + short interest.

Foreign and institutional net buying are a dominant signal in KR markets. We
measure recent streaks/acceleration and short-interest build-up/unwind from the
per-ticker flow frame (one row per date, oldest first).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _streak(values: pd.Series) -> int:
    """Length of the current consecutive same-sign run at the tail (signed)."""
    arr = values.dropna().to_numpy()
    if len(arr) == 0:
        return 0
    sign = np.sign(arr[-1])
    if sign == 0:
        return 0
    count = 0
    for v in arr[::-1]:
        if np.sign(v) == sign:
            count += 1
        else:
            break
    return int(count * sign)


def compute_supply_demand_metrics(flows: pd.DataFrame, window: int = 20) -> dict[str, float]:
    """Return supply/demand metrics. {} if no data.

    Keys: foreign_net_sum_20, inst_net_sum_20, foreign_streak, inst_streak,
    combined_net_sum_20, short_change_20 (signed % change in short balance),
    short_build (1 if short balance rising).
    """
    if flows is None or flows.empty:
        return {}
    flows = flows.reset_index(drop=True)
    out: dict[str, float] = {}
    tail = flows.tail(window)

    for col, key in (("foreign_net", "foreign_net_sum_20"), ("inst_net", "inst_net_sum_20")):
        if col in flows.columns:
            out[key] = float(pd.to_numeric(tail[col], errors="coerce").fillna(0).sum())

    if "foreign_net" in flows.columns:
        out["foreign_streak"] = float(_streak(pd.to_numeric(flows["foreign_net"], errors="coerce")))
    if "inst_net" in flows.columns:
        out["inst_streak"] = float(_streak(pd.to_numeric(flows["inst_net"], errors="coerce")))

    out["combined_net_sum_20"] = out.get("foreign_net_sum_20", 0.0) + out.get("inst_net_sum_20", 0.0)

    if "short_balance" in flows.columns:
        sb = pd.to_numeric(flows["short_balance"], errors="coerce").dropna()
        if len(sb) > window:
            past, now = sb.iloc[-window - 1], sb.iloc[-1]
            if past and past != 0:
                chg = float(now / past - 1.0)
                out["short_change_20"] = chg
                out["short_build"] = float(chg > 0)
    return out
