# wikis/ — Fandom Scrapy spider (reference only, never used)

This Scrapy project was built while evaluating Fandom wikis as a data source and
was **never used to build the corpus**: Fandom content is licensed
**CC BY-NC-SA**, and the NonCommercial clause conflicts with this project's
goals (see the data-source decision table in the root `CLAUDE.md`).

It is kept as reference code for the Scrapy-based crawling approach (robots.txt
compliance, politeness settings, item pipelines). The shipped knowledge base is
built exclusively from English Wikipedia via `scraping/wikipedia/`.
