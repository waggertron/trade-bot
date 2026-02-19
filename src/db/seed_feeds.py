"""Parse the free-news-feeds-reference.md and seed the feeds table."""

from __future__ import annotations

import re
from pathlib import Path

from src.db.models import FeedRecord

# Map section headings to category slugs
CATEGORY_MAP = {
    "1. Markets & Finance": "markets",
    "2. Politics": "politics",
    "3. Technology": "technology",
    "4. Trade & International": "trade",
    "5. Industry / Sector-Specific": "industry",
    "6. Media & Journalism": "media",
}

# Rate limits parsed from the "Rate Limits at a Glance" table
RATE_LIMITS: dict[str, int] = {
    "Finnhub": 60,
    "Alpha Vantage": 25,
    "Polygon.io": 5,
    "NewsAPI.org": 100,
    "GNews": 100,
    "NewsData.io": 200,
    "Mediastack": 100,
    "Finlight.me": 5000,
    "EODHD": 20,
    "FRED": 120,
    "SEC EDGAR": 600,  # 10/sec
}

DEFAULT_REFERENCE_PATH = Path("docs/reference/free-news-feeds-reference.md")


def _extract_url(cell: str) -> str:
    """Extract a URL from a markdown table cell (may be wrapped in backticks)."""
    m = re.search(r"`(https?://[^`]+)`", cell)
    if m:
        return m.group(1)
    m = re.search(r"(https?://\S+)", cell)
    if m:
        return m.group(1).rstrip("|").rstrip()
    return cell.strip().strip("`")


def _extract_name(cell: str) -> str:
    """Extract name from a markdown table cell (remove bold markers)."""
    return cell.strip().replace("**", "").strip()


def _detect_auth_type(url: str, extra_text: str = "") -> str:
    """Detect if a feed requires an API key."""
    indicators = ["token=KEY", "apikey=KEY", "apiKey=KEY", "api_key=KEY",
                  "access_key=KEY", "api_token=KEY"]
    for ind in indicators:
        if ind.lower() in url.lower():
            return "api_key"
    if "key" in extra_text.lower() and "no key" not in extra_text.lower():
        if "api key" in extra_text.lower() or "free key" in extra_text.lower():
            return "api_key"
    return "free"


def _get_rate_limit(name: str, feed_type: str) -> int:
    """Look up rate limit for a provider, defaulting to 60 for RSS."""
    for provider, rpm in RATE_LIMITS.items():
        if provider.lower() in name.lower():
            return rpm
    return 60 if feed_type == "rss" else 60


def parse_feeds_from_reference(path: Path | None = None) -> list[FeedRecord]:
    """Parse the reference markdown and return FeedRecord objects."""
    if path is None:
        path = DEFAULT_REFERENCE_PATH
    text = path.read_text()
    lines = text.split("\n")

    records: list[FeedRecord] = []
    seen_urls: set[str] = set()
    current_category = ""
    current_sub_type = ""

    for i, line in enumerate(lines):
        # Detect category sections: ## N. Category Name
        if line.startswith("## "):
            heading = line[3:].strip()
            for pattern, slug in CATEGORY_MAP.items():
                if pattern in heading:
                    current_category = slug
                    break
            else:
                # Cross-Category Power Tools
                if "Cross-Category" in heading:
                    current_category = "cross_category"

        # Detect sub-type sections: ### RSS Feeds, ### APIs, ### Government
        if line.startswith("### "):
            sub = line[4:].strip().lower()
            if "rss" in sub:
                current_sub_type = "rss"
            elif "api" in sub:
                current_sub_type = "json_api"
            elif "government" in sub:
                current_sub_type = "government"

        # Parse table rows: | Name | URL | ... |
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        # Filter out empty cells from leading/trailing pipes
        cells = [c for c in cells if c]

        if len(cells) < 2:
            continue
        # Skip header/separator rows
        if cells[0].startswith("---") or cells[0].startswith("Source") or cells[0].startswith("Provider") or cells[0].startswith("Tool") or cells[0].startswith("Category") or cells[0].startswith("Feed URL"):
            continue

        name = _extract_name(cells[0])
        url_cell = cells[1]
        url = _extract_url(url_cell)
        extra_text = " ".join(cells[2:]) if len(cells) > 2 else ""

        if not url or not url.startswith("http"):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Determine feed_type
        feed_type = current_sub_type
        if not feed_type:
            # Cross-category table: detect from URL/context
            if "KEY" in url or "token=" in url or "apikey=" in url or "apiKey=" in url or "access_key=" in url or "api_token=" in url:
                feed_type = "json_api"
            elif url.endswith(".xml") or url.endswith(".rss") or "/rss/" in url or "/feed/" in url or "/feeds/" in url:
                feed_type = "rss"
            else:
                feed_type = "json_api"

        # Determine auth type
        auth_type = _detect_auth_type(url, extra_text)

        # Category fallback
        category = current_category or "cross_category"

        rate_limit = _get_rate_limit(name, feed_type)

        records.append(FeedRecord(
            name=name,
            url=url,
            feed_type=feed_type,
            category=category,
            auth_type=auth_type,
            rate_limit_rpm=rate_limit,
        ))

    return records


async def seed_feeds_from_reference(
    db: "Database",  # noqa: F821
    path: Path | None = None,
) -> int:
    """Parse reference doc and seed feeds into the database."""
    records = parse_feeds_from_reference(path)
    await db.seed_feeds(records)
    return len(records)
