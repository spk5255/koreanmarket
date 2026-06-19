"""Weekly orchestration: ingest -> analyze -> score -> project -> report.

`run_once` is the idempotent integration entry point. It reads whatever market
data is already in the DB (live-ingested or synthetic), computes per-ticker
metrics, builds the cross-sectional factor table, blends the composite, projects
the coming week, persists scores + projections, and writes the markdown report.

`schedule_weekly` wires the same job to APScheduler (Sunday 18:00 KST) so the
report is ready before Monday open.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from config.settings import settings
from config.universe import get_universe
from src.analysis.fundamental import compute_fundamental_metrics
from src.analysis.supply_demand import compute_supply_demand_metrics
from src.analysis.technical import compute_technical_metrics
from src.logging_setup import get_logger
from src.reporting.weekly_report import build_report, write_report
from src.scoring.composite import composite_score, signal_agreement
from src.scoring.factors import build_factor_table
from src.scoring.projection import project_week
from src.storage.db import session_scope
from src.storage.repository import (
    get_flows,
    get_fundamentals,
    get_prices,
    list_companies,
    save_factor_scores,
    save_projection,
)
from src.utils import iso_week_label

log = get_logger(__name__)


@dataclass
class RunResult:
    week: str
    n_scored: int
    report_path: str
    ranked: pd.DataFrame


def _collect_raw_metrics(session) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Build the per-ticker raw-metrics table + a side table of name/close/vol."""
    rows: dict[str, dict] = {}
    aux: dict[str, dict] = {}
    for company in list_companies(session):
        t = company.ticker
        prices = get_prices(session, t)
        if prices.empty:
            continue
        tech = compute_technical_metrics(prices)
        flows = get_flows(session, t)
        sd = compute_supply_demand_metrics(flows) if not flows.empty else {}
        funds = get_fundamentals(session, t)
        fund = compute_fundamental_metrics(funds) if not funds.empty else {}
        # Sentiment: offline default neutral (news ingestion is Phase 1 live-only).
        sentiment = {"sentiment": 0.0}

        rows[t] = {**fund, **tech, **sd, **sentiment}
        aux[t] = {
            "name": company.name,
            "last_close": tech.get("close"),
            "weekly_vol": tech.get("weekly_vol", float("nan")),
        }
    return pd.DataFrame.from_dict(rows, orient="index"), aux


def run_once(*, week: str | None = None, top_n: int = 5) -> RunResult:
    """Execute the full weekly pipeline against current DB data."""
    week = week or iso_week_label(date.today())
    log.info("Weekly run starting for %s", week)

    with session_scope() as session:
        raw, aux = _collect_raw_metrics(session)
        if raw.empty:
            raise RuntimeError("No market data in DB. Seed it first (scripts/seed_synthetic.py or ingestion).")

        factor_table = build_factor_table(raw)
        composite = composite_score(factor_table, settings.factor_weights)
        agreement = signal_agreement(factor_table)

        ranked_rows = []
        for ticker in composite.sort_values(ascending=False).index:
            a = aux[ticker]
            proj = project_week(
                ticker, week,
                composite=float(composite[ticker]),
                weekly_vol=float(a["weekly_vol"]) if a["weekly_vol"] == a["weekly_vol"] else float("nan"),
                last_close=float(a["last_close"]) if a["last_close"] else 0.0,
                agreement=float(agreement[ticker]),
            )
            row = {
                "ticker": ticker, "name": a["name"],
                "composite": float(composite[ticker]),
                **{g: float(factor_table.loc[ticker, g]) for g in factor_table.columns},
                "last_close": proj.last_close, "base": proj.base, "bull": proj.bull,
                "bear": proj.bear, "prob_up": proj.prob_up, "confidence": proj.confidence,
            }
            ranked_rows.append(row)
            save_projection(session, proj.as_row())

        asof = date.today()
        save_factor_scores(session, [
            {"ticker": t, "asof": asof,
             "fundamental": float(factor_table.loc[t, "fundamental"]),
             "technical": float(factor_table.loc[t, "technical"]),
             "supply_demand": float(factor_table.loc[t, "supply_demand"]),
             "sentiment": float(factor_table.loc[t, "sentiment"]),
             "composite": float(composite[t])}
            for t in factor_table.index
        ])

        ranked = pd.DataFrame(ranked_rows)

    markdown = build_report(ranked, week, top_n=top_n)
    path = write_report(markdown, week)
    log.info("Weekly run complete: %d names scored, report -> %s", len(ranked), path)
    return RunResult(week=week, n_scored=len(ranked), report_path=str(path), ranked=ranked)


def schedule_weekly() -> None:  # pragma: no cover - requires apscheduler + long-running process
    """Run the weekly job on a cron (Sunday 18:00 in the configured timezone)."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(run_once, CronTrigger(day_of_week="sun", hour=18, minute=0))
    log.info("Scheduler started: weekly job Sun 18:00 %s", settings.timezone)
    scheduler.start()
