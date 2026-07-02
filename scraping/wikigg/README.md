# wikigg/ — wiki.gg fetcher (reference only, never used)

This fetcher was built while evaluating wiki.gg as a data source and was
**never used to build the corpus**: only two relevant wikis existed there and
their API behavior was inconsistent (see the data-source decision table in the
root `CLAUDE.md`).

It is kept as reference code for the multi-wiki MediaWiki-API approach. The
shipped knowledge base is built exclusively from English Wikipedia via
`scraping/wikipedia/`.
