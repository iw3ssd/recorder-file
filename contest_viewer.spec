# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Contest Online ScoreBoard Viewer"""

a = Analysis(
    ['contest_viewer.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['requests', 'bs4', 'urllib3', 'charset_normalizer', 'certifi', 'idna', 'soupsieve'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ContestViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
