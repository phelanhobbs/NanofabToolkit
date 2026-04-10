# MicroPython SPS30 (I2C) driver + API transmission for Raspberry Pi Pico W
# Sends particle sensor data to API endpoint with room name, sensor number, and all datapoints.
# Configured for headless (no USB terminal) operation.

import time
import struct
import ujson
import urequests
import network
import gc
import sys
import os
import machine
from machine import I2C, Pin, WDT

try:
    import ntptime
except ImportError:
    ntptime = None

# Module-level WDT reference so helper functions can feed it without
# needing the wdt object passed through every call chain.
_wdt = None

# ===== Headless-safe print =====
# When no USB serial host is connected, print() can block or raise an
# exception. Catching Exception (not just OSError) handles both cases.
def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        pass  # USB serial not connected or buffer full — discard output

def log_error(msg):
    """Append msg to error_log.txt, capping the file at ~4 KB to avoid filling flash."""
    try:
        try:
            if os.stat("error_log.txt")[6] > 4096:
                open_mode = "w"  # file too large — start fresh
            else:
                open_mode = "a"
        except OSError:
            open_mode = "a"
        with open("error_log.txt", open_mode) as f:
            f.write(msg if msg.endswith("\n") else msg + "\n")
    except Exception:
        pass

# LED setup for Raspberry Pi Pico W
# The onboard LED is connected to GPIO 25 on Pico W
LED_PIN = Pin("LED", Pin.OUT)  # Use "LED" for Pico W onboard LED

# ===== User config =====
I2C_ID = 0          # 0 or 1
SDA_PIN = 4         # GP4 for I2C0
SCL_PIN = 5         # GP5 for I2C0
ADDR    = 0x69      # SPS30 I2C address
MEASUREMENT_PERIOD_S = 15   # Read sensor data every 15 seconds

# Scheduled sending configuration
SCHEDULED_SENDING = True    # If True, send data at exact times; if False, send every MEASUREMENT_PERIOD_S
SEND_INTERVAL_MINUTES = 15  # Send data every 15 minutes (at :00, :15, :30, :45)

# Time synchronization configuration (recommended for scheduled sending)
TIME_SYNC_ENABLED = True
TIME_SYNC_INTERVAL_HOURS = 6  # Re-sync clock every 6 hours
NTP_SERVERS = (
    "time.google.com",
    "pool.ntp.org",
    "time.nist.gov",  # NIST (time.gov-related ecosystem)
)

# WiFi credentials
WIFI_SSID = "ULink"
WIFI_PASSWORD = "u0919472632117"

# API endpoint configuration
API_URL = "https://nfhistory.nanofab.utah.edu/particle-data"  # Production API endpoint URL

# Alternative endpoints for testing (uncomment to use):
# API_URL = "http://nfhistory.nanofab.utah.edu/particle-data"  # HTTP version (if HTTPS fails)
# API_URL = "http://155.98.11.8/particle-data"  # Direct IP address (bypasses DNS)
# API_URL = "http://192.168.1.100:443/particle-data"  # Replace with your local server IP
# API_URL = "http://10.0.0.100:443/particle-data"     # Replace with your local server IP

ROOM_NAME = "HEADLESS"  # Name of the room where this sensor is located
SENSOR_NUMBER = "009"     # Unique sensor identifier/number

# UTC offset in hours (Mountain Time: UTC-7 in standard time, UTC-6 in daylight saving time)
# Use -7 for Mountain Standard Time (MST) or -6 for Mountain Daylight Time (MDT)
UTC_OFFSET_HOURS = -7  # Adjust this based on current time (MST = -7, MDT = -6)

# Conversion factor from #/cm³ to #/ft³
CM3_TO_FT3 = 28316.8  # 1 ft³ = 28,316.8 cm³

# MicroPython on RP2040 uses epoch 2000-01-01; the server expects Unix epoch (1970-01-01).
# Add this offset to time.time() before sending timestamps to the server.
MICROPYTHON_TO_UNIX_EPOCH = 946684800

# ===== SPS30 constants (from datasheet) =====
# Command "pointers"
PTR_START_MEAS   = 0x0010  # write: [0x03, 0x00, CRC] for big-endian IEEE754 floats
PTR_STOP_MEAS    = 0x0104
PTR_DATA_RDY     = 0x0202  # read 3 bytes (2 data + CRC); byte[1] is flag (0x01 ready)
PTR_READ_VALUES  = 0x0300  # read 60 bytes for float format (10 floats, 2 CRCs per float)
# CRC-8 parameters for word packets (poly 0x31, init 0xFF)
def _crc8_word(b0, b1):
    crc = 0xFF
    for byte in (b0, b1):
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if (crc & 0x80) else ((crc << 1) & 0xFF)
    return crc

class SPS30:
    def __init__(self, i2c, addr=ADDR):
        self.i2c = i2c
        self.addr = addr

    def _write_ptr(self, ptr):
        # Write 16-bit pointer, big-endian
        self.i2c.writeto(self.addr, bytes([(ptr >> 8) & 0xFF, ptr & 0xFF]))

    def _write_ptr_with_data(self, ptr, payload):
        self.i2c.writeto(self.addr, bytes([(ptr >> 8) & 0xFF, ptr & 0xFF]) + payload)

    def start_measurement_float(self):
        # payload: [0x03, 0x00, CRC]  => 0x03 selects float output; 0x00 dummy; CRC over the two bytes
        try:
            b0, b1 = 0x03, 0x00
            crc = _crc8_word(b0, b1)
            self._write_ptr_with_data(PTR_START_MEAS, bytes([b0, b1, crc]))
        except OSError as e:
            safe_print(f"SPS30 start_measurement failed: {e} (errno: {e.errno})")
            raise

    def stop_measurement(self):
        self._write_ptr(PTR_STOP_MEAS)

    def read_data_ready(self):
        self._write_ptr(PTR_DATA_RDY)
        data = self.i2c.readfrom(self.addr, 3)  # 2 bytes + CRC
        # verify CRC (optional, but let's be good)
        if _crc8_word(data[0], data[1]) != data[2]:
            return False
        return data[1] == 0x01

    def read_measured_values_float(self):
        # Returns list of 10 floats:
        # [mass_PM1, mass_PM2_5, mass_PM4, mass_PM10,
        #  num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, typical_particle_size_um]
        self._write_ptr(PTR_READ_VALUES)
        raw = self.i2c.readfrom(self.addr, 60)  # 10 floats * (2 bytes + CRC + 2 bytes + CRC)
        vals = []
        # Each float spans 6 bytes: [hi0, hi1, CRC, lo0, lo1, CRC]
        for i in range(10):
            base = i * 6
            hi0, hi1, crc1, lo0, lo1, crc2 = raw[base:base+6]
            if _crc8_word(hi0, hi1) != crc1 or _crc8_word(lo0, lo1) != crc2:
                raise ValueError("CRC error on float index {}".format(i))
            fbytes = bytes([hi0, hi1, lo0, lo1])  # big-endian 32-bit float
            vals.append(struct.unpack('>f', fbytes)[0])
        return vals

def format_row(v):
    # Keep it tight but readable
    return "{:10.2f}".format(v)

def scan_i2c_devices(i2c):
    """Scan for I2C devices and return list of addresses"""
    safe_print("Scanning I2C bus...")
    try:
        devices = i2c.scan()
        if devices:
            safe_print(f"Found devices at addresses: {[hex(addr) for addr in devices]}")
        else:
            safe_print("No I2C devices found!")
        return devices
    except OSError as e:
        safe_print(f"I2C scan failed: {e} (errno: {e.errno})")
        if e.errno == 5:  # EIO
            safe_print("I2C EIO Error - Check:")
            safe_print("- Wiring connections (SDA/SCL)")
            safe_print("- Power supply (5V for SPS30)")
            safe_print("- Ground connections")
            safe_print("- Pull-up resistors")
        return []

def test_i2c_connection(i2c, addr):
    """Test basic I2C communication with device"""
    try:
        # Try to read 1 byte (this will fail gracefully if device exists)
        i2c.readfrom(addr, 1)
        return True
    except OSError as e:
        if e.errno == 5:  # EIO - device exists but command failed
            return True
        elif e.errno == 19:  # ENODEV - no device at address  
            return False
        else:
            safe_print(f"Unexpected I2C error: {e}")
            return False

def test_dns_resolution():
    """Test DNS resolution with different servers"""
    safe_print("Testing DNS resolution...")
    
    # Test with well-known servers
    test_domains = [
        "google.com",
        "8.8.8.8",  # Google DNS (should work as IP)
        "httpbin.org",
        "nfhistory.nanofab.utah.edu"
    ]
    
    for domain in test_domains:
        try:
            if domain == "8.8.8.8":
                # Test direct IP connection
                test_response = urequests.get(f"http://{domain}", timeout=5)
                test_response.close()
                safe_print(f"Direct IP connection works: {domain}")
            else:
                # Test domain name resolution
                test_response = urequests.get(f"http://{domain}", timeout=5)
                test_response.close()
                safe_print(f"DNS resolution works: {domain}")
        except OSError as e:
            if e.errno == -2:
                safe_print(f"DNS failed: {domain}")
            elif e.errno == -1:
                safe_print(f"Timeout: {domain}")
            else:
                safe_print(f"Error {e.errno}: {domain}")
        except Exception as e:
            safe_print(f"Exception: {domain} - {e}")

def test_network_connectivity():
    """Test basic network connectivity and DNS resolution.
    Skips slow external HTTP checks to avoid blocking headless startup."""
    safe_print("=== Network Diagnostics ===")
    
    # Check WiFi status
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        config = wlan.ifconfig()
        safe_print(f"WiFi connected")
        safe_print(f"  IP: {config[0]}")
        safe_print(f"  Netmask: {config[1]}")
        safe_print(f"  Gateway: {config[2]}")
        safe_print(f"  DNS: {config[3]}")
        # If we have an IP that isn't 0.0.0.0, WiFi is connected and DNS likely works.
        # Skip the slow external HTTP checks (httpbin.org) — they waste time headless
        # and can fail on networks that block arbitrary outbound traffic.
        return config[0] != "0.0.0.0"
    else:
        safe_print("WiFi not connected")
        return False

def configure_dns():
    """Try to configure DNS manually if automatic configuration fails"""
    safe_print("Attempting manual DNS configuration...")
    
    try:
        import socket
        # Try to manually set DNS servers (Google and Cloudflare)
        # Note: This may not work in all MicroPython implementations
        safe_print("Setting DNS servers: 8.8.8.8, 1.1.1.1")
        # This is implementation-dependent and may not be available
    except Exception as e:
        safe_print(f"Manual DNS configuration not available: {e}")
    
    safe_print("DNS troubleshooting suggestions:")
    safe_print("1. Check router/network DNS settings")
    safe_print("2. Try connecting to a different WiFi network") 
    safe_print("3. Use a mobile hotspot for testing")
    safe_print("4. Contact network administrator")

def clock_looks_valid():
    """Basic sanity check for RTC clock (epoch starts near year 2000 on unsynced boards)."""
    try:
        return time.localtime()[0] >= 2024
    except Exception:
        return False

def sync_time_ntp(max_attempts_per_server=2):
    """Sync RTC from NTP servers. Returns True on success."""
    if not TIME_SYNC_ENABLED:
        return False

    if ntptime is None:
        safe_print("ntptime module not available on this firmware; skipping NTP sync")
        return False

    safe_print("Synchronizing time via NTP...")

    for server in NTP_SERVERS:
        for attempt in range(max_attempts_per_server):
            try:
                ntptime.host = server
                ntptime.settime()  # Sets RTC to UTC

                utc_now = time.time()
                local_now = utc_now + (UTC_OFFSET_HOURS * 3600)
                safe_print(f"Time sync OK via {server}")
                safe_print(f"  UTC:   {format_local_time(utc_now)}")
                safe_print(f"  Local: {format_local_time(local_now)}")
                return True
            except OSError as e:
                safe_print(f"NTP failed via {server} attempt {attempt + 1}: {e} (errno: {e.errno})")
                time.sleep(1)
                if _wdt:
                    _wdt.feed()
            except Exception as e:
                safe_print(f"NTP failed via {server} attempt {attempt + 1}: {e}")
                time.sleep(1)
                if _wdt:
                    _wdt.feed()

    safe_print("NTP sync failed on all servers")
    return False

def calculate_next_send_time():
    """Calculate the next scheduled send time based on current local time"""
    import time
    
    # Get current local time
    current_utc = time.time()
    current_local = current_utc + (UTC_OFFSET_HOURS * 3600)
    
    # Convert to time structure
    time_struct = time.localtime(current_local)
    
    # Calculate minutes since the hour
    minutes_since_hour = time_struct[4]  # tm_min
    seconds_since_hour = time_struct[5]  # tm_sec
    
    # Find the next send interval
    next_send_minute = ((minutes_since_hour // SEND_INTERVAL_MINUTES) + 1) * SEND_INTERVAL_MINUTES
    
    # If we've gone past 60 minutes, move to next hour
    if next_send_minute >= 60:
        next_send_minute = 0
        # Move to next hour
        next_hour = time_struct[3] + 1
        if next_hour >= 24:
            next_hour = 0
            # Would need to handle day rollover, but for simplicity we'll just use time math
    
    # Calculate the target time
    current_hour_start = current_local - (minutes_since_hour * 60) - seconds_since_hour
    
    if next_send_minute == 0:
        # Next hour
        target_time = current_hour_start + 3600  # Add one hour
    else:
        # Same hour, different minute
        target_time = current_hour_start + (next_send_minute * 60)
    
    return target_time

def format_local_time(timestamp):
    """Format a local timestamp for display"""
    time_struct = time.localtime(timestamp)
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        time_struct[0], time_struct[1], time_struct[2],  # year, month, day
        time_struct[3], time_struct[4], time_struct[5]   # hour, minute, second
    )

def connect_wifi(max_attempts=3):
    """Connect to WiFi network with retries for headless reliability"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    status_names = {
        0: "STAT_IDLE",
        1: "STAT_CONNECTING",
        2: "STAT_WRONG_PASSWORD",
        3: "STAT_NO_AP_FOUND",
        4: "STAT_CONNECT_FAIL",
        5: "STAT_GOT_IP",
        -1: "STAT_CONNECT_FAIL",
        -2: "STAT_NO_AP_FOUND",
        -3: "STAT_WRONG_PASSWORD",
    }
    
    # Give the CYW43 WiFi chip time to initialise (critical for headless boot)
    time.sleep(1)
    
    for attempt in range(max_attempts):
        if wlan.isconnected():
            safe_print(f"Already connected to WiFi. IP: {wlan.ifconfig()[0]}")
            return True

        # Reset state between attempts for better reliability
        try:
            wlan.disconnect()
        except Exception:
            pass
        time.sleep(1)
        
        safe_print(f"Connecting to WiFi: {WIFI_SSID} (attempt {attempt + 1}/{max_attempts})")
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as e:
            safe_print(f"WiFi connect call failed: {e}")
            time.sleep(2)
            continue
        
        # Wait for connection — 20 s is more reliable headless than 10 s
        timeout = 20
        while timeout > 0 and not wlan.isconnected():
            time.sleep(1)
            timeout -= 1
            if _wdt:
                _wdt.feed()
        
        if wlan.isconnected():
            safe_print(f"WiFi connected! IP: {wlan.ifconfig()[0]}")
            return True
        else:
            st = wlan.status()
            safe_print(f"WiFi attempt {attempt + 1} failed, status: {st} ({status_names.get(st, 'UNKNOWN')})")
            wlan.disconnect()
            time.sleep(2)
    
    safe_print("Failed to connect to WiFi after all attempts")
    return False

def reset_wifi():
    """Fully tear down and re-establish the WiFi interface.
    Called periodically to clear CYW43 internal state that accumulates
    over days of operation and can cause silent connection failures."""
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
    safe_print("WiFi reset failed — triggering machine reset")
    machine.reset()

def send_to_api(vals):
    """Send particle sensor data to API endpoint with fallback URLs"""
    
    # Only the HTTPS endpoint works — nginx on port 80 does not proxy to Flask.
    api_urls_to_try = [
        API_URL,
    ]
    
    for url_attempt, current_url in enumerate(api_urls_to_try):
        response = None
        try:
            # Unpack sensor values
            mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
            num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = vals

            if url_attempt == 0:  # Only print debug info on first attempt
                # DEBUG: Print raw sensor values before any conversion
                safe_print(f"\n===== RAW SENSOR DATA =====")
                safe_print(f"Mass PM1.0: {mass_PM1:.3f} ug/m3")
                safe_print(f"Mass PM2.5: {mass_PM2_5:.3f} ug/m3")
                safe_print(f"Mass PM4.0: {mass_PM4:.3f} ug/m3")
                safe_print(f"Mass PM10:  {mass_PM10:.3f} ug/m3")
                safe_print(f"Num PM0.5:  {num_PM0_5:.1f} #/cm3")
                safe_print(f"Num PM1.0:  {num_PM1:.1f} #/cm3")
                safe_print(f"Num PM2.5:  {num_PM2_5:.1f} #/cm3")
                safe_print(f"Num PM4.0:  {num_PM4:.1f} #/cm3")
                safe_print(f"Num PM10:   {num_PM10:.1f} #/cm3")
                safe_print(f"Typical particle size: {tps_um:.3f} um")
                safe_print(f"============================")

            # Convert number concentrations from #/cm³ to #/ft³
            num_PM0_5_ft3 = num_PM0_5 * CM3_TO_FT3
            num_PM1_ft3 = num_PM1 * CM3_TO_FT3
            num_PM2_5_ft3 = num_PM2_5 * CM3_TO_FT3
            num_PM4_ft3 = num_PM4 * CM3_TO_FT3
            num_PM10_ft3 = num_PM10 * CM3_TO_FT3

            if url_attempt == 0:  # Only print debug info on first attempt
                # DEBUG: Print converted values
                safe_print(f"===== CONVERTED DATA =====")
                safe_print(f"Num PM0.5:  {num_PM0_5_ft3:.0f} #/ft3")
                safe_print(f"Num PM1.0:  {num_PM1_ft3:.0f} #/ft3")
                safe_print(f"Num PM2.5:  {num_PM2_5_ft3:.0f} #/ft3")
                safe_print(f"Num PM4.0:  {num_PM4_ft3:.0f} #/ft3")
                safe_print(f"Num PM10:   {num_PM10_ft3:.0f} #/ft3")
                safe_print(f"===========================")

            # Calculate differential bins (as in original code)
            b0 = max(num_PM0_5_ft3, 0.0)                    # 0.3–0.5 µm
            b1 = max(num_PM1_ft3 - num_PM0_5_ft3, 0.0)      # 0.5–1.0 µm
            b2 = max(num_PM2_5_ft3 - num_PM1_ft3, 0.0)      # 1.0–2.5 µm
            b3 = max(num_PM4_ft3 - num_PM2_5_ft3, 0.0)      # 2.5–4.0 µm
            b4 = max(num_PM10_ft3 - num_PM4_ft3, 0.0)       # 4.0–10.0 µm

            # Calculate local timestamp by applying UTC offset
            # Add epoch offset so the server (which uses Unix epoch 1970) gets the right date.
            utc_timestamp = time.time() + MICROPYTHON_TO_UNIX_EPOCH
            local_timestamp = utc_timestamp + (UTC_OFFSET_HOURS * 3600)  # Convert hours to seconds
            
            # Prepare data payload with room name, sensor number, and all datapoint values
            data = {
                "room_name": ROOM_NAME,
                "sensor_number": SENSOR_NUMBER,
                "timestamp": local_timestamp,
                "raw_measurements": {
                    "mass_pm1": round(mass_PM1, 3),
                    "mass_pm2_5": round(mass_PM2_5, 3),
                    "mass_pm4": round(mass_PM4, 3),
                    "mass_pm10": round(mass_PM10, 3),
                    "num_pm0_5": round(num_PM0_5, 3),
                    "num_pm1": round(num_PM1, 3),
                    "num_pm2_5": round(num_PM2_5, 3),
                    "num_pm4": round(num_PM4, 3),
                    "num_pm10": round(num_PM10, 3),
                    "typical_particle_size_um": round(tps_um, 3)
                },
                "converted_values": {
                    "number_concentrations_ft3": {
                        "pm0_5": round(num_PM0_5_ft3, 2),
                        "pm1": round(num_PM1_ft3, 2),
                        "pm2_5": round(num_PM2_5_ft3, 2),
                        "pm4": round(num_PM4_ft3, 2),
                        "pm10": round(num_PM10_ft3, 2)
                    },
                    "differential_bins_ft3": {
                        "bin_0_3_to_0_5": round(b0, 2),
                        "bin_0_5_to_1_0": round(b1, 2),
                        "bin_1_0_to_2_5": round(b2, 2),
                        "bin_2_5_to_4_0": round(b3, 2),
                        "bin_4_0_to_10": round(b4, 2)
                    },
                    "mass_concentrations_ug_m3": {
                        "pm1": round(mass_PM1, 2),
                        "pm2_5": round(mass_PM2_5, 2),
                        "pm4": round(mass_PM4, 2),
                        "pm10": round(mass_PM10, 2)
                    }
                }
            }

            # Convert to JSON
            json_data = ujson.dumps(data)
            
            safe_print(f"Attempting to send data to: {current_url}")
            if url_attempt > 0:
                safe_print(f"  (Fallback attempt #{url_attempt})")
            safe_print(f"Data size: {len(json_data)} bytes")
            
            # Send HTTP POST request with timeout
            headers = {'Content-Type': 'application/json'}
            response = urequests.post(current_url, data=json_data, headers=headers, timeout=7)
            
            safe_print(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                safe_print(f"Data sent successfully to API. Total particles: {round(num_PM0_5_ft3, 0)} #/ft3")
                if url_attempt > 0:
                    safe_print(f"  Success using fallback URL: {current_url}")
                return True
            else:
                response_text = ""
                try:
                    response_text = response.text
                except:
                    response_text = "<unable to read response>"
                safe_print(f"HTTP {response.status_code}: {response_text}")
                # Don't return here - try next URL
            
        except OSError as e:
            safe_print(f"Network error for {current_url}: {e} (errno: {e.errno})")
            if e.errno == -2:
                safe_print("  DNS resolution failed")
            elif e.errno == -1:
                safe_print("  Connection timeout")
            elif e.errno == 104:
                safe_print("  Connection reset by peer")
            elif e.errno == 113:
                safe_print("  No route to host")
            # Don't return here - try next URL
        except Exception as e:
            safe_print(f"Error with {current_url}: {e} (type: {type(e)})")
            # Don't return here - try next URL
        finally:
            if response:
                try:
                    response.close()
                except:
                    pass
            # Feed WDT between URL attempts — 2 URLs × 7 s timeout > 8.3 s limit
            if _wdt:
                _wdt.feed()
            gc.collect()
    
    # If we get here, all URLs failed
    safe_print("All API endpoints failed")
    return False

def blink_led_startup():
    """Blink the onboard LED twice to indicate startup"""
    safe_print("Initializing - LED startup sequence...")
    for i in range(2):
        LED_PIN.on()   # Turn LED on
        time.sleep(0.3)
        LED_PIN.off()  # Turn LED off
        time.sleep(0.3)
    safe_print("Startup sequence complete")

def led_error_code(error_type):
    """Flash LED with different patterns to indicate different errors"""
    # Turn off LED first
    LED_PIN.off()
    time.sleep(0.5)
    
    if error_type == "wifi":
        # 3 quick blinks for WiFi error
        for i in range(3):
            LED_PIN.on()
            time.sleep(0.2)
            LED_PIN.off()
            time.sleep(0.2)
    elif error_type == "i2c":
        # 4 quick blinks for I2C error
        for i in range(4):
            LED_PIN.on()
            time.sleep(0.2)
            LED_PIN.off()
            time.sleep(0.2)
    elif error_type == "sensor":
        # 5 quick blinks for sensor error
        for i in range(5):
            LED_PIN.on()
            time.sleep(0.2)
            LED_PIN.off()
            time.sleep(0.2)
    elif error_type == "general":
        # Long blink pattern for general errors
        for i in range(2):
            LED_PIN.on()
            time.sleep(1.0)
            LED_PIN.off()
            time.sleep(0.5)
    
    # Keep LED off after error indication
    LED_PIN.off()

def main():
    # ---- Enable hardware watchdog (8.3 s max on RP2040) ----
    # If the code hangs for any reason the Pico will auto-reset.
    global _wdt
    wdt = WDT(timeout=8300)  # milliseconds
    _wdt = wdt
    wdt.feed()

    try:
        safe_print("=== Particle Sensor with API Data Transmission ===")
        safe_print(f"Room: {ROOM_NAME}, Sensor: {SENSOR_NUMBER}")
        safe_print(f"Target API: {API_URL}")
        
        # LED startup sequence - blink twice
        blink_led_startup()
        wdt.feed()
        
        # Turn LED on and keep it on while code is running
        LED_PIN.on()
        safe_print("LED is now on - indicates sensor is running")
        
        # Longer stabilisation delay for headless boot (no USB enumeration to slow us down)
        safe_print("Waiting for system to stabilize...")
        for _ in range(5):          # 5 seconds total, feeding watchdog each second
            time.sleep(1)
            wdt.feed()
        
        # Free any boot-time garbage before we start allocating
        gc.collect()
        wdt.feed()
        
        # Connect to WiFi first (with retries built in)
        if not connect_wifi():
            safe_print("Cannot proceed without WiFi connection")
            led_error_code("wifi")  # 3 blinks for WiFi error
            raise RuntimeError("WiFi connection failed during startup")
        wdt.feed()

        # Sync RTC time for accurate scheduled sending
        if not sync_time_ntp():
            safe_print("Proceeding without confirmed RTC sync. Scheduled send times may drift.")
        # Always set so the periodic re-sync fires after TIME_SYNC_INTERVAL_HOURS even if
        # the initial sync failed (previously None would skip the re-sync check forever).
        last_time_sync_utc = time.time()
        wdt.feed()
        
        # Quick connectivity check (no slow external HTTP calls)
        if not test_network_connectivity():
            safe_print("Network connectivity issues detected")
            configure_dns()
            safe_print("Will continue but API calls may fail")
        else:
            safe_print("Network connectivity looks good")
        wdt.feed()
        
        safe_print("Initializing I2C...")
        # Add delay before I2C initialization
        time.sleep(1)
        wdt.feed()
        
        try:
            i2c = I2C(I2C_ID, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100_000)
            safe_print(f"I2C initialized successfully on pins SDA={SDA_PIN}, SCL={SCL_PIN}")
            # Give I2C bus time to settle
            time.sleep(0.5)
        except Exception as e:
            safe_print(f"Failed to initialize I2C: {e}")
            safe_print(f"Error type: {type(e).__name__}")
            if hasattr(e, 'errno'):
                safe_print(f"Error number: {e.errno}")
            led_error_code("i2c")  # 4 blinks for I2C error
            log_error(f"I2C Init Error at {time.time()}: {e}")
            raise RuntimeError("I2C initialization failed")
        wdt.feed()
        
        # Scan for devices with retries
        safe_print("Scanning for I2C devices...")
        devices = []
        max_retries = 3
        
        for attempt in range(max_retries):
            devices = scan_i2c_devices(i2c)
            if devices or attempt == max_retries - 1:
                break
            safe_print(f"Scan attempt {attempt + 1} failed, retrying in 1 second...")
            time.sleep(1)
            wdt.feed()
        
        wdt.feed()
        
        # Check if SPS30 is present
        if ADDR not in devices:
            safe_print(f"SPS30 not found at address {hex(ADDR)}")
            safe_print("Check wiring:")
            safe_print(f"- SDA: GPIO{SDA_PIN}")
            safe_print(f"- SCL: GPIO{SCL_PIN}")
            safe_print("- VCC: 5V (SPS30 requires 5V)")
            safe_print("- GND: Ground")
            safe_print("- Pull-up resistors on SDA/SCL (usually built into Pico)")
            led_error_code("sensor")  # 5 blinks for sensor not found
            raise RuntimeError("SPS30 not found on I2C bus")
        
        safe_print(f"SPS30 found at {hex(ADDR)}")
        
        # Test basic communication
        safe_print("Testing SPS30 communication...")
        if not test_i2c_connection(i2c, ADDR):
            safe_print("Cannot communicate with SPS30")
            safe_print("This could indicate:")
            safe_print("- Faulty sensor")
            safe_print("- Incorrect I2C address")
            safe_print("- Power supply issues (ensure 5V, not 3.3V)")
            safe_print("- Poor connections")
            led_error_code("sensor")  # 5 blinks for sensor communication error
            log_error(f"SPS30 Communication Error at {time.time()}: Cannot communicate with sensor")
            raise RuntimeError("SPS30 communication test failed")
        else:
            safe_print("SPS30 communication test passed")
        wdt.feed()
        
        sps = SPS30(i2c)
        
        # Try to stop any existing measurement first (sensor might be in unknown state)
        safe_print("Resetting sensor state...")
        try:
            sps.stop_measurement()
            time.sleep(1)  # Give sensor time to stop
        except Exception:
            pass  # Ignore errors if sensor wasn't measuring
        wdt.feed()
        
        safe_print("Starting measurement...")
        # Add retry logic for starting measurement
        measurement_started = False
        for attempt in range(3):
            try:
                # Start measurement in float mode
                sps.start_measurement_float()
                safe_print("Measurement started successfully!")
                measurement_started = True
                break
            except OSError as e:
                safe_print(f"Attempt {attempt + 1} failed: {e} (errno: {e.errno})")
                if attempt < 2:  # Don't sleep on last attempt
                    safe_print("Retrying in 2 seconds...")
                    time.sleep(2)
                    wdt.feed()
        
        if not measurement_started:
            safe_print("Failed to start measurement after 3 attempts")
            led_error_code("sensor")  # 5 blinks for measurement start error
            log_error(f"Measurement Start Failed after retries at {time.time()}")
            raise RuntimeError("Failed to start SPS30 measurement")
        wdt.feed()

        # Warm-up: sensor specifies ~1 s cadence; stable startup may take several seconds.
        # Give extra time for standalone operation
        safe_print("Waiting for sensor to stabilize (10 seconds)...")
        t0 = time.ticks_ms()
        sensor_ready = False
        
        while time.ticks_diff(time.ticks_ms(), t0) < 10000:  # Wait up to 10 seconds
            wdt.feed()
            try:
                if sps.read_data_ready():
                    sensor_ready = True
                    safe_print("Sensor is ready!")
                    break
            except Exception as e:
                safe_print(f"Error checking sensor ready state: {e}")
            time.sleep_ms(500)  # Check every 500ms
        
        if not sensor_ready:
            safe_print("Warning: Sensor may not be fully ready, continuing anyway...")
        wdt.feed()

        safe_print("Starting particle data collection and API transmission...")
        if SCHEDULED_SENDING:
            safe_print(f"Reading sensor data every {MEASUREMENT_PERIOD_S} seconds")
            safe_print(f"Sending data to API every {SEND_INTERVAL_MINUTES} minutes at exact intervals")
            next_send_time = calculate_next_send_time()
            safe_print(f"Next scheduled send: {format_local_time(next_send_time)}")
            if not clock_looks_valid():
                safe_print("Warning: Clock does not look valid yet. Send schedule may be inaccurate.")
        else:
            safe_print(f"Sending data every {MEASUREMENT_PERIOD_S} seconds")
        safe_print("-" * 60)

        try:
            latest_vals = None
            loop_count = 0
            consecutive_failures = 0
            last_send_ticks = time.ticks_ms()
            last_wifi_reset_ticks = time.ticks_ms()
            WIFI_RESET_INTERVAL_MS = 24 * 3600 * 1000  # full WiFi reset every 24 hours
            fallback_interval_ms = SEND_INTERVAL_MINUTES * 60 * 1000
            while True:
                wdt.feed()

                # Periodic time resync to limit long-term drift
                if TIME_SYNC_ENABLED and last_time_sync_utc is not None:
                    now_utc = time.time()
                    if now_utc - last_time_sync_utc >= (TIME_SYNC_INTERVAL_HOURS * 3600):
                        safe_print("Periodic NTP re-sync due")
                        if sync_time_ntp():
                            last_time_sync_utc = time.time()
                            if SCHEDULED_SENDING:
                                next_send_time = calculate_next_send_time()
                                safe_print(f"Schedule refreshed. Next send: {format_local_time(next_send_time)}")
                        wdt.feed()
                
                # Periodic full WiFi reset to clear CYW43 state (every 24 hours)
                if time.ticks_diff(time.ticks_ms(), last_wifi_reset_ticks) >= WIFI_RESET_INTERVAL_MS:
                    safe_print("Scheduled WiFi reset due")
                    reset_wifi()
                    last_wifi_reset_ticks = time.ticks_ms()
                    wdt.feed()

                # Periodic garbage collection and memory check every 20 loops (~5 min)
                loop_count += 1
                if loop_count % 20 == 0:
                    gc.collect()
                    free = gc.mem_free()
                    if free < 15000:
                        safe_print(f"Low memory ({free} bytes free) — resetting to recover")
                        log_error(f"Low memory reset: {free} bytes free at {time.time()}")
                        machine.reset()
                
                # Read sensor data
                try:
                    vals = sps.read_measured_values_float()
                except Exception as e:
                    safe_print(f"Sensor read failed: {e}; retrying next cycle")
                    time.sleep(1)
                    wdt.feed()
                    continue
                latest_vals = vals
                
                # Determine if we should send data
                should_send = False
                
                if SCHEDULED_SENDING:
                    current_utc = time.time()
                    current_local = current_utc + (UTC_OFFSET_HOURS * 3600)
                    
                    # Check if it's time to send
                    if current_local >= next_send_time:
                        should_send = True
                        safe_print("\nScheduled send time reached")
                    else:
                        # Fallback in case RTC drifts or jumps unexpectedly
                        elapsed_ms = time.ticks_diff(time.ticks_ms(), last_send_ticks)
                        if elapsed_ms >= fallback_interval_ms:
                            should_send = True
                            safe_print("\nFallback send due to elapsed interval")
                else:
                    # Send every cycle in non-scheduled mode
                    should_send = True
                
                if should_send:
                    # Ensure WiFi is still connected before sending
                    wlan = network.WLAN(network.STA_IF)
                    if not wlan.isconnected():
                        safe_print("WiFi disconnected — reconnecting...")
                        if not connect_wifi():
                            safe_print("WiFi reconnect failed — resetting device")
                            machine.reset()
                        wdt.feed()

                    # Send data to API
                    success = send_to_api(vals)
                    wdt.feed()

                    if success:
                        consecutive_failures = 0
                        last_send_ticks = time.ticks_ms()
                        if SCHEDULED_SENDING:
                            next_send_time = calculate_next_send_time()
                            safe_print(f"Next scheduled send: {format_local_time(next_send_time)}")

                        # Also print a summary to console for local monitoring
                        mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
                        num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = vals
                        
                        # Convert to #/ft3 for display
                        num_PM0_5_ft3 = num_PM0_5 * CM3_TO_FT3
                        
                        safe_print(f"Room: {ROOM_NAME} | Sensor: {SENSOR_NUMBER} | "
                              f"Total particles: {round(num_PM0_5_ft3, 0)} #/ft3 | "
                              f"PM2.5 mass: {round(mass_PM2_5, 1)} ug/m3")
                    else:
                        consecutive_failures += 1
                        if SCHEDULED_SENDING:
                            safe_print(f"Failed to send data to API - will retry on next loop ({consecutive_failures} consecutive failures)")
                        else:
                            safe_print(f"Failed to send data to API ({consecutive_failures} consecutive failures)")
                        if consecutive_failures >= 5:
                            safe_print("Too many consecutive send failures — resetting device")
                            log_error(f"Reset after {consecutive_failures} consecutive send failures at {time.time()}")
                            machine.reset()
                else:
                    # Just log the reading without sending
                    mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
                    num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = vals
                    num_PM0_5_ft3 = num_PM0_5 * CM3_TO_FT3
                    
                    current_time_str = format_local_time(time.time() + (UTC_OFFSET_HOURS * 3600))
                    safe_print(f"[{current_time_str}] Reading: {round(num_PM0_5_ft3, 0)} #/ft3, PM2.5: {round(mass_PM2_5, 1)} ug/m3")

                # Sleep in 1-second chunks so we can keep feeding the watchdog
                for _ in range(MEASUREMENT_PERIOD_S):
                    time.sleep(1)
                    wdt.feed()
        except KeyboardInterrupt:
            safe_print("\nShutting down...")
            LED_PIN.off()  # Turn off LED when shutting down
            raise
        finally:
            try:
                sps.stop_measurement()
                LED_PIN.off()  # Ensure LED is off when program ends
            except Exception:
                pass 
    except Exception as e:
        safe_print(f"Unexpected error in main(): {e}")
        led_error_code("general")  # 2 long blinks for general error
        log_error(f"Error at {time.time()}: {e}")
        raise

if __name__ == "__main__":
    # Headless-safe boot: wait a few seconds so the Pico W's power rails
    # and CYW43 WiFi chip are fully stable before touching any peripherals.
    time.sleep(5)
    
    # Retry loop — if main() crashes for any reason, log it and try again
    # rather than leaving the Pico dead until someone power-cycles it.
    MAX_RETRIES = 10          # give up after this many consecutive failures
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            main()
            # In production, main() is expected to run forever.
            # If it returns, treat it as a failure so we restart cleanly.
            raise RuntimeError("main() returned unexpectedly")
        except Exception as e:
            retry_count += 1
            log_error(f"top-level crash #{retry_count} at {time.time()}: {e}")
            safe_print(f"main() crashed ({e}), resetting ({retry_count}/{MAX_RETRIES})")
            LED_PIN.off()
            gc.collect()
            machine.reset()  # Hard reset — WDT would fire during any sleep > 8.3 s anyway
    
    # If we exhausted retries, do a hard reset so the watchdog/board starts fresh
    if retry_count >= MAX_RETRIES:
        log_error(f"Exhausted {MAX_RETRIES} retries at {time.time()}, resetting...")
        machine.reset()




