"""Refresh the DB with REAL market data. Usage: python scripts/ingest_real.py [--years 1]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.backfill import backfill_universe  # noqa: E402
from src.logging_setup import configure_logging, get_logger  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=1.0)
    ap.add_argument("--no-financials", action="store_true")
    args = ap.parse_args()
    configure_logging()
    n = backfill_universe(years=args.years, with_financials=not args.no_financials)
    get_logger("ingest").info("Wrote %d real price rows.", n)
    return 0 if n > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
