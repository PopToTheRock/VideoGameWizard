BOT_NAME = "wikis"

SPIDER_MODULES = ["wikis.spiders"]
NEWSPIDER_MODULE = "wikis.spiders"

# Identify ourselves honestly
USER_AGENT = "VideoGameWizardBot/1.0 (+https://github.com/your-repo)"

# Respect robots.txt
ROBOTSTXT_OBEY = True

# Be polite — don't hammer servers
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Auto-throttle adjusts delay based on server load
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# Retry on transient errors only
RETRY_ENABLED = True
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 429]

# Cache responses during development to avoid re-hitting servers
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400  # 1 day
HTTPCACHE_DIR = ".scrapy/httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = [404, 429, 500]

# Output pipeline
ITEM_PIPELINES = {
    "wikis.pipelines.JsonlWriterPipeline": 300,
}

OUTPUT_FILE = "../../data/wiki_raw.jsonl"

# Limit crawl depth to avoid infinite link-following
DEPTH_LIMIT = 4

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
