"""The tracked universe of tickers.

Start small (CLAUDE.md guidance) to get the full pipeline working end-to-end
before scaling to the ~2,000+ KOSPI+KOSDAQ listings. The starter set below is
hand-picked liquid names plus the verification tickers from the build plan
(Samsung Electronics 005930, a KOSDAQ name).

In Phase 1 ``get_universe`` will optionally pull the live constituent list from
pykrx; until then it returns this static starter set so downstream code has a
stable target.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseMember:
    ticker: str       # 6-digit KRX code
    name: str
    market: str       # "KOSPI" | "KOSDAQ"


# Hand-picked liquid starter set. Keep names ASCII-safe in comments; the `name`
# field holds the official short name (Korean kept where useful for reports).
STARTER_UNIVERSE: tuple[UniverseMember, ...] = (
    # --- KOSPI large caps ---
    UniverseMember("005930", "삼성전자", "KOSPI"),        # Samsung Electronics (verification ticker)
    UniverseMember("000660", "SK하이닉스", "KOSPI"),       # SK hynix
    UniverseMember("373220", "LG에너지솔루션", "KOSPI"),    # LG Energy Solution
    UniverseMember("207940", "삼성바이오로직스", "KOSPI"),  # Samsung Biologics
    UniverseMember("005380", "현대차", "KOSPI"),          # Hyundai Motor
    UniverseMember("000270", "기아", "KOSPI"),            # Kia
    UniverseMember("068270", "셀트리온", "KOSPI"),         # Celltrion
    UniverseMember("035420", "NAVER", "KOSPI"),           # NAVER
    UniverseMember("105560", "KB금융", "KOSPI"),          # KB Financial
    UniverseMember("005490", "POSCO홀딩스", "KOSPI"),      # POSCO Holdings
    # --- KOSDAQ names (incl. a verification ticker) ---
    UniverseMember("247540", "에코프로비엠", "KOSDAQ"),     # EcoProBM (KOSDAQ verification ticker)
    UniverseMember("086520", "에코프로", "KOSDAQ"),        # EcoPro
    UniverseMember("196170", "알테오젠", "KOSDAQ"),        # Alteogen
    UniverseMember("091990", "셀트리온헬스케어", "KOSDAQ"),  # Celltrion Healthcare
    UniverseMember("066970", "엘앤에프", "KOSDAQ"),        # L&F
)

# Tickers used to verify ingestion end-to-end in Phase 1.
VERIFICATION_TICKERS: tuple[str, ...] = ("005930", "247540")


def get_universe(market: str | None = None) -> list[UniverseMember]:
    """Return the tracked universe, optionally filtered by market.

    Args:
        market: ``"KOSPI"``, ``"KOSDAQ"``, or ``None`` for all.

    Phase 1 will extend this to optionally fetch live constituents (e.g.
    KOSPI200) from pykrx for a given date; the signature stays compatible.
    """
    members = list(STARTER_UNIVERSE)
    if market is not None:
        market = market.upper()
        members = [m for m in members if m.market == market]
    return members


def get_tickers(market: str | None = None) -> list[str]:
    """Convenience: just the 6-digit codes."""
    return [m.ticker for m in get_universe(market)]
