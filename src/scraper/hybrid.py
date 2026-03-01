import asyncio
import logging
import re
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from src.models.schemas import Article, Source

logger = logging.getLogger(__name__)

# Headers to act more like a normal browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Known RSS feed paths to check alongside the main URL
COMMON_RSS_PATHS = [
    "/feed",
    "/rss",
    "/feed.xml",
    "/rss.xml",
    "/index.xml",
]

class HybridScraper:
    # Regex patterns to strip event metadata from titles
    _META_PATTERNS = [
        r'\d{1,2}\s+de\s+\w+\.?\s+de\s+\d{4}',   # "28 de jan. de 2026"
        r'\d{1,2}/\d{1,2}/\d{2,4}',                 # "28/01/2026"
        r'\d{2}:\d{2}(?:WEST|WET|UTC|GMT|CET)?',     # "18:00WEST"
        r'\b\d+\s*participantes\b',                  # "12 participantes"
        r',\s*PT\d*\s*participantes',                 # ", PT12 participantes"
        r'\bPT\d+\b',                                # "PT12"
        r',\s*[A-Z]{2}\d+\s',                        # ", PT33 "
    ]

    @staticmethod
    def _clean_title(raw_title: str) -> str:
        """Strip event metadata, dates, addresses, and participant counts."""
        title = raw_title
        for pattern in HybridScraper._META_PATTERNS:
            title = re.sub(pattern, ' ', title, flags=re.IGNORECASE)
        # Collapse whitespace and trim
        title = re.sub(r'\s{2,}', ' ', title).strip()
        # Remove trailing/leading commas or dashes
        title = title.strip(' ,-–—')
        # Cap at 200 chars
        return title[:200] if title else raw_title[:200]

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True)

    async def close(self):
        await self.client.aclose()

    async def _fetch_html(self, url: str) -> str | None:
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.debug("Failed to fetch HTML for %s: %s", url, e)
            return None

    def _parse_rss_entries(self, feed_url: str, content: str, source: Source) -> list[Article]:
        articles = []
        try:
            feed = feedparser.parse(content)
            for entry in feed.entries:
                if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                    continue
                
                # Enforce 24-hour time limit
                published_date = ""
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    import time
                    from calendar import timegm
                    
                    # Convert parsed time struct to timestamp
                    entry_ts = timegm(entry.published_parsed)
                    now_ts = time.time()
                    
                    # Skip if older than 24 hours (86400 seconds)
                    if (now_ts - entry_ts) > 86400:
                        continue
                        
                    published_date = f"{entry.published_parsed.tm_year}-{entry.published_parsed.tm_mon:02d}-{entry.published_parsed.tm_mday:02d}"
                
                abstract = ""
                if hasattr(entry, 'summary'):
                    abstract = BeautifulSoup(entry.summary, "html.parser").get_text(separator=" ", strip=True)[:300]

                image_url = ""
                # Try to find common media tags in RSS
                if hasattr(entry, 'media_content') and entry.media_content:
                    image_url = entry.media_content[0].get('url', '')
                elif hasattr(entry, 'links'):
                    for link in entry.links:
                        if link.get('type', '').startswith('image/'):
                            image_url = link.get('href', '')
                            break

                articles.append(
                    Article(
                        title=self._clean_title(entry.title),
                        url=entry.link,
                        source_name=source.name,
                        category=source.category,
                        abstract=abstract,
                        published_date=published_date,
                        image_url=image_url,
                    )
                )
        except Exception as e:
            logger.debug("Error parsing RSS for %s (%s): %s", source.name, feed_url, e)
        return articles

    # Patterns that indicate non-news event/address content in titles
    _JUNK_TITLE_PATTERNS = re.compile(
        r'(?:'
        r'R\.\s+de\s+\w+'           # "R. de Aníbal Cunha 218"
        r'|\d{4}-\d{3}\s'           # "4050-047 " (postal code)
        r'|participantes'
        r'|Register\s+Today'
        r'|Join\s+Our\s+Community'
        r'|Subscribe\s+Now'
        r'|Sign\s+Up'
        r'|celebration\s+of'        # event preamble
        r')',
        re.IGNORECASE
    )

    async def _scrape_html(self, url: str, content: str, source: Source) -> list[Article]:
        articles = []
        try:
            soup = BeautifulSoup(content, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']

                # Filter out obvious non-article links
                lower_href = href.lower()
                if any(skip in lower_href for skip in ("login", "subscribe", "about", "contact", "privacy", "terms")):
                    continue

                # Prefer text from a parent heading, otherwise use the link text
                parent_h = a.find_parent(['h1', 'h2', 'h3', 'h4'])
                if parent_h:
                    title = parent_h.get_text(separator=' ', strip=True)
                else:
                    # Only take direct text, not deeply nested content
                    title = a.get_text(separator=' ', strip=True)

                # Skip too short or too long (concatenated garbage)
                if len(title) < 20 or len(title) > 200:
                    continue

                # Skip titles that contain address/event junk patterns
                if self._JUNK_TITLE_PATTERNS.search(title):
                    continue

                full_url = urljoin(url, href)

                # Try to find a nearby image
                image_url = ""
                img = a.find('img')
                if img and img.get('src'):
                    image_url = urljoin(url, img['src'])
                else:
                    parent = a.find_parent(['div', 'article', 'section', 'li'])
                    if parent:
                        img = parent.find('img')
                        if img and img.get('src'):
                            image_url = urljoin(url, img['src'])

                # Fallback to page og:image
                if not image_url:
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        image_url = urljoin(url, og_image['content'])

                articles.append(
                    Article(
                        title=self._clean_title(title),
                        url=full_url,
                        source_name=source.name,
                        category=source.category,
                        image_url=image_url,
                    )
                )
        except Exception as e:
            logger.debug("Error parsing HTML for %s (%s): %s", source.name, url, e)
            
        return articles

    async def process_source(self, source: Source) -> list[Article]:
        """Fetch using both RSS and HTML scraping in parallel."""
        all_articles = []
        seen_urls = set()

        # 1. Fetch main page HTML
        main_html = await self._fetch_html(source.url)
        
        rss_urls = [source.url] # Sometime the main URL IS an RSS feed
        
        if main_html:
            # Autodiscover RSS feeds from main HTML
            soup = BeautifulSoup(main_html, 'html.parser')
            for link in soup.find_all('link', type=['application/rss+xml', 'application/atom+xml']):
                href = link.get('href')
                if href:
                    rss_urls.append(urljoin(source.url, href))
            
            # If no autodiscovered feeds, test common paths
            if len(rss_urls) == 1:
                parsed_url = urlparse(source.url)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                for path in COMMON_RSS_PATHS:
                    rss_urls.append(urljoin(base_url, path))

        # 2. Parallel fetch for RSS
        rss_tasks = [self._fetch_html(url) for url in set(rss_urls)] # Deduplicate URLs to fetch
        rss_contents = await asyncio.gather(*rss_tasks, return_exceptions=True)
        
        for url, content in zip(set(rss_urls), rss_contents):
            if isinstance(content, str) and content:
                # Basic heuristic: if it looks like XML/RSS, parse it as RSS
                if "<?xml" in content or "<rss" in content or "<feed" in content:
                    rss_articles = self._parse_rss_entries(url, content, source)
                    for art in rss_articles:
                        if art.url not in seen_urls:
                            seen_urls.add(art.url)
                            all_articles.append(art)
        
        # 3. Process main HTML as fallback/supplement
        if main_html:
            html_articles = await self._scrape_html(source.url, main_html, source)
            for art in html_articles:
                if art.url not in seen_urls:
                    seen_urls.add(art.url)
                    all_articles.append(art)

        logger.info("🔍 [%s] Scraped %d articles via hybrid method, keeping top 3", source.name, len(all_articles))
        
        # Hard limit to prevent blowing up the Gemini context and output token limits, and keep it under 15 mins read
        return all_articles[:3]

async def run_hybrid_scraper(sources: list[Source]) -> list[Article]:
    """Runs the hybrid scraper for all sources concurrently."""
    scraper = HybridScraper()
    sem = asyncio.Semaphore(5)  # Limit concurrent sources to avoid socket exhaustion

    async def _bounded_process(source: Source):
        async with sem:
            return await scraper.process_source(source)

    try:
        tasks = [_bounded_process(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_articles = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("❌ [%s] Scraper failed: %s", sources[i].name, result)
            else:
                all_articles.extend(result)
                
        # Final global deduplication just in case
        unique_articles = []
        seen = set()
        for article in all_articles:
            if article.url not in seen:
                seen.add(article.url)
                unique_articles.append(article)
                
        return unique_articles
    finally:
        await scraper.close()
