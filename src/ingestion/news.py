"""News ingestion: Naver Finance per-ticker news + RSS, with dedup.

httpx / BeautifulSoup / feedparser imported lazily. Network failures degrade to
an empty list so the pipeline keeps running offline.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.logging_setup import get_logger

log = get_logger(__name__)

NAVER_NEWS_URL = "https://finance.naver.com/item/news_news.naver?code={code}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (KMA research bot; +https://example.invalid)"}


@dataclass
class NewsItem:
    ticker: str
    title: str
    url: str
    source: str | None = None
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    snippet: str | None = None

    @property
    def dedup_key(self) -> str:
        h = hashlib.sha1(f"{self.url}|{self.title}".encode()).hexdigest()
        return h


def _dedup(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    out: list[NewsItem] = []
    for it in items:
        if it.dedup_key in seen:
            continue
        seen.add(it.dedup_key)
        out.append(it)
    return out


def fetch_naver_news(ticker: str, *, limit: int = 20, timeout: float = 10.0) -> list[NewsItem]:
    """Scrape recent Naver Finance news headlines for a ticker. [] on any failure."""
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover
        log.warning("httpx/bs4 not installed; skipping Naver news for %s", ticker)
        return []

    url = NAVER_NEWS_URL.format(code=ticker)
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - network
        log.warning("Naver news fetch failed for %s: %s", ticker, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[NewsItem] = []
    for a in soup.select("a.tit, td.title a"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue
        if href.startswith("/"):
            href = "https://finance.naver.com" + href
        items.append(NewsItem(ticker=ticker, title=title, url=href, source="naver"))
        if len(items) >= limit:
            break
    return _dedup(items)


def fetch_rss(ticker: str, feed_url: str) -> list[NewsItem]:
    """Parse an RSS feed into NewsItems tagged with a ticker. [] on failure."""
    try:
        import feedparser
    except ImportError:  # pragma: no cover
        return []
    try:
        feed = feedparser.parse(feed_url)
    except Exception:  # pragma: no cover
        return []
    out: list[NewsItem] = []
    for entry in getattr(feed, "entries", []):
        out.append(NewsItem(
            ticker=ticker,
            title=getattr(entry, "title", ""),
            url=getattr(entry, "link", ""),
            source="rss",
            snippet=getattr(entry, "summary", None),
        ))
    return _dedup(out)
