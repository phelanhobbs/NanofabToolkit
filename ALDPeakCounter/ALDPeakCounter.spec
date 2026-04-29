block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/assets/icon.ico', 'src/assets'),
    ],
    hiddenimports=[
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends._backend_tk',
        'numpy',
        'scipy',
        'scipy.signal',
        'scipy.special._ufuncs_cxx',
        'scipy.linalg.cython_blas',
        'scipy.linalg.cython_lapack',
        'scipy.sparse.csgraph._validation',
    ],
    hookspath=['../pyinstaller/hooks'],
    runtime_hooks=['../pyinstaller/hooks/hook-runtime.py'],
    excludes=['PyQt5', 'PySide2', 'PySide6'],
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
    name='ALDPeakCounter',
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
    icon='src/assets/icon.ico',
)
