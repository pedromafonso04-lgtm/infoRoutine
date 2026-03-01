# infoRoutine — Daily Strategic Intelligence Briefing

An AI-powered pipeline that scrapes 60+ global and Portuguese news sources, curates and analyzes them through Google Gemini, and publishes a structured daily briefing to a Notion database.

## 🏗️ Architecture

```
Scraper (0 API calls)  →  Pre-Filter (0 API calls)  →  Curator AI (1 API call)  →  Synthesizer AI (1 API call)  →  Notion Publisher
```

| Phase | Module | Description |
|-------|--------|-------------|
| **Phase 1** | `src/scraper/hybrid.py` | RSS + HTML scraping across 60+ sources (parallel, 0 API calls) |
| **Phase 1.5** | `src/scraper/prefilter.py` | Rule-based junk removal (stubs, nav elements, duplicates) |
| **Phase 2a** | `src/ai/curator.py` | AI quality gate — classifies articles as KEEP/DISCARD, cleans and translates titles to Portuguese |
| **Phase 2b** | `src/ai/synthesizer.py` | Deep strategic analysis (150-200 words per article) + interconnected Executive Summary |
| **Phase 3** | `src/notion/publisher.py` | Publishes briefing + article tiles to Notion Gallery database |

## 📰 Output

Each daily run produces:
- **Executive Summary** — interconnected analysis across 4 thematic scopes (Politics, Economics, Social Trends, Technology), with a Portugal focus
- **Article Tiles** — individual Notion Gallery cards with cover image, clean Portuguese title, strategic analysis, date, and source link

## 🚀 Setup

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/infoRoutine.git
cd infoRoutine
pip install -e .
```

### 2. Configure environment

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google AI Studio API key ([get one here](https://aistudio.google.com/apikey)) |
| `NOTION_TOKEN` | ✅ | Notion integration token ([create one here](https://www.notion.so/my-integrations)) |
| `NOTION_DATABASE_ID` | ❌ | Explicit database ID (auto-detected if omitted) |
| `GEMINI_MODEL` | ❌ | Model to use (default: `gemini-2.5-flash`) |
| `TOKEN_BUDGET` | ❌ | Max tokens per run (default: `1000000`) |

### 3. Notion setup

1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Create a database called **"Newsletter diária"** with these properties:
   - `Título` (Title)
   - `Âmbito` (Select: Política, Economia, Social Trends, Tecnologia, Resumo)
   - `Data` (Date)
   - `URL` (URL)
3. Share the database with your integration

### 4. Run

```bash
# Full run (scrape → curate → analyze → publish to Notion)
python -m src.main

# Dry run (print JSON to stdout, skip Notion)
python -m src.main --dry-run
```

## ⏰ Scheduled Execution

A GitHub Actions workflow runs the pipeline daily at **06:00 UTC**.

To enable it, add these secrets to your GitHub repository settings:

| Secret | Value |
|--------|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `NOTION_TOKEN` | Your Notion integration token |
| `NOTION_DATABASE_ID` | Your Notion database ID |

You can also trigger a manual run from the Actions tab → "Daily Briefing" → "Run workflow".

## 📁 Project Structure

```
src/
├── main.py                 # Pipeline orchestrator
├── config.py               # Settings (from .env)
├── models/schemas.py       # Pydantic data models
├── ai/
│   ├── curator.py          # AI quality gate (KEEP/DISCARD)
│   ├── synthesizer.py      # Deep analysis + Executive Summary
│   └── token_budget.py     # Token usage tracker
├── scraper/
│   ├── hybrid.py           # RSS + HTML scraper
│   └── prefilter.py        # Rule-based junk filter
├── notion/
│   ├── client.py           # Notion API client
│   └── publisher.py        # Briefing → Notion tiles
└── sources/
    └── registry.py         # Source list from Sources.xlsx
```

## 📊 Source Matrix

The pipeline scrapes from 60+ complementary and often contradictory sources across 4 thematic scopes, covering global trends with a Portugal focus. Sources include think tanks, economic institutions, government data portals, tech publications, and Portuguese media.

Full source list is maintained in `.docs/Sources.xlsx`.

## 🔧 Tech Stack

- **Python 3.12+**
- **Google Gemini API** (`gemini-2.5-flash`) — 2 API calls per run
- **Notion API** — database publishing
- **feedparser** + **BeautifulSoup4** — RSS/HTML scraping
- **httpx** — async HTTP client
- **Pydantic** — data validation

## 📄 License

Private project.
