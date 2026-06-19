"""DART (OpenDartReader) ingestion + account-name normalization.

OpenDartReader is imported lazily and uses settings.dart_api_key. DART returns
financial statements with messy Korean account names; ACCOUNT_MAP normalizes the
common ones into our stable internal schema (see src/storage/models.Fundamental).

NOTE: live calls require a DART API key and network; not exercised offline.
"""

from __future__ import annotations

import pandas as pd

from config.settings import settings
from src.logging_setup import get_logger
from src.utils import read_cache, retry, write_cache

log = get_logger(__name__)

# DART report codes
REPRT_ANNUAL = "11011"
REPRT_Q1 = "11013"
REPRT_HALF = "11012"
REPRT_Q3 = "11014"

# Korean account name -> internal field. Multiple aliases map to one field.
ACCOUNT_MAP: dict[str, str] = {
    "매출액": "revenue",
    "수익(매출액)": "revenue",
    "영업수익": "revenue",
    "영업이익": "op_profit",
    "영업이익(손실)": "op_profit",
    "당기순이익": "net_income",
    "당기순이익(손실)": "net_income",
    "자산총계": "total_assets",
    "부채총계": "total_liab",
    "자본총계": "equity",
    "영업활동현금흐름": "ocf",
    "영업활동으로인한현금흐름": "ocf",
}
# Capex is usually derived from the cash-flow statement line for PP&E purchases.
CAPEX_ALIASES = ("유형자산의취득", "유형자산의 취득")


def _reader():  # lazy import
    try:
        import OpenDartReader
    except ImportError as exc:  # pragma: no cover
        raise ImportError("OpenDartReader is required for DART (pip install OpenDartReader)") from exc
    key = settings.dart_api_key.get_secret_value() if settings.dart_api_key else None
    if not key:
        raise RuntimeError("DART_API_KEY is not set; cannot query DART.")
    return OpenDartReader(key)  # package imports as the class itself


@retry(times=3)
def get_corp_code(ticker: str) -> str | None:
    """Map a 6-digit ticker to its DART corp_code (cached)."""
    cache = read_cache("dart_corp_codes.csv")
    if cache is not None and "ticker" in cache.columns:
        hit = cache.loc[cache["ticker"] == ticker, "corp_code"]
        if len(hit):
            return str(hit.iloc[0]).zfill(8)
    code = _reader().find_corp_code(ticker)
    return str(code).zfill(8) if code else None


@retry(times=3)
def fetch_financial_statements(corp: str, year: int, reprt_code: str = REPRT_ANNUAL) -> pd.DataFrame:
    """Raw consolidated financial statements for a corp/year/report (DART finstate_all)."""
    name = f"dart_{corp}_{year}_{reprt_code}.csv"
    if (cached := read_cache(name)) is not None:
        return cached
    df = _reader().finstate_all(corp, year, reprt_code=reprt_code)
    write_cache(df, name)
    return df


def normalize_statements(df: pd.DataFrame) -> dict[str, float]:
    """Collapse a raw DART statement frame into our internal fundamental fields.

    Looks for ``account_nm`` + ``thstrm_amount`` columns (DART's standard names),
    maps Korean account names via ACCOUNT_MAP, and returns a flat dict. Missing
    fields are simply absent.
    """
    out: dict[str, float] = {}
    if df is None or df.empty:
        return out
    name_col = "account_nm" if "account_nm" in df.columns else df.columns[0]
    amt_col = "thstrm_amount" if "thstrm_amount" in df.columns else None
    if amt_col is None:
        return out

    def _to_num(x: object) -> float | None:
        try:
            return float(str(x).replace(",", "").strip())
        except (ValueError, AttributeError):
            return None

    for _, row in df.iterrows():
        acct = str(row[name_col]).strip()
        val = _to_num(row[amt_col])
        if val is None:
            continue
        if acct in ACCOUNT_MAP:
            out.setdefault(ACCOUNT_MAP[acct], val)
        elif acct in CAPEX_ALIASES:
            out.setdefault("capex", abs(val))
    return out

