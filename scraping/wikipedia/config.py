"""
Wikipedia fetcher configuration.
"""

# Identifies our bot to Wikipedia — required by their API policy
USER_AGENT = (
    "VideoGameWizardBot/1.0 "
    "(https://github.com/PopToTheRock/VideoGameWizard; alex.novicicy@gmail.com)"
)

# Seed categories to crawl. The fetcher recurses into subcategories up to
# CATEGORY_DEPTH levels deep. Adjust this list to broaden or narrow scope.
SEED_CATEGORIES = [
    "Action-adventure games",
    "Role-playing video games",
    "Open world video games",
    "Massively multiplayer online role-playing games",
    "First-person shooter games",
    "Battle royale games",
    "Survival video games",
    "Soulslike video games",
    "Metroidvania games",
    "Strategy video games",
    "Simulation video games",
    "Sports video games",
    "Fighting games",
    "Puzzle video games",
    # Individual high-value series
    "The Legend of Zelda video games",
    "Pokémon video games",
    "Grand Theft Auto video games",
    "Dark Souls video games",
    "The Elder Scrolls video games",
    "Fallout video games",
    "Call of Duty video games",
    "Halo video games",
    "God of War video games",
    "Final Fantasy video games",
    "Monster Hunter video games",
    "Persona video games",
]

# How many subcategory levels deep to recurse (keep low to avoid explosion)
CATEGORY_DEPTH = 2

# Wikipedia API batch size for extract requests.
# The TextExtracts API enforces exlimit=1 for whole-article requests,
# meaning only 1 article per API call can receive content. Must be 1.
BATCH_SIZE = 1

# Seconds between API requests — be polite
REQUEST_DELAY = 0.5

# Minimum article length in characters (skip very short stubs)
MIN_ARTICLE_LENGTH = 500

# Output file
OUTPUT_FILE = "scraping/data/wikipedia_raw.jsonl"
