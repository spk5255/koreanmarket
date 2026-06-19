"""Explainability: turn the computed metrics into plain-Korean reasoning.

Rule-based (no LLM, no cost): given a ticker's price/fundamental/flow data, it
recomputes the underlying signals and emits human-readable drivers, a summary
tied to the probability, and a financial-statement listing. The dashboard uses
this for the "왜 이 확률인가" panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.analysis.fundamental import compute_fundamental_metrics
from src.analysis.supply_demand import compute_supply_demand_metrics
from src.analysis.technical import compute_technical_metrics


@dataclass
class Driver:
    label: str
    detail: str
    polarity: str  # "pos" | "neg" | "neutral"


@dataclass
class Reasoning:
    summary: str
    drivers: list[Driver] = field(default_factory=list)
    financials: list[tuple[str, str]] = field(default_factory=list)
    financial_period: str | None = None


def _eok(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x / 1e8:,.0f}억원"


def _pct(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:.1%}"


def build_reasoning(prices: pd.DataFrame, fundamentals: pd.DataFrame, flows: pd.DataFrame,
                    *, prob_up: float, composite: float) -> Reasoning:
    tech = compute_technical_metrics(prices) if prices is not None and not prices.empty else {}
    fund = compute_fundamental_metrics(fundamentals) if fundamentals is not None and not fundamentals.empty else {}
    sd = compute_supply_demand_metrics(flows) if flows is not None and not flows.empty else {}

    drivers: list[Driver] = []

    # --- 기술적 ---
    mom = tech.get("momentum_120")
    if mom is not None and not pd.isna(mom):
        drivers.append(Driver("주가 추세 (120일선 대비)",
                              f"{mom:+.1%} · {'상승 추세' if mom > 0 else '하락 추세'}",
                              "pos" if mom > 0 else "neg"))
    rsi = tech.get("rsi14")
    if rsi is not None and not pd.isna(rsi):
        if rsi >= 70:
            txt, pol = "과열 구간 (조정 위험)", "neg"
        elif rsi <= 30:
            txt, pol = "과매도 구간 (반등 여지)", "pos"
        else:
            txt, pol = "중립 구간", "neutral"
        drivers.append(Driver("모멘텀 (RSI 14)", f"RSI {rsi:.0f} · {txt}", pol))
    if tech.get("golden_cross"):
        drivers.append(Driver("골든크로스", "20일선이 60일선을 상향 돌파", "pos"))
    if tech.get("above_sma60") == 0.0:
        drivers.append(Driver("60일선 이탈", "현재가가 60일 이동평균 아래", "neg"))

    # --- 펀더멘털 ---
    roe = fund.get("roe")
    if roe is not None:
        drivers.append(Driver("자기자본이익률 (ROE)", _pct(roe),
                              "pos" if roe > 0.10 else "neg" if roe < 0.05 else "neutral"))
    opm = fund.get("op_margin")
    if opm is not None:
        drivers.append(Driver("영업이익률", _pct(opm),
                              "pos" if opm > 0.12 else "neg" if opm < 0.04 else "neutral"))
    dte = fund.get("debt_to_equity")
    if dte is not None:
        drivers.append(Driver("부채비율 (부채/자본)", _pct(dte),
                              "neg" if dte > 1.5 else "pos" if dte < 0.5 else "neutral"))
    ocf_ni = fund.get("ocf_to_ni")
    if ocf_ni is not None:
        drivers.append(Driver("이익의 질 (영업현금/순이익)", f"{ocf_ni:.2f}배",
                              "pos" if ocf_ni > 1.0 else "neg" if ocf_ni < 0.7 else "neutral"))

    # --- 수급 ---
    fstreak = sd.get("foreign_streak")
    if fstreak:
        drivers.append(Driver("외국인 수급",
                              f"{abs(int(fstreak))}일 연속 {'순매수' if fstreak > 0 else '순매도'}",
                              "pos" if fstreak > 0 else "neg"))
    istreak = sd.get("inst_streak")
    if istreak:
        drivers.append(Driver("기관 수급",
                              f"{abs(int(istreak))}일 연속 {'순매수' if istreak > 0 else '순매도'}",
                              "pos" if istreak > 0 else "neg"))
    if sd.get("short_build") == 1.0:
        drivers.append(Driver("공매도 잔고 증가", "최근 공매도 잔고 확대", "neg"))

    pos = sum(1 for d in drivers if d.polarity == "pos")
    neg = sum(1 for d in drivers if d.polarity == "neg")
    tone = "상승 우위" if prob_up >= 0.55 else "하락 우위" if prob_up <= 0.45 else "중립"
    summary = (f"상승확률 {prob_up:.0%} · 종합점수 {composite:.1f}점 — "
               f"긍정 신호 {pos}개, 부정 신호 {neg}개로 종합 판단은 '{tone}'입니다.")

    # --- 재무제표 listing ---
    financials: list[tuple[str, str]] = []
    period = None
    if fundamentals is not None and not fundamentals.empty:
        last = fundamentals.iloc[-1]
        period = str(last.get("period"))
        financials = [
            ("매출액", _eok(last.get("revenue"))),
            ("영업이익", _eok(last.get("op_profit"))),
            ("당기순이익", _eok(last.get("net_income"))),
            ("자본총계", _eok(last.get("equity"))),
            ("부채총계", _eok(last.get("total_liab"))),
            ("영업현금흐름", _eok(last.get("ocf"))),
            ("ROE", _pct(roe)),
            ("영업이익률", _pct(opm)),
            ("부채비율", _pct(dte)),
        ]

    return Reasoning(summary=summary, drivers=drivers, financials=financials, financial_period=period)
