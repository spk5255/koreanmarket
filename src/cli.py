"""Command-line entry point: ``kma``.

Commands
--------
* ``kma info``           — resolved config (no secrets) + schema.
* ``kma init-db``        — create tables (``--drop`` to recreate).
* ``kma seed``           — upsert the starter universe into ``companies``.
* ``kma seed-synthetic`` — generate offline synthetic prices/flows/fundamentals.
* ``kma run``            — full weekly pipeline -> ranked report.
* ``kma backtest``       — walk-forward backtest of the default scorer.
* ``kma schedule``       — start the weekly APScheduler job (blocking).
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from config.settings import settings
from config.universe import get_universe
from src.logging_setup import configure_logging, get_logger
from src.storage.db import init_db, session_scope
from src.storage.models import Base
from src.storage.repository import get_prices, list_companies, seed_companies

log = get_logger(__name__)


def _cmd_info(_a: argparse.Namespace) -> int:
    print("Korean Market Analyzer — configuration")
    print(f"  db_url          : {settings.resolved_db_url}")
    print(f"  anthropic_model : {settings.anthropic_model}")
    print(f"  timezone        : {settings.timezone}")
    print(f"  dart_key set    : {settings.dart_api_key is not None}")
    print(f"  anthropic_key   : {settings.anthropic_api_key is not None}")
    print(f"  factor_weights  : {settings.factor_weights.as_dict()}")
    print(f"  universe size   : {len(get_universe())}")
    print(f"  tables          : {', '.join(sorted(Base.metadata.tables))}")
    return 0


def _cmd_init_db(a: argparse.Namespace) -> int:
    init_db(drop=a.drop)
    print(f"Database ready at {settings.resolved_db_url}")
    return 0


def _cmd_seed(_a: argparse.Namespace) -> int:
    init_db()
    with session_scope() as s:
        n = seed_companies(s, get_universe())
    print(f"Seeded {n} companies.")
    return 0


def _cmd_seed_synthetic(a: argparse.Namespace) -> int:
    from scripts.seed_synthetic import main as seed_main
    return seed_main_wrapper(seed_main, a)


def seed_main_wrapper(seed_main, a) -> int:  # keep argparse separate from the script's own
    sys.argv = ["seed_synthetic", "--years", str(a.years), "--seed", str(a.seed)]
    return seed_main()


def _cmd_run(a: argparse.Namespace) -> int:
    from src.scheduler.weekly_job import run_once
    res = run_once(week=a.week, top_n=a.top)
    print(f"Scored {res.n_scored} names for {res.week}.")
    print(f"Report: {res.report_path}")
    print("\nTop of ranking:")
    print(res.ranked.head(a.top)[["ticker", "name", "composite", "confidence", "prob_up"]].to_string(index=False))
    return 0


def _cmd_backtest(a: argparse.Namespace) -> int:
    from src.backtest.engine import momentum_scorer, walk_forward
    prices: dict[str, pd.DataFrame] = {}
    with session_scope() as s:
        for c in list_companies(s):
            df = get_prices(s, c.ticker)
            if not df.empty:
                prices[c.ticker] = df[["date", "close"]]
    if not prices:
        print("No price data. Run `kma seed-synthetic` first.")
        return 1
    result = walk_forward(prices, lambda p: momentum_scorer(p, a.lookback), step_days=a.step)
    print("Backtest (default momentum scorer):")
    print("  " + result.summary())
    return 0


def _cmd_schedule(_a: argparse.Namespace) -> int:  # pragma: no cover
    from src.scheduler.weekly_job import schedule_weekly
    schedule_weekly()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kma", description="Korean Market Analyzer")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="show config and schema").set_defaults(func=_cmd_info)

    pi = sub.add_parser("init-db", help="create database tables")
    pi.add_argument("--drop", action="store_true")
    pi.set_defaults(func=_cmd_init_db)

    sub.add_parser("seed", help="seed the starter universe").set_defaults(func=_cmd_seed)

    ps = sub.add_parser("seed-synthetic", help="generate offline synthetic data")
    ps.add_argument("--years", type=float, default=3.0)
    ps.add_argument("--seed", type=int, default=42)
    ps.set_defaults(func=_cmd_seed_synthetic)

    pr = sub.add_parser("run", help="run the weekly pipeline -> report")
    pr.add_argument("--week", type=str, default=None)
    pr.add_argument("--top", type=int, default=5)
    pr.set_defaults(func=_cmd_run)

    pb = sub.add_parser("backtest", help="walk-forward backtest")
    pb.add_argument("--lookback", type=int, default=60)
    pb.add_argument("--step", type=int, default=5)
    pb.set_defaults(func=_cmd_backtest)

    sub.add_parser("schedule", help="start the weekly scheduler (blocking)").set_defaults(func=_cmd_schedule)
    return p


def main(argv: list[str] | None = None) -> int:
    # Korean names break the default Windows cp1252 console; force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    configure_logging()
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
