from PyInstaller.utils.hooks import collect_all

# Collect all numpy.f2py package for proper inclusion
datas, binaries, hiddenimports = collect_all('numpy.f2py')