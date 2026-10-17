# -*- mode: python ; coding: utf-8 -*-
import os

spec_dir = os.path.dirname(os.path.abspath(SPEC)) if 'SPEC' in locals() else os.getcwd()
frontend_path = os.path.join(spec_dir, 'frontend')

a = Analysis(
    ['main.py'],
    pathex=[spec_dir],
    binaries=[],
    datas=[(frontend_path, 'frontend')],
    hiddenimports=['snap7', 'snap7.error', 'snap7.util', 'snap7.type', 'snap7.client', 'clr_loader', 'pythonnet', 'webview'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='RepoGen-S7',
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
