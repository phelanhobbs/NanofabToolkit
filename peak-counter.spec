# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all necessary packages
scipy_ret = collect_all('scipy')
numpy_ret = collect_all('numpy') 
matplotlib_ret = collect_all('matplotlib')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=scipy_ret[0] + numpy_ret[0] + matplotlib_ret[0],  # datas
    hiddenimports=scipy_ret[2] + numpy_ret[2] + matplotlib_ret[2] + [
        'matplotlib.backends.backend_tkagg',
    ],
    hookspath=['.'],  # Look for hooks in current directory
    hooksconfig={},
    runtime_hooks=['f2py_hook.py'],  # Add our runtime hook
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
    name='PeakCounter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)