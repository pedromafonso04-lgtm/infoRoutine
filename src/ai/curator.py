"""AI Curator Agent — quality gate for scraped articles.

Uses a lightweight Gemini call to classify articles as KEEP or DISCARD,
clean titles, and translate them to Portuguese. Runs before the Synthesizer
so that only high-quality articles receive deep analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from google import genai
from google.genai import types

from src.ai.token_budget import TokenBudget
from src.models.schemas import Article

logger = logging.getLogger(__name__)

CURATOR_PROMPT = """És um curador de notícias. O teu trabalho é filtrar artigos claramente inválidos antes que cheguem ao analista.

**Data:** {today}

**Para CADA artigo na lista abaixo, decide:**

1. **KEEP** — se tem algum valor informativo ou noticioso. EM CASO DE DÚVIDA, KEEP.
2. **DISCARD** — APENAS se é claramente lixo. Indica o motivo:
   - `no_content`: título completamente sem significado ou ilegível
   - `event_listing`: é APENAS um evento/meetup SEM análise ou notícia associada
   - `marketing`: é publicidade pura ou press release sem valor noticioso
   - `not_news`: é uma página de navegação, lista de tags, ou conteúdo claramente não-noticioso

**Para artigos KEEP:**
- Traduz e limpa o título para Português de Portugal.
- Remove metadados do título: datas, horas, locais, códigos, número de participantes.
- O título limpo deve ser uma frase curta e informativa.

**REGRAS FUNDAMENTAIS:**
- Sê CONSERVADOR. É melhor manter um artigo medíocre do que perder uma notícia importante.
- Se o título parece ser uma notícia real mas o abstract está vazio, KEEP — o analista desenvolverá o conteúdo.
- Garante diversidade temática: mantém artigos de TODAS as categorias (Política, Economia, Social Trends, Tecnologia).
- Duplicados: se dois artigos cobrem a mesma história, KEEP o com melhor título e DISCARD o outro.

**Artigos para triagem:**
{articles_json}

Retorna um JSON com:
- "curated": array de objetos, cada um com:
  - "original_title" (string): o título original EXATO da entrada
  - "decision" (string): "KEEP" ou "DISCARD"
  - "clean_title_pt" (string): título limpo em PT (vazio se DISCARD)
  - "reason" (string): motivo do descarte (vazio se KEEP)
"""

CURATOR_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "curated": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "original_title": types.Schema(type=types.Type.STRING),
                    "decision": types.Schema(type=types.Type.STRING, enum=["KEEP", "DISCARD"]),
                    "clean_title_pt": types.Schema(type=types.Type.STRING),
                    "reason": types.Schema(type=types.Type.STRING),
                },
                required=["original_title", "decision"],
            ),
        ),
    },
    required=["curated"],
)


class Curator:
    def __init__(self, client: genai.Client, model: str, budget: TokenBudget) -> None:
        self.client = client
        self.model = model
        self.budget = budget

    async def curate(self, articles: list[Article]) -> list[Article]:
        """Filter articles through the AI curator. Returns only KEEP articles with cleaned titles."""
        if not articles:
            return articles

        # Build a lightweight JSON payload (title + abstract snippet + source)
        articles_payload = []
        for a in articles:
            articles_payload.append({
                "title": a.title,
                "abstract": (a.abstract or "")[:200],
                "source": a.source_name,
                "category": a.category.value,
            })

        prompt = CURATOR_PROMPT.format(
            today=date.today().isoformat(),
            articles_json=json.dumps(articles_payload, ensure_ascii=False, indent=1),
        )

        logger.info("🔍 Curator: evaluating %d articles...", len(articles))

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CURATOR_RESPONSE_SCHEMA,
                temperature=0.1,
            ),
        )

        # Track token usage
        if response.usage_metadata:
            used = (response.usage_metadata.prompt_token_count or 0) + (
                response.usage_metadata.candidates_token_count or 0
            )
            self.budget.record_usage(used)
            logger.info("🔍 Curator tokens: %s", f"{used:,}")

        # Parse response
        try:
            data = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Curator JSON parse error: %s", exc)
            return articles  # fallback: keep all

        curated_map: dict[str, dict] = {}
        for item in data.get("curated", []):
            curated_map[item["original_title"]] = item

        # Apply decisions
        kept: list[Article] = []
        discard_reasons: dict[str, int] = {}

        for article in articles:
            decision_data = curated_map.get(article.title)
            if not decision_data:
                # AI didn't return a decision for this article, keep it by default
                kept.append(article)
                continue

            if decision_data["decision"] == "KEEP":
                # Apply cleaned title if available
                clean_title = decision_data.get("clean_title_pt", "").strip()
                if clean_title:
                    article.title = clean_title
                kept.append(article)
            else:
                reason = decision_data.get("reason", "unknown")
                discard_reasons[reason] = discard_reasons.get(reason, 0) + 1

        logger.info(
            "🔍 Curator: %d → %d articles (discarded %d)",
            len(articles), len(kept), len(articles) - len(kept),
        )
        if discard_reasons:
            for reason, count in sorted(discard_reasons.items(), key=lambda x: -x[1]):
                logger.info("   ├─ %s: %d", reason, count)

        return kept
