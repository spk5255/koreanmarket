"""Assemble the ranked weekly markdown report.

Takes a ranked DataFrame (one row per ticker with composite, group scores, and
projection fields) and renders top opportunities + top risks with the factor
breakdown, scenario ranges, and confidence. An optional Claude narrative can be
layered on; offline we use a templated narrative.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.settings import REPORTS_DIR

DISCLAIMER = (
    "> **Not investment advice.** This is research/decision-support output. "
    "Projections are uncertain; ranges are scenario estimates, not guarantees. "
    "Model credibility depends on the backtest — see hit-rate before trusting any number."
)


def _fmt_won(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:,.0f}"


def _row_block(r: pd.Series) -> str:
    groups = (
        f"F {r.get('fundamental', float('nan')):.2f} · "
        f"T {r.get('technical', float('nan')):.2f} · "
        f"S/D {r.get('supply_demand', float('nan')):.2f} · "
        f"Sent {r.get('sentiment', float('nan')):.2f}"
    )
    return (
        f"### {r['ticker']} {r.get('name', '')} — composite **{r['composite']:.1f}** "
        f"({r.get('confidence', 'low')} confidence)\n\n"
        f"- Factors: {groups}\n"
        f"- Last close: {_fmt_won(r.get('last_close'))}  →  "
        f"base **{_fmt_won(r.get('base'))}**, "
        f"bull {_fmt_won(r.get('bull'))}, bear {_fmt_won(r.get('bear'))}  "
        f"(P(up) {r.get('prob_up', float('nan')):.0%})\n"
    )


def build_report(ranked: pd.DataFrame, week: str, *, top_n: int = 5) -> str:
    """Render the full markdown report string."""
    ranked = ranked.sort_values("composite", ascending=False).reset_index(drop=True)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    opps = ranked.head(top_n)
    risks = ranked.tail(top_n).sort_values("composite")

    lines: list[str] = []
    lines.append(f"# Korean Market — Weekly Projection · {week}\n")
    lines.append(f"_Generated {generated} · universe: {len(ranked)} names_\n")
    lines.append(DISCLAIMER + "\n")
    lines.append("---\n")

    lines.append(f"## Top {len(opps)} Opportunities\n")
    for _, r in opps.iterrows():
        lines.append(_row_block(r))

    lines.append("\n---\n")
    lines.append(f"## Top {len(risks)} Risk Flags\n")
    for _, r in risks.iterrows():
        lines.append(_row_block(r))

    lines.append("\n---\n")
    lines.append("## Full Ranking\n")
    cols = ["ticker", "name", "composite", "confidence", "prob_up", "base"]
    have = [c for c in cols if c in ranked.columns]
    header = "| " + " | ".join(have) + " |"
    sep = "| " + " | ".join("---" for _ in have) + " |"
    lines.append(header)
    lines.append(sep)
    for _, r in ranked.iterrows():
        cells = []
        for c in have:
            v = r[c]
            if c == "prob_up" and pd.notna(v):
                cells.append(f"{v:.0%}")
            elif c == "composite" and pd.notna(v):
                cells.append(f"{v:.1f}")
            elif c == "base" and pd.notna(v):
                cells.append(_fmt_won(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"


def write_report(markdown: str, week: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"weekly_{week}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
