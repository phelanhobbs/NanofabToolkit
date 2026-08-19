#!/usr/bin/env python3
"""Log a MicroPython Pico's USB-serial output to a timestamped file on THIS computer.

Any lab user can run this to capture whatever the Pico is printing -- sensor
readings, errors, reboots -- into a plain-text file they can open, grep, or share.
The Pico writes nothing to the computer itself; this script reads the USB serial
stream the Pico is already printing and saves it.

Usage:
    python3 pico_logger.py                       # auto-detect the Pico
    python3 pico_logger.py /dev/cu.usbmodem1101  # or name the port explicitly
    python3 pico_logger.py --list                # just list available serial ports

Stop with Ctrl-C. The file is written line-buffered, so it stays safe even if the
Pico is unplugged mid-run. If the Pico resets (e.g. watchdog reboot), the logger
waits and reconnects automatically, so reboot cycles get captured too.

Requires pyserial:   pip3 install pyserial

NOTE: close/disconnect Thonny first -- only one program can hold the serial port
at a time. Also, the Pico only produces output when it is actually printing, so
if the headless print-sink boot.py is enabled the log will be empty (disable it
while you want to capture data).
"""
import sys
import time
import datetime

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed -- run:  pip3 install pyserial")

BAUD = 115200
PICO_VID = 0x2E8A  # Raspberry Pi USB vendor id


def list_all():
    ports = list(list_ports.comports())
    if not ports:
        print("  (no serial ports found)")
    for p in ports:
        print("  %-24s %s" % (p.device, p.description))


def find_pico():
    for p in list_ports.comports():
        dev = p.device or ""
        if p.vid == PICO_VID or "usbmodem" in dev or "ACM" in dev:
            return p.device
    return None


def open_serial(port):
    """Block until the port opens (waits for the Pico to appear / reappear)."""
    while True:
        try:
            return serial.Serial(port, BAUD, timeout=1)
        except Exception:
            time.sleep(1)


def main():
    if "--list" in sys.argv:
        list_all()
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = args[0] if args else find_pico()
    if not port:
        print("No Pico found. Plug it in and close Thonny, or pass the port explicitly.")
        print("Serial ports seen:")
        list_all()
        sys.exit(1)

    logname = "pico_log_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print("Logging %s  ->  %s   (Ctrl-C to stop)" % (port, logname))

    with open(logname, "a", buffering=1) as f:
        f.write("# pico log started %s on %s\n" %
                (datetime.datetime.now().isoformat(), port))
        try:
            while True:
                ser = open_serial(port)
                try:
                    while True:
                        raw = ser.readline()
                        if not raw:
                            continue
                        text = raw.decode("utf-8", "replace").rstrip("\r\n")
                        line = "[%s] %s" % (
                            datetime.datetime.now().strftime("%H:%M:%S"), text)
                        print(line)
                        f.write(line + "\n")
                except (serial.SerialException, OSError):
                    note = "[%s] --- serial dropped (Pico reset/unplugged?), reconnecting ---" % \
                        datetime.datetime.now().strftime("%H:%M:%S")
                    print(note)
                    f.write(note + "\n")
                    try:
                        ser.close()
                    except Exception:
                        pass
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped. Saved to %s" % logname)


if __name__ == "__main__":
    main()
