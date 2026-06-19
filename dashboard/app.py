"""Streamlit dashboard — Robinhood-style, fully Korean.

Hosted demo entry point. On first load it seeds synthetic data and runs the
pipeline (no live APIs, no Anthropic), then renders an app-like dark UI.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import pandas as pd

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise SystemExit("streamlit not installed. pip install -e '.[dashboard]'") from exc

from sqlalchemy import func, select

from src.storage.db import init_db, session_scope
from src.storage.models import Company, FactorScore, Price, Projection
from src.storage.repository import get_prices
from src.utils import iso_week_label

DEMO_YEARS = 1.5
GREEN = "#00C805"
RED = "#FF5000"
MUTED = "#9b9b9b"

CONF_KO = {"low": "낮음", "medium": "보통", "high": "높음"}
FACTOR_KO = {"fundamental": "펀더멘털", "technical": "기술적", "supply_demand": "수급", "sentiment": "심리"}


# ----------------------------------------------------------------- bootstrap ---

@st.cache_resource(show_spinner="데모 데이터를 준비하는 중…")
def bootstrap() -> str:
    init_db()
    week = iso_week_label(date.today())
    with session_scope() as s:
        n_prices = s.scalar(select(func.count()).select_from(Price)) or 0
    if n_prices == 0:
        from scripts.seed_synthetic import main as seed_main
        sys.argv = ["seed_synthetic", "--years", str(DEMO_YEARS), "--seed", "42"]
        seed_main()
    with session_scope() as s:
        n_week = s.scalar(select(func.count()).select_from(Projection).where(Projection.week == week)) or 0
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


@st.cache_data(ttl=120)
def load_prices(ticker: str) -> pd.DataFrame:
    with session_scope() as s:
        df = get_prices(s, ticker)
    if df.empty:
        return df
    df = df.tail(120).copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


# --------------------------------------------------------------------- style ---

def inject_css() -> None:
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"], .stApp {{ font-family: 'Inter', -apple-system, sans-serif; }}
    .stApp {{ background: #0a0a0a; }}
    #MainMenu, header, footer {{ visibility: hidden; }}
    [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
    .block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 880px; }}
    .rh-title {{ font-size: 1.6rem; font-weight: 800; color: #fff; letter-spacing: -0.5px; }}
    .rh-sub {{ color: {MUTED}; font-size: 0.85rem; margin-top: 2px; }}
    .rh-stat-label {{ color: {MUTED}; font-size: 0.78rem; font-weight: 500; }}
    .rh-stat-value {{ color: #fff; font-size: 1.9rem; font-weight: 700; letter-spacing: -1px; line-height: 1.1; }}
    .rh-card {{ background: #131720; border: 1px solid #1f2429; border-radius: 14px; padding: 6px 14px; }}
    .rh-row {{ display:flex; justify-content:space-between; align-items:center; padding: 13px 4px; border-bottom: 1px solid #1a1f25; }}
    .rh-row:last-child {{ border-bottom: none; }}
    .rh-name {{ color:#fff; font-weight:600; font-size:0.98rem; }}
    .rh-ticker {{ color:{MUTED}; font-size:0.74rem; margin-top:1px; }}
    .rh-score {{ font-weight:700; font-size:1.15rem; text-align:right; }}
    .rh-prob {{ font-size:0.78rem; font-weight:600; text-align:right; margin-top:1px; }}
    .rh-chip {{ display:inline-block; background:#131720; border:1px solid #1f2429; border-radius:10px;
               padding:8px 14px; margin-right:8px; }}
    .rh-chip-label {{ color:{MUTED}; font-size:0.7rem; }}
    .rh-chip-val {{ color:#fff; font-weight:700; font-size:1.05rem; }}
    .rh-bar-track {{ background:#1a1f25; border-radius:6px; height:8px; width:100%; overflow:hidden; }}
    .rh-bar-fill {{ background:{GREEN}; height:8px; border-radius:6px; }}
    .rh-bar-label {{ color:{MUTED}; font-size:0.8rem; display:flex; justify-content:space-between; margin:10px 0 4px; }}
    .rh-disclaimer {{ color:#6b7280; font-size:0.72rem; margin-top:6px; }}
    div[data-baseweb="select"] > div {{ background:#131720; border-color:#1f2429; }}
    </style>
    """, unsafe_allow_html=True)


def _won(x) -> str:
    return f"₩{x:,.0f}" if pd.notna(x) else "—"


def _score_color(v) -> str:
    if pd.isna(v):
        return MUTED
    return GREEN if v >= 55 else (RED if v <= 45 else "#d0d0d0")


def render_ranking(df: pd.DataFrame) -> None:
    rows_html = ""
    for _, r in df.iterrows():
        c = _score_color(r["composite"])
        up = pd.notna(r["prob_up"]) and r["prob_up"] >= 0.5
        pc = GREEN if up else RED
        arrow = "▲" if up else "▼"
        prob = f"{r['prob_up']:.0%}" if pd.notna(r["prob_up"]) else "—"
        rows_html += (
            f'<div class="rh-row">'
            f'<div><div class="rh-name">{r["name"]}</div><div class="rh-ticker">{r["ticker"]}</div></div>'
            f'<div><div class="rh-score" style="color:{c}">{r["composite"]:.1f}</div>'
            f'<div class="rh-prob" style="color:{pc}">{arrow} 상승확률 {prob}</div></div>'
            f'</div>'
        )
    st.markdown(f'<div class="rh-card">{rows_html}</div>', unsafe_allow_html=True)


def render_price_chart(ticker: str) -> None:
    pdf = load_prices(ticker)
    if pdf.empty:
        return
    up = pdf["close"].iloc[-1] >= pdf["close"].iloc[0]
    color = GREEN if up else RED
    ret = pdf["close"].iloc[-1] / pdf["close"].iloc[0] - 1
    area = (
        alt.Chart(pdf)
        .mark_area(
            line={"color": color, "size": 2},
            color=alt.Gradient(
                gradient="linear",
                stops=[alt.GradientStop(color="#0a0a0a", offset=0),
                       alt.GradientStop(color=color, offset=1)],
                x1=1, x2=1, y1=1, y2=0,
            ),
            opacity=0.25,
        )
        .encode(
            x=alt.X("date:T", axis=None),
            y=alt.Y("close:Q", axis=None, scale=alt.Scale(zero=False)),
        )
        .properties(height=170)
        .configure_view(strokeWidth=0)
        .configure(background="#0a0a0a")
    )
    st.markdown(
        f'<div class="rh-sub">최근 {len(pdf)}거래일 · '
        f'<span style="color:{color};font-weight:600">{ret:+.1%}</span></div>',
        unsafe_allow_html=True,
    )
    st.altair_chart(area, use_container_width=True)


def render_factor_bars(r: pd.Series) -> None:
    html = ""
    for key, label in FACTOR_KO.items():
        v = r[key] if pd.notna(r[key]) else 0.5
        pct = max(0, min(100, v * 100))
        html += (
            f'<div class="rh-bar-label"><span>{label}</span>'
            f'<span style="color:#fff">{v:.2f}</span></div>'
            f'<div class="rh-bar-track"><div class="rh-bar-fill" style="width:{pct:.0f}%"></div></div>'
        )
    st.markdown(html, unsafe_allow_html=True)


def _password_ok() -> bool:
    try:
        pw = st.secrets.get("app_password")
    except Exception:
        pw = None
    if not pw:
        return True
    if st.session_state.get("authed"):
        return True
    entered = st.text_input("비밀번호", type="password")
    if entered == pw:
        st.session_state["authed"] = True
        return True
    if entered:
        st.error("비밀번호가 올바르지 않습니다.")
    return False


def stat_block(label: str, value: str, sub: str = "", color: str = "#fff") -> str:
    sub_html = f'<div class="rh-prob" style="color:{MUTED};text-align:left">{sub}</div>' if sub else ""
    return (f'<div><div class="rh-stat-label">{label}</div>'
            f'<div class="rh-stat-value" style="color:{color}">{value}</div>{sub_html}</div>')


def main() -> None:
    st.set_page_config(page_title="한국 시장 주간 전망", page_icon="📈", layout="centered")
    inject_css()
    if not _password_ok():
        st.stop()

    week = bootstrap()
    df = load_ranking(week)

    st.markdown('<div class="rh-title">한국 시장 · 주간 전망</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rh-sub">ISO {week} · 합성 데이터 데모 · 투자 자문 아님</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if df.empty:
        st.warning("데이터가 없습니다.")
        return

    top = df.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.markdown(stat_block("최고 종합점수", f"{top['composite']:.1f}",
                           f"{top['name']} {top['ticker']}", GREEN), unsafe_allow_html=True)
    c2.markdown(stat_block("분석 종목 수", f"{len(df)}"), unsafe_allow_html=True)
    c3.markdown(stat_block("평균 상승확률", f"{df['prob_up'].mean():.0%}"), unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="rh-stat-label" style="font-size:0.95rem;color:#fff;font-weight:700;margin-bottom:8px">종목 순위</div>', unsafe_allow_html=True)
    render_ranking(df)

    st.write("")
    st.markdown('<div class="rh-stat-label" style="font-size:0.95rem;color:#fff;font-weight:700">종목 상세</div>', unsafe_allow_html=True)
    options = [f"{r['name']} ({r['ticker']})" for _, r in df.iterrows()]
    pick = st.selectbox("종목 선택", options, label_visibility="collapsed")
    ticker = pick[pick.rfind("(") + 1: pick.rfind(")")]
    r = df[df["ticker"] == ticker].iloc[0]

    cc = _score_color(r["composite"])
    st.markdown(stat_block("종합점수", f"{r['composite']:.1f}", "", cc), unsafe_allow_html=True)
    render_price_chart(ticker)

    st.write("")
    up = pd.notna(r["prob_up"]) and r["prob_up"] >= 0.5
    chips = (
        f'<span class="rh-chip"><div class="rh-chip-label">기준</div>'
        f'<div class="rh-chip-val">{_won(r["base"])}</div></span>'
        f'<span class="rh-chip"><div class="rh-chip-label">강세</div>'
        f'<div class="rh-chip-val" style="color:{GREEN}">{_won(r["bull"])}</div></span>'
        f'<span class="rh-chip"><div class="rh-chip-label">약세</div>'
        f'<div class="rh-chip-val" style="color:{RED}">{_won(r["bear"])}</div></span>'
        f'<span class="rh-chip"><div class="rh-chip-label">상승확률</div>'
        f'<div class="rh-chip-val" style="color:{GREEN if up else RED}">{r["prob_up"]:.0%}</div></span>'
        f'<span class="rh-chip"><div class="rh-chip-label">신뢰도</div>'
        f'<div class="rh-chip-val">{CONF_KO.get(str(r["confidence"]), r["confidence"])}</div></span>'
    )
    st.markdown(chips, unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="rh-stat-label" style="margin-bottom:2px">팩터 분석</div>', unsafe_allow_html=True)
    render_factor_bars(r)

    st.markdown(
        '<div class="rh-disclaimer">※ 본 화면은 합성(가상) 데이터로 모델을 시연하기 위한 리서치 도구입니다. '
        '실제 시장 데이터가 아니며 투자 자문이 아닙니다.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
