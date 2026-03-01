"""Local pre-filter for scraped articles.

Removes obvious junk before any AI call is made, saving tokens and
improving the signal-to-noise ratio for downstream agents.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from src.models.schemas import Article

logger = logging.getLogger(__name__)

# ── Compiled patterns ─────────────────────────────────────────────────────────

_NON_ARTICLE_URL_SEGMENTS = re.compile(
    r'/(?:login|signin|subscribe|signup|register|about|contact|privacy|terms|tag/|page/\d|author/|category/|#)',
    re.IGNORECASE,
)

_ALL_CAPS_PATTERN = re.compile(r'^[A-Z0-9\s\-:!?.,]{15,}$')

_WHITESPACE_RATIO_THRESHOLD = 0.05  # titles with <5% spaces are likely garbage


def _is_junk_title(title: str) -> str | None:
    """Return a discard reason if the title is obvious junk, else None."""
    stripped = title.strip()

    if len(stripped) < 15:
        return "too_short"

    if len(stripped) > 200:
        return "too_long"

    if _ALL_CAPS_PATTERN.match(stripped) and len(stripped) > 40:
        return "all_caps_garbage"

    # Titles with no spaces are nav elements or concatenated slugs
    space_count = stripped.count(' ')
    if space_count == 0 and len(stripped) > 20:
        return "no_spaces"

    return None


def _is_junk_url(url: str) -> str | None:
    """Return a discard reason if the URL pattern is non-article, else None."""
    if _NON_ARTICLE_URL_SEGMENTS.search(url):
        return "non_article_url"
    return None


def _deduplicate_by_title(articles: list[Article], threshold: float = 0.85) -> list[Article]:
    """Remove near-duplicate titles using fuzzy matching."""
    kept: list[Article] = []
    seen_titles: list[str] = []

    for article in articles:
        normalised = article.title.lower().strip()
        is_dup = False
        for seen in seen_titles:
            if SequenceMatcher(None, normalised, seen).ratio() >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(article)
            seen_titles.append(normalised)

    return kept


def prefilter_articles(articles: list[Article]) -> list[Article]:
    """Apply rule-based filtering to remove obvious junk articles.

    Returns the filtered list and logs removal statistics.
    """
    original_count = len(articles)
    reasons: dict[str, int] = {}

    filtered: list[Article] = []
    for article in articles:
        # Check title quality
        reason = _is_junk_title(article.title)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue

        # Check URL pattern
        reason = _is_junk_url(article.url)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue

        # Only discard true stubs: no abstract AND a very short title
        if not article.abstract and len(article.title.strip()) < 25:
            reasons["stub_no_content"] = reasons.get("stub_no_content", 0) + 1
            continue

        filtered.append(article)

    # Deduplicate by similar titles
    before_dedup = len(filtered)
    filtered = _deduplicate_by_title(filtered)
    dup_count = before_dedup - len(filtered)
    if dup_count:
        reasons["near_duplicate"] = dup_count

    removed = original_count - len(filtered)
    logger.info(
        "🧹 Pre-filter: %d → %d articles (removed %d)", original_count, len(filtered), removed
    )
    if reasons:
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            logger.info("   ├─ %s: %d", reason, count)

    return filtered
