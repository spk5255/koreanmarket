"""One-shot DB bootstrap: create tables and seed the starter universe.

Usage (from project root):
    python scripts/bootstrap_db.py            # create + seed
    python scripts/bootstrap_db.py --drop     # recreate from scratch

Equivalent to ``kma init-db [--drop]`` followed by ``kma seed``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a plain script (python scripts/bootstrap_db.py) by putting
# the project root on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.universe import get_universe  # noqa: E402
from src.logging_setup import configure_logging, get_logger  # noqa: E402
from src.storage.db import init_db, session_scope  # noqa: E402
from src.storage.repository import list_companies, seed_companies  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the market database.")
    parser.add_argument("--drop", action="store_true", help="drop existing tables first")
    args = parser.parse_args()

    configure_logging()
    log = get_logger("bootstrap")

    init_db(drop=args.drop)
    with session_scope() as session:
        n = seed_companies(session, get_universe())
    with session_scope() as session:
        total = len(list_companies(session))

    log.info("Bootstrap complete: seeded %d companies, %d total rows.", n, total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
