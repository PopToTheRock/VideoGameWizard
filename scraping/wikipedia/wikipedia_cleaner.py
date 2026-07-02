"""
Wikipedia data cleaner.

Reads wikipedia_raw.jsonl and writes wikipedia_clean.jsonl with:
  - Boilerplate tail sections removed (References, See also, External links, etc.)
  - MediaWiki template remnants removed ({{cite book}}, CS1 maint notices, etc.)
  - Unicode replacement characters removed
  - Excessive whitespace normalized

Run from scraping/wikipedia/:
    py wikipedia_cleaner.py
"""

import json
import logging
import re
from pathlib import Path

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Section names that mark the start of non-content tail matter.
# These appear as standalone lines in the plain-text extract.
BOILERPLATE_SECTIONS = {
    "See also",
    "References",
    "External links",
    "Notes",
    "Further reading",
    "Bibliography",
    "Footnotes",
    "Citations",
    "Sources",
    "Works cited",
}

# Matches MediaWiki template fragments like {{cite book}}, {{cite web}}, {{reflist}}, etc.
_RE_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")

# Matches CS1 error/maintenance notices that follow template fragments
_RE_CS1 = re.compile(r":\s+CS1 maint:[^\n]+")

# Matches numbered citation markers like [1], [23], [nb 1], [note 2]
_RE_CITE = re.compile(r"\[(?:\d+|nb \d+|note \d+)\]")

# Unicode replacement character (U+FFFD) from encoding errors
_RE_REPLACEMENT = re.compile(r"\ufffd+")


def truncate_at_boilerplate(text: str) -> str:
    """Cut the article at the first boilerplate section heading."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() in BOILERPLATE_SECTIONS:
            return "\n".join(lines[:i])
    return text


def clean_content(text: str) -> str:
    # 1. Remove boilerplate tail sections first (biggest win)
    text = truncate_at_boilerplate(text)

    # 2. Remove MediaWiki template remnants and CS1 notices
    text = _RE_TEMPLATE.sub("", text)
    text = _RE_CS1.sub("", text)

    # 3. Remove citation markers
    text = _RE_CITE.sub("", text)

    # 4. Remove Unicode replacement characters
    text = _RE_REPLACEMENT.sub("", text)

    # 5. Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]

    # 6. Collapse 3+ consecutive blank lines to 2
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 2:
                cleaned.append(line)
        else:
            blank_run = 0
            cleaned.append(line)

    return "\n".join(cleaned).strip()


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    input_path = project_root / config.OUTPUT_FILE
    output_path = project_root / "scraping/data/wikipedia_clean.jsonl"

    if not input_path.exists():
        log.error(f"Input file not found: {input_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = written = skipped = 0
    chars_before = chars_after = 0

    with (
        open(input_path, encoding="utf-8") as in_f,
        open(output_path, "w", encoding="utf-8") as out_f,
    ):
        for raw_line in in_f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            total += 1

            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as e:
                log.warning(f"Bad JSON on record {total}: {e}")
                skipped += 1
                continue

            original_len = len(record["content"])
            cleaned = clean_content(record["content"])

            if len(cleaned) < config.MIN_ARTICLE_LENGTH:
                log.debug(f"SKIP (too short after cleaning): {record['title']}")
                skipped += 1
                continue

            chars_before += original_len
            chars_after += len(cleaned)
            record["content"] = cleaned
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    reduction = 100 * (1 - chars_after / chars_before) if chars_before else 0
    log.info(f"Done. Input: {total}, Written: {written}, Skipped: {skipped}")
    log.info(f"Text reduction: {chars_before:,} → {chars_after:,} chars ({reduction:.1f}% removed)")
    log.info(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
