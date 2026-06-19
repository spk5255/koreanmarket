# Korean Market Analyzer

A research / decision-support engine that ingests Korean market data (KOSPI, KOSDAQ),
company financials, investor supply/demand flows, and news, then produces a **ranked,
probabilistic weekly projection** per stock with confidence scores and supporting evidence.

> **Not investment advice.** Projections are uncertain. Every model is backtested before its
> output is trusted, and reports surface confidence and assumptions — never a guaranteed price.
> See `CLAUDE.md` for the full architecture and build plan.

---

## Status — Phase 0 (scaffold) ✅

What exists today:

- Project layout, packaging (`pyproject.toml`), tooling (ruff, mypy, pytest).
- Typed configuration via pydantic-settings (`config/settings.py`) with validated factor weights.
- Starter ticker universe (`config/universe.py`) incl. verification tickers Samsung `005930` + EcoProBM `247540`.
- SQLAlchemy ORM for the full starter schema (`src/storage/models.py`) and a DB bootstrap (`src/storage/db.py`).
- Logging setup, a `kma` CLI, a bootstrap script, and passing tests.
- Empty module stubs for every later phase (ingestion / analysis / scoring / backtest / reporting / scheduler).

Later phases (ingestion → analysis → scoring → backtest → reporting → scheduler) are scaffolded but not implemented — see the build order in `CLAUDE.md §7`.

---

## Setup

Requires Python 3.11+.

```bash
# from the project root: korean-market-analyzer/
python -m venv .venv
. .venv/Scripts/activate          # Windows (PowerShell: .venv\Scripts\Activate.ps1)
# source .venv/bin/activate       # macOS / Linux

pip install -e ".[dev]"           # install package + dev tools

cp .env.example .env              # then fill in DART_API_KEY / ANTHROPIC_API_KEY
```

`.env` keys:

| Key | Purpose |
|---|---|
| `DART_API_KEY` | DART OpenAPI (free: <https://opendart.fss.or.kr>) — financial filings |
| `ANTHROPIC_API_KEY` | News sentiment + weekly report narrative |
| `KMA_DB_URL` | Database URL (default `sqlite:///data/market.db`) |
| `KMA_ANTHROPIC_MODEL` | Model for sentiment/report (default `claude-opus-4-8`) |
| `KMA_LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `KMA_TIMEZONE` | Scheduler timezone (default `Asia/Seoul`) |

The pipeline runs without any keys for Phase 0 (DB + config only); keys are needed once ingestion lands.

---

## Usage (Phase 0)

```bash
kma info            # print resolved config (no secrets) + schema
kma init-db         # create all tables (add --drop to recreate)
kma seed            # upsert the starter universe into `companies`

# or, without installing the console script:
python scripts/bootstrap_db.py          # init-db + seed in one shot
python scripts/bootstrap_db.py --drop   # recreate from scratch
```

## Tests

```bash
pytest
```

---

## Layout

```
korean-market-analyzer/
├── config/        # settings (factor weights) + tracked universe
├── src/
│   ├── ingestion/ # market_data · financials · investor_flows · news   (Phase 1)
│   ├── storage/   # models · db · repository                            (Phase 0/2)
│   ├── analysis/  # fundamental · technical · supply_demand · sentiment (Phase 3)
│   ├── scoring/   # factors · composite · projection                    (Phase 4)
│   ├── backtest/  # engine · metrics                                    (Phase 5)
│   ├── reporting/ # weekly_report                                       (Phase 6)
│   ├── scheduler/ # weekly_job                                          (Phase 6)
│   ├── cli.py     # `kma` entry point
│   └── logging_setup.py
├── scripts/       # bootstrap_db.py
├── data/          # raw/ · processed/ (git-ignored)
├── reports/       # generated weekly reports (git-ignored)
└── tests/
```

See `CLAUDE.md` for the data model (§6), module specs (§5), and guardrails (§9).
