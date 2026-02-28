#!/usr/bin/env python3
"""
Build script for creating standalone DeckLister executables.

Usage:
    python build.py          Build for the current platform
    python build.py --clean  Clean build artifacts first

Prerequisites:
    pip install pyinstaller
    pip install -r requirements.txt
"""

import subprocess
import sys
import shutil
import os


def clean():
    """Remove previous build artifacts."""
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"Removing {folder}/...")
            shutil.rmtree(folder)
    print("Clean complete.")


def build():
    """Run PyInstaller with the spec file."""
    print(f"Building for {sys.platform}...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "decklister.spec", "--noconfirm"],
        cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
    )
    if result.returncode == 0:
        print("\nBuild successful!")
        print(f"Output: dist/DeckLister{'.app' if sys.platform == 'darwin' else '.exe' if sys.platform == 'win32' else ''}")
    else:
        print("\nBuild failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    build()
