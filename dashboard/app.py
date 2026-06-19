"""Streamlit dashboard — hosted demo entry point.

Designed to run on Streamlit Community Cloud with ZERO setup: on first load it
seeds synthetic data and runs the full scoring pipeline, then renders the
ranking. It never calls live market APIs or Anthropic, so a public link cannot
incur cost. Optionally gate behind a password via Streamlit secrets:

    # .streamlit/secrets.toml  (set in the Streamlit Cloud UI, NOT committed)
    app_password = "letmein"
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise SystemExit("streamlit not installed. pip install -e '.[dashboard]'") from exc

from sqlalchemy import func, select

from src.storage.db import init_db, session_scope
from src.storage.models import Company, FactorScore, Price, Projection
from src.utils import iso_week_label

DEMO_YEARS = 1.5  # smaller history = faster cold start on the free tier


@st.cache_resource(show_spinner="Preparing demo data (one-time)…")
def bootstrap() -> str:
    """Seed synthetic data + run the pipeline once per container. Returns the week."""
    init_db()
    week = iso_week_label(date.today())
    with session_scope() as s:
        n_prices = s.scalar(select(func.count()).select_from(Price)) or 0
    if n_prices == 0:
        from scripts.seed_synthetic import main as seed_main
        sys.argv = ["seed_synthetic", "--years", str(DEMO_YEARS), "--seed", "42"]
        seed_main()
    with session_scope() as s:
        n_week = s.scalar(
            select(func.count()).select_from(Projection).where(Projection.week == week)
        ) or 0
    if n_week == 0:
        from src.scheduler.weekly_job import run_once
        run_once(week=week)
    return week


@st.cache_data(ttl=120)
def load_ranking(week: str) -> pd.DataFrame:
    with session_scope() as s:
        names = {c.ticker: c.name for c in s.scalars(select(Company)).all()}
        projs = s.scalars(select(Projection).where(Projection.week == week)).all()
        latest = s.scalars(select(FactorScore.asof).order_by(FactorScore.asof.desc())).first()
        scores = s.scalars(select(FactorScore).where(FactorScore.asof == latest)).all() if latest else []
    sc = {f.ticker: f for f in scores}
    rows = []
    for p in projs:
        f = sc.get(p.ticker)
        rows.append({
            "ticker": p.ticker, "name": names.get(p.ticker, ""),
            "composite": f.composite if f else None,
            "fundamental": f.fundamental if f else None, "technical": f.technical if f else None,
            "supply_demand": f.supply_demand if f else None, "sentiment": f.sentiment if f else None,
            "base": p.base, "bull": p.bull, "bear": p.bear,
            "prob_up": p.prob_up, "confidence": p.confidence,
        })
    df = pd.DataFrame(rows)
    return df.sort_values("composite", ascending=False).reset_index(drop=True) if not df.empty else df


def _password_ok() -> bool:
    try:
        pw = st.secrets.get("app_password")
    except Exception:
        pw = None
    if not pw:
        return True
    if st.session_state.get("authed"):
        return True
    entered = st.text_input("Password", type="password")
    if entered == pw:
        st.session_state["authed"] = True
        return True
    if entered:
        st.error("Incorrect password.")
    return False


def main() -> None:
    st.set_page_config(page_title="Korean Market Analyzer", page_icon="📈", layout="wide")
    if not _password_ok():
        st.stop()

    st.title("📈 Korean Market — Weekly Projection")
    st.caption("Demo on **synthetic data** · research/decision-support only · **not investment advice**")

    week = bootstrap()
    df = load_ranking(week)
    if df.empty:
        st.warning("No data available.")
        return

    st.info(f"Showing {len(df)} names for ISO week **{week}**. "
            "All numbers are generated from synthetic prices to demonstrate the model — not real market data.")

    c1, c2, c3 = st.columns(3)
    top = df.iloc[0]
    c1.metric("Top composite", f"{top['composite']:.1f}", top["ticker"] + " " + top["name"])
    c2.metric("Names ranked", len(df))
    c3.metric("Avg P(up)", f"{df['prob_up'].mean():.0%}")

    st.subheader("Ranking")
    show = df.copy()
    show["prob_up"] = (show["prob_up"] * 100).round(0).astype("Int64").astype(str) + "%"
    st.dataframe(show, use_container_width=True, hide_index=True)

    st.subheader("Drill into a name")
    pick = st.selectbox("Stock", df["ticker"] + " — " + df["name"])
    ticker = pick.split(" — ")[0]
    r = df[df["ticker"] == ticker].iloc[0]
    a, b, c = st.columns(3)
    a.metric("Composite", f"{r['composite']:.1f}")
    b.metric("P(up)", f"{r['prob_up']:.0%}")
    c.metric("Confidence", str(r["confidence"]))
    st.write(f"**Scenario** — base **{r['base']:,.0f}** · bull {r['bull']:,.0f} · bear {r['bear']:,.0f}")
    st.bar_chart(pd.Series(
        {g: r[g] for g in ("fundamental", "technical", "supply_demand", "sentiment")},
        name="factor score (0–1)",
    ))


if __name__ == "__main__":
    main()
