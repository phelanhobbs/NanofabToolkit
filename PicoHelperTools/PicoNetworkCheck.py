# ── WiFi credentials ──────────────────────────────────────────────────────────
SSID     = "ULink"
PASSWORD = "your_password_here"
# ─────────────────────────────────────────────────────────────────────────────

import network
import machine
import time

LED = machine.Pin("LED", machine.Pin.OUT)
LED.off()

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Connecting to", SSID, "...")

timeout = 20  # seconds to wait before giving up
start = time.time()

while not wlan.isconnected():
    if time.time() - start > timeout:
        print("✗ Connection timed out – chip may be damaged or credentials are wrong.")
        LED.off()
        break
    time.sleep(1)
    print("  waiting...")
else:
    ip, subnet, gateway, dns = wlan.ifconfig()
    print("✓ Connected!")
    print("  IP      :", ip)
    print("  Gateway :", gateway)
    print("  DNS     :", dns)
    # Blink LED 3 times to signal success
    for _ in range(3):
        LED.on()
        time.sleep(0.2)
        LED.off()
        time.sleep(0.2)
    LED.on()  # stay on = connected
