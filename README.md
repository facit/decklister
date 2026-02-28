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
```

Optionally specify an output path:

```bash
py -m decklister my_deck.json my_config.json -o output.png
```

If no output path is given, files are auto-named `deck_output_1.png`, `deck_output_2.png`, etc.

## Project Structure

```
project/
├── README.md
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
│   ├── gui.py
│   ├── config_drawer.py
│   └── tests.py
```

## Deck Format

Two formats are supported. You can use either the **list format** or the **legacy format** for leaders and bases, but not both in the same file.

### List format

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

### Legacy format

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

## Config Format

```json
{
  "resolution": [1920, 1080],
  "background": "background.png",
  "foreground": "foreground.png",
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
| `background` | `string` or `[r, g, b]` | Dark gray | Path to a background image, or an RGB color. |
| `foreground` | `string` | None | Path to a foreground image (RGBA). Alpha-composited on top of everything at the end. |
| `leader_areas` | `[[x0,y0,x1,y1], ...]` | `[]` | Rectangles where leader cards are placed. Supports any number of leaders. |
| `base_areas` | `[[x0,y0,x1,y1], ...]` | `[]` | Rectangles where base cards are placed. Supports any number of bases. |
| `deck_area` | `[x0,y0,x1,y1]` | None | Rectangle where main deck cards are laid out in a grid. |
| `sb_area` | `[x0,y0,x1,y1]` | None | Rectangle where sideboard cards are laid out in a grid. |
| `count_background` | `string` | None | Path to an image (RGBA) placed behind each card's count number. |
| `uniform_card_size` | `bool` | `true` | If true, deck and sideboard cards use the same size (the smaller of the two). If false, each area is sized independently. |
| `padding` | `int` | `3` | Space in pixels between cards in the grid. |

All areas use the coordinate format `[x0, y0, x1, y1]` where `(x0, y0)` is the top-left corner and `(x1, y1)` is the bottom-right corner.

Leader and base cards are scaled to fit within their area while preserving their original aspect ratio, and centered within the area.

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
| `renderer.py` | Composes the final image: background → leaders → bases → deck grid → sideboard grid → foreground. |
| `count_overlay.py` | Draws the card count on each card. Pluggable strategy — subclass and override `apply()` to customize. |
| `config.py` | Loads and holds the JSON config. |
| `deck.py` | Parses deck JSON into Card/Deck objects. Supports both list and legacy formats. |
| `image_downloader.py` | Downloads card images from swudb.com. Handles portrait/landscape/back variants. |
| `gui.py` | PySide6 GUI — file pickers, generate button, config drawer launcher, and log output. |
| `config_drawer.py` | Standalone Tkinter tool for visually creating config files. |

## Running Tests

```bash
py -m pytest decklister/tests.py -v
```

Tests cover the card sizer (sizing, aspect ratio, fit validation) and deck parser (both formats, conflict detection, edge cases).
