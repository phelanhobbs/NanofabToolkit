# This is a PyInstaller hook file to help bundle SciPy correctly

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('scipy')
hiddenimports += collect_submodules('numpy')
datas = collect_data_files('scipy')
datas += collect_data_files('numpy')