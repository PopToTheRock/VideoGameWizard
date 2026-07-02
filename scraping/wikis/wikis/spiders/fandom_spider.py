"""
Fandom wiki spider.

Crawls article pages on Fandom game wikis, extracts clean plain-text content,
and yields WikiArticleItem instances for the output pipeline.

Run from scraping/wikis/:
    scrapy crawl fandom
    scrapy crawl fandom -a wikis=minecraft,elderscrolls   # override wiki list
    scrapy crawl fandom -a wikis=minecraft -s CLOSESPIDER_ITEMCOUNT=200
"""

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from scrapy import Spider
from scrapy.http import Response

from wikis.items import WikiArticleItem

# ---------------------------------------------------------------------------
# Wiki definitions
# Each entry: (wiki_name, start_url)
# The spider follows internal /wiki/* links automatically.
# Add or remove wikis here to control what gets scraped.
# ---------------------------------------------------------------------------
FANDOM_WIKIS: list[tuple[str, str]] = [
    ("minecraft", "https://minecraft.fandom.com/wiki/Minecraft_Wiki"),
    ("elderscrolls", "https://elderscrolls.fandom.com/wiki/The_Elder_Scrolls_Wiki"),
    ("witcher", "https://witcher.fandom.com/wiki/The_Witcher_Wiki"),
    ("eldenring", "https://eldenring.fandom.com/wiki/Elden_Ring_Wiki"),
    ("pokemon", "https://bulbapedia.bulbagarden.net/wiki/Main_Page"),
    ("stardewvalley", "https://stardewvalleywiki.com/Stardew_Valley_Wiki"),
    ("zelda", "https://zelda.fandom.com/wiki/The_Legend_of_Zelda_Wiki"),
]

# Article URL patterns to follow (Fandom-style)
ARTICLE_PATH_RE = re.compile(r"^/wiki/[^:]+$")

# Fandom noise selectors — elements to strip before extracting text
STRIP_SELECTORS = [
    "aside",  # infobox sidebars
    ".navbox",  # navigation boxes
    ".toc",  # table of contents
    ".references",  # citation lists
    ".mw-editsection",  # [edit] links
    "sup.reference",  # inline footnote numbers
    ".noprint",
    "script",
    "style",
    ".wikia-ad",
    ".fandom-sticky-header",
    ".page-footer",
    "#WikiaBar",
    ".notifications-placeholder",
]

# Minimum article body length (chars) — skip stubs and redirects
MIN_CONTENT_LENGTH = 150


class FandomSpider(Spider):
    name = "fandom"

    def __init__(self, wikis: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if wikis:
            names = {w.strip() for w in wikis.split(",")}
            self._wikis = [(n, u) for n, u in FANDOM_WIKIS if n in names]
        else:
            self._wikis = FANDOM_WIKIS

    def start_requests(self):
        import scrapy

        for wiki_name, start_url in self._wikis:
            yield scrapy.Request(
                start_url,
                callback=self.parse_article,
                cb_kwargs={"wiki_name": wiki_name},
                errback=self._handle_error,
            )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_article(self, response: Response, wiki_name: str):
        # Follow internal article links first
        yield from self._follow_article_links(response, wiki_name)

        # Skip non-200 or non-HTML
        if response.status != 200:
            return
        if "text/html" not in response.headers.get("Content-Type", b"").decode():
            return

        item = self._extract_article(response, wiki_name)
        if item is not None:
            yield item

    def _follow_article_links(self, response: Response, wiki_name: str):
        import scrapy

        base = urlparse(response.url)
        seen_urls = set()

        for href in response.css("a::attr(href)").getall():
            if not href:
                continue
            parsed = urlparse(href)
            # Resolve relative URLs
            if not parsed.netloc:
                parsed = parsed._replace(netloc=base.netloc, scheme=base.scheme)
            # Only follow links on the same domain
            if parsed.netloc != base.netloc:
                continue
            # Must match the article path pattern
            if not ARTICLE_PATH_RE.match(parsed.path):
                continue
            # Drop fragment / query to avoid duplicate URLs
            canonical = parsed._replace(fragment="", query="").geturl()
            if canonical in seen_urls:
                continue
            seen_urls.add(canonical)
            yield scrapy.Request(
                canonical,
                callback=self.parse_article,
                cb_kwargs={"wiki_name": wiki_name},
                errback=self._handle_error,
            )

    def _extract_article(self, response: Response, wiki_name: str) -> WikiArticleItem | None:
        soup = BeautifulSoup(response.text, "html.parser")

        # --- Title ---
        title_tag = soup.find("h1", id="firstHeading") or soup.find("h1")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)

        # Skip disambiguation, talk, file, category, user pages
        skip_prefixes = (
            "talk:",
            "file:",
            "category:",
            "user:",
            "template:",
            "help:",
            "special:",
            "mediawiki:",
        )
        if any(title.lower().startswith(p) for p in skip_prefixes):
            return None

        # --- Content ---
        content_div = (
            soup.find("div", class_="mw-parser-output")
            or soup.find("div", id="mw-content-text")
            or soup.find("article")
        )
        if not content_div:
            return None

        # Strip noise
        for selector in STRIP_SELECTORS:
            for el in content_div.select(selector):
                el.decompose()

        content = self._extract_text(content_div)
        if len(content) < MIN_CONTENT_LENGTH:
            return None

        # --- Categories ---
        categories = [a.get_text(strip=True) for a in soup.select("#mw-normal-catlinks ul li a")]

        return WikiArticleItem(
            wiki_name=wiki_name,
            title=title,
            url=response.url,
            content=content,
            categories=categories,
            scraped_at=datetime.now(UTC).isoformat(),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(element) -> str:
        """Convert an HTML element to clean plain text."""
        lines = []
        for block in element.find_all(["p", "h2", "h3", "h4", "li", "dt", "dd"], recursive=True):
            text = block.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                lines.append(text)
        return "\n".join(lines)

    def _handle_error(self, failure):
        self.logger.warning(f"Request failed: {failure.request.url} — {failure.value}")
