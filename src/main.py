from __future__ import annotations

import asyncio
import argparse
import json
import logging
import sys
from datetime import date

from google import genai

from src.ai.curator import Curator
from src.ai.synthesizer import Synthesizer
from src.ai.token_budget import TokenBudget
from src.config import Settings, load_settings
from src.models.schemas import Article, DailyBriefing, TokenStats
from src.notion.client import NotionManager
from src.notion.publisher import Publisher
from src.sources.registry import get_all_sources

logger = logging.getLogger("inforoutine")


async def run_pipeline(settings: Settings, dry_run: bool = False) -> DailyBriefing:
    today = date.today().isoformat()
    logger.info("═══════════════════════════════════════════════════")
    logger.info("  infoRoutine — Daily Briefing Pipeline")
    logger.info("  Date: %s | Model: %s | Budget: %s tokens",
                today, settings.gemini_model, f"{settings.token_budget:,}")
    logger.info("  Dry run: %s", dry_run)
    logger.info("═══════════════════════════════════════════════════")

    budget = TokenBudget(settings.token_budget)
    gemini_client = genai.Client(api_key=settings.gemini_api_key)

    # ── Phase 1: Research (Hybrid Scraper, 0 API calls) ───────────────────────
    from src.scraper.hybrid import run_hybrid_scraper

    sources = get_all_sources()
    logger.info("📡 Phase 1: Scraping %d sources (0 API calls)...", len(sources))

    all_articles = await run_hybrid_scraper(sources)
    errors: list[str] = []
    sources_processed = len(sources)
    sources_skipped = 0

    logger.info("📊 Research complete: scraped %d articles across %d sources",
                len(all_articles), sources_processed)

    # ── Phase 1.5: Pre-Filter (rule-based, 0 API calls) ──────────────────────
    from src.scraper.prefilter import prefilter_articles

    logger.info("🧹 Phase 1.5: Pre-filtering articles (0 API calls)...")
    all_articles = prefilter_articles(all_articles)

    # ── Phase 2a: Curator (quality gate, 1 API call) ──────────────────────────
    logger.info("🔍 Phase 2a: Curating articles (1 API call)...")
    curator = Curator(gemini_client, settings.gemini_model, budget)
    all_articles = await curator.curate(all_articles)

    # ── Phase 2b: Synthesis (deep analysis, 1 API call) ───────────────────────
    logger.info("🧠 Phase 2b: Generating deep analysis + Executive Summary...")

    synthesizer = Synthesizer(gemini_client, settings.gemini_model, budget)
    all_articles, summary = await synthesizer.synthesize(all_articles)

    token_stats = TokenStats(
        total_budget=budget.total,
        tokens_used=budget.used,
        tokens_remaining=budget.remaining,
        sources_processed=sources_processed,
        sources_skipped=sources_skipped,
    )

    briefing = DailyBriefing(
        date=today,
        summary=summary,
        articles=all_articles,
        token_stats=token_stats,
        errors=errors,
    )

    # ── Phase 3: Publish ──────────────────────────────────────────────────
    if dry_run:
        logger.info("🏁 DRY RUN — printing briefing to stdout")
        print(briefing.model_dump_json(indent=2))
    else:
        logger.info("📤 Phase 3: Publishing to Notion...")
        notion = NotionManager(settings.notion_token, target_database_id=settings.notion_database_id)

        if not notion.is_configured:
            db_id = await notion.find_database()
            if not db_id:
                logger.error("❌ Could not find 'Newsletter diária' database in Notion.")
                logger.error("   Make sure the integration has access to the database.")
                return briefing

        publisher = Publisher(notion)
        await publisher.publish_briefing(summary, all_articles)

    # ── Summary ───────────────────────────────────────────────────────────
    logger.info("═══════════════════════════════════════════════════")
    logger.info("  ✅ Pipeline complete")
    logger.info("  Articles: %d | Tokens: %s / %s",
                len(all_articles),
                f"{budget.used:,}",
                f"{budget.total:,}")
    logger.info("  Errors: %d", len(errors))
    logger.info("═══════════════════════════════════════════════════")

    return briefing


def main() -> None:
    parser = argparse.ArgumentParser(description="infoRoutine — Daily Briefing Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Skip Notion push, print JSON")
    args = parser.parse_args()

    settings = load_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(run_pipeline(settings, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
