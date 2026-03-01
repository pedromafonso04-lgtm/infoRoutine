from src.models.schemas import Category, Geography
from src.sources.registry import get_all_sources, get_sources_by_category


def test_sources_loaded_from_excel():
    sources = get_all_sources()
    assert len(sources) > 0, "No sources loaded from Excel"
    assert len(sources) <= 20, f"Expected ≤20 sources, got {len(sources)}"


def test_no_duplicate_names():
    sources = get_all_sources()
    names = [s.name for s in sources]
    assert len(names) == len(set(names)), "Duplicate source names found"


def test_all_categories_represented():
    for category in Category:
        sources = get_sources_by_category(category)
        assert len(sources) > 0, f"No sources for category {category.value}"


def test_all_sources_have_url():
    for source in get_all_sources():
        assert source.url, f"{source.name} has no URL"
        assert source.url.startswith("http"), f"{source.name} URL doesn't start with http"


def test_all_sources_have_research_hint():
    for source in get_all_sources():
        assert source.research_hint, f"{source.name} has no research_hint"


def test_portuguese_sources_have_portugal_geography():
    pt_sources = [s for s in get_all_sources() if s.language == "pt"]
    for s in pt_sources:
        assert s.geography == Geography.PORTUGAL, f"{s.name} should have geography PORTUGAL"


def test_portuguese_sources_have_pt_language():
    pt_sources = [s for s in get_all_sources() if s.geography == Geography.PORTUGAL]
    for s in pt_sources:
        assert s.language == "pt", f"{s.name} should have language 'pt'"
