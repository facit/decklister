# Deck Image Generator

A tool for generating composite deck images for Star Wars Unlimited. Takes a JSON deck list and a JSON config, downloads card images, and renders a single PNG with all cards laid out in a grid — with leader cards, base cards, sideboard, card counts, and customizable backgrounds.

## Requirements

- Python 3.8+
- Internet connection (for downloading card images from swudb.com)

Install dependencies:

```bash
pip install -r requirements.txt
```

For development (testing):

```bash
pip install -r dev-requirements.txt
```

## Installation

### Option 1: pip install (recommended for Python users)

From the project root:

```bash
pip install .
```

This gives you two commands:

- `decklister` — launches the GUI
- `decklister-cli` — runs the CLI (e.g., `decklister-cli my_deck.json my_config.json -o output.png`)

### Option 2: Standalone executable (no Python required)

Build a standalone `.exe` (Windows) or `.app` (macOS):

```bash
pip install pyinstaller
python build.py
```

The output will be in the `dist/` folder:

- **Windows:** `dist/DeckLister.exe`
- **macOS:** `dist/DeckLister.app`

Use `python build.py --clean` to remove previous build artifacts before rebuilding.

## Quick Start

### GUI

Launch the GUI by running the module with no arguments:

```bash
py -m decklister
```

The GUI lets you pick your deck file, config file, and optional output path, then hit "Generate Image." It also has a button to launch the Config Drawer.

### CLI

```bash
py -m decklister my_deck.json my_config.json
py -m decklister my_deck.csv my_config.json
```

Optionally specify an output path:

```bash
py -m decklister my_deck.json my_config.json -o output.png
```

If no output path is given, files are auto-named `deck_output_1.png`, `deck_output_2.png`, etc.

#### CLI flags

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Output file path. Auto-named if omitted. |
| `--hyperspace` | Use hyperspace variant art for all cards. |
| `--showcase` | Use showcase variant art for leaders (overrides `--hyperspace` for leaders). |
| `--player NAME` | (CSV only) Select a deck by player name from a multi-deck CSV export. |
| `--index N` | (CSV only) Select a deck by 0-based index from a multi-deck CSV export (default: 0). |

## Project Structure

```
project/
├── README.md
├── swudb_api.md
├── requirements.txt
├── dev-requirements.txt
├── pyproject.toml
├── build.py
├── decklister.spec
├── icon_64.png
├── icon_256.png
├── icon.ico
├── example_background.png
├── example_foreground.png
├── example_count_background.png
├── example_config.json
├── decklister/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── deck.py
│   ├── card_sizer.py
│   ├── count_overlay.py
│   ├── renderer.py
│   ├── deck_image_generator.py
│   ├── image_downloader.py
│   ├── melee_csv_parser.py
│   ├── variant_resolver.py
│   ├── card_cache.json
│   ├── gui.py
│   ├── config_drawer.py
│   └── tests.py
```

## Deck Format

Three input formats are supported.

### JSON — list format

Allows any number of leaders or bases.

```json
{
  "metadata": {
    "name": "My Deck",
    "author": "Player"
  },
  "leaders": [
    { "id": "SHD_009", "count": 1 },
    { "id": "JTL_003", "count": 1 }
  ],
  "bases": [
    { "id": "SOR_030", "count": 1 }
  ],
  "deck": [
    { "id": "SEC_068", "count": 3 },
    { "id": "SOR_010", "count": 2 }
  ],
  "sideboard": [
    { "id": "SOR_045", "count": 1 }
  ]
}
```

### JSON — swudb format

The format used by deck exports from swudb.com.

```json
{
  "leader": { "id": "SHD_009", "count": 1 },
  "secondleader": { "id": "JTL_003", "count": 1 },
  "base": { "id": "SOR_030", "count": 1 },
  "deck": [
    { "id": "SEC_068", "count": 3 }
  ],
  "sideboard": []
}
```

Card IDs follow the format `SET_NUMBER` (e.g., `SHD_009`). The `count` field defaults to 1 if omitted.

### Melee.gg CSV format

Tournament CSV exports from [melee.gg](https://melee.gg). The file can contain decks from multiple players; use `--player` or `--index` to select which one.

```bash
py -m decklister tournament.csv my_config.json --player "PlayerName"
py -m decklister tournament.csv my_config.json --index 2
```

Card set and number are resolved automatically by looking up each card name (and subtitle where applicable) via the swudb.com API. Resolved lookups are cached locally in `decklister/card_cache.json` so subsequent runs don't repeat API calls.

## Config Format

```json
{
  "resolution": [1920, 1080],
  "layers": [
    "background.png",
    {"type": "cards"},
    "foreground.png"
  ],
  "leader_areas": [[90, 90, 390, 490]],
  "base_areas": [[90, 530, 390, 930]],
  "deck_area": [390, 90, 1870, 660],
  "sb_area": [390, 700, 1870, 1000],
  "count_background": "count_background.png",
  "uniform_card_size": true,
  "padding": 3
}
```

### Config fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `resolution` | `[w, h]` | `[1920, 1080]` | Output image resolution in pixels. |
| `layers` | array | `[{"type":"cards"}]` | Ordered list of layers drawn bottom to top. See [Layers](#layers) below. |
| `leader_areas` | `[[x0,y0,x1,y1], ...]` | `[]` | Rectangles where leader cards are placed. Supports any number of leaders. |
| `base_areas` | `[[x0,y0,x1,y1], ...]` | `[]` | Rectangles where base cards are placed. Supports any number of bases. |
| `deck_area` | `[x0,y0,x1,y1]` | None | Rectangle where main deck cards are laid out in a grid. |
| `sb_area` | `[x0,y0,x1,y1]` | None | Rectangle where sideboard cards are laid out in a grid. |
| `count_background` | `string` | None | Path to an image (RGBA) placed behind each card's count number. |
| `uniform_card_size` | `bool` | `true` | If true, deck and sideboard cards use the same size (the smaller of the two). If false, each area is sized independently. |
| `padding` | `int` | `3` | Space in pixels between cards in the grid. |

All areas use the coordinate format `[x0, y0, x1, y1]` where `(x0, y0)` is the top-left corner and `(x1, y1)` is the bottom-right corner.

Leader and base cards are scaled to fit within their area while preserving their original aspect ratio, and centered within the area.

### Layers

The `layers` array controls what is drawn and in what order. Each entry is drawn on top of the previous. There are three layer types:

#### Image layer

Draws an image file onto the canvas. If no `area` is given, the image is stretched to fill the entire canvas. If `area` is given, the image is stretched to fit that rectangle.

```json
"background.png"
```
```json
{"type": "image", "path": "logo.png", "area": [100, 100, 400, 300]}
```

A bare string is shorthand for a full-canvas image layer.

#### Color layer

Fills the canvas (or a rectangle) with a solid color. Useful for setting a background color or adding a colored overlay with transparency.

```json
[30, 30, 30]
```
```json
{"type": "color", "color": [0, 0, 0, 128]}
```

A bare `[r, g, b]` array is shorthand for a full-canvas color layer. A fourth value sets alpha (0–255).

#### Cards layer

Renders all card elements at this position in the stack: leaders, bases, the main deck grid, and the sideboard grid.

```json
{"type": "cards"}
```

There must be exactly one cards layer. Layers before it appear behind the cards; layers after it appear in front.

#### Example: background → cards → overlay

```json
"layers": [
  "stream_background.png",
  {"type": "cards"},
  {"type": "image", "path": "guest_overlay.png", "area": [1500, 0, 1920, 200]},
  "frame_foreground.png"
]
```

### Backwards compatibility

Old configs using `background` and `foreground` fields are still supported and are automatically converted to the layers format at load time.

## Config Drawer

A visual tool for drawing config areas on top of a background image:

```bash
py -m decklister.config_drawer
```

Requires `tkinter` (included with most Python installations). Load a background image, draw rectangles, name them, and export to JSON.

## Architecture

| Module | Purpose |
|--------|---------|
| `deck_image_generator.py` | Orchestrator — loads config/deck, downloads images, calculates sizes, renders, saves. |
| `card_sizer.py` | Pure math — calculates optimal card size and grid layout for a given area and card count. |
| `renderer.py` | Composes the final image by processing the `layers` list in order. |
| `count_overlay.py` | Draws the card count on each card. Pluggable strategy — subclass and override `apply()` to customize. |
| `config.py` | Loads and holds the JSON config. Converts old `background`/`foreground` fields to `layers` format automatically. |
| `deck.py` | Parses deck JSON into Card/Deck objects. Supports both list and swudb formats. |
| `melee_csv_parser.py` | Parses Melee.gg tournament CSV exports. Resolves card names to set/number via the swudb.com API, with a local cache. |
| `variant_resolver.py` | Resolves card numbers to their hyperspace or showcase variant equivalents. |
| `image_downloader.py` | Downloads card images from swudb.com. Handles portrait/landscape/back variants. |
| `gui.py` | PySide6 GUI — file pickers, generate button, config drawer launcher, and log output. |
| `config_drawer.py` | Standalone Tkinter tool for visually creating config files. |

## Running Tests

```bash
py -m pytest decklister/tests.py -v
```

Tests cover the card sizer (sizing, aspect ratio, fit validation) and deck parser (both formats, conflict detection, edge cases).
