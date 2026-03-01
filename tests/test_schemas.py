from src.models.schemas import (
    Article,
    BriefingSection,
    Category,
    DailyBriefing,
    ExecutiveSummary,
    Source,
    SourceResearchResult,
    TokenStats,
)


def test_source_creation():
    source = Source(
        name="Test Source",
        url="https://example.com",
        category=Category.POLITICS,
        research_hint="Focus on policy",
    )
    assert source.name == "Test Source"
    assert source.category == Category.POLITICS
    assert source.language == "en"


def test_article_defaults():
    article = Article(
        title="Test Article",
        url="https://example.com/article",
        source_name="Test Source",
        category=Category.TECH,
    )
    assert article.elevator_pitch == ""
    assert article.image_url == ""
    assert article.abstract == ""


def test_article_full():
    article = Article(
        title="Breakthrough in Materials Science",
        url="https://nature.com/article/123",
        source_name="Nature Materials",
        category=Category.TECH,
        abstract="A new polymer was discovered.",
        elevator_pitch="Game-changing polymer discovery.",
        image_url="https://nature.com/img.jpg",
        published_date="2026-02-27",
    )
    assert article.source_name == "Nature Materials"
    data = article.model_dump()
    assert "title" in data
    assert "url" in data


def test_source_research_result_success():
    result = SourceResearchResult(
        source_name="Brookings",
        articles=[
            Article(
                title="Policy Update",
                url="https://brookings.edu/1",
                source_name="Brookings",
                category=Category.POLITICS,
            )
        ],
        tokens_used=1500,
    )
    assert len(result.articles) == 1
    assert result.error is None


def test_source_research_result_error():
    result = SourceResearchResult(
        source_name="Failed Source",
        error="Connection timeout",
    )
    assert len(result.articles) == 0
    assert result.error == "Connection timeout"


def test_executive_summary():
    summary = ExecutiveSummary(
        date="2026-02-27",
        sections=[
            BriefingSection(
                category=Category.POLITICS,
                bullets=["EU tariff impact on supply chains.", "Portugal coalition shifts."],
            ),
        ],
        meta_narrative="Global trade tensions dominate the day.",
    )
    assert len(summary.sections) == 1
    assert len(summary.sections[0].bullets) == 2


def test_daily_briefing_serialization():
    briefing = DailyBriefing(
        date="2026-02-27",
        summary=ExecutiveSummary(date="2026-02-27", meta_narrative="Test"),
        articles=[
            Article(
                title="Test",
                url="https://test.com",
                source_name="Source",
                category=Category.ECONOMICS,
            )
        ],
        token_stats=TokenStats(
            total_budget=1000000,
            tokens_used=50000,
            tokens_remaining=950000,
            sources_processed=48,
            sources_skipped=2,
        ),
    )
    json_str = briefing.model_dump_json()
    assert "Test" in json_str
    assert "950000" in json_str


def test_category_values():
    assert Category.POLITICS.value == "Política"
    assert Category.ECONOMICS.value == "Economia"
    assert Category.SOCIAL.value == "Social Trends"
    assert Category.TECH.value == "Tecnologia"
