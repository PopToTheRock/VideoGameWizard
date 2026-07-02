import scrapy


class WikiArticleItem(scrapy.Item):
    wiki_name = scrapy.Field()  # e.g. "minecraft", "elderscrolls"
    title = scrapy.Field()  # Article title
    url = scrapy.Field()  # Canonical URL
    content = scrapy.Field()  # Plain text body (cleaned)
    categories = scrapy.Field()  # List of wiki categories for this article
    scraped_at = scrapy.Field()  # ISO timestamp
