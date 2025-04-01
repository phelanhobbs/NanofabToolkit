# Runtime hook to fix the 'NoneType' has no attribute 'write' error in numpy.f2py
import sys
import os

# Create dummy file-like objects for stdout and stderr
class DummyFile:
    def write(self, x): pass
    def flush(self): pass
    def read(self, *args, **kwargs): return ""
    def readline(self, *args, **kwargs): return ""
    def readlines(self, *args, **kwargs): return []

# Ensure stdout and stderr are not None before f2py is imported
if sys.stdout is None:
    sys.stdout = DummyFile()
if sys.stderr is None:
    sys.stderr = DummyFile()