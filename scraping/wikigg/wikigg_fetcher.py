"""
wiki.gg game wiki fetcher.

Uses the MediaWiki Action API (same as Wikipedia) to:
  1. Verify each configured wiki exists
  2. Enumerate all main-namespace articles
  3. Fetch plain-text content one article at a time
  4. Write results to a JSONL file

Run from scraping/wikigg/:
    py wikigg_fetcher.py

Optional flags:
    --dry-run        Enumerate articles only, do not fetch content
    --limit N        Stop after N articles total (useful for testing)
    --wikis a,b,c    Only fetch these wiki subdomains (overrides config)
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({"User-Agent": config.USER_AGENT})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_url(wiki: str) -> str:
    return f"https://{wiki}.wiki.gg/w/api.php"


def wiki_exists(wiki: str) -> bool:
    """Return True if the wiki subdomain resolves and has a working API."""
    try:
        resp = session.get(
            api_url(wiki),
            params={"action": "query", "meta": "siteinfo", "format": "json"},
            timeout=10,
        )
        return resp.status_code == 200 and "query" in resp.json()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Article enumeration
# ---------------------------------------------------------------------------

def get_all_page_ids(wiki: str) -> list[int]:
    """Enumerate all main-namespace article IDs for a wiki."""
    page_ids: list[int] = []
    params = {
        "action": "query",
        "list": "allpages",
        "apnamespace": 0,       # Main namespace only
        "apfilterredir": "nonredirects",
        "aplimit": 500,
        "format": "json",
    }
    url = api_url(wiki)
    while True:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        page_ids.extend(p["pageid"] for p in data["query"]["allpages"])
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
        time.sleep(config.REQUEST_DELAY)
    return page_ids


# ---------------------------------------------------------------------------
# Article fetching
# ---------------------------------------------------------------------------

def fetch_article(wiki: str, page_id: int) -> dict:
    """Fetch plain-text content for a single article."""
    params = {
        "action": "query",
        "pageids": page_id,
        "prop": "extracts|categories|pageprops",
        "explaintext": "1",
        "exsectionformat": "plain",
        "exlimit": "max",       # API enforces 1 for full articles — we fetch one at a time
        "cllimit": 20,
        "redirects": "1",
        "format": "json",
    }
    resp = session.get(api_url(wiki), params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        log.error(f"API error for page {page_id}: {data['error']}")
    pages = data["query"]["pages"]
    return next(iter(pages.values()))


def build_item(page: dict, wiki: str) -> dict | None:
    """Convert a raw API page dict into a clean output record."""
    title = page.get("title", "")
    content = page.get("extract", "")

    if page.get("missing"):
        log.debug(f"  SKIP (missing): {title}")
        return None
    if page.get("pageprops", {}).get("disambiguation") is not None:
        log.debug(f"  SKIP (disambiguation): {title}")
        return None
    if len(content) < config.MIN_ARTICLE_LENGTH:
        log.debug(f"  SKIP (short, {len(content)} chars): {title}")
        return None

    categories = [
        c["title"].removeprefix("Category:")
        for c in page.get("categories", [])
    ]

    return {
        "source": f"wikigg:{wiki}",
        "wiki": wiki,
        "title": title,
        "url": f"https://{wiki}.wiki.gg/wiki/{title.replace(' ', '_')}",
        "content": content,
        "categories": categories,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False, limit: int | None = None, wikis: list[str] | None = None) -> None:
    target_wikis = wikis or config.TARGET_WIKIS

    project_root = Path(__file__).resolve().parent.parent.parent
    output_path = project_root / config.OUTPUT_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = skipped = 0
    remaining = limit  # tracks articles left across all wikis

    with open(output_path, "a", encoding="utf-8") as out_f:
        for wiki in target_wikis:
            log.info(f"Checking {wiki}.wiki.gg...")
            if not wiki_exists(wiki):
                log.warning(f"  {wiki}.wiki.gg not found — skipping")
                continue

            log.info(f"Enumerating articles for {wiki}.wiki.gg...")
            try:
                page_ids = get_all_page_ids(wiki)
            except Exception as e:
                log.error(f"  Failed to enumerate {wiki}: {e}")
                continue

            log.info(f"  → {len(page_ids)} articles")

            if dry_run:
                continue

            if remaining is not None:
                page_ids = page_ids[:remaining]

            total = len(page_ids)
            log_every = max(1, total // 20)

            for i, page_id in enumerate(page_ids, start=1):
                if i == 1 or i % log_every == 0 or i == total:
                    log.info(f"  [{wiki}] {i}/{total} (written={written}, skipped={skipped})")

                try:
                    page = fetch_article(wiki, page_id)
                    item = build_item(page, wiki)
                    if item:
                        out_f.write(json.dumps(item, ensure_ascii=False) + "\n")
                        out_f.flush()
                        written += 1
                    else:
                        skipped += 1
                except Exception as e:
                    log.error(f"  [{wiki}] page {page_id} failed: {e}")
                    skipped += 1

                time.sleep(config.REQUEST_DELAY)

            if remaining is not None:
                remaining -= len(page_ids)
                if remaining <= 0:
                    break

    if not dry_run:
        log.info(f"Done. Written: {written}, Skipped: {skipped}")
        log.info(f"Output: {output_path.resolve()}")
    else:
        log.info("Dry run complete — no content fetched.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Enumerate only, no fetching")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to fetch in total")
    parser.add_argument("--wikis", type=str, default=None, help="Comma-separated wiki subdomains")
    args = parser.parse_args()

    wiki_list = [w.strip() for w in args.wikis.split(",")] if args.wikis else None
    main(dry_run=args.dry_run, limit=args.limit, wikis=wiki_list)
