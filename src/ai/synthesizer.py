from __future__ import annotations

import json
import logging
from datetime import date

from google import genai
from google.genai import types

from src.ai.token_budget import TokenBudget
from src.models.schemas import Article, BriefingSection, Category, ExecutiveSummary

logger = logging.getLogger(__name__)

COMBINED_PROMPT_TEMPLATE = """És um Editor-Chefe a produzir um briefing diário de inteligência estratégica para {today}.

**O teu público:** Um gestor estratégico que exige alto sinal e zero ruído. O briefing completo (sumário executivo + todos os artigos) deve ser legível em ~10 minutos.

**A tua tarefa tem DUAS partes. Usa APENAS os artigos fornecidos abaixo. NÃO faças referência a informação externa.**

**NOTA:** Os títulos dos artigos já foram curados e traduzidos para Português. Usa-os TAL COMO ESTÃO no campo "translated_title" — não modifiques os títulos.

---

**PARTE 1 — Análise de Artigos:**
Para CADA artigo na lista:

1. Copia o título curado para o campo "translated_title" (sem alterar).
2. Escreve uma **análise estratégica aprofundada** (campo "elevator_pitch"):
   - 4 a 6 frases, entre 150 e 200 palavras.
   - Estrutura: O que aconteceu → Contexto e antecedentes → Porque importa → Impacto potencial para Portugal ou para o setor.
   - Sê analítico, factual e preciso. Nunca sensacionalista.
   - Adiciona perspetiva: não repitas o título, explica o "e então?" com profundidade.
   - ESCREVE em Português de Portugal.

**PARTE 2 — Sumário Executivo Interligado:**
Para cada um dos 4 âmbitos temáticos, escreve 3-5 pontos que:
- Liguem os pontos entre histórias (ex: como uma tarifa política na UE afeta uma cadeia de produção de deep tech ou a confiança do consumidor em Portugal)
- Destaquem impactos especificamente relevantes para **Portugal** sempre que possível
- Cada ponto deve ter 2-3 frases completas (não meros fragmentos)
- Sejam analíticos e estritamente factuais
- Nunca usem linguagem moralizadora ou adjetivos sensacionalistas

Escreve também uma "meta_narrative" (3-4 frases) que capture o tema transversal mais importante do dia.

**Os 4 âmbitos (usa estes nomes EXATOS como "category"):**
1. Política
2. Economia
3. Social Trends
4. Tecnologia

---

**Artigos curados para análise:**
{articles_json}

**ESCREVE TUDO EM PORTUGUÊS DE PORTUGAL.**

Retorna um objeto JSON com:
- "articles_processed": array de objetos com "original_title" (o título original exato da entrada), "translated_title" (copia o título curado — NÃO modifiques), e "elevator_pitch" (a tua análise aprofundada de 4-6 frases).
- "sections": array de 4 objetos, cada um com "category" (nome exato do âmbito) e "bullets" (array de strings com 2-3 frases cada)
- "meta_narrative": string (3-4 frases)
"""

COMBINED_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "articles_processed": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "original_title": types.Schema(type=types.Type.STRING),
                    "translated_title": types.Schema(type=types.Type.STRING),
                    "elevator_pitch": types.Schema(type=types.Type.STRING),
                },
                required=["original_title", "translated_title", "elevator_pitch"],
            ),
        ),
        "sections": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "category": types.Schema(type=types.Type.STRING),
                    "bullets": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                    ),
                },
                required=["category", "bullets"],
            ),
        ),
        "meta_narrative": types.Schema(type=types.Type.STRING),
    },
    required=["articles_processed", "sections", "meta_narrative"],
)

CATEGORY_NAME_MAP = {
    "Política": Category.POLITICS,
    "Economia": Category.ECONOMICS,
    "Social Trends": Category.SOCIAL,
    "Tecnologia": Category.TECH,
}


class Synthesizer:
    def __init__(self, client: genai.Client, model: str, budget: TokenBudget) -> None:
        self._client = client
        self._model = model
        self._budget = budget

    async def synthesize(self, articles: list[Article]) -> tuple[list[Article], ExecutiveSummary]:
        """Generate pitches AND executive summary in a single API call."""
        today = date.today().isoformat()

        if not articles:
            logger.warning("⚠️ No articles to synthesize")
            return articles, ExecutiveSummary(
                date=today,
                meta_narrative="Nenhum artigo foi recolhido hoje.",
            )

        if self._budget.is_exhausted:
            logger.warning("⚠️ Budget exhausted — generating minimal summary")
            return articles, ExecutiveSummary(
                date=today,
                meta_narrative="Orçamento de tokens esgotado antes da síntese. Reveja os artigos individuais.",
            )

        articles_data = [
            {
                "index": i,
                "title": a.title,
                "source": a.source_name,
                "category": a.category.value,
                "abstract": a.abstract,
            }
            for i, a in enumerate(articles)
        ]

        prompt = COMBINED_PROMPT_TEMPLATE.format(
            today=today,
            articles_json=json.dumps(articles_data, indent=2, ensure_ascii=False),
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=COMBINED_RESPONSE_SCHEMA,
                    temperature=0.3,
                ),
            )

            if response.usage_metadata:
                self._budget.record_usage(response.usage_metadata.total_token_count or 0)

            if not response.text:
                return articles, ExecutiveSummary(
                    date=today, meta_narrative="A síntese não produziu resultados."
                )

            raw = json.loads(response.text)

            # Apply pitches using index-based matching (robust against title changes)
            processed_map: dict[str, dict] = {}
            for p in raw.get("articles_processed", []):
                if isinstance(p, dict) and p.get("original_title"):
                    processed_map[p["original_title"]] = p

            updated_articles = []
            matched = 0
            for article in articles:
                p = processed_map.get(article.title)
                if p:
                    article.elevator_pitch = p.get("elevator_pitch", "")
                    # Only override title if synthesizer returned a different one
                    translated = p.get("translated_title", "")
                    if translated:
                        article.title = translated
                    matched += 1
                updated_articles.append(article)

            logger.info("✅ Generated pitches for %d / %d articles", matched, len(articles))

            # Build executive summary
            sections = []
            for s in raw.get("sections", []):
                category = CATEGORY_NAME_MAP.get(s.get("category", ""))
                if category:
                    sections.append(
                        BriefingSection(category=category, bullets=s.get("bullets", []))
                    )

            summary = ExecutiveSummary(
                date=today,
                sections=sections,
                meta_narrative=raw.get("meta_narrative", ""),
            )

            logger.info("✅ Executive summary generated with %d sections", len(sections))
            return updated_articles, summary

        except Exception as e:
            logger.error("❌ Synthesis failed: %s", e)
            return articles, ExecutiveSummary(
                date=today,
                meta_narrative=f"A síntese falhou: {e}",
            )
