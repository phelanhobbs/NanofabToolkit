# MicroPython DHT22/AM2302 temperature & humidity sensor + API transmission
# for Raspberry Pi Pico W.  Sends readings to the /env-data API endpoint.
# Configured for headless (no USB terminal) operation.
#
# Wiring:
#   DHT22 pin 1 (VCC)  → 3.3V
#   DHT22 pin 2 (Data) → GPIO pin (DATA_PIN below) + 4.7 kΩ pull-up to 3.3V
#   DHT22 pin 3 (NC)   → not connected
#   DHT22 pin 4 (GND)  → GND
#
# NOTE: The server endpoint /env-data must be added to UNanofabTools/app/blueprints/api.py
# before data will be accepted.  See bottom of this file for the expected JSON schema.

import time
import ujson
import urequests
import network
import gc
import os
import machine
import dht
from machine import Pin, WDT

try:
    import ntptime
except ImportError:
    ntptime = None

# Module-level WDT reference so helpers can feed it without passing it around.
_wdt = None

# ===== Headless-safe print =====
def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        pass

def log_error(msg):
    """Append msg to error_log_dht.txt, capping at ~4 KB to avoid filling flash."""
    try:
        try:
            if os.stat("error_log_dht.txt")[6] > 4096:
                open_mode = "w"
            else:
                open_mode = "a"
        except OSError:
            open_mode = "a"
        with open("error_log_dht.txt", open_mode) as f:
            f.write(msg if msg.endswith("\n") else msg + "\n")
    except Exception:
        pass

# ===== Onboard LED =====
LED_PIN = Pin("LED", Pin.OUT)

# ===== User config =====
DATA_PIN = 2            # GPIO pin connected to DHT22 data line (GP2 by default)

MEASUREMENT_PERIOD_S = 30   # How often to take a reading (seconds; min 2 for DHT22)

# Scheduled sending: if True, send at fixed intervals (:00, :15, :30, :45, etc.)
# If False, send every MEASUREMENT_PERIOD_S.
SCHEDULED_SENDING = True
SEND_INTERVAL_MINUTES = 15  # Send every 15 minutes

# NTP / clock
TIME_SYNC_ENABLED = True
TIME_SYNC_INTERVAL_HOURS = 6
NTP_SERVERS = (
    "time.google.com",
    "pool.ntp.org",
    "time.nist.gov",
)

# WiFi credentials
WIFI_SSID = "ULink"
WIFI_PASSWORD = "u0919472632117"

# API endpoint — add /env-data route to the server before deploying
API_URL = "https://nfhistory.nanofab.utah.edu/env-data"

ROOM_NAME = "HEADLESS"   # Room/location label sent with every reading
SENSOR_NUMBER = "001"    # Unique sensor identifier

UTC_OFFSET_HOURS = -7    # MST = -7, MDT = -6

# MicroPython RP2040 epoch is 2000-01-01; server expects Unix epoch (1970-01-01).
MICROPYTHON_TO_UNIX_EPOCH = 946684800

# After this many consecutive send failures, reset the board.
MAX_CONSECUTIVE_FAILURES = 5

# Perform a full WiFi reset every 24 hours to clear CYW43 accumulated state.
WIFI_RESET_INTERVAL_MS = 24 * 3600 * 1000


# ===== Time helpers =====

def clock_looks_valid():
    try:
        return time.localtime()[0] >= 2024
    except Exception:
        return False


def format_time(timestamp):
    t = time.localtime(timestamp)
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5])


def sync_time_ntp(max_attempts_per_server=2):
    """Sync RTC from NTP. Returns True on success."""
    if not TIME_SYNC_ENABLED or ntptime is None:
        return False

    safe_print("Synchronizing time via NTP...")
    for server in NTP_SERVERS:
        for attempt in range(max_attempts_per_server):
            try:
                ntptime.host = server
                ntptime.settime()
                safe_print(f"NTP sync OK via {server}: {format_time(time.time())}")
                return True
            except Exception as e:
                safe_print(f"NTP failed ({server} attempt {attempt + 1}): {e}")
                time.sleep(1)
                if _wdt:
                    _wdt.feed()

    safe_print("NTP sync failed on all servers")
    return False


def calculate_next_send_time():
    """Return the Unix timestamp (local) of the next scheduled send slot."""
    current_utc   = time.time()
    current_local = current_utc + (UTC_OFFSET_HOURS * 3600)
    t = time.localtime(current_local)
    minutes_past  = t[4]
    seconds_past  = t[5]

    next_min = ((minutes_past // SEND_INTERVAL_MINUTES) + 1) * SEND_INTERVAL_MINUTES
    hour_start = current_local - minutes_past * 60 - seconds_past

    if next_min >= 60:
        return hour_start + 3600
    return hour_start + next_min * 60


# ===== WiFi helpers =====

def connect_wifi(max_attempts=3):
    """Connect to WiFi, feeding WDT throughout.  Returns True on success."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(1)

    status_names = {
        0: "IDLE", 1: "CONNECTING", 2: "WRONG_PASSWORD",
        3: "NO_AP_FOUND", 4: "CONNECT_FAIL", 5: "GOT_IP",
    }

    for attempt in range(max_attempts):
        if wlan.isconnected():
            safe_print(f"WiFi already connected. IP: {wlan.ifconfig()[0]}")
            return True
        try:
            wlan.disconnect()
        except Exception:
            pass
        time.sleep(1)

        safe_print(f"WiFi connect attempt {attempt + 1}/{max_attempts}…")
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as e:
            safe_print(f"connect() call failed: {e}")
            time.sleep(2)
            continue

        timeout = 20
        while timeout > 0 and not wlan.isconnected():
            time.sleep(1)
            timeout -= 1
            if _wdt:
                _wdt.feed()

        if wlan.isconnected():
            safe_print(f"WiFi connected. IP: {wlan.ifconfig()[0]}")
            return True
        else:
            st = wlan.status()
            safe_print(f"Attempt {attempt + 1} failed — status {st} ({status_names.get(st, '?')})")
            wlan.disconnect()
            time.sleep(2)

    safe_print("WiFi connect failed after all attempts")
    return False


def reset_wifi():
    """Full CYW43 teardown + reconnect.  Calls machine.reset() if reconnect fails."""
    safe_print("Performing scheduled WiFi reset…")
    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.disconnect()
    except Exception:
        pass
    wlan.active(False)
    time.sleep(2)
    if _wdt:
        _wdt.feed()
    wlan.active(True)
    time.sleep(1)
    if _wdt:
        _wdt.feed()
    if connect_wifi():
        safe_print("WiFi reset complete")
        return True
    safe_print("WiFi reset failed — triggering machine.reset()")
    machine.reset()


# ===== DHT22 reading =====

def read_dht22(sensor):
    """Call measure() and return (temperature_c, humidity_pct) or raise OSError."""
    sensor.measure()
    # DHT22 needs ≥2 s between reads; the caller is responsible for pacing.
    return sensor.temperature(), sensor.humidity()


# ===== API send =====

def send_to_api(temperature_c, humidity_pct):
    """POST temperature/humidity reading to the server.  Returns True on success."""
    response = None
    try:
        utc_timestamp = time.time() + MICROPYTHON_TO_UNIX_EPOCH

        payload = {
            "room_name":     ROOM_NAME,
            "sensor_number": SENSOR_NUMBER,
            "timestamp":     utc_timestamp,
            "temperature_c": temperature_c,
            "humidity_pct":  humidity_pct,
        }

        safe_print(f"Sending — temp: {temperature_c:.1f} °C  humidity: {humidity_pct:.1f} %")

        headers = {"Content-Type": "application/json"}
        response = urequests.post(
            API_URL,
            data=ujson.dumps(payload),
            headers=headers,
            timeout=7,
        )

        if response.status_code == 200:
            safe_print(f"API OK ({response.status_code})")
            return True
        else:
            msg = f"API error {response.status_code}"
            safe_print(msg)
            log_error(msg)
            return False

    except OSError as e:
        msg = f"send_to_api OSError: {e} (errno {e.errno})"
        safe_print(msg)
        log_error(msg)
        return False
    except Exception as e:
        msg = f"send_to_api Exception: {e}"
        safe_print(msg)
        log_error(msg)
        return False
    finally:
        if response:
            try:
                response.close()
            except Exception:
                pass
        if _wdt:
            _wdt.feed()


# ===== Main =====

def main():
    global _wdt

    safe_print("DHT22 sensor starting…")

    # Start watchdog — must be fed at least every ~8 s
    _wdt = WDT(timeout=8300)

    # Connect to WiFi; reset board if it fails
    if not connect_wifi():
        log_error("WiFi failed at startup — resetting")
        machine.reset()

    # Sync clock; continue without it if NTP is unreachable
    sync_time_ntp()
    last_time_sync = time.time()

    # Initialise the DHT22 sensor
    sensor = dht.DHT22(Pin(DATA_PIN))

    # Give sensor time to settle after power-on (first read can be bad)
    safe_print("Waiting for DHT22 to settle…")
    time.sleep(2)
    if _wdt:
        _wdt.feed()

    # Do a throwaway read to warm up the sensor
    try:
        sensor.measure()
    except Exception:
        pass
    time.sleep(2)
    if _wdt:
        _wdt.feed()

    # Determine first send time
    if SCHEDULED_SENDING and clock_looks_valid():
        next_send_local = calculate_next_send_time()
        safe_print(f"First send at: {format_time(next_send_local - UTC_OFFSET_HOURS * 3600 + UTC_OFFSET_HOURS * 3600)}")
    else:
        next_send_local = time.time() + UTC_OFFSET_HOURS * 3600  # send on first iteration

    consecutive_failures = 0
    last_wifi_reset_ticks = time.ticks_ms()
    last_read_time = 0  # enforce DHT22 2 s minimum between reads

    safe_print(f"Target API: {API_URL}")
    safe_print(f"Location:   {ROOM_NAME} / sensor {SENSOR_NUMBER}")

    while True:
        _wdt.feed()
        gc.collect()

        # Low-memory safety check
        if gc.mem_free() < 15000:
            log_error("Low memory — resetting")
            machine.reset()

        # Periodic WiFi reset
        if time.ticks_diff(time.ticks_ms(), last_wifi_reset_ticks) >= WIFI_RESET_INTERVAL_MS:
            reset_wifi()
            last_wifi_reset_ticks = time.ticks_ms()

        # Periodic NTP re-sync
        if TIME_SYNC_ENABLED:
            hours_since_sync = (time.time() - last_time_sync) / 3600
            if hours_since_sync >= TIME_SYNC_INTERVAL_HOURS:
                sync_time_ntp()
                last_time_sync = time.time()

        # Reconnect if WiFi dropped
        if not network.WLAN(network.STA_IF).isconnected():
            safe_print("WiFi lost — reconnecting…")
            if not connect_wifi():
                log_error("WiFi reconnect failed — resetting")
                machine.reset()

        # Read sensor (enforce 2 s minimum between reads)
        now = time.time()
        secs_since_read = now - last_read_time
        if secs_since_read < 2:
            time.sleep(2 - secs_since_read)
            _wdt.feed()

        try:
            temperature_c, humidity_pct = read_dht22(sensor)
            last_read_time = time.time()
            LED_PIN.on()
        except OSError as e:
            msg = f"DHT22 read error: {e}"
            safe_print(msg)
            log_error(msg)
            LED_PIN.off()
            time.sleep(2)
            _wdt.feed()
            continue

        LED_PIN.off()

        # Decide whether it is time to send
        current_local = time.time() + UTC_OFFSET_HOURS * 3600
        should_send = (
            not SCHEDULED_SENDING
            or not clock_looks_valid()
            or current_local >= next_send_local
        )

        if should_send:
            if send_to_api(temperature_c, humidity_pct):
                consecutive_failures = 0
                if SCHEDULED_SENDING and clock_looks_valid():
                    next_send_local = calculate_next_send_time()
            else:
                consecutive_failures += 1
                safe_print(f"Consecutive failures: {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    log_error(f"Too many failures ({consecutive_failures}) — resetting")
                    machine.reset()

        # Sleep until next measurement
        time.sleep(MEASUREMENT_PERIOD_S)
        _wdt.feed()


main()


# =============================================================================
# Expected JSON sent to POST /env-data:
# {
#   "room_name":     "HEADLESS",
#   "sensor_number": "001",
#   "timestamp":     1744300800,   # Unix timestamp (UTC)
#   "temperature_c": 22.5,
#   "humidity_pct":  45.3
# }
# =============================================================================
