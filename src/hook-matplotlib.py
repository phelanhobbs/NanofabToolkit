from PyInstaller.utils.hooks import collect_submodules

# Only include necessary backends
hiddenimports = ['matplotlib.backends.backend_tkagg']

# Exclude unnecessary backends
excludedimports = ['matplotlib.backends.backend_qt5agg',
                  'matplotlib.backends.backend_qt4agg',
                  'matplotlib.backends.backend_cairo',
                  'matplotlib.backends.backend_gtk3cairo']