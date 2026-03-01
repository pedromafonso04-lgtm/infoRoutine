from __future__ import annotations

import logging
from datetime import date

from src.models.schemas import Article, Category, ExecutiveSummary
from src.notion.client import NotionManager

logger = logging.getLogger(__name__)

CATEGORY_PLACEHOLDERS = {
    Category.POLITICS: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=600",
    Category.ECONOMICS: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600",
    Category.SOCIAL: "https://images.unsplash.com/photo-1517048676732-d65bc937f952?w=600",
    Category.TECH: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600",
}


class Publisher:
    """Publishes to the existing 'Newsletter diária' database.

    Database columns (matching user's Notion workspace):
    - Título (title) — article title
    - Data (date) — publication date
    - Âmbito (select) — Política / Economia / Social Trends / Tecnologia
    - URL (url) — source link
    """

    def __init__(self, notion: NotionManager) -> None:
        self._notion = notion

    async def publish_briefing(
        self,
        summary: ExecutiveSummary,
        articles: list[Article],
    ) -> None:
        if not self._notion.database_id:
            logger.error("❌ Base de dados Notion não configurada — impossível publicar")
            return

        # Publish Executive Summary as the first tile
        await self._create_summary_tile(summary)

        # Publish each article as a tile
        published = 0
        for article in articles:
            success = await self._create_article_tile(article)
            if success:
                published += 1

        logger.info("✅ Publicados: sumário executivo + %d / %d artigos", published, len(articles))

    async def _create_summary_tile(self, summary: ExecutiveSummary) -> bool:
        try:
            body_blocks = self._build_summary_blocks(summary)

            await self._notion.client.pages.create(
                parent={"database_id": self._notion.database_id},
                cover={"type": "external", "external": {"url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600"}},
                icon={"type": "emoji", "emoji": "📊"},
                properties={
                    "Título": {
                        "title": [
                            {
                                "type": "text",
                                "text": {"content": f"Briefing Diário — {summary.date}"},
                            }
                        ]
                    },
                    "Data": {"date": {"start": summary.date}},
                    "Âmbito": {"select": {"name": "Resumo"}},
                },
                children=body_blocks,
            )
            logger.info("✅ Sumário executivo publicado para %s", summary.date)
            return True

        except Exception as e:
            logger.error("❌ Falha ao criar página do sumário: %s", e)
            return False

    def _build_summary_blocks(self, summary: ExecutiveSummary) -> list[dict]:
        blocks: list[dict] = []

        # Add a placeholder cover image to the summary body so it shows up in Gallery view
        blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600"}
            }
        })

        if summary.meta_narrative:
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🎯"},
                    "rich_text": [{"type": "text", "text": {"content": summary.meta_narrative}}],
                },
            })
            blocks.append({"object": "block", "type": "divider", "divider": {}})

        scope_emojis = {
            Category.POLITICS: "🏛️",
            Category.ECONOMICS: "📈",
            Category.SOCIAL: "👥",
            Category.TECH: "🔬",
        }

        for section in summary.sections:
            emoji = scope_emojis.get(section.category, "📌")
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"{emoji} {section.category.value}"}}
                    ]
                },
            })

            for bullet in section.bullets:
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": bullet}}]
                    },
                })

        return blocks

    async def _create_article_tile(self, article: Article) -> bool:
        """Create an article tile matching the user's DB schema: Título, Data, Âmbito, URL."""
        try:
            cover = None
            image_url = article.image_url or CATEGORY_PLACEHOLDERS.get(article.category, "")
            if image_url:
                cover = {"type": "external", "external": {"url": image_url}}

            properties: dict = {
                "Título": {
                    "title": [
                        {"type": "text", "text": {"content": article.title[:2000]}}
                    ]
                },
                "Âmbito": {"select": {"name": article.category.value}},
                "URL": {"url": article.url},
            }

            # Always set date — fallback to today since we only scrape 24h articles
            article_date = article.published_date or date.today().isoformat()
            properties["Data"] = {"date": {"start": article_date}}

            # Build page content with elevator pitch and abstract
            children = []
            
            if image_url:
                children.append({
                    "object": "block",
                    "type": "image",
                    "image": {
                        "type": "external",
                        "external": {"url": image_url}
                    }
                })

            if article.elevator_pitch:
                children.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "icon": {"type": "emoji", "emoji": "💡"},
                        "rich_text": [
                            {"type": "text", "text": {"content": article.elevator_pitch}}
                        ],
                    },
                })
            # NOTE: abstract removed to avoid text duplication.
            # The elevator_pitch already provides a richer contextual analysis.
            if article.source_name:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": f"Fonte: {article.source_name}"},
                                "annotations": {"italic": True, "color": "gray"},
                            }
                        ]
                    },
                })

            await self._notion.client.pages.create(
                parent={"database_id": self._notion.database_id},
                cover=cover,
                properties=properties,
                children=children if children else None,
            )
            return True

        except Exception as e:
            logger.error("❌ Falha ao criar tile para '%s': %s", article.title[:50], e)
            return False
