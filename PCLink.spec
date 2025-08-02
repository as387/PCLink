# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['PCLink.py'],
    pathex=[],
    binaries=[],
    datas=[('PCLink.ico', '.'), ('config.json', '.')],
    hiddenimports=['pystray.images'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PCLink',
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
    icon=['C:\\Users\\Саша\\Desktop 2\\python_projects\\удачные проекты\\PCLink\\PCLink.ico'],
)
