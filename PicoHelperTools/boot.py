# boot.py — runs before main.py on every Pico W reset.
#
# Problem: when no USB host (terminal) is connected, MicroPython's USB CDC
# driver can block indefinitely once its 1 KB TX buffer fills up.  A single
# burst of safe_print() output is enough to fill it, stalling the program
# until the WDT fires.  The WDT reset repeats the same block → the device
# never gets past startup.  This does NOT happen when a terminal is attached
# because the host drains the buffer continuously.
#
# Fix: redirect sys.stdout and sys.stderr to a no-op sink so every write
# returns immediately without touching the USB hardware.
#
# TO DEBUG WITH A TERMINAL: comment out the three lines under "Headless mode"
# below, save this file to the Pico, then reconnect USB and reboot.  All
# safe_print() output will appear in the terminal as normal.

import sys

class _Sink:
    def write(self, s):
        return len(s) if isinstance(s, str) else len(s)
    def flush(self):
        pass

# ---- Headless mode ----
sys.stdout = _Sink()
sys.stderr = _Sink()
