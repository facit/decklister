"""
Parser for Melee.gg decklist CSV exports.

Each row in the CSV represents one submitted decklist. Card IDs (set + number)
are resolved by looking up card names against the swudb.com API.
Resolved names are cached in card_cache.json to avoid redundant API calls.
"""
import csv
import json
import os
import sys
import urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from .deck import Card, Deck
    from .app_paths import get_card_cache_path
except ImportError:
    from decklister.deck import Card, Deck
    from decklister.app_paths import get_card_cache_path

SWUDB_SEARCH = "https://swudb.com/api/search"
SWUDB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
MAX_WORKERS = 4  # Conservative to avoid rate-limiting


def _cache_key(name, subtitle):
    return f"{name}|{subtitle}" if subtitle else name


def _load_cache():
    cache_path = get_card_cache_path()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache):
    cache_path = get_card_cache_path()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: could not save card cache: {e}")


def _lookup_card_id(name, subtitle):
    """
    Look up a card's SET_NUMBER from the swudb.com API.

    Args:
        name: Card name (e.g. "IG-11").
        subtitle: Card subtitle, or None (e.g. "I Cannot Be Captured").

    Returns:
        "SET_NUMBER" string (e.g. "SHD_170"), or None if not found.
    """
    try:
        query = f'{name} title:"{subtitle}"' if subtitle else name
        url = (
            f"{SWUDB_SEARCH}/{urllib.parse.quote(query)}"
            f"?grouping=cards&sortorder=setno&sortdir=asc"
        )
        resp = requests.get(url, headers=SWUDB_HEADERS, timeout=10)
        resp.raise_for_status()

        printings = resp.json().get("printings", [])
        # Prefer normal variant (variantType=1) to avoid returning a hyperspace number
        normal = [p for p in printings if p.get("variantType") == 1]
        candidates = normal or printings

        if candidates:
            p = candidates[0]
            return f"{p['expansionAbbreviation']}_{p['cardNumber']}"

        print(f"Warning: card not found on swudb.com — '{name}' / '{subtitle}'")
        return None

    except Exception as e:
        print(f"Warning: lookup failed for '{name}': {e}")
        return None


def _count_rows(path):
    """Quick count of data rows in a CSV file (without full parsing)."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if raw.startswith(b'\xef\xbb\xbf'):
            raw = raw[3:]
        text = raw.decode("utf-8", errors="replace")
        import io
        reader = csv.DictReader(io.StringIO(text))
        return sum(1 for _ in reader)
    except Exception:
        return 1


def _select_row(rows, player_name=None, deck_index=0):
    """Pick which CSV row to use and return it."""
    if not rows:
        raise ValueError("CSV file contains no decks.")

    if player_name:
        matching = [
            r for r in rows
            if r.get("OwnerDisplayName") == player_name
            or r.get("OwnerUsername") == player_name
            or r.get("OwnerNameFirstLast") == player_name
        ]
        if not matching:
            available = sorted({r.get("OwnerDisplayName", "") for r in rows})
            raise ValueError(
                f"Player '{player_name}' not found in CSV.\n"
                f"Available players: {', '.join(available)}"
            )
        return matching[0]

    if deck_index >= len(rows):
        raise ValueError(
            f"Deck index {deck_index} out of range — CSV has {len(rows)} deck(s)."
        )

    row = rows[deck_index]
    if len(rows) > 1:
        display = row.get("OwnerDisplayName") or row.get("OwnerUsername", "?")
        print(
            f"CSV contains {len(rows)} decks — using index {deck_index} ({display}). "
            f"Use --player or --index to select a different deck."
        )
    return row


def parse_melee_csv(path, player_name=None, deck_index=0):
    """
    Parse a Melee.gg CSV export and return a Deck object.

    Card IDs are resolved via the swu-db.com API. When a card appears in
    multiple sets, the first API result is used.

    Args:
        path: Path to the Melee.gg CSV file.
        player_name: OwnerDisplayName, OwnerUsername, or full name to filter by.
                     If None, deck_index is used instead.
        deck_index: 0-based row index when player_name is not given (default 0).

    Returns:
        Deck object ready for rendering.
    """
    # Read raw bytes to detect encoding issues
    with open(path, "rb") as f:
        raw = f.read()

    # Strip UTF-8 BOM if present
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]

    # Decode as UTF-8
    text = raw.decode("utf-8", errors="replace")

    # Repair double UTF-8 encoding: if text was UTF-8 encoded twice,
    # re-encoding as latin-1 gives back the original UTF-8 bytes
    try:
        repaired = text.encode("latin-1").decode("utf-8")
        # If that worked without error, it was double-encoded
        text = repaired
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass  # Not double-encoded, keep as-is

    import io
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    row = _select_row(rows, player_name=player_name, deck_index=deck_index)

    deck_name = row.get("Name", "")
    print(f"Parsing deck: {deck_name}")

    records_raw = row.get("Records", "[]")
    try:
        stripped = records_raw.strip()
        if stripped.startswith("["):
            records = json.loads(stripped)
        else:
            records = [json.loads(part.strip()) for part in stripped.split("|") if part.strip()]
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse Records field for deck '{deck_name}': {e}\n"
            f"Raw value (first 200 chars): {records_raw[:200]!r}"
        ) from e

    # Collect unique (name, subtitle) pairs to minimise API calls
    unique_cards = {}
    for rec in records:
        key = (rec["n"], rec.get("s"))
        unique_cards[key] = None

    # Check cache first
    cache = _load_cache()
    for key in unique_cards:
        name, subtitle = key
        cached = cache.get(_cache_key(name, subtitle))
        if cached:
            unique_cards[key] = cached

    # Resolve remaining card IDs from the API in parallel
    uncached = {k: v for k, v in unique_cards.items() if v is None}
    if uncached:
        print(f"Resolving {len(uncached)} card(s) via swu-db.com API ({len(unique_cards) - len(uncached)} cached)...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_lookup_card_id, name, subtitle): (name, subtitle)
                for name, subtitle in uncached
            }
            for future in as_completed(futures):
                key = futures[future]
                result = future.result()
                unique_cards[key] = result
                if result:
                    name, subtitle = key
                    cache[_cache_key(name, subtitle)] = result
        _save_cache(cache)
    else:
        print(f"All {len(unique_cards)} card(s) resolved from cache.")

    # Build Deck from records
    leaders, bases, main_deck, sideboard = [], [], [], []

    for rec in records:
        key = (rec["n"], rec.get("s"))
        card_id = unique_cards.get(key)
        if not card_id:
            subtitle_str = f" / {rec['s']}" if rec.get("s") else ""
            print(f"Skipping unresolved card: {rec['n']}{subtitle_str}")
            continue

        card = Card({"id": card_id, "count": rec["q"]})
        category = rec["c"]

        if category == 6:
            leaders.append(card)
        elif category == 7:
            bases.append(card)
        elif category == 0:
            main_deck.append(card)
        elif category == 99:
            sideboard.append(card)

    row_meta = {k: v for k, v in row.items() if k != "Records"}
    return Deck(leaders, bases, main_deck, sideboard, metadata={"name": deck_name, **row_meta})