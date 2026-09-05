"""
Resolves card names from the swu-db.com API.
Results are cached to avoid redundant API calls.
"""
import os
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from .app_paths import get_card_cache_path
except ImportError:
    from decklister.app_paths import get_card_cache_path

API_BASE = "https://api.swu-db.com/cards"
MAX_WORKERS = 8
CACHE_KEY_PREFIX = "name:"


def _load_name_cache():
    cache_path = get_card_cache_path()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_name_cache(cache):
    cache_path = get_card_cache_path()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: could not save name cache: {e}")


def _lookup_card_name(card_set, card_number):
    """
    Look up a card's name and subtitle from the swu-db.com API.

    Args:
        card_set: Card set identifier (e.g., 'SOR').
        card_number: Card number (str or int).

    Returns:
        Dict {"name": str, "subtitle": str} or None if not found.
    """
    num_str = str(card_number)
    try:
        url = f"{API_BASE}/{card_set}/{num_str}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # The API may return the card directly or in a wrapper
        if isinstance(data, dict):
            name = data.get("name") or data.get("Name")
            subtitle = data.get("subtitle") or data.get("Subtitle")
            if name:
                return {"name": name, "subtitle": subtitle or ""}

        return None
    except Exception as e:
        print(f"Warning: name lookup failed for {card_set}_{num_str}: {e}")
        return None


def _format_name(entry, show_subtitles=True):
    """Build the display name from a cache entry (dict or legacy string)."""
    if isinstance(entry, dict):
        name = entry.get("name", "")
        subtitle = entry.get("subtitle", "")
        if show_subtitles and subtitle:
            return f"{name}, {subtitle}"
        return name
    # Legacy cache format: a plain string that may include ", subtitle"
    if isinstance(entry, str):
        if not show_subtitles and ", " in entry:
            return entry.split(", ", 1)[0]
        return entry
    return ""


def resolve_card_names(cards, show_subtitles=True):
    """
    Resolve names for a list of Card objects.
    Sets card.name on each card.

    Args:
        cards: List of Card objects with card_set and card_number attributes.
        show_subtitles: If False, only the card name is used (subtitle dropped).
    """
    cache = _load_name_cache()
    to_resolve = []

    # Check cache first
    for card in cards:
        cache_key = f"{CACHE_KEY_PREFIX}{card.card_set}_{card.card_number}"
        cached = cache.get(cache_key)
        if cached:
            card.name = _format_name(cached, show_subtitles)
        else:
            to_resolve.append(card)

    if to_resolve:
        # Deduplicate by set_number
        unique = {}
        for card in to_resolve:
            key = f"{card.card_set}_{card.card_number}"
            if key not in unique:
                unique[key] = card

        print(f"Resolving {len(unique)} card name(s) via API ({len(cards) - len(to_resolve)} cached)...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_lookup_card_name, card.card_set, card.card_number): key
                for key, card in unique.items()
            }
            for future in as_completed(futures):
                key = futures[future]
                result = future.result()
                cache_key = f"{CACHE_KEY_PREFIX}{key}"
                if result:
                    cache[cache_key] = result

        _save_name_cache(cache)

        # Apply names to all cards (including duplicates)
        for card in to_resolve:
            cache_key = f"{CACHE_KEY_PREFIX}{card.card_set}_{card.card_number}"
            entry = cache.get(cache_key)
            if entry:
                card.name = _format_name(entry, show_subtitles)
            else:
                card.name = f"{card.card_set} {card.card_number}"
