"""
Wikipedia game article fetcher.

Uses the Wikipedia MediaWiki API (no scraping) to:
  1. Enumerate all articles under the configured seed categories
  2. Fetch clean plain-text content for each article in batches
  3. Write results to a JSONL file

Run from scraping/wikipedia/:
    py wikipedia_fetcher.py

Optional flags:
    --dry-run      Enumerate articles only, do not fetch content
    --limit N      Stop after N articles (useful for testing)
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
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"

session = requests.Session()
session.headers.update({"User-Agent": config.USER_AGENT})


# ---------------------------------------------------------------------------
# Category enumeration
# ---------------------------------------------------------------------------

def get_category_members(category: str, member_type: str) -> list[dict]:
    """Fetch all members of a category (articles or subcategories)."""
    members = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": member_type,
        "cmlimit": 500,
        "format": "json",
    }
    while True:
        response = session.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        members.extend(data["query"]["categorymembers"])
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
        time.sleep(config.REQUEST_DELAY)
    return members


def collect_article_ids(
    categories: list[str],
    depth: int,
    visited_categories: set[str] | None = None,
) -> set[int]:
    """Recursively collect page IDs for all articles under given categories."""
    if visited_categories is None:
        visited_categories = set()

    page_ids: set[int] = set()

    for category in categories:
        if category in visited_categories:
            continue
        visited_categories.add(category)
        log.info(f"Enumerating category: {category}")

        # Collect articles directly in this category
        try:
            articles = get_category_members(category, member_type="page")
            page_ids.update(a["pageid"] for a in articles)
            log.info(f"  → {len(articles)} articles")
        except Exception as e:
            log.warning(f"  Failed to fetch articles for '{category}': {e}")

        # Recurse into subcategories
        if depth > 0:
            try:
                subcats = get_category_members(category, member_type="subcat")
                subcat_names = [s["title"].removeprefix("Category:") for s in subcats]
                child_ids = collect_article_ids(subcat_names, depth - 1, visited_categories)
                page_ids.update(child_ids)
            except Exception as e:
                log.warning(f"  Failed to fetch subcategories for '{category}': {e}")

        time.sleep(config.REQUEST_DELAY)

    return page_ids


# ---------------------------------------------------------------------------
# Article fetching
# ---------------------------------------------------------------------------

def fetch_articles_batch(page_ids: list[int]) -> list[dict]:
    """Fetch plain-text content for a batch of page IDs via the API."""
    params = {
        "action": "query",
        "pageids": "|".join(str(p) for p in page_ids),
        "prop": "extracts|categories|pageprops",
        "explaintext": "1",        # Returns clean plain text (no markup)
        "exsectionformat": "plain",
        "exlimit": "max",          # Return extracts for all pages in the batch
        "cllimit": 20,
        "redirects": "1",          # Resolve redirects automatically
        "format": "json",
    }
    response = session.get(API_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        log.error(f"API error: {data['error']}")

    return list(data["query"]["pages"].values())


def build_item(page: dict) -> dict | None:
    """Convert a raw API page dict into a clean output record."""
    title = page.get("title", "")
    content = page.get("extract", "")

    # Skip missing pages, disambiguation pages, or stubs
    if page.get("missing"):
        log.debug(f"  SKIP (missing): {title}")
        return None
    if page.get("pageprops", {}).get("disambiguation") is not None:
        log.debug(f"  SKIP (disambiguation): {title}")
        return None
    if len(content) < config.MIN_ARTICLE_LENGTH:
        log.debug(f"  SKIP (short extract, {len(content)} chars): {title}")
        return None

    categories = [
        c["title"].removeprefix("Category:")
        for c in page.get("categories", [])
    ]

    return {
        "source": "wikipedia",
        "title": title,
        "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        "content": content,
        "categories": categories,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False, limit: int | None = None) -> None:
    log.info("Collecting article IDs from seed categories...")
    all_page_ids = collect_article_ids(
        config.SEED_CATEGORIES,
        depth=config.CATEGORY_DEPTH,
    )

    page_ids = sorted(all_page_ids)
    log.info(f"Total unique articles found: {len(page_ids)}")

    if limit:
        page_ids = page_ids[:limit]
        log.info(f"Limiting to {limit} articles")

    if dry_run:
        log.info("Dry run — skipping content fetch.")
        return

    # Resolve output path relative to the project root (two levels up from this script)
    project_root = Path(__file__).resolve().parent.parent.parent
    output_path = project_root / config.OUTPUT_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0

    total = len(page_ids)
    log_every = max(1, total // 20)  # Log progress ~20 times

    with open(output_path, "a", encoding="utf-8") as out_file:
        for i, page_id in enumerate(page_ids, start=1):
            if i == 1 or i % log_every == 0 or i == total:
                log.info(f"Fetching article {i}/{total} (written={written}, skipped={skipped})...")
            try:
                pages = fetch_articles_batch([page_id])
                for page in pages:
                    item = build_item(page)
                    if item:
                        out_file.write(json.dumps(item, ensure_ascii=False) + "\n")
                        out_file.flush()
                        written += 1
                    else:
                        skipped += 1
            except Exception as e:
                log.error(f"Article {page_id} failed: {e}")
            time.sleep(config.REQUEST_DELAY)

    log.info(f"Done. Written: {written}, Skipped: {skipped}")
    log.info(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Enumerate only, no fetching")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to fetch")
    args = parser.parse_args()
    main(dry_run=args.dry_run, limit=args.limit)
