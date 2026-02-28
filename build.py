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
    script_dir = os.path.dirname(os.path.abspath(__file__)) or "."
    spec_file = os.path.join(script_dir, "decklister.spec")

    print(f"Building for {sys.platform}...")
    print(f"Working directory: {script_dir}")
    print(f"Spec file: {spec_file}")

    # Verify key files exist
    for f in ["decklister/__main__.py", "icon_256.png", "example_background.png"]:
        full = os.path.join(script_dir, f)
        print(f"  {'✓' if os.path.exists(full) else '✗'} {f}")

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"],
        cwd=script_dir,
    )
    if result.returncode == 0:
        print("\nBuild successful!")
        if sys.platform == 'darwin':
            print("Output: dist/DeckLister.app")
        elif sys.platform == 'win32':
            print("Output: dist/DeckLister.exe")
        else:
            print("Output: dist/DeckLister")
    else:
        print("\nBuild failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    build()
