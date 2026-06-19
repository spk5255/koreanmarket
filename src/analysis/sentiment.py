"""News sentiment + event tagging.

Sends recent Korean headlines to Claude and expects structured JSON back:
{sentiment: -1..1, event_tags: [...], summary: str}. When no API key / SDK is
available it degrades to a deterministic lexicon fallback so the pipeline still
produces a (clearly-labelled) sentiment number offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from config.settings import settings
from src.ingestion.news import NewsItem
from src.logging_setup import get_logger

log = get_logger(__name__)

EVENT_TAGS = (
    "earnings_surprise", "contract", "m&a", "guidance", "litigation",
    "regulation", "product_launch", "management_change", "dividend",
)

# Tiny KR/EN lexicon for the offline fallback only.
_POS = ("최대", "사상", "수주", "흑자", "성장", "호조", "상향", "수출", "신고가", "surge", "beat", "record")
_NEG = ("적자", "하락", "감소", "소송", "리콜", "부진", "하향", "급락", "손실", "miss", "probe", "plunge")

_PROMPT = """You are a Korean equity news analyst. Given headlines for one stock,
return ONLY compact JSON: {{"sentiment": <float -1..1>, "event_tags": [...], "summary": "<=200 chars"}}.
event_tags must be a subset of: {tags}.
Headlines:
{headlines}"""


@dataclass
class SentimentResult:
    sentiment: float
    event_tags: list[str]
    summary: str
    source: str  # "claude" | "fallback"


def _fallback(items: list[NewsItem]) -> SentimentResult:
    if not items:
        return SentimentResult(0.0, [], "no news", "fallback")
    score = 0
    for it in items:
        text = (it.title or "") + " " + (it.snippet or "")
        score += sum(w in text for w in _POS)
        score -= sum(w in text for w in _NEG)
    norm = max(-1.0, min(1.0, score / (len(items) * 2)))
    return SentimentResult(round(norm, 3), [], f"{len(items)} headlines (lexicon)", "fallback")


def analyze_news(items: list[NewsItem], *, model: str | None = None) -> SentimentResult:
    """Analyze a batch of news items for one ticker."""
    if not items:
        return SentimentResult(0.0, [], "no news", "fallback")
    if settings.anthropic_api_key is None:
        return _fallback(items)
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return _fallback(items)

    headlines = "\n".join(f"- {it.title}" for it in items[:25])
    prompt = _PROMPT.format(tags=", ".join(EVENT_TAGS), headlines=headlines)
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
        resp = client.messages.create(
            model=model or settings.anthropic_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        tags = [t for t in data.get("event_tags", []) if t in EVENT_TAGS]
        return SentimentResult(
            sentiment=max(-1.0, min(1.0, float(data.get("sentiment", 0.0)))),
            event_tags=tags,
            summary=str(data.get("summary", ""))[:200],
            source="claude",
        )
    except Exception as exc:  # pragma: no cover - network/parse
        log.warning("Claude sentiment failed (%s); using fallback", exc)
        return _fallback(items)
