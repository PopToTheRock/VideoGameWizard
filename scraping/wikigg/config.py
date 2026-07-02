"""
wiki.gg fetcher configuration.
"""

# Identifies our bot to wiki.gg — required by MediaWiki API policy
USER_AGENT = (
    "VideoGameWizardBot/1.0 "
    "(https://github.com/PopToTheRock/VideoGameWizard; alex.novicicy@gmail.com)"
)

# wiki.gg subdomains to scrape.
# Each entry is the subdomain prefix, e.g. "zelda" → zelda.wiki.gg
# Verify each one exists at https://<name>.wiki.gg before adding.
TARGET_WIKIS = [
    "zelda",
    "pokemon",
    "minecraft",
    "eldenring",
    "darksouls",
    "finalfantasy",
    "godofwar",
    "monsterhunter",
    "stardewvalley",
    "hollowknight",
    "hades",
    "cyberpunk",
    "witcher",
    "metroid",
    "fireemblem",
]

# Seconds between API requests — be polite
REQUEST_DELAY = 0.5

# Minimum article length in characters (skip stubs)
MIN_ARTICLE_LENGTH = 500

# Output file (relative to project root)
OUTPUT_FILE = "scraping/data/wikigg_raw.jsonl"
