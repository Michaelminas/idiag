"""Market pricing service — Swappa scraping with static fallback."""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Model name -> Swappa URL slug
_SWAPPA_SLUGS: dict[str, str] = {
    "iPhone 16 Pro Max": "apple-iphone-16-pro-max",
    "iPhone 16 Pro": "apple-iphone-16-pro",
    "iPhone 16 Plus": "apple-iphone-16-plus",
    "iPhone 16": "apple-iphone-16",
    "iPhone 15 Pro Max": "apple-iphone-15-pro-max",
    "iPhone 15 Pro": "apple-iphone-15-pro",
    "iPhone 15 Plus": "apple-iphone-15-plus",
    "iPhone 15": "apple-iphone-15",
    "iPhone 14 Pro Max": "apple-iphone-14-pro-max",
    "iPhone 14 Pro": "apple-iphone-14-pro",
    "iPhone 14 Plus": "apple-iphone-14-plus",
    "iPhone 14": "apple-iphone-14",
    "iPhone 13 Pro Max": "apple-iphone-13-pro-max",
    "iPhone 13 Pro": "apple-iphone-13-pro",
    "iPhone 13": "apple-iphone-13",
    "iPhone 13 mini": "apple-iphone-13-mini",
    "iPhone 12 Pro Max": "apple-iphone-12-pro-max",
    "iPhone 12 Pro": "apple-iphone-12-pro",
    "iPhone 12": "apple-iphone-12",
    "iPhone 12 mini": "apple-iphone-12-mini",
    "iPhone 11 Pro Max": "apple-iphone-11-pro-max",
    "iPhone 11 Pro": "apple-iphone-11-pro",
    "iPhone 11": "apple-iphone-11",
    "iPhone SE 3": "apple-iphone-se-3rd-gen",
    "iPhone SE 2": "apple-iphone-se-2nd-gen",
    "iPhone XS Max": "apple-iphone-xs-max",
    "iPhone XS": "apple-iphone-xs",
    "iPhone XR": "apple-iphone-xr",
    "iPhone X": "apple-iphone-x",
    "iPhone 8 Plus": "apple-iphone-8-plus",
    "iPhone 8": "apple-iphone-8",
}

# In-memory cache: slug -> (timestamp, {storage: {condition: price}})
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 86400  # 24 hours


def _load_static_prices() -> dict:
    path = settings.data_dir / "market_prices.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    data.pop("_meta", None)
    return data


try:
    _STATIC_PRICES = _load_static_prices()
except Exception:
    logger.error("Failed to load static market prices")
    _STATIC_PRICES = {}


def _scrape_swappa(slug: str) -> Optional[dict]:
    """Fetch pricing data from Swappa's listing page.

    Returns dict like {"128": {"good": 450, "fair": 380, "poor": 300}, ...}
    or None on failure.
    """
    url = f"https://swappa.com/guide/{slug}/prices"
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })
        if resp.status_code != 200:
            logger.warning("Swappa returned %d for %s", resp.status_code, slug)
            return None
        return _parse_swappa_html(resp.text)
    except Exception as e:
        logger.warning("Swappa scrape failed for %s: %s", slug, e)
        return None


def _parse_swappa_html(html: str) -> Optional[dict]:
    """Extract pricing data from Swappa pricing guide HTML.

    Looks for price patterns in the page content. Swappa pages include
    pricing tables with storage variants and condition-based prices.
    """
    prices: dict[str, dict[str, int]] = {}

    # Look for price data in JSON-LD or structured data
    # Swappa embeds pricing in various formats; try multiple strategies

    # Strategy 1: Find price patterns near storage labels (e.g., "128GB")
    storage_pattern = re.compile(r'(\d+)\s*(?:GB|TB)', re.IGNORECASE)
    price_pattern = re.compile(r'\$(\d{2,4})')

    # Find all storage mentions and nearby prices
    for storage_match in storage_pattern.finditer(html):
        storage = storage_match.group(1)
        if storage == "1" or storage == "1024":
            storage = "1024"
        # Look in the surrounding context (500 chars after the storage label)
        start = storage_match.start()
        context = html[start:start + 500]
        found_prices = price_pattern.findall(context)
        if found_prices:
            int_prices = sorted([int(p) for p in found_prices if 30 < int(p) < 3000])
            if len(int_prices) >= 3:
                prices[storage] = {
                    "good": int_prices[-1],
                    "fair": int_prices[len(int_prices) // 2],
                    "poor": int_prices[0],
                }
            elif len(int_prices) >= 1:
                avg = int_prices[len(int_prices) // 2]
                prices[storage] = {
                    "good": int(avg * 1.1),
                    "fair": avg,
                    "poor": int(avg * 0.85),
                }

    return prices if prices else None


def _grade_to_condition(grade: str) -> str:
    """Map iDiag grade to pricing condition."""
    g = grade.upper().strip()
    if g in ("A", "A+", "A-"):
        return "good"
    if g in ("B", "B+", "B-"):
        return "good"
    if g in ("C", "C+", "C-"):
        return "fair"
    return "poor"


def lookup_price(
    model: str,
    storage_gb: int = 0,
    grade: str = "",
) -> dict:
    """Look up market price for a device.

    Args:
        model: Device model name (e.g. "iPhone 13 Pro").
        storage_gb: Storage in GB (e.g. 128, 256). 0 = return all storage options.
        grade: iDiag grade (A/B/C/D) — maps to good/fair/poor condition.

    Returns:
        {
            "model": str,
            "source": "swappa" | "static" | "none",
            "prices": {
                "128": {"good": 450, "fair": 380, "poor": 300},
                ...
            },
            "suggested_price": int | None,  # specific price for given storage+grade
        }
    """
    slug = _SWAPPA_SLUGS.get(model, "")
    prices = None
    source = "none"

    # Try Swappa cache / scrape
    if slug:
        cached = _cache.get(slug)
        if cached and (time.time() - cached[0]) < _CACHE_TTL:
            prices = cached[1]
            source = "swappa"
        else:
            scraped = _scrape_swappa(slug)
            if scraped:
                _cache[slug] = (time.time(), scraped)
                prices = scraped
                source = "swappa"

    # Fallback to static prices
    if not prices and model in _STATIC_PRICES:
        prices = _STATIC_PRICES[model]
        source = "static"

    # Compute suggested price
    suggested = None
    if prices and storage_gb > 0:
        storage_key = str(storage_gb)
        storage_prices = prices.get(storage_key, {})
        if storage_prices:
            condition = _grade_to_condition(grade) if grade else "fair"
            suggested = storage_prices.get(condition)

    return {
        "model": model,
        "source": source,
        "prices": prices or {},
        "suggested_price": suggested,
    }
