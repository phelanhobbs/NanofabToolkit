# MicroPython SPS30 (I2C) driver + API transmission for Raspberry Pi Pico W
# Sends particle sensor data to API endpoint with room name, sensor number, and all datapoints.

import time
import struct
import ujson
import urequests
import network
from machine import I2C, Pin

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

ROOM_NAME = "LTDirtyTest"  # Name of the room where this sensor is located
SENSOR_NUMBER = "006"     # Unique sensor identifier/number

# UTC offset in hours (Mountain Time: UTC-7 in standard time, UTC-6 in daylight saving time)
# Use -7 for Mountain Standard Time (MST) or -6 for Mountain Daylight Time (MDT)
UTC_OFFSET_HOURS = -7  # Adjust this based on current time (MST = -7, MDT = -6)

# Conversion factor from #/cm³ to #/ft³
CM3_TO_FT3 = 28316.8  # 1 ft³ = 28,316.8 cm³

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
            print(f"SPS30 start_measurement failed: {e} (errno: {e.errno})")
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
    print("Scanning I2C bus...")
    try:
        devices = i2c.scan()
        if devices:
            print(f"Found devices at addresses: {[hex(addr) for addr in devices]}")
        else:
            print("No I2C devices found!")
        return devices
    except OSError as e:
        print(f"I2C scan failed: {e} (errno: {e.errno})")
        if e.errno == 5:  # EIO
            print("I2C EIO Error - Check:")
            print("- Wiring connections (SDA/SCL)")
            print("- Power supply (5V for SPS30)")
            print("- Ground connections")
            print("- Pull-up resistors")
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
            print(f"Unexpected I2C error: {e}")
            return False

def test_dns_resolution():
    """Test DNS resolution with different servers"""
    print("Testing DNS resolution...")
    
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
                print(f"✓ Direct IP connection works: {domain}")
            else:
                # Test domain name resolution
                test_response = urequests.get(f"http://{domain}", timeout=5)
                test_response.close()
                print(f"✓ DNS resolution works: {domain}")
        except OSError as e:
            if e.errno == -2:
                print(f"✗ DNS failed: {domain}")
            elif e.errno == -1:
                print(f"✗ Timeout: {domain}")
            else:
                print(f"✗ Error {e.errno}: {domain}")
        except Exception as e:
            print(f"✗ Exception: {domain} - {e}")

def test_network_connectivity():
    """Test basic network connectivity and DNS resolution"""
    print("=== Network Diagnostics ===")
    
    # Check WiFi status
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        config = wlan.ifconfig()
        print(f"✓ WiFi connected")
        print(f"  IP: {config[0]}")
        print(f"  Netmask: {config[1]}")
        print(f"  Gateway: {config[2]}")
        print(f"  DNS: {config[3]}")
    else:
        print("✗ WiFi not connected")
        return False
    
    # Test DNS resolution
    test_dns_resolution()
    
    try:
        # Test simple HTTP request to a reliable server
        print("Testing basic HTTP connectivity...")
        test_response = urequests.get("http://httpbin.org/ip", timeout=10)
        if test_response.status_code == 200:
            print("✓ Basic HTTP connectivity works")
            response_data = test_response.text
            test_response.close()
            print(f"  Response: {response_data[:100]}...")
            return True
        else:
            print(f"✗ HTTP test failed with status {test_response.status_code}")
            test_response.close()
            return False
    except OSError as e:
        print(f"✗ Network connectivity test failed: {e} (errno: {e.errno})")
        if e.errno == -2:
            print("  DNS resolution not working - try using IP addresses")
        elif e.errno == -1:
            print("  Connection timeout")
        return False
    except Exception as e:
        print(f"✗ Network test error: {e}")
        return False

def configure_dns():
    """Try to configure DNS manually if automatic configuration fails"""
    print("Attempting manual DNS configuration...")
    
    try:
        import socket
        # Try to manually set DNS servers (Google and Cloudflare)
        # Note: This may not work in all MicroPython implementations
        print("Setting DNS servers: 8.8.8.8, 1.1.1.1")
        # This is implementation-dependent and may not be available
    except Exception as e:
        print(f"Manual DNS configuration not available: {e}")
    
    print("DNS troubleshooting suggestions:")
    print("1. Check router/network DNS settings")
    print("2. Try connecting to a different WiFi network") 
    print("3. Use a mobile hotspot for testing")
    print("4. Contact network administrator")

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

def connect_wifi():
    """Connect to WiFi network"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print(f"Connecting to WiFi: {WIFI_SSID}")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Wait for connection
        timeout = 10
        while timeout > 0 and not wlan.isconnected():
            time.sleep(1)
            timeout -= 1
            
        if wlan.isconnected():
            print(f"WiFi connected! IP: {wlan.ifconfig()[0]}")
            return True
        else:
            print("Failed to connect to WiFi")
            return False
    else:
        print(f"Already connected to WiFi. IP: {wlan.ifconfig()[0]}")
        return True

def send_to_api(vals):
    """Send particle sensor data to API endpoint with fallback URLs"""
    
    # Try different API URLs in order of preference
    api_urls_to_try = [
        API_URL,  # Primary URL from config
        "http://nfhistory.nanofab.utah.edu/particle-data",  # HTTP fallback
        "https://155.98.11.8/particle-data",  # Direct IP HTTPS (bypasses DNS)
    ]
    
    for url_attempt, current_url in enumerate(api_urls_to_try):
        response = None
        try:
            # Unpack sensor values
            mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
            num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = vals

            if url_attempt == 0:  # Only print debug info on first attempt
                # DEBUG: Print raw sensor values before any conversion
                print(f"\n===== RAW SENSOR DATA =====")
                print(f"Mass PM1.0: {mass_PM1:.3f} μg/m³")
                print(f"Mass PM2.5: {mass_PM2_5:.3f} μg/m³")
                print(f"Mass PM4.0: {mass_PM4:.3f} μg/m³")
                print(f"Mass PM10:  {mass_PM10:.3f} μg/m³")
                print(f"Num PM0.5:  {num_PM0_5:.1f} #/cm³")
                print(f"Num PM1.0:  {num_PM1:.1f} #/cm³")
                print(f"Num PM2.5:  {num_PM2_5:.1f} #/cm³")
                print(f"Num PM4.0:  {num_PM4:.1f} #/cm³")
                print(f"Num PM10:   {num_PM10:.1f} #/cm³")
                print(f"Typical particle size: {tps_um:.3f} μm")
                print(f"============================")

            # Convert number concentrations from #/cm³ to #/ft³
            num_PM0_5_ft3 = num_PM0_5 * CM3_TO_FT3
            num_PM1_ft3 = num_PM1 * CM3_TO_FT3
            num_PM2_5_ft3 = num_PM2_5 * CM3_TO_FT3
            num_PM4_ft3 = num_PM4 * CM3_TO_FT3
            num_PM10_ft3 = num_PM10 * CM3_TO_FT3

            if url_attempt == 0:  # Only print debug info on first attempt
                # DEBUG: Print converted values
                print(f"===== CONVERTED DATA =====")
                print(f"Num PM0.5:  {num_PM0_5_ft3:.0f} #/ft³")
                print(f"Num PM1.0:  {num_PM1_ft3:.0f} #/ft³")
                print(f"Num PM2.5:  {num_PM2_5_ft3:.0f} #/ft³")
                print(f"Num PM4.0:  {num_PM4_ft3:.0f} #/ft³")
                print(f"Num PM10:   {num_PM10_ft3:.0f} #/ft³")
                print(f"===========================")

            # Calculate differential bins (as in original code)
            b0 = max(num_PM0_5_ft3, 0.0)                    # 0.3–0.5 µm
            b1 = max(num_PM1_ft3 - num_PM0_5_ft3, 0.0)      # 0.5–1.0 µm
            b2 = max(num_PM2_5_ft3 - num_PM1_ft3, 0.0)      # 1.0–2.5 µm
            b3 = max(num_PM4_ft3 - num_PM2_5_ft3, 0.0)      # 2.5–4.0 µm
            b4 = max(num_PM10_ft3 - num_PM4_ft3, 0.0)       # 4.0–10.0 µm

            # Calculate local timestamp by applying UTC offset
            utc_timestamp = time.time()
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
            
            print(f"Attempting to send data to: {current_url}")
            if url_attempt > 0:
                print(f"  (Fallback attempt #{url_attempt})")
            print(f"Data size: {len(json_data)} bytes")
            
            # Send HTTP POST request with timeout
            headers = {'Content-Type': 'application/json'}
            response = urequests.post(current_url, data=json_data, headers=headers)
            
            print(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✓ Data sent successfully to API. Total particles: {round(num_PM0_5_ft3, 0)} #/ft³")
                if url_attempt > 0:
                    print(f"  Success using fallback URL: {current_url}")
                return True
            else:
                response_text = ""
                try:
                    response_text = response.text
                except:
                    response_text = "<unable to read response>"
                print(f"✗ HTTP {response.status_code}: {response_text}")
                # Don't return here - try next URL
            
        except OSError as e:
            print(f"✗ Network error for {current_url}: {e} (errno: {e.errno})")
            if e.errno == -2:
                print("  DNS resolution failed")
            elif e.errno == -1:
                print("  Connection timeout")
            elif e.errno == 104:
                print("  Connection reset by peer")
            elif e.errno == 113:
                print("  No route to host")
            # Don't return here - try next URL
        except Exception as e:
            print(f"✗ Error with {current_url}: {e} (type: {type(e)})")
            # Don't return here - try next URL
        finally:
            if response:
                try:
                    response.close()
                except:
                    pass
    
    # If we get here, all URLs failed
    print("✗ All API endpoints failed")
    return False

def blink_led_startup():
    """Blink the onboard LED twice to indicate startup"""
    print("Initializing - LED startup sequence...")
    for i in range(2):
        LED_PIN.on()   # Turn LED on
        time.sleep(0.3)
        LED_PIN.off()  # Turn LED off
        time.sleep(0.3)
    print("Startup sequence complete")

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
    try:
        print("=== Particle Sensor with API Data Transmission ===")
        print(f"Room: {ROOM_NAME}, Sensor: {SENSOR_NUMBER}")
        print(f"Target API: {API_URL}")
        
        # LED startup sequence - blink twice
        blink_led_startup()
        
        # Turn LED on and keep it on while code is running
        LED_PIN.on()
        print("LED is now on - indicates sensor is running")
        
        # Add delay for system stabilization (important for standalone operation)
        print("Waiting for system to stabilize...")
        time.sleep(2)
        
        # Connect to WiFi first
        if not connect_wifi():
            print("Cannot proceed without WiFi connection")
            led_error_code("wifi")  # 3 blinks for WiFi error
            return
        
        # Test network connectivity
        if not test_network_connectivity():
            print("Network connectivity issues detected")
            print("Attempting DNS troubleshooting...")
            configure_dns()
            print("Will continue but API calls may fail")
            print("Consider:")
            print("- Using a different WiFi network")
            print("- Using mobile hotspot for testing")
            print("- Contacting network administrator")
            print("- Using local development server")
        else:
            print("✓ Network connectivity looks good")
        
        print("Initializing I2C...")
        # Add delay before I2C initialization
        time.sleep(1)
        
        try:
            i2c = I2C(I2C_ID, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100_000)
            print(f"I2C initialized successfully on pins SDA={SDA_PIN}, SCL={SCL_PIN}")
            # Give I2C bus time to settle
            time.sleep(0.5)
        except Exception as e:
            print(f"Failed to initialize I2C: {e}")
            print(f"Error type: {type(e).__name__}")
            if hasattr(e, 'errno'):
                print(f"Error number: {e.errno}")
            led_error_code("i2c")  # 4 blinks for I2C error
            try:
                with open("error_log.txt", "a") as f:
                    f.write(f"I2C Init Error at {time.time()}: {e}\n")
            except:
                pass
            return
        
        # Scan for devices with retries
        print("Scanning for I2C devices...")
        devices = []
        max_retries = 3
        
        for attempt in range(max_retries):
            devices = scan_i2c_devices(i2c)
            if devices or attempt == max_retries - 1:
                break
            print(f"Scan attempt {attempt + 1} failed, retrying in 1 second...")
            time.sleep(1)
        
        # Check if SPS30 is present
        if ADDR not in devices:
            print(f"SPS30 not found at address {hex(ADDR)}")
            print("Check wiring:")
            print(f"- SDA: GPIO{SDA_PIN}")
            print(f"- SCL: GPIO{SCL_PIN}")
            print("- VCC: 5V (SPS30 requires 5V)")
            print("- GND: Ground")
            print("- Pull-up resistors on SDA/SCL (usually built into Pico)")
            led_error_code("sensor")  # 5 blinks for sensor not found
            return
        
        print(f"SPS30 found at {hex(ADDR)}")
        
        # Test basic communication
        print("Testing SPS30 communication...")
        if not test_i2c_connection(i2c, ADDR):
            print("Cannot communicate with SPS30")
            print("This could indicate:")
            print("- Faulty sensor")
            print("- Incorrect I2C address")
            print("- Power supply issues (ensure 5V, not 3.3V)")
            print("- Poor connections")
            led_error_code("sensor")  # 5 blinks for sensor communication error
            try:
                with open("error_log.txt", "a") as f:
                    f.write(f"SPS30 Communication Error at {time.time()}: Cannot communicate with sensor\n")
            except:
                pass
            return
        else:
            print("SPS30 communication test passed")
        
        sps = SPS30(i2c)
        
        # Try to stop any existing measurement first (sensor might be in unknown state)
        print("Resetting sensor state...")
        try:
            sps.stop_measurement()
            time.sleep(1)  # Give sensor time to stop
        except Exception:
            pass  # Ignore errors if sensor wasn't measuring
        
        print("Starting measurement...")
        # Add retry logic for starting measurement
        measurement_started = False
        for attempt in range(3):
            try:
                # Start measurement in float mode
                sps.start_measurement_float()
                print("Measurement started successfully!")
                measurement_started = True
                break
            except OSError as e:
                print(f"Attempt {attempt + 1} failed: {e} (errno: {e.errno})")
                if attempt < 2:  # Don't sleep on last attempt
                    print("Retrying in 2 seconds...")
                    time.sleep(2)
        
        if not measurement_started:
            print("Failed to start measurement after 3 attempts")
            led_error_code("sensor")  # 5 blinks for measurement start error
            try:
                with open("error_log.txt", "a") as f:
                    f.write(f"Measurement Start Failed after retries at {time.time()}\n")
            except:
                pass
            return

        # Warm-up: sensor specifies ~1 s cadence; stable startup may take several seconds.
        # Give extra time for standalone operation
        print("Waiting for sensor to stabilize (10 seconds)...")
        t0 = time.ticks_ms()
        sensor_ready = False
        
        while time.ticks_diff(time.ticks_ms(), t0) < 10000:  # Wait up to 10 seconds
            try:
                if sps.read_data_ready():
                    sensor_ready = True
                    print("Sensor is ready!")
                    break
            except Exception as e:
                print(f"Error checking sensor ready state: {e}")
            time.sleep_ms(500)  # Check every 500ms
        
        if not sensor_ready:
            print("Warning: Sensor may not be fully ready, continuing anyway...")

        print("Starting particle data collection and API transmission...")
        if SCHEDULED_SENDING:
            print(f"Reading sensor data every {MEASUREMENT_PERIOD_S} seconds")
            print(f"Sending data to API every {SEND_INTERVAL_MINUTES} minutes at exact intervals (:00, :{SEND_INTERVAL_MINUTES:02d}, :{SEND_INTERVAL_MINUTES*2:02d}, :{SEND_INTERVAL_MINUTES*3:02d})")
            next_send_time = calculate_next_send_time()
            print(f"Next scheduled send: {format_local_time(next_send_time)}")
        else:
            print(f"Sending data every {MEASUREMENT_PERIOD_S} seconds")
        print("-" * 60)

        try:
            latest_vals = None
            while True:
                # Read sensor data
                vals = sps.read_measured_values_float()
                latest_vals = vals
                
                # Determine if we should send data
                should_send = False
                
                if SCHEDULED_SENDING:
                    current_utc = time.time()
                    current_local = current_utc + (UTC_OFFSET_HOURS * 3600)
                    
                    # Check if it's time to send
                    if current_local >= next_send_time:
                        should_send = True
                        next_send_time = calculate_next_send_time()
                        print(f"\nScheduled send time reached. Next send: {format_local_time(next_send_time)}")
                else:
                    # Send every cycle in non-scheduled mode
                    should_send = True
                
                if should_send:
                    # Send data to API
                    success = send_to_api(vals)
                    
                    if success:
                        # Also print a summary to console for local monitoring
                        mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
                        num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = vals
                        
                        # Convert to #/ft³ for display
                        num_PM0_5_ft3 = num_PM0_5 * CM3_TO_FT3
                        
                        print(f"✓ Room: {ROOM_NAME} | Sensor: {SENSOR_NUMBER} | "
                              f"Total particles: {round(num_PM0_5_ft3, 0)} #/ft³ | "
                              f"PM2.5 mass: {round(mass_PM2_5, 1)} µg/m³")
                    else:
                        print("Failed to send data to API - will retry next scheduled time")
                else:
                    # Just log the reading without sending
                    mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
                    num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = vals
                    num_PM0_5_ft3 = num_PM0_5 * CM3_TO_FT3
                    
                    current_time_str = format_local_time(time.time() + (UTC_OFFSET_HOURS * 3600))
                    print(f"[{current_time_str}] Reading: {round(num_PM0_5_ft3, 0)} #/ft³, PM2.5: {round(mass_PM2_5, 1)} µg/m³")

                time.sleep(MEASUREMENT_PERIOD_S)
        except KeyboardInterrupt:
            print("\nShutting down...")
            LED_PIN.off()  # Turn off LED when shutting down
        finally:
            try:
                sps.stop_measurement()
                LED_PIN.off()  # Ensure LED is off when program ends
            except Exception:
                pass 
    except Exception as e:
        print(f"Unexpected error in main(): {e}")
        led_error_code("general")  # 2 long blinks for general error
        # Optional: you could also print the error to a file for debugging
        try:
            with open("error_log.txt", "a") as f:
                f.write(f"Error at {time.time()}: {e}\n")
        except:
            pass 

if __name__ == "__main__":
    # Uncomment the next line to run network diagnostics only
    # test_network_connectivity(); exit()
    
    main()




