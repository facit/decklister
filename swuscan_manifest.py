"""
Card manifest builder for swu scan (a separate iOS app), not decklister itself.

Pages the official Star Wars: Unlimited admin API for the full card catalog
and writes a local card_manifest.json — the game's own images (see
decklister/image_downloader.py) has no use for this. Deliberately kept
outside the decklister package: decklister's normal deck-image flow must
never depend on building this catalog, and this file's own history (foil
detection, art-quality selection, rate limiting) is unrelated to decklister's
concerns.

Usage: python swuscan_manifest.py --all --dir <path>   (see bottom of file
for the full command list.)
"""
import os
import re
import sys
import json
import time
import shutil
import tempfile
import threading
import requests
from io import BytesIO
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit, parse_qs, unquote

from PIL import Image

try:
    from decklister.app_paths import get_image_cache_dir   # run from the project root (the norm here)
except ImportError:
    from app_paths import get_image_cache_dir              # decklister/ itself is on sys.path instead


API_BASE = "https://admin.starwarsunlimited.com/api"
CARD_LIST_ENDPOINT = f"{API_BASE}/card-list"

# The official API rejects requests without an Origin/Referer it recognizes.
API_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://starwarsunlimited.com",
    "Referer": "https://starwarsunlimited.com/",
}

MAX_WORKERS = 8          # concurrent image downloads
PAGE_SIZE = 25           # cards per API page (smaller = lighter payload, fewer timeouts)
REQUEST_TIMEOUT = 60     # seconds per HTTP request
MAX_RETRIES = 6          # attempts for a timed-out / 5xx page before giving up
INCLUDE_VARIANTS = True  # include hyperspace/showcase printings (their own high card numbers)
MANIFEST_FILENAME = "card_manifest.json"
PREVIOUS_MANIFEST_FILENAME = "card_manifest.prev.json"   # last version, before the most recent update
CHANGELOG_FILENAME = "manifest_changes.jsonl"            # append-only record of every applied update
SET_SETTINGS_FILENAME = "set_settings.json"   # optional per-set finish overrides

# If a single back-art URL is shared by more than this many cards, it's almost
# certainly a generic placeholder (not a real double-sided back), so we drop it.
# Real double-sided backs are unique per card, so this never trips on them.
PLACEHOLDER_BACK_THRESHOLD = 5

# Tokens are numbered in their own 1,2,3,... sequence that overlaps the main
# card numbering (so a token and a leader can both be "#1" in the same set).
# We prefix token stems with this so they never collide on key or filename.
TOKEN_PREFIX = "T"

# --------------------------------------------------------------------------- #
# Card art discovery.
#
# The public /cards page never downloads full-res art directly: images go
# through Next's optimizer (/_next/image?url=<encoded>&w=...&q=...), which
# downscales AND re-encodes as WebP regardless of the .png in the encoded
# URL. The real asset lives on cdn.starwarsunlimited.com, which is
# Strapi-backed: each upload gets a set of resized variants distinguished by
# a filename prefix, all sharing one trailing "_<hash>.<ext>". The prefixes
# in use (xxxsmall_/xxsmall_/thumbnail_/xsmall_/card_/small_/medium_, and no
# prefix for the original) aren't hardcoded anywhere below — variants are
# grouped purely by that trailing hash and the largest is picked by MEASURED
# pixel area, since file size doesn't reliably track resolution here (a more
# heavily-compressed original can be smaller than a resized-but-less-
# compressed "card" variant of nearly the same dimensions).
CDN_HOSTNAME = "cdn.starwarsunlimited.com"
NEXT_IMAGE_SUFFIX = "/_next/image"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
HASH_SUFFIX_RE = re.compile(r"_([0-9a-fA-F]{6,})\.(png|jpe?g|webp)$", re.IGNORECASE)

# Strapi format-name prefixes to drop outright rather than measure: "icon_"
# variants are unrelated UI badges (aspect/keyword/rarity icons, etc.), and
# leaders' "..._Leader_Unit_Thumbnail_..." asset is a 300x100 deck-list
# strip — never a candidate for "the" front or back face.
ICON_PREFIX = "icon_"
LEADER_UNIT_THUMBNAIL_MARKER = "leader_unit_thumbnail"
LEADER_UNIT_MARKER = "leader_unit"   # deployed leader face -> back

DIMENSION_CACHE_FILENAME = "image_dimensions_cache.json"   # url -> [width, height]

# Requests/second shared across every thread hitting the CDN — kept as two
# separate budgets because a dimension probe (a 24-byte Range read) costs
# the server almost nothing, while a full image download is real bandwidth.
# Both are still a single shared budget per kind, not one each: concurrency
# (MAX_WORKERS) must not translate into a burst against either.
CDN_PROBE_REQUESTS_PER_SECOND = 50
CDN_DOWNLOAD_REQUESTS_PER_SECOND = 20


class _RateLimiter:
    """Thread-safe pacing so every thread's CDN requests share ONE combined
    budget, not one budget each. Without this, MAX_WORKERS concurrent
    threads would each independently hammer the CDN at full speed."""

    def __init__(self, requests_per_second):
        self._interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self):
        if self._interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self._interval
        if delay > 0:
            time.sleep(delay)


_cdn_probe_limiter = _RateLimiter(CDN_PROBE_REQUESTS_PER_SECOND)
_cdn_download_limiter = _RateLimiter(CDN_DOWNLOAD_REQUESTS_PER_SECOND)


def _rate_limit_probe(url):
    """Pace a dimension-probe request (tiny — a 24-byte Range read)."""
    try:
        if urlsplit(url).hostname == CDN_HOSTNAME:
            _cdn_probe_limiter.wait()
    except ValueError:
        pass


def _rate_limit_download(url):
    """Pace a full-image download — real bandwidth, kept more conservative
    than the probe budget."""
    try:
        if urlsplit(url).hostname == CDN_HOSTNAME:
            _cdn_download_limiter.wait()
    except ValueError:
        pass


# Directory overrides. Precedence: explicit set_images_dir() call > environment
# variable > the app's default cache dir. The manifest (and set_settings.json)
# follow the image dir unless given their own override, so you can point images
# at a scratch/export location while still reusing the canonical manifest.
IMAGES_DIR_ENV = "DECKLISTER_IMAGE_DIR"
MANIFEST_DIR_ENV = "DECKLISTER_MANIFEST_DIR"

_IMAGES_DIR_OVERRIDE = None
_MANIFEST_DIR_OVERRIDE = None


def _expand(path):
    return os.path.abspath(os.path.expanduser(path)) if path else None


def _as_manifest_dir(path):
    """Normalise a manifest location to a directory.

    The option is a *directory*, but being handed .../card_manifest.json is the
    obvious mistake and would otherwise resolve to a nonexistent
    .../card_manifest.json/card_manifest.json — which reads as an empty cache
    (so every card looks new) and then blows up on write. Strip the filename.
    """
    path = _expand(path)
    if path and (os.path.basename(path) == MANIFEST_FILENAME or os.path.isfile(path)):
        return os.path.dirname(path)
    return path


def set_images_dir(path, manifest_dir=None):
    """Override where card images are written, for the rest of the process.

    path         - image root; None restores the default cache dir.
    manifest_dir - where card_manifest.json and set_settings.json live. None (the
                   default) makes them follow `path`; pass the canonical cache dir
                   to reuse the existing manifest while writing images elsewhere.

    Returns the resolved image directory.
    """
    global _IMAGES_DIR_OVERRIDE, _MANIFEST_DIR_OVERRIDE
    _IMAGES_DIR_OVERRIDE = _expand(path)
    _MANIFEST_DIR_OVERRIDE = _as_manifest_dir(manifest_dir)
    return _images_dir()


def _images_dir():
    """Base directory for card images."""
    return (_IMAGES_DIR_OVERRIDE
            or _expand(os.environ.get(IMAGES_DIR_ENV))
            or get_image_cache_dir())


def _manifest_dir():
    """Where card_manifest.json / set_settings.json live (images dir by default)."""
    return (_MANIFEST_DIR_OVERRIDE
            or _as_manifest_dir(os.environ.get(MANIFEST_DIR_ENV))
            or _images_dir())


def _manifest_path():
    return os.path.join(_manifest_dir(), MANIFEST_FILENAME)


def _load_set_settings():
    """Optional per-set finish overrides, e.g. {"J25": {"foil": "all"}}.

    Keyed by set code exactly as it appears in manifest keys (SOR, J25, ...). Recognised
    foil values: "all" (every card foil), "none" (every card non-foil), "user" (ask).
    An optional "_default" entry covers unlisted sets; without it they default to "user".
    Missing/unreadable file -> every set behaves as "user".
    """
    path = os.path.join(_manifest_dir(), SET_SETTINGS_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _dimension_cache_path():
    return os.path.join(_manifest_dir(), DIMENSION_CACHE_FILENAME)


def _load_dimension_cache():
    """url -> [width, height], so a manifest rebuild never re-probes an
    asset it already measured (on this machine or a prior run)."""
    try:
        with open(_dimension_cache_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_dimension_cache(cache):
    """Best-effort atomic write; a failure here shouldn't abort the build,
    it just means the next run re-probes what this one already measured."""
    directory = _manifest_dir()
    tmp_path = None
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".image_dims-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp_path, _dimension_cache_path())
    except OSError as e:
        print(f"Warning: could not save image-dimension cache: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _norm_number(card_number):
    """Match the existing filename convention: zero-pad numeric IDs to 3 digits.
    Non-numeric stems (e.g. an already-prefixed 'T001') pass through unchanged."""
    s = str(card_number)
    return s.zfill(3) if s.isdigit() else s


def _key(card_set, stem):
    """Stable lookup key, case-insensitive on the set code."""
    return f"{str(card_set).upper()}/{_norm_number(stem)}"


def _absolute(url):
    """Strapi media URLs are usually absolute (CDN), but fall back to the
    admin host if a relative path ever comes through."""
    if url and url.startswith("/"):
        return f"https://admin.starwarsunlimited.com{url}"
    return url


def _unwrap(node):
    """Strip the v4 `data`/`attributes` envelopes if present; on v5 (flattened)
    this is a no-op."""
    node = (node or {}).get("data", node) or {}
    return node.get("attributes", node) or {}


def _unwrap_next_image_url(url):
    """/cards renders art through Next's image optimizer
    (/_next/image?url=<percent-encoded>&w=...&q=...), which downscales AND
    re-encodes as WebP regardless of the extension in the encoded URL. If
    this is one of those, return the real CDN URL underneath; otherwise
    return the URL unchanged."""
    parsed = urlsplit(url)
    if not parsed.path.endswith(NEXT_IMAGE_SUFFIX):
        return url
    inner = parse_qs(parsed.query).get("url", [None])[0]
    return unquote(inner) if inner else url


def _normalize_cdn_url(url):
    """Collapse a doubled slash right after the host (some CDN URLs in the
    API response have one) so the same image doesn't produce two different
    cache keys / manifest entries."""
    return re.sub(r"^(https?://[^/]+)/+", r"\1/", url)


def _looks_like_image_url(value):
    """A real URL/path, not a bare filename.

    Strapi media objects carry both a "name" (the original uploaded
    filename, e.g. "xxsmall_SWH01_005_Luke Skywalker_Thumbnail.png" — no
    host, no path, nothing to fetch) and a "url" (the actual servable
    path). Both end in an image extension, so the extension check alone
    can't tell them apart; requiring a "/" does, since every real URL or
    relative path has at least one and a bare filename never does.
    """
    path = value.split("?", 1)[0].split("#", 1)[0]
    if "/" not in path:
        return False
    return path.lower().endswith(IMAGE_EXTENSIONS)


def _iter_image_urls(node):
    """Recursively yield every image URL found anywhere inside `node`.

    Deliberately schema-agnostic: rather than trusting specific field names
    (artFront/artBack) or a hardcoded list of Strapi format names, this
    walks the WHOLE record and lets filename patterns (hash suffix, role
    markers) do the sorting downstream. That's what survives a JSON shape
    we haven't fully mapped, or fields the admin API adds/renames later.
    """
    if isinstance(node, dict):
        for v in node.values():
            yield from _iter_image_urls(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_image_urls(v)
    elif isinstance(node, str):
        resolved = _normalize_cdn_url(_absolute(_unwrap_next_image_url(node)))
        if _looks_like_image_url(resolved):
            yield resolved


def _is_excluded_candidate(url):
    """Drop UI-badge icons and the leader deck-list thumbnail strip — never
    real candidates for a card's front or back face art."""
    name = os.path.basename(urlsplit(url).path).lower()
    return name.startswith(ICON_PREFIX) or LEADER_UNIT_THUMBNAIL_MARKER in name


def _group_candidates_by_hash(urls):
    """Group same-image size variants by their shared trailing
    "_<hash>.<ext>" rather than by any assumed prefix list — a URL with no
    recognizable hash suffix just becomes its own singleton group."""
    groups = defaultdict(list)
    for url in urls:
        m = HASH_SUFFIX_RE.search(url)
        key = m.group(1).lower() if m else url
        groups[key].append(url)
    return groups


def _png_dimensions_from_header(data):
    """Parse width/height from a PNG's IHDR chunk (bytes 16:24 of the
    file). Returns None if `data` isn't recognizably a PNG — the caller
    falls back to a full download for anything else (WebP/JPEG)."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return (width, height)


_dim_cache_lock = threading.Lock()


def _probe_dimensions(session, url, dim_cache):
    """Measure an image's pixel dimensions without downloading it in full.

    A 24-byte Range request is enough for a PNG (see _png_dimensions_from_header);
    that covers every asset on this CDN in practice, so the full-download
    fallback (via Pillow) only exists for a format that never showed up in
    what we've seen. Results are cached on disk by URL so a repeat manifest
    build never re-probes the same asset, and every CDN hit — probe or full
    download alike — goes through the shared rate limiter. Called from a
    thread pool (see _probe_all), so the cache dict itself is guarded by a
    lock — cheap, since each probe holds it only long enough to read or
    write one entry.
    """
    with _dim_cache_lock:
        cached = dim_cache.get(url)
    if cached is not None:
        return tuple(cached)

    _rate_limit_probe(url)
    try:
        resp = session.get(url, headers={"Range": "bytes=0-23"}, timeout=REQUEST_TIMEOUT)
        if resp.status_code not in (200, 206):
            return None
        dims = _png_dimensions_from_header(resp.content)
        if dims is None:
            _rate_limit_download(url)   # full fallback fetch — real bandwidth this time
            full = session.get(url, timeout=REQUEST_TIMEOUT)
            full.raise_for_status()
            with Image.open(BytesIO(full.content)) as im:
                dims = im.size
    except Exception as e:
        print(f"  Warning: could not measure {url}: {e}")
        return None

    with _dim_cache_lock:
        dim_cache[url] = list(dims)
    return dims


def _probe_all(pool, session, urls, dim_cache):
    """Measure every URL in `urls` concurrently on `pool`, regardless of
    which hash-group each belongs to, and return {url: dims-or-None}.

    Submitting a card's ENTIRE candidate pool at once — front group and
    back group together — matters as much as the concurrency itself: two
    groups measured one after another still stacks two full rounds of
    waiting, even though the shared rate limiter has room to interleave
    them. One batch means one round of waiting per card, not one per face.
    """
    futures = {pool.submit(_probe_dimensions, session, url, dim_cache): url for url in urls}
    results = {}
    for future in as_completed(futures):
        results[futures[future]] = future.result()
    return results


def _pick_best(urls, dims_by_url):
    """From same-hash size variants of one image (already measured — see
    _probe_all), return the (url, dims) with the largest pixel area. Never
    infers "the original" from an absence of known prefix — file size
    doesn't reliably track resolution here, so every candidate is measured
    rather than assumed."""
    best_url, best_dims, best_area = None, None, -1
    for url in urls:
        dims = dims_by_url.get(url)
        if dims is None:
            continue
        area = dims[0] * dims[1]
        if area > best_area:
            best_url, best_dims, best_area = url, dims, area
    if best_url is None:
        # Every probe failed (network hiccup, unrecognized format) — keep
        # some URL rather than dropping the card's art entirely.
        best_url = urls[0]
    return best_url, best_dims


def _extract_card_art(attrs, pool, session, dim_cache):
    """Find this card's front/back art by scanning its ENTIRE record for
    image URLs — not specific fields, not a known format-prefix list.
    Same-hash size variants are grouped and reduced to the largest by
    measured pixel area; role (front vs. back) comes from the
    "..._Leader_Unit_..." filename marker (the deployed/back face),
    defaulting to front otherwise — the only signal that survives
    regardless of how the surrounding JSON happens to be shaped.

    Returns (front_url, front_dims, back_url, back_dims); any of these can
    be None (no front means no usable art at all for this card).
    """
    candidates = {u for u in _iter_image_urls(attrs) if not _is_excluded_candidate(u)}
    if not candidates:
        return None, None, None, None

    groups = _group_candidates_by_hash(candidates)
    dims_by_url = _probe_all(pool, session, candidates, dim_cache)

    best = {"front": (None, None, -1), "back": (None, None, -1)}
    for urls in groups.values():
        url, dims = _pick_best(urls, dims_by_url)
        area = (dims[0] * dims[1]) if dims else 0
        name = os.path.basename(urlsplit(url).path).lower()
        role = "back" if LEADER_UNIT_MARKER in name else "front"
        if area > best[role][2]:
            best[role] = (url, dims, area)

    front_url, front_dims, _ = best["front"]
    back_url, back_dims, _ = best["back"]
    return front_url, front_dims, back_url, back_dims


def _card_type(attributes):
    """Card type name, e.g. 'Leader', 'Base', 'Unit', 'Token'."""
    return _unwrap(attributes.get("type")).get("name") or attributes.get("type")


def _is_token(type_name):
    """A token is anything whose type name mentions 'token'. Matches 'Token',
    'Base Token', 'Unit Token', etc."""
    return "token" in (type_name or "").lower()


def _rel_list(node):
    """Related records as a list of attribute dicts, handling both the v4
    `{data: [{attributes: {...}}]}` shape and the v5 flattened `[{...}]` list."""
    data = (node or {}).get("data", node)
    if data is None:
        return []
    if isinstance(data, dict):          # a single relation where a list is expected
        data = [data]
    return [item.get("attributes", item) for item in data if isinstance(item, dict)]


def _names(node):
    """The 'name' of each related record (e.g. aspects -> ['Vigilance', 'Heroism'])."""
    return [a.get("name") for a in _rel_list(node) if a.get("name")]


def _resolve_foil(vt_foil, set_code, set_settings):
    """Resolve finish into (foil, foil_determined).

    foil            - is THIS printing a foil? (default shown until proven otherwise)
    foil_determined - is the finish FIXED by the printing identity (set+number), so there is no
                      other option? If False, the same number sells in both finishes and the
                      scan/user must decide. (A clearer name would be `foil_fixed`.)

    Priority:
      1. variantTypes[].foil == True -> a foil printing. Foils get their own card number, so the
         finish is fixed -> (True, True).
      2. A per-set rule from set_settings.json ("all"/"none") pins the whole set's finish.
      3. Otherwise NOT fixed -> (False, False). Note: variantTypes[].foil == False only means "this
         variant type is the non-foil one"; it does NOT mean the number is non-foil-only. Standard
         cards sell in both finishes at the same number, so False must NOT be coerced to determined.
         The authoritative fixed/loose signal comes later from the Cardmarket price guide (a number
         with only a foil price, or only a non-foil price, is fixed).
    """
    if vt_foil is True:
        return True, True
    rule = (set_settings.get((set_code or "").upper())
            or set_settings.get("_default") or {}).get("foil", "user")
    if rule == "all":
        return True, True
    if rule == "none":
        return False, True
    return False, False


def _extract_meta(attrs, set_code, set_settings):
    """Catalog/identification metadata added to each manifest entry.

    Everything here either identifies the card or is visible on it (so it can later serve
    as a confirmation signal). Notes on two fields that look like data but aren't:
      * variant_label - variantTypes[].name is FREE-FORM human text ("Hyperspace",
        "Weekly Play", "Gift Box", "Judge Program", ...). Display it to confirm the match;
        never branch on it. None when absent rather than a fabricated "Standard".
      * foil / foil_determined - see _resolve_foil. The treatment booleans (hyperspace/
        showcase) and hasFoil are deliberately NOT stored: they're either unreliable or
        can't represent the open-ended set of real treatments.
    """
    vts = _rel_list(attrs.get("variantTypes"))
    vt = vts[0] if vts else {}                     # always exactly one in practice
    foil, foil_determined = _resolve_foil(vt.get("foil"), set_code, set_settings)
    arenas = _names(attrs.get("arenas"))           # a unit has at most one; null otherwise
    rarity = _unwrap(attrs.get("rarity"))
    return {
        "name": attrs.get("title"),
        "subtitle": (attrs.get("subtitle") or None),   # normalise "" -> None for clean grouping
        "variant_label": vt.get("name"),               # display-only; free-form; may be None
        "foil": foil,
        "foil_determined": foil_determined,
        "rarity": rarity.get("name"),
        "cost": attrs.get("cost"),
        "hp": attrs.get("hp"),
        "power": attrs.get("power"),
        "aspects": _names(attrs.get("aspects")),
        "traits": _names(attrs.get("traits")),
        "arena": (arenas[0] if arenas else None),
        "keywords": _names(attrs.get("keywords")),
    }


def _get_with_retries(session, url, **kwargs):
    """GET with exponential backoff for transient failures (timeouts, dropped
    connections, 5xx). Client errors (4xx) are raised immediately since a retry
    won't help."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code < 500:
                raise
            last_err = e
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            last_err = e
        if attempt < MAX_RETRIES:
            wait = min(2 ** (attempt - 1), 30)   # 1s, 2s, 4s, 8s, 16s, 30s...
            print(f"  network issue (attempt {attempt}/{MAX_RETRIES}); "
                  f"retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


def _report_progress(processed, total, start_time):
    """Show that card processing is still alive.

    Tracked per CARD, not per page: each card can trigger several
    rate-limited CDN probe requests (see _extract_card_art), so a single
    page's processing time now varies a lot — a page of leaders can take
    far longer than a page of ordinary units. Per-page granularity could
    leave the terminal silent for a long stretch with no visible sign of
    life; per-card granularity means something prints for every single
    card, however fast or slow the page around it is.

    On a terminal this redraws a single progress line; piped or redirected
    output instead gets an occasional plain line, so a log file doesn't
    fill up with thousands of near-duplicate rows.
    """
    total = total or processed or 1
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0
    eta = (total - processed) / rate if rate > 0 else 0
    done = processed >= total

    if sys.stdout.isatty():
        width = 30
        filled = min(width, int(width * processed / total)) if total else width
        bar = "#" * filled + "-" * (width - filled)
        sys.stdout.write(f"\r  [{bar}] {processed}/{total} card(s)  eta {eta:.0f}s   ")
        sys.stdout.flush()
        if done:
            sys.stdout.write("\n")
            sys.stdout.flush()
    else:
        step = max(1, total // 40)   # ~40 updates over the whole run
        if done or processed % step == 0:
            print(f"  {processed}/{total} card(s)  eta {eta:.0f}s")


def _fetch_manifest_from_api():
    """Page through the official card-list API and build a lookup of
    "SET/STEM" -> {"front", "back", "width", "height", "type", "serial",
    "double_sided"}.

    Tokens get a "T"-prefixed stem so their overlapping 1,2,3 numbering doesn't
    collide with leaders/cards of the same number. Double-sidedness is decided
    by back-art presence (the same signal the official UI uses to allow a flip),
    so leaders today and any future double-sided type are picked up automatically.

    Front/back art is the largest MEASURED variant found anywhere in each
    card's record (see _extract_card_art) — not a guess based on field names
    or a known Strapi format list. Dimension probes are cached to disk
    (dim_cache) and persisted periodically, so an interrupted build doesn't
    lose that work, and a rebuild never re-probes an asset it already
    measured.
    """
    collected = []          # one record per kept card, before key disambiguation
    back_counts = Counter()
    set_settings = _load_set_settings()
    session = requests.Session()
    session.headers.update(API_HEADERS)
    dim_cache = _load_dimension_cache()

    page = 1
    total_pages = None
    total_cards = None
    processed = 0
    start_time = time.time()
    pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)   # shared across every card's dimension probes
    try:
        while True:
            params = {
                "locale": "en",
                "pagination[page]": page,
                "pagination[pageSize]": PAGE_SIZE,
                "populate": "*",
            }
            if not INCLUDE_VARIANTS:
                # Restrict to base cards only (drops hyperspace/showcase printings).
                params["filters[variantOf][id][$null]"] = "true"
            resp = _get_with_retries(session, CARD_LIST_ENDPOINT, params=params)
            data = resp.json()

            pagination = data.get("meta", {}).get("pagination", {})
            if total_pages is None:
                total_pages = pagination.get("pageCount", 1)
                total_cards = pagination.get("total") or (total_pages * PAGE_SIZE)
                print(f"Building card manifest: {pagination.get('total', '?')} "
                      f"cards across {total_pages} page(s)...")

            for entry in data.get("data", []):
                processed += 1
                _report_progress(processed, total_cards, start_time)

                attrs = entry.get("attributes", entry)  # v5 falls back to entry itself
                number = attrs.get("cardNumber")
                expansion = _unwrap(attrs.get("expansion"))
                set_code = expansion.get("code")
                if not set_code or number is None:
                    continue

                front, front_dims, back, back_dims = _extract_card_art(attrs, pool, session, dim_cache)
                if not front:
                    continue
                if back and back != front:           # ignore a back that just echoes the front
                    back_counts[back] += 1
                else:
                    back, back_dims = None, None

                type_name = _card_type(attrs)
                # Tokens live in a separate "T"-prefixed namespace.
                stem = _norm_number(number)
                if _is_token(type_name):
                    stem = f"{TOKEN_PREFIX}{stem}"

                collected.append({
                    "attrs": attrs,
                    "set_code": set_code,
                    "stem": stem,
                    "front": front,
                    "back": back,
                    "front_dims": front_dims,
                    "back_dims": back_dims,
                    "type": type_name,
                    "serial": attrs.get("serialCode"),
                    # variantOf is set on hyperspace/showcase/reprint records, null on base cards.
                    "is_variant": bool(_unwrap(attrs.get("variantOf"))),
                    "card_count": attrs.get("cardCount"),    # the printed "/M"; identifies the logical set
                })

            if page % 20 == 0:
                _save_dimension_cache(dim_cache)   # checkpoint — this build can take a while

            if page >= total_pages:
                break
            page += 1
    finally:
        pool.shutdown(wait=True)   # let any in-flight probes finish before saving what they found
        _save_dimension_cache(dim_cache)   # keep whatever we measured even on an early exit

    return _build_manifest(collected, back_counts, set_settings)


def _build_manifest(collected, back_counts, set_settings):
    """Turn collected card records into the final manifest, disambiguating keys.

    A set code can cover more than one logical set: pre-JTL weekly-play promos were folded into a
    base set's code (e.g. "SHD") but carry their OWN, smaller cardCount and reuse low numbers, so
    they collide with — and were silently dropped against — the base card of the same number. The
    fix: a set's BASE printing is its largest cardCount; any card sharing the code with a SMALLER
    cardCount is such a promo and gets a count-qualified synthetic set code ("SHD-20"), so it
    keeps its own entry. The bare code is reserved for the base, which is what an ordinary lookup
    (and a no-total card like a P25 promo, already its own set) resolves to.
    """
    # Each set's base size = its largest *positive* cardCount. A 0 (or null) is the API's
    # placeholder for "no usable total" (it shows up on some non-standard treatments), NOT a
    # distinct set — so it must never count toward the base nor trigger a synthetic code.
    set_counts = defaultdict(set)
    for c in collected:
        if c["card_count"]:                       # truthy skips both None and 0
            set_counts[c["set_code"]].add(c["card_count"])
    base_count = {code: max(counts) for code, counts in set_counts.items() if counts}

    def effective_code(set_code, card_count):
        base = base_count.get(set_code)
        if not card_count or base is None or card_count == base:
            return set_code                       # no usable count, or the base -> bare code
        return f"{set_code}-{card_count}"         # folded-in promo -> count-qualified code

    raw = {}
    for c in collected:
        eff = effective_code(c["set_code"], c["card_count"])
        key = _key(eff, c["stem"])

        if key in raw:
            if c["is_variant"]:
                # A variant reusing an existing number WITHIN the same logical set (deployed
                # leader-unit, same-number reprint, ...). Real hyperspace/showcase printings have
                # unique high numbers and don't land here; folded promos now have their own code
                # and don't either. Skip quietly.
                continue
            if raw[key].get("_variant"):
                pass  # this is a base card; let it overwrite the stored variant
            elif c["serial"]:
                # base vs base: a genuine, unexpected clash — keep both via serial.
                prev_type = raw[key]["type"]
                key = _key(eff, f'{c["stem"]}-{c["serial"]}')
                print(f"Warning: base-card collision on {eff}/{c['stem']} "
                      f"({prev_type} vs {c['type']}); stored second as {key}.")
            else:
                continue

        front_w, front_h = c["front_dims"] or (None, None)
        back_w, back_h = c["back_dims"] or (None, None)
        raw[key] = {
            "front": c["front"],
            "back": c["back"],
            "width": front_w,
            "height": front_h,
            "back_width": back_w,
            "back_height": back_h,
            "type": c["type"],
            "serial": c["serial"],
            "_variant": c["is_variant"],
            "card_count": c["card_count"],
            # foil rules key on the effective code, so a promo subset can carry its own rule.
            **_extract_meta(c["attrs"], eff, set_settings),
        }

    # Identify generic/placeholder backs shared across many cards and drop them.
    placeholders = {url for url, n in back_counts.items()
                    if n > PLACEHOLDER_BACK_THRESHOLD}
    if placeholders:
        print(f"Ignoring {len(placeholders)} shared placeholder back image(s).")

    manifest = {}
    for key, rec in raw.items():
        back = rec["back"] if rec["back"] not in placeholders else None
        rec = dict(rec)                       # copy so all captured fields carry through
        rec.pop("_variant", None)             # internal-only flag, not part of the manifest
        rec["back"] = back
        rec["double_sided"] = back is not None
        if back is None:
            rec["back_width"] = None
            rec["back_height"] = None
        manifest[key] = rec
    return manifest


def _load_cached_manifest():
    """Read the on-disk manifest without ever touching the network.

    Returns (cards, built_at); (None, None) when the file is missing, corrupt or
    empty. Use this — not get_card_manifest — when the *absence* of a cache is
    itself meaningful (as in the new-card check)."""
    try:
        with open(_manifest_path(), "r", encoding="utf-8") as f:
            cached = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None, None
    cards = cached.get("cards")
    if not isinstance(cards, dict) or not cards:
        return None, None
    return cards, cached.get("built_at")


def _previous_manifest_path():
    return os.path.join(_manifest_dir(), PREVIOUS_MANIFEST_FILENAME)


def _changelog_path():
    return os.path.join(_manifest_dir(), CHANGELOG_FILENAME)


def _save_manifest(cards, keep_previous=True):
    """Write the manifest cache atomically. Returns True on success.

    Same path, full replace — but via a temp file in the same directory plus
    os.replace(), so an interrupted write can't leave a truncated manifest
    behind. That matters because a corrupt manifest reads as "no cache", which
    silently turns the next run into a full rebuild and re-download.

    keep_previous copies the outgoing manifest to card_manifest.prev.json first,
    so the version you just replaced is always recoverable and any diff against
    it can be recomputed later.
    """
    directory = _manifest_dir()
    tmp_path = None
    try:
        os.makedirs(directory, exist_ok=True)
        if keep_previous and os.path.isfile(_manifest_path()):
            shutil.copy2(_manifest_path(), _previous_manifest_path())
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".card_manifest-",
                                        suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"built_at": time.time(), "cards": cards}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, _manifest_path())   # atomic on POSIX and Windows
        return True
    except OSError as e:
        print(f"Warning: could not cache manifest: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False


def get_card_manifest(force_refresh=False):
    """Return the "SET/STEM" -> card-info lookup, cached on disk.

    The official site has no guessable per-card image path, so we fetch the
    card list once and reuse it. Pass force_refresh=True to rebuild (e.g.
    after a new set releases)."""
    if not force_refresh:
        cards, _ = _load_cached_manifest()
        if cards:
            return cards

    cards = _fetch_manifest_from_api()
    _save_manifest(cards)
    return cards


# --------------------------------------------------------------------------- #
# What's new?  (live API vs. the cached card_manifest.json)
# --------------------------------------------------------------------------- #

# Fields whose change invalidates already-downloaded artwork. "double_sided" is
# derived from "back", so it lives here too rather than showing up as metadata noise.
# width/height/back_width/back_height are derived from front/back too, but track
# them explicitly since a re-measurement (bugfix, new Strapi variant) can change
# the chosen resolution without the URL itself changing.
ART_FIELDS = ("front", "back", "double_sided", "width", "height", "back_width", "back_height")

# Order isn't meaningful for these, so compare them as sets to avoid phantom diffs
# when the API returns the same related records in a different order.
UNORDERED_FIELDS = ("aspects", "traits", "keywords")


def _comparable(field, value):
    """Normalise a field value so equality means 'same data', not 'same JSON'."""
    if field in UNORDERED_FIELDS and isinstance(value, list):
        return tuple(sorted(str(v) for v in value))
    return value


def diff_manifests(old, new):
    """Compare two "SET/STEM" -> record manifests.

    Returns:
      added        - sorted keys present only in `new`
      removed      - sorted keys present only in `old` (usually a sign the API
                     reshuffled keys — e.g. a promo gaining its own set code —
                     rather than a card genuinely disappearing)
      art_changed  - {key: {field: (old, new)}} for ART_FIELDS; these need a re-download
      meta_changed - {key: {field: (old, new)}} for everything else; manifest-only update
      new_sets     - sorted set codes that appear only in `new`
    """
    old, new = old or {}, new or {}
    old_keys, new_keys = set(old), set(new)

    art_changed, meta_changed = {}, {}
    for key in sorted(old_keys & new_keys):
        o, n = old[key], new[key]
        deltas = {
            f: (o.get(f), n.get(f))
            for f in sorted(set(o) | set(n))
            if _comparable(f, o.get(f)) != _comparable(f, n.get(f))
        }
        art = {f: v for f, v in deltas.items() if f in ART_FIELDS}
        meta = {f: v for f, v in deltas.items() if f not in ART_FIELDS}
        if art:
            art_changed[key] = art
        if meta:
            meta_changed[key] = meta

    added = sorted(new_keys - old_keys)
    return {
        "added": added,
        "removed": sorted(old_keys - new_keys),
        "art_changed": art_changed,
        "meta_changed": meta_changed,
        "new_sets": sorted({k.split("/", 1)[0] for k in added}
                           - {k.split("/", 1)[0] for k in old_keys}),
    }


def _write_change_log(diff, old, new, old_built_at=None):
    """Append one JSON line describing an applied update. Returns True if written.

    The console report is truncated for readability; this is the complete record.
    Removed entries are stored in FULL (not just their keys) — the manifest write
    is a whole-file replace, so this log is the only surviving copy of anything
    the API stopped returning.
    """
    if not any(diff.get(k) for k in ("added", "removed", "art_changed", "meta_changed")):
        return False

    # With no prior manifest every card is "added", which isn't a change — logging
    # full records there would duplicate the entire manifest into a single line.
    initial = not old
    now = time.time()
    record = {
        "at": now,
        "at_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "initial": initial,
        "previous_built_at": old_built_at,
        "counts": {
            "old": len(old), "new": len(new),
            "added": len(diff["added"]), "removed": len(diff["removed"]),
            "art_changed": len(diff["art_changed"]),
            "meta_changed": len(diff["meta_changed"]),
        },
        "new_sets": diff["new_sets"],
        "added": {} if initial else {key: new[key] for key in diff["added"]},
        "removed": {key: old[key] for key in diff["removed"]},
        "art_changed": diff["art_changed"],
        "meta_changed": diff["meta_changed"],
    }
    if initial:
        record["note"] = ("initial build — added entries omitted; "
                          "they are the manifest itself")
    try:
        os.makedirs(_manifest_dir(), exist_ok=True)
        with open(_changelog_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        return True
    except OSError as e:
        print(f"Warning: could not write change log: {e}")
        return False


def read_change_log(limit=None):
    """Return change-log records, oldest first. limit keeps only the last N.

    Unparseable lines are skipped rather than fatal — a truncated final line
    from a killed process shouldn't cost you the whole history.
    """
    try:
        with open(_changelog_path(), "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (FileNotFoundError, OSError):
        return []

    records = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records[-limit:] if limit else records


def show_change_history(limit=5, detail=False):
    """Print past manifest updates, most recent last."""
    records = read_change_log(limit=limit)
    if not records:
        print(f"No change log yet ({_changelog_path()}).")
        return records

    for rec in records:
        c = rec.get("counts", {})
        tag = "  [initial build]" if rec.get("initial") else ""
        print(f"\n{rec.get('at_iso', '?')}  "
              f"{c.get('old', '?')} -> {c.get('new', '?')} cards  "
              f"(+{c.get('added', 0)} added, -{c.get('removed', 0)} removed, "
              f"{c.get('art_changed', 0)} art, {c.get('meta_changed', 0)} meta){tag}")
        if rec.get("new_sets"):
            print(f"  new set(s): {', '.join(rec['new_sets'])}")
        if not detail:
            continue
        for key, entry in (rec.get("added") or {}).items():
            print(f"  + {key}  {entry.get('name') or '?'}")
        for key, entry in (rec.get("removed") or {}).items():
            print(f"  - {key}  {entry.get('name') or '?'}")
        for key, fields in (rec.get("art_changed") or {}).items():
            print(f"  ~ {key}  art: {', '.join(fields)}")
        for key, fields in (rec.get("meta_changed") or {}).items():
            deltas = ", ".join(f"{f}: {o!r} -> {n!r}" for f, (o, n) in fields.items())
            print(f"  ~ {key}  {deltas}")
    return records


def _describe(manifest, key):
    """One-line human label for a manifest key, for report output."""
    rec = manifest.get(key) or {}
    name = rec.get("name") or "?"
    bits = [b for b in (rec.get("subtitle"), rec.get("variant_label")) if b]
    suffix = f" ({', '.join(bits)})" if bits else ""
    return f"{key}  {name}{suffix}"


def _print_diff(diff, new_manifest, old_manifest, built_at, sample=10):
    """Print a readable summary of diff_manifests() output."""
    if built_at:
        age_h = (time.time() - built_at) / 3600
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(built_at))
        print(f"Cached manifest built {stamp} ({age_h:.1f}h ago), "
              f"{len(old_manifest)} card(s).")
    print(f"Live API: {len(new_manifest)} card(s).")

    if diff["new_sets"]:
        print(f"\nNew set code(s): {', '.join(diff['new_sets'])}")

    added = diff["added"]
    if added:
        per_set = Counter(k.split("/", 1)[0] for k in added)
        print(f"\n{len(added)} new card(s):")
        for code, n in sorted(per_set.items()):
            print(f"  {code}: {n}")
        for key in added[:sample]:
            print(f"    + {_describe(new_manifest, key)}")
        if len(added) > sample:
            print(f"    ... and {len(added) - sample} more")

    if diff["art_changed"]:
        print(f"\n{len(diff['art_changed'])} card(s) with changed artwork "
              f"(not downloaded; refresh manually if wanted):")
        for key in list(diff["art_changed"])[:sample]:
            print(f"    ~ {_describe(new_manifest, key)} "
                  f"[{', '.join(diff['art_changed'][key])}]")

    if diff["meta_changed"]:
        print(f"\n{len(diff['meta_changed'])} card(s) with changed metadata only.")
        for key in list(diff["meta_changed"])[:sample]:
            fields = ", ".join(f"{f}: {o!r} -> {n!r}"
                               for f, (o, n) in diff["meta_changed"][key].items())
            print(f"    ~ {key}  {fields}")

    if diff["removed"]:
        print(f"\n{len(diff['removed'])} key(s) no longer in the API "
              f"(likely re-keyed, not deleted):")
        for key in diff["removed"][:sample]:
            print(f"    - {_describe(old_manifest, key)}")

    if not any(diff[k] for k in ("added", "art_changed", "meta_changed", "removed")):
        print("\nNothing new — the cached manifest is up to date.")


def check_for_new_cards(update=False, download=False, report=True, sample=10,
                        log=True):
    """Fetch a fresh manifest from the API and diff it against card_manifest.json.

    update   - overwrite the cached manifest with the fresh one
    download - fetch images for NEW cards only (implies update, so the cache never
               claims images we didn't get). Cards whose artwork changed are
               reported but left alone; refresh those deliberately with
               download_manifest_keys(diff["art_changed"], diff["manifest"],
               refresh=True).
    log      - when the manifest is written, append the full diff to
               manifest_changes.jsonl and keep the outgoing manifest as
               card_manifest.prev.json. The console report is truncated; the log
               is complete, and it holds the only copy of removed entries.

    Returns the diff dict from diff_manifests(); the fresh manifest is available
    under the "manifest" key.
    """
    old, built_at = _load_cached_manifest()
    if old is None:
        print("No usable cached manifest — every card will look new.")
        old = {}

    new = _fetch_manifest_from_api()
    diff = diff_manifests(old, new)
    diff["manifest"] = new

    if report:
        _print_diff(diff, new, old, built_at, sample=sample)

    if download:
        # New cards only — changed artwork is reported, never silently replaced.
        if diff["added"]:
            download_manifest_keys(diff["added"], new)
        else:
            print("\nNo new cards to download.")
        update = True

    if update:
        if _save_manifest(new):
            if log and _write_change_log(diff, old, new, built_at):
                print(f"\nChange log: {_changelog_path()}")
                print(f"Previous manifest kept at: {_previous_manifest_path()}")

    return diff


def download_manifest_keys(keys, manifest, refresh=False):
    """Download images for explicit "SET/STEM" manifest keys.

    refresh=True deletes any existing front/back file first, so changed artwork
    actually replaces the stale image instead of being skipped as 'already present'.
    """
    keys = [k for k in keys if k in manifest]
    if not keys:
        return

    for key in keys:
        card_set, stem = key.split("/", 1)
        output_dir = os.path.join(_images_dir(), card_set)
        os.makedirs(output_dir, exist_ok=True)
        if refresh:
            for path in (os.path.join(output_dir, f"{stem}.png"),
                         os.path.join(output_dir, f"{stem}-back.png")):
                try:
                    os.remove(path)
                except OSError:
                    pass

    print(f"{'Re-downloading' if refresh else 'Downloading'} "
          f"{len(keys)} card image(s)...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for key in keys:
            card_set, stem = key.split("/", 1)
            futures[executor.submit(
                download_card, card_set, stem,
                os.path.join(_images_dir(), card_set), manifest)] = key
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error downloading {futures[future]}: {e}")


def download_card(card_set, card_number, output_dir, manifest=None):
    """Download a single card's front image, plus its back image if the card is
    double-sided (saved as "<stem>-back.png").

    `card_number` is the stem used in the manifest: a plain number for normal
    cards ("1" -> "001.png") or a token stem ("T001" -> "T001.png").

    `manifest` is optional for backward compatibility; if omitted it's loaded
    on demand (inefficient in a loop — prefer passing one in).

    Returns 1 if the front was downloaded, 0 if already present, -1 if not
    found / failed.
    """
    if manifest is None:
        manifest = get_card_manifest()

    stem = _norm_number(card_number)
    entry = manifest.get(_key(card_set, stem))
    if not entry:
        print(f"{card_set} #{stem} not found in card manifest.")
        return -1

    front_path = os.path.join(output_dir, f"{stem}.png")
    back_url = entry.get("back")
    back_path = os.path.join(output_dir, f"{stem}-back.png")

    # Front face.
    result = 0
    if not os.path.isfile(front_path):
        print(f"Downloading {card_set} #{stem}...")
        try:
            _rate_limit_download(entry["front"])
            resp = requests.get(entry["front"], headers=API_HEADERS,
                                allow_redirects=True, timeout=30)
            resp.raise_for_status()
            with open(front_path, "wb") as f:
                f.write(resp.content)
            result = 1
        except Exception as e:
            print(f"Failed to download {card_set} #{stem}: {e}")
            return -1

    # Back face — only for double-sided cards (leaders today, anything the API
    # gives back art to in the future).
    if back_url and not os.path.isfile(back_path):
        try:
            _rate_limit_download(back_url)
            resp = requests.get(back_url, headers=API_HEADERS,
                                allow_redirects=True, timeout=30)
            resp.raise_for_status()
            with open(back_path, "wb") as f:
                f.write(resp.content)
        except Exception as e:
            print(f"Failed to download back of {card_set} #{stem}: {e}")

    return result


def _missing_from_disk(cards):
    """Return the subset whose front image isn't already saved."""
    missing = []
    for card_set, card_number in cards:
        front = os.path.join(_images_dir(), str(card_set),
                             f"{_norm_number(card_number)}.png")
        if not os.path.isfile(front):
            missing.append((card_set, card_number))
    return missing


def download_images_batch(cards):
    """Download images for a list of (card_set, card_number) tuples concurrently."""
    to_download = _missing_from_disk(list(set(cards)))
    if not to_download:
        return

    try:
        manifest = get_card_manifest()
    except Exception as e:
        print(f"Could not load card manifest: {e}")
        return

    # Cards absent from the manifest usually mean it's stale (new set dropped).
    # Refresh once and retry; if the refresh fails, keep using what we have.
    if any(_key(c[0], c[1]) not in manifest for c in to_download):
        try:
            manifest = get_card_manifest(force_refresh=True)
        except Exception as e:
            print(f"Could not refresh manifest ({e}); using cached data.")

    for card_set, _ in to_download:
        os.makedirs(os.path.join(_images_dir(), str(card_set)), exist_ok=True)

    print(f"Downloading {len(to_download)} card image(s)...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                download_card, card_set, card_number,
                os.path.join(_images_dir(), str(card_set)), manifest
            ): (card_set, card_number)
            for card_set, card_number in to_download
        }
        for future in as_completed(futures):
            card_set, card_number = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error downloading {card_set} #{card_number}: {e}")


def download_images(card_set, card_number=None):
    """Download one card, or every card in a set.

    With the official API we know exactly which cards exist, so the whole-set
    case filters the manifest instead of probing numbers until a 404.
    """
    if not card_set:
        print("No card set specified.")
        return

    output_dir = os.path.join(_images_dir(), card_set)
    os.makedirs(output_dir, exist_ok=True)

    try:
        manifest = get_card_manifest()
    except Exception as e:
        print(f"Could not load card manifest: {e}")
        return

    if card_number is not None:
        download_card(card_set, card_number, output_dir, manifest)
        return

    prefix = f"{card_set.upper()}/"
    set_keys = [k for k in manifest if k.startswith(prefix)]
    if not set_keys:
        print(f"No cards found for set '{card_set}'. Is the set code correct?")
        return

    print(f"Downloading {len(set_keys)} card(s) for {card_set}...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(download_card, card_set,
                            key.split("/", 1)[1], output_dir, manifest)
            for key in set_keys
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error: {e}")


def download_all_images():
    """Download every card image in every set the manifest knows about.

    Already-downloaded files are skipped, so this is also a safe way to top up
    after a new set releases (it will fetch a fresh manifest if cards are
    missing on the next batch/set call; pass force-refresh via get_card_manifest
    if you want to rebuild explicitly)."""
    try:
        manifest = get_card_manifest()
    except Exception as e:
        print(f"Could not load card manifest: {e}")
        return

    sets = {key.split("/", 1)[0] for key in manifest}
    for card_set in sets:
        os.makedirs(os.path.join(_images_dir(), card_set), exist_ok=True)

    print(f"Downloading {len(manifest)} card image(s) across {len(sets)} set(s)...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for key in manifest:
            card_set, stem = key.split("/", 1)
            output_dir = os.path.join(_images_dir(), card_set)
            futures[executor.submit(download_card, card_set, stem,
                                    output_dir, manifest)] = key
        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error downloading {key}: {e}")
    print("Done.")


def _extract_option(args, names):
    """Pull `--opt VALUE` or `--opt=VALUE` out of an argv list.

    Returns (value, remaining_args). Raises ValueError if the flag is present
    with no value. Last occurrence wins.
    """
    value, rest, i = None, [], 0
    while i < len(args):
        arg = args[i]
        matched = next((n for n in names if arg == n or arg.startswith(n + "=")), None)
        if matched is None:
            rest.append(arg)
        elif "=" in arg:
            value = arg.split("=", 1)[1]
        elif i + 1 < len(args):
            value = args[i + 1]
            i += 1
        else:
            raise ValueError(f"{matched} needs a directory path")
        i += 1
    return value, rest


if __name__ == "__main__":
    import sys
    try:
        images_dir, args = _extract_option(sys.argv[1:], ("--dir", "-o", "--output"))
        manifest_dir, args = _extract_option(args, ("--manifest-dir",))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if images_dir or manifest_dir:
        set_images_dir(images_dir, manifest_dir)
        print(f"Images:   {_images_dir()}")
        print(f"Manifest: {_manifest_path()}")

    flags = {a for a in args if a.startswith("-")}
    positional = [a for a in args if not a.startswith("-")]

    CHECK_VERBS = {"--check", "-c", "check", "--new"}
    UPDATE_FLAGS = {"--update", "-u"}
    DOWNLOAD_FLAGS = {"--download", "-d"}
    HISTORY_VERBS = {"--history", "--log"}

    if args and args[0] in HISTORY_VERBS:
        limit = next((int(a) for a in positional if a.isdigit()), 5)
        show_change_history(limit=limit,
                            detail="--detail" in flags or "-v" in flags)
    # --update / --download imply the check, so `--download` on its own works.
    elif args and args[0] in CHECK_VERBS | UPDATE_FLAGS | DOWNLOAD_FLAGS:
        check_for_new_cards(update=bool(flags & UPDATE_FLAGS),
                            download=bool(flags & DOWNLOAD_FLAGS))
    elif args and args[0] in ("--all", "-a", "all"):
        download_all_images()
    elif positional:
        download_images(positional[0],
                        positional[1] if len(positional) > 1 else None)
    else:
        print("Usage:")
        print("  python swuscan_manifest.py <card_set> [<card_number>]")
        print("  python swuscan_manifest.py --all")
        print("  python swuscan_manifest.py --check      # report only")
        print("  python swuscan_manifest.py --update     # report + save manifest")
        print("  python swuscan_manifest.py --download   # + fetch new cards")
        print("  python swuscan_manifest.py --history [N] [--detail]")
        print("")
        print("Options (any command):")
        print("  --dir PATH            image root (default: app cache dir)")
        print("  --manifest-dir PATH   where card_manifest.json lives "
              "(default: --dir)")
        sys.exit(1)
