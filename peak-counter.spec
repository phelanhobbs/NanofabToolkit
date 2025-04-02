# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all necessary packages
scipy_ret = collect_all('scipy')
numpy_ret = collect_all('numpy') 
matplotlib_ret = collect_all('matplotlib')

a = Analysis(
    ['main.py'],  # Change this to your actual main Python file
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['numpy.f2py', 'numpy.f2py.crackfortran', 'scipy.special.cython_special'],
    hookspath=[],  # Remove current directory from hook search path
    hooksconfig={},
    runtime_hooks=['./pyinstaller/hooks/hook-runtime.py'],
    excludes=['matplotlib.tests', 'numpy.tests', 'scipy.tests', 
              'PIL.ImageQt', 'PySide2', 'PyQt5', 'PyQt6', 'PySide6',
              'IPython', 'pandas', 'sphinx', 'jupyter', 'pytest',
              'matplotlib.backends.backend_qt5agg', 'matplotlib.backends.backend_qt4agg'
              'matplotlib.backends.backend_cairo', 'matplotlib.backends.backend_gtk3cairo',
              'scipy.signal.windows.multiprocess'
              'unittest', 'doctest', 'pdb', 'tkinter.test'
              'email', 'xmlrpc', 'pip', 'markupsafe'],
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
    strip=True,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'python3*.dll'],
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico',
    compress=True,
    lzma_compress=True,
)