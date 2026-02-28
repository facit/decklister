# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Deck Image Generator
#
# Build commands:
#   Windows:  pyinstaller decklister.spec
#   macOS:    pyinstaller decklister.spec
#
# Prerequisites:
#   pip install pyinstaller
#   pip install -r requirements.txt

import sys
import os

block_cipher = None

# Use SPECPATH (set by PyInstaller to the directory containing this spec file)
SPEC_DIR = SPECPATH

a = Analysis(
    [os.path.join(SPEC_DIR, 'decklister', '__main__.py')],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=[
        (os.path.join(SPEC_DIR, 'icon_256.png'), '.'),
        (os.path.join(SPEC_DIR, 'icon_64.png'), '.'),
        (os.path.join(SPEC_DIR, 'icon.ico'), '.'),
        (os.path.join(SPEC_DIR, 'example_background.png'), '.'),
        (os.path.join(SPEC_DIR, 'example_foreground.png'), '.'),
        (os.path.join(SPEC_DIR, 'example_count_background.png'), '.'),
        (os.path.join(SPEC_DIR, 'example_config.json'), '.'),
    ],
    hiddenimports=[
        'decklister',
        'decklister.gui',
        'decklister.deck_image_generator',
        'decklister.config',
        'decklister.deck',
        'decklister.card_sizer',
        'decklister.count_overlay',
        'decklister.renderer',
        'decklister.image_downloader',
        'decklister.config_drawer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DeckLister',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPEC_DIR, 'icon.ico') if sys.platform == 'win32' else os.path.join(SPEC_DIR, 'icon_256.png'),
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='DeckLister.app',
        icon=os.path.join(SPEC_DIR, 'icon_256.png'),
        bundle_identifier='com.decklister.app',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleName': 'DeckLister',
            'NSHighResolutionCapable': True,
        },
    )
