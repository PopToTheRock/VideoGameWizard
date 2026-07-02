import json
from pathlib import Path

from itemadapter import ItemAdapter


class JsonlWriterPipeline:
    """Writes each scraped item as a JSON line to the output file."""

    def __init__(self, output_file: str):
        self.output_file = output_file
        self.file = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(output_file=crawler.settings.get("OUTPUT_FILE"))

    def open_spider(self, spider):
        path = Path(self.output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Append so multiple spider runs accumulate data
        self.file = open(path, "a", encoding="utf-8")
        spider.logger.info(f"Writing output to {path.resolve()}")

    def close_spider(self, spider):
        if self.file:
            self.file.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        line = json.dumps(adapter.asdict(), ensure_ascii=False)
        self.file.write(line + "\n")
        return item
