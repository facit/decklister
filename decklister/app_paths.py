"""
Shared utility for determining the application data directory.
"""
import os
import sys


APP_NAME = "DeckLister"


def get_app_data_dir():
    """
    Get the application data directory.

    - Bundled exe (Windows): %APPDATA%/DeckLister
    - Bundled exe (macOS): ~/Library/Application Support/DeckLister
    - Bundled exe (Linux): ~/.local/share/DeckLister
    - Development: project root (parent of the decklister package)

    The directory is created if it doesn't exist.
    """
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
        elif sys.platform == 'darwin':
            base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
        else:
            base = os.environ.get('XDG_DATA_HOME', os.path.join(os.path.expanduser('~'), '.local', 'share'))
        app_dir = os.path.join(base, APP_NAME)
    else:
        # Development — use project root
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_image_cache_dir():
    """Get the directory for cached card images."""
    img_dir = os.path.join(get_app_data_dir(), "images")
    os.makedirs(img_dir, exist_ok=True)
    return img_dir


def get_card_cache_path():
    """Get the path for the card name → ID cache file."""
    return os.path.join(get_app_data_dir(), "card_cache.json")
