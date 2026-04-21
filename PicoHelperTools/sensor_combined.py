# MicroPython combined SPS30 (particle) + DHT22 (temperature/humidity) sensor
# driver + API transmission for Raspberry Pi Pico W.
# Sends both datasets to the /sensor-data API endpoint in a single JSON request.
# Configured for headless (no USB terminal) operation.
#
# Wiring:
#   SPS30 (I2C):
#     SDA  → GP4  (I2C0 SDA)
#     SCL  → GP5  (I2C0 SCL)
#     VCC  → 5V (VBUS)
#     GND  → GND
#     SEL  → GND (selects I2C mode)
#
#   DHT22 (3-pin module with built-in pull-up):
#     VCC  → 3V3
#     S    → GP2 + 4.7 kΩ pull-up to 3V3
#     GND  → GND
#
# NOTE: The server endpoint /sensor-data must be added to
# UNanofabTools/app/blueprints/api.py before data will be accepted.

import time
import struct
import ujson
import urequests
import network
import gc
import os
import machine
import dht
from machine import I2C, Pin, WDT

try:
    import socket
except ImportError:
    socket = None

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
    """Append msg to error_log.txt, capping at ~4 KB to avoid filling flash."""
    try:
        try:
            if os.stat("error_log.txt")[6] > 4096:
                open_mode = "w"
            else:
                open_mode = "a"
        except OSError:
            open_mode = "a"
        with open("error_log.txt", open_mode) as f:
            f.write(msg if msg.endswith("\n") else msg + "\n")
    except Exception:
        pass


def sleep_with_wdt(total_seconds, step_seconds=1):
    """Sleep in short chunks so the watchdog can be fed during long waits."""
    end_ticks = time.ticks_add(time.ticks_ms(), int(total_seconds * 1000))
    while time.ticks_diff(end_ticks, time.ticks_ms()) > 0:
        remaining_ms = time.ticks_diff(end_ticks, time.ticks_ms())
        sleep_ms = min(int(step_seconds * 1000), remaining_ms)
        time.sleep_ms(sleep_ms)
        if _wdt:
            _wdt.feed()


# ===== Onboard LED =====
LED_PIN = Pin("LED", Pin.OUT)


# ===== User config =====

# SPS30 particle sensor (I2C)
I2C_ID = 0
SDA_PIN = 4         # GP4 for I2C0
SCL_PIN = 5         # GP5 for I2C0
SPS30_ADDR = 0x69   # SPS30 default I2C address

# DHT22 temperature/humidity sensor
DHT_PIN = 2         # GP2

# Timing
MEASUREMENT_PERIOD_S = 15   # Read sensors every 15 seconds
SCHEDULED_SENDING = True
SEND_INTERVAL_MINUTES = 15  # Send at :00, :15, :30, :45

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

# API endpoint — combined sensor data
API_URL = "https://nfhistory.nanofab.utah.edu/sensor-data"
API_HOST = "nfhistory.nanofab.utah.edu"
DNS_RECOVERY_RETRIES = 2

ROOM_NAME = "COMBINED"      # Room/location label
SENSOR_NUMBER = "011"        # Unique sensor identifier

UTC_OFFSET_HOURS = -7        # MST = -7, MDT = -6

# Conversion factor from #/cm³ to #/ft³
CM3_TO_FT3 = 28316.8

# MicroPython RP2040 epoch is 2000-01-01; server expects Unix epoch (1970-01-01).
MICROPYTHON_TO_UNIX_EPOCH = 946684800

MAX_CONSECUTIVE_FAILURES = 5
WIFI_RESET_INTERVAL_MS = 24 * 3600 * 1000  # full WiFi reset every 24 hours
HTTP_TIMEOUT_S = 5
HTTP_SEND_RETRIES = 2
ENABLE_WATCHDOG = False
WDT_TIMEOUT_MS = 8000
WDT_MAX_TIMEOUT_MS = 8388


# ===== SPS30 I2C driver =====

PTR_START_MEAS = 0x0010
PTR_STOP_MEAS  = 0x0104
PTR_DATA_RDY   = 0x0202
PTR_READ_VALUES = 0x0300


def _crc8_word(b0, b1):
    crc = 0xFF
    for byte in (b0, b1):
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if (crc & 0x80) else ((crc << 1) & 0xFF)
    return crc


class SPS30:
    def __init__(self, i2c, addr=SPS30_ADDR):
        self.i2c = i2c
        self.addr = addr

    def _write_ptr(self, ptr):
        self.i2c.writeto(self.addr, bytes([(ptr >> 8) & 0xFF, ptr & 0xFF]))

    def _write_ptr_with_data(self, ptr, payload):
        self.i2c.writeto(self.addr, bytes([(ptr >> 8) & 0xFF, ptr & 0xFF]) + payload)

    def start_measurement_float(self):
        try:
            b0, b1 = 0x03, 0x00
            crc = _crc8_word(b0, b1)
            self._write_ptr_with_data(PTR_START_MEAS, bytes([b0, b1, crc]))
        except OSError as e:
            safe_print(f"SPS30 start_measurement failed: {e}")
            raise

    def stop_measurement(self):
        self._write_ptr(PTR_STOP_MEAS)

    def read_data_ready(self):
        self._write_ptr(PTR_DATA_RDY)
        data = self.i2c.readfrom(self.addr, 3)
        if _crc8_word(data[0], data[1]) != data[2]:
            return False
        return data[1] == 0x01

    def read_measured_values_float(self):
        """Returns list of 10 floats:
        [mass_PM1, mass_PM2_5, mass_PM4, mass_PM10,
         num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, typical_particle_size_um]"""
        self._write_ptr(PTR_READ_VALUES)
        raw = self.i2c.readfrom(self.addr, 60)
        vals = []
        for i in range(10):
            base = i * 6
            hi0, hi1, crc1, lo0, lo1, crc2 = raw[base:base + 6]
            if _crc8_word(hi0, hi1) != crc1 or _crc8_word(lo0, lo1) != crc2:
                raise ValueError("CRC error on float index {}".format(i))
            fbytes = bytes([hi0, hi1, lo0, lo1])
            vals.append(struct.unpack('>f', fbytes)[0])
        return vals


# ===== Time helpers =====

def clock_looks_valid():
    try:
        return time.localtime()[0] >= 2024
    except Exception:
        return False


def format_local_time(timestamp):
    t = time.localtime(timestamp)
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5])


def sync_time_ntp(max_attempts_per_server=2):
    if not TIME_SYNC_ENABLED or ntptime is None:
        return False
    safe_print("Synchronizing time via NTP...")
    for server in NTP_SERVERS:
        for attempt in range(max_attempts_per_server):
            try:
                ntptime.host = server
                ntptime.settime()
                safe_print(f"NTP sync OK via {server}: {format_local_time(time.time())}")
                return True
            except Exception as e:
                safe_print(f"NTP failed ({server} attempt {attempt + 1}): {e}")
                time.sleep(1)
                if _wdt:
                    _wdt.feed()
    safe_print("NTP sync failed on all servers")
    return False


def calculate_next_send_time():
    current_utc = time.time()
    current_local = current_utc + (UTC_OFFSET_HOURS * 3600)
    t = time.localtime(current_local)
    minutes_past = t[4]
    seconds_past = t[5]
    next_min = ((minutes_past // SEND_INTERVAL_MINUTES) + 1) * SEND_INTERVAL_MINUTES
    hour_start = current_local - minutes_past * 60 - seconds_past
    if next_min >= 60:
        return hour_start + 3600
    return hour_start + next_min * 60


# ===== WiFi helpers =====

def connect_wifi(max_attempts=3):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(1)
    if _wdt:
        _wdt.feed()

    status_names = {
        0: "IDLE", 1: "CONNECTING", 2: "WRONG_PASSWORD",
        3: "NO_AP_FOUND", 4: "CONNECT_FAIL", 5: "GOT_IP",
    }

    for attempt in range(max_attempts):
        if wlan.isconnected():
            safe_print(f"WiFi connected. IP: {wlan.ifconfig()[0]}")
            return True
        try:
            wlan.disconnect()
        except Exception:
            pass
        time.sleep(1)
        if _wdt:
            _wdt.feed()

        safe_print(f"WiFi attempt {attempt + 1}/{max_attempts}...")
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as e:
            safe_print(f"connect() failed: {e}")
            time.sleep(2)
            if _wdt:
                _wdt.feed()
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
            if _wdt:
                _wdt.feed()

    safe_print("WiFi connect failed")
    return False


def reset_wifi():
    """Full CYW43 teardown + reconnect. Calls machine.reset() if reconnect fails."""
    safe_print("Performing scheduled WiFi reset...")
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
    safe_print("WiFi reset failed — resetting board")
    machine.reset()


# ===== DHT22 reading =====

def read_dht22(sensor):
    """Call measure() and return (temperature_c, humidity_pct) or raise OSError."""
    sensor.measure()
    return sensor.temperature(), sensor.humidity()


def check_api_dns():
    """Resolve the API host and return True if DNS lookup succeeds."""
    if socket is None:
        return True

    wlan = network.WLAN(network.STA_IF)

    for attempt in range(DNS_RECOVERY_RETRIES + 1):
        try:
            info = socket.getaddrinfo(API_HOST, 443)
            if info:
                safe_print("API DNS resolved: {}".format(info[0][4][0]))
            return True
        except Exception as e:
            msg = "API DNS lookup failed for {}: {}".format(API_HOST, e)
            safe_print(msg)
            log_error(msg)

            if attempt >= DNS_RECOVERY_RETRIES:
                break

            safe_print("DNS recovery {}/{}: reconnecting WiFi...".format(
                attempt + 1, DNS_RECOVERY_RETRIES
            ))

            try:
                if wlan.isconnected():
                    safe_print("WiFi config: {}".format(wlan.ifconfig()))
                wlan.disconnect()
            except Exception:
                pass

            sleep_with_wdt(2)
            connect_wifi(max_attempts=1)
            sleep_with_wdt(1)

    return False


def is_timeout_oserror(err):
    """Return True for ETIMEDOUT-like OSError variants used by MicroPython."""
    try:
        if err.args and err.args[0] == 110:
            return True
    except Exception:
        pass
    return "ETIMEDOUT" in str(err)


class NoopWDT:
    def feed(self):
        pass


def create_watchdog():
    if not ENABLE_WATCHDOG:
        safe_print("Watchdog disabled (ENABLE_WATCHDOG=False)")
        return NoopWDT()

    requested_timeout = WDT_TIMEOUT_MS
    timeout_ms = min(requested_timeout, WDT_MAX_TIMEOUT_MS)
    if timeout_ms != requested_timeout:
        safe_print(
            "Requested WDT timeout {}ms exceeds RP2040 max {}ms; using {}ms".format(
                requested_timeout, WDT_MAX_TIMEOUT_MS, timeout_ms
            )
        )
    try:
        return WDT(timeout=timeout_ms)
    except Exception as e:
        safe_print("WDT init failed ({}); continuing without watchdog".format(e))
        log_error("WDT init failed: {}".format(e))
        return NoopWDT()


# ===== Combined API send =====

def send_to_api(particle_vals, temperature_c, humidity_pct):
    """POST combined particle + environmental data to the server. Returns True on success."""
    response = None
    try:
        if not check_api_dns():
            return False

        utc_timestamp = time.time() + MICROPYTHON_TO_UNIX_EPOCH
        local_timestamp = utc_timestamp + (UTC_OFFSET_HOURS * 3600)

        data = {
            "room_name": ROOM_NAME,
            "sensor_number": SENSOR_NUMBER,
            "timestamp": local_timestamp,
        }

        # Environmental data (may be None if DHT22 read failed)
        if temperature_c is not None:
            data["temperature_c"] = round(temperature_c, 1)
            data["humidity_pct"] = round(humidity_pct, 1)

        # Particle data
        if particle_vals is not None:
            mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
                num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = particle_vals

            # Convert number concentrations from #/cm³ to #/ft³
            num_PM0_5_ft3 = num_PM0_5 * CM3_TO_FT3
            num_PM1_ft3 = num_PM1 * CM3_TO_FT3
            num_PM2_5_ft3 = num_PM2_5 * CM3_TO_FT3
            num_PM4_ft3 = num_PM4 * CM3_TO_FT3
            num_PM10_ft3 = num_PM10 * CM3_TO_FT3

            # Differential bins
            b0 = max(num_PM0_5_ft3, 0.0)
            b1 = max(num_PM1_ft3 - num_PM0_5_ft3, 0.0)
            b2 = max(num_PM2_5_ft3 - num_PM1_ft3, 0.0)
            b3 = max(num_PM4_ft3 - num_PM2_5_ft3, 0.0)
            b4 = max(num_PM10_ft3 - num_PM4_ft3, 0.0)

            data["raw_measurements"] = {
                "mass_pm1": round(mass_PM1, 3),
                "mass_pm2_5": round(mass_PM2_5, 3),
                "mass_pm4": round(mass_PM4, 3),
                "mass_pm10": round(mass_PM10, 3),
                "num_pm0_5": round(num_PM0_5, 3),
                "num_pm1": round(num_PM1, 3),
                "num_pm2_5": round(num_PM2_5, 3),
                "num_pm4": round(num_PM4, 3),
                "num_pm10": round(num_PM10, 3),
                "typical_particle_size_um": round(tps_um, 3),
            }
            data["converted_values"] = {
                "number_concentrations_ft3": {
                    "pm0_5": round(num_PM0_5_ft3, 2),
                    "pm1": round(num_PM1_ft3, 2),
                    "pm2_5": round(num_PM2_5_ft3, 2),
                    "pm4": round(num_PM4_ft3, 2),
                    "pm10": round(num_PM10_ft3, 2),
                },
                "differential_bins_ft3": {
                    "bin_0_3_to_0_5": round(b0, 2),
                    "bin_0_5_to_1_0": round(b1, 2),
                    "bin_1_0_to_2_5": round(b2, 2),
                    "bin_2_5_to_4_0": round(b3, 2),
                    "bin_4_0_to_10": round(b4, 2),
                },
                "mass_concentrations_ug_m3": {
                    "pm1": round(mass_PM1, 2),
                    "pm2_5": round(mass_PM2_5, 2),
                    "pm4": round(mass_PM4, 2),
                    "pm10": round(mass_PM10, 2),
                },
            }

        json_data = ujson.dumps(data)
        safe_print(f"Sending combined data ({len(json_data)} bytes)...")

        headers = {"Content-Type": "application/json"}

        for attempt in range(HTTP_SEND_RETRIES + 1):
            try:
                response = urequests.post(
                    API_URL,
                    data=json_data,
                    headers=headers,
                    timeout=HTTP_TIMEOUT_S,
                )

                if response.status_code == 200:
                    safe_print(f"API OK ({response.status_code})")
                    return True

                msg = f"API error {response.status_code}"
                safe_print(msg)
                log_error(msg)
                return False

            except OSError as e:
                if not is_timeout_oserror(e):
                    raise

                msg = "send_to_api timeout attempt {}/{}: {}".format(
                    attempt + 1, HTTP_SEND_RETRIES + 1, e
                )
                safe_print(msg)
                log_error(msg)

                if attempt >= HTTP_SEND_RETRIES:
                    raise

                safe_print("Timeout recovery: reconnecting WiFi before retry...")
                try:
                    network.WLAN(network.STA_IF).disconnect()
                except Exception:
                    pass
                sleep_with_wdt(2)
                connect_wifi(max_attempts=1)
                sleep_with_wdt(1)

    except OSError as e:
        if e.args and e.args[0] == -2:
            msg = "send_to_api OSError: -2 (DNS/name resolution or host lookup failure for {})".format(API_HOST)
        elif is_timeout_oserror(e):
            msg = "send_to_api OSError: ETIMEDOUT (server reachable by DNS, but TCP/HTTPS timed out)"
        else:
            msg = f"send_to_api OSError: {e}"
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
        gc.collect()


# ===== LED helpers =====

def blink_led_startup():
    for i in range(2):
        LED_PIN.on()
        time.sleep(0.3)
        LED_PIN.off()
        time.sleep(0.3)


def led_error_code(error_type):
    LED_PIN.off()
    time.sleep(0.5)
    patterns = {"wifi": (3, 0.2), "i2c": (4, 0.2), "sensor": (5, 0.2), "general": (2, 1.0)}
    blinks, duration = patterns.get(error_type, (2, 1.0))
    for i in range(blinks):
        LED_PIN.on()
        time.sleep(duration)
        LED_PIN.off()
        time.sleep(0.2 if duration < 0.5 else 0.5)


# ===== Main =====

def main():
    global _wdt

    wdt = create_watchdog()
    _wdt = wdt
    wdt.feed()

    try:
        safe_print("=== Combined Sensor (SPS30 + DHT22) ===")
        safe_print(f"Room: {ROOM_NAME}, Sensor: {SENSOR_NUMBER}")
        safe_print(f"Target API: {API_URL}")

        blink_led_startup()
        wdt.feed()
        LED_PIN.on()

        # Stabilisation delay for headless boot
        for _ in range(5):
            time.sleep(1)
            wdt.feed()
        gc.collect()
        wdt.feed()

        # ---- WiFi ----
        if not connect_wifi():
            led_error_code("wifi")
            log_error("WiFi failed at startup — resetting")
            machine.reset()
        wdt.feed()

        # ---- NTP sync ----
        sync_time_ntp()
        last_time_sync_utc = time.time()
        wdt.feed()

        # ---- DHT22 init ----
        safe_print(f"Initializing DHT22 on GPIO{DHT_PIN}...")
        dht_sensor = dht.DHT22(Pin(DHT_PIN))
        time.sleep(2)
        wdt.feed()
        # Warm-up read — first DHT22 read after power-on can be inaccurate
        try:
            dht_sensor.measure()
        except Exception:
            pass
        time.sleep(2)
        wdt.feed()
        safe_print("DHT22 initialized")

        # ---- I2C + SPS30 init ----
        safe_print(f"Initializing I2C (SDA=GP{SDA_PIN}, SCL=GP{SCL_PIN})...")
        time.sleep(1)
        wdt.feed()

        try:
            i2c = I2C(I2C_ID, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100_000)
            time.sleep(0.5)
        except Exception as e:
            safe_print(f"I2C init failed: {e}")
            led_error_code("i2c")
            log_error(f"I2C Init Error: {e}")
            raise RuntimeError("I2C initialization failed")
        wdt.feed()

        # Scan for SPS30 with retries
        devices = []
        for attempt in range(3):
            devices = i2c.scan()
            if devices:
                safe_print(f"I2C devices: {[hex(a) for a in devices]}")
                break
            safe_print(f"I2C scan attempt {attempt + 1} — no devices")
            time.sleep(1)
            wdt.feed()

        if SPS30_ADDR not in devices:
            safe_print(f"SPS30 not found at {hex(SPS30_ADDR)}")
            safe_print("Check: SDA→GP4, SCL→GP5, VCC→5V, GND, SEL→GND")
            led_error_code("sensor")
            raise RuntimeError("SPS30 not found on I2C bus")
        safe_print(f"SPS30 found at {hex(SPS30_ADDR)}")
        wdt.feed()

        sps = SPS30(i2c)

        # Reset SPS30 state (may have been measuring from a previous run)
        try:
            sps.stop_measurement()
            time.sleep(1)
        except Exception:
            pass
        wdt.feed()

        # Start SPS30 measurement with retries
        measurement_started = False
        for attempt in range(3):
            try:
                sps.start_measurement_float()
                safe_print("SPS30 measurement started")
                measurement_started = True
                break
            except OSError as e:
                safe_print(f"SPS30 start attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)
                    wdt.feed()

        if not measurement_started:
            led_error_code("sensor")
            log_error("SPS30 measurement start failed after retries")
            raise RuntimeError("Failed to start SPS30 measurement")
        wdt.feed()

        # Wait for SPS30 to stabilize (up to 10 s)
        safe_print("Waiting for SPS30 to stabilize...")
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 10000:
            wdt.feed()
            try:
                if sps.read_data_ready():
                    safe_print("SPS30 ready")
                    break
            except Exception:
                pass
            time.sleep_ms(500)
        wdt.feed()

        # ---- Main loop setup ----
        safe_print("Starting combined data collection...")
        if SCHEDULED_SENDING:
            safe_print(f"Reading every {MEASUREMENT_PERIOD_S}s, sending every {SEND_INTERVAL_MINUTES}min")
            next_send_time = calculate_next_send_time()
            safe_print(f"Next send: {format_local_time(next_send_time)}")
            if not clock_looks_valid():
                safe_print("Warning: Clock not valid yet — send schedule may be inaccurate")
        else:
            safe_print(f"Sending every {MEASUREMENT_PERIOD_S}s")
        safe_print("-" * 50)

        try:
            loop_count = 0
            consecutive_failures = 0
            last_send_ticks = time.ticks_ms()
            last_wifi_reset_ticks = time.ticks_ms()
            last_dht_read = 0
            fallback_interval_ms = SEND_INTERVAL_MINUTES * 60 * 1000
            latest_temperature = None
            latest_humidity = None

            while True:
                wdt.feed()

                # Periodic NTP re-sync
                if TIME_SYNC_ENABLED:
                    if time.time() - last_time_sync_utc >= TIME_SYNC_INTERVAL_HOURS * 3600:
                        if sync_time_ntp():
                            last_time_sync_utc = time.time()
                            if SCHEDULED_SENDING:
                                next_send_time = calculate_next_send_time()
                        wdt.feed()

                # Periodic WiFi reset (24 h)
                if time.ticks_diff(time.ticks_ms(), last_wifi_reset_ticks) >= WIFI_RESET_INTERVAL_MS:
                    reset_wifi()
                    last_wifi_reset_ticks = time.ticks_ms()
                    wdt.feed()

                # Memory check every ~20 loops
                loop_count += 1
                if loop_count % 20 == 0:
                    gc.collect()
                    if gc.mem_free() < 15000:
                        log_error("Low memory — resetting")
                        machine.reset()

                # ---- Read DHT22 (enforce 2 s minimum between reads) ----
                now = time.time()
                if now - last_dht_read >= 2:
                    try:
                        latest_temperature, latest_humidity = read_dht22(dht_sensor)
                        last_dht_read = time.time()
                    except OSError as e:
                        safe_print(f"DHT22 read error: {e}")
                        # Keep last good values — don't clear

                # ---- Read SPS30 ----
                try:
                    particle_vals = sps.read_measured_values_float()
                except Exception as e:
                    safe_print(f"SPS30 read failed: {e}")
                    time.sleep(1)
                    wdt.feed()
                    continue

                # ---- Determine if we should send ----
                should_send = False
                if SCHEDULED_SENDING:
                    current_local = time.time() + (UTC_OFFSET_HOURS * 3600)
                    if current_local >= next_send_time:
                        should_send = True
                    elif time.ticks_diff(time.ticks_ms(), last_send_ticks) >= fallback_interval_ms:
                        should_send = True
                        safe_print("Fallback send (elapsed interval)")
                else:
                    should_send = True

                if should_send:
                    # Reconnect WiFi if needed
                    if not network.WLAN(network.STA_IF).isconnected():
                        safe_print("WiFi lost — reconnecting...")
                        if not connect_wifi():
                            log_error("WiFi reconnect failed — resetting")
                            machine.reset()
                        wdt.feed()

                    success = send_to_api(particle_vals, latest_temperature, latest_humidity)
                    wdt.feed()

                    if success:
                        consecutive_failures = 0
                        last_send_ticks = time.ticks_ms()
                        if SCHEDULED_SENDING:
                            next_send_time = calculate_next_send_time()
                            safe_print(f"Next send: {format_local_time(next_send_time)}")

                        # Summary log
                        mass_PM2_5 = particle_vals[1]
                        num_PM0_5_ft3 = particle_vals[4] * CM3_TO_FT3
                        temp_str = "{:.1f}C".format(latest_temperature) if latest_temperature is not None else "N/A"
                        hum_str = "{:.1f}%".format(latest_humidity) if latest_humidity is not None else "N/A"
                        safe_print(
                            "{} | {}/ft3 | PM2.5: {} ug/m3 | Temp: {} | RH: {}".format(
                                ROOM_NAME, round(num_PM0_5_ft3),
                                round(mass_PM2_5, 1), temp_str, hum_str
                            )
                        )
                    else:
                        consecutive_failures += 1
                        safe_print(
                            "Send failed ({}/{})".format(
                                consecutive_failures, MAX_CONSECUTIVE_FAILURES
                            )
                        )
                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            log_error(f"Too many failures ({consecutive_failures}) — resetting")
                            machine.reset()
                else:
                    # Log reading without sending
                    num_PM0_5_ft3 = particle_vals[4] * CM3_TO_FT3
                    mass_PM2_5 = particle_vals[1]
                    temp_str = "{:.1f}C".format(latest_temperature) if latest_temperature is not None else "N/A"
                    hum_str = "{:.1f}%".format(latest_humidity) if latest_humidity is not None else "N/A"
                    t_str = format_local_time(time.time() + UTC_OFFSET_HOURS * 3600)
                    safe_print(
                        "[{}] {}/ft3  PM2.5: {}  Temp: {}  RH: {}".format(
                            t_str, round(num_PM0_5_ft3), round(mass_PM2_5, 1), temp_str, hum_str
                        )
                    )

                # Sleep between measurements (feeds WDT internally)
                sleep_with_wdt(MEASUREMENT_PERIOD_S)

        except KeyboardInterrupt:
            safe_print("Shutting down...")
            LED_PIN.off()
            raise
        finally:
            try:
                sps.stop_measurement()
                LED_PIN.off()
            except Exception:
                pass

    except Exception as e:
        safe_print(f"Error in main(): {e}")
        led_error_code("general")
        log_error(f"Error: {e}")
        raise


if __name__ == "__main__":
    # Headless-safe boot: wait for power rails and CYW43 to stabilize
    time.sleep(5)

    MAX_RETRIES = 10
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            main()
            raise RuntimeError("main() returned unexpectedly")
        except Exception as e:
            retry_count += 1
            log_error(f"crash #{retry_count}: {e}")
            safe_print(f"Crashed ({e}), resetting ({retry_count}/{MAX_RETRIES})")
            LED_PIN.off()
            gc.collect()
            machine.reset()

    if retry_count >= MAX_RETRIES:
        log_error(f"Exhausted {MAX_RETRIES} retries, resetting...")
        machine.reset()


# =============================================================================
# Expected JSON sent to POST /sensor-data:
# {
#   "room_name":     "COMBINED",
#   "sensor_number": "001",
#   "timestamp":     1744300800,
#   "temperature_c": 22.5,          (omitted if DHT22 read failed)
#   "humidity_pct":  45.3,           (omitted if DHT22 read failed)
#   "raw_measurements": {
#     "mass_pm1": 1.234,  "mass_pm2_5": 2.345,  "mass_pm4": 3.456,  "mass_pm10": 4.567,
#     "num_pm0_5": 0.123, "num_pm1": 0.234,      "num_pm2_5": 0.345, "num_pm4": 0.456,
#     "num_pm10": 0.567,  "typical_particle_size_um": 0.678
#   },
#   "converted_values": {
#     "number_concentrations_ft3": {"pm0_5": ..., "pm1": ..., "pm2_5": ..., "pm4": ..., "pm10": ...},
#     "differential_bins_ft3":     {"bin_0_3_to_0_5": ..., ...},
#     "mass_concentrations_ug_m3": {"pm1": ..., "pm2_5": ..., "pm4": ..., "pm10": ...}
#   }
# }
# =============================================================================
