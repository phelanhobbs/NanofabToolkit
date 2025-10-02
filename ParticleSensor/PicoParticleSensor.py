# MicroPython SPS30 (I2C) minimal driver + CLI for Raspberry Pi Pico (RP2040)
# Prints number concentration: cumulative (>= thresholds) and binned ranges.

import time
import struct
from machine import I2C, Pin

# ===== User config =====
I2C_ID = 0          # 0 or 1
SDA_PIN = 4         # GP4 for I2C0
SCL_PIN = 5         # GP5 for I2C0
ADDR    = 0x69      # SPS30 I2C address
PRINT_PERIOD_S = 1  # SPS30 updates every ~1 s

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
        b0, b1 = 0x03, 0x00
        crc = _crc8_word(b0, b1)
        self._write_ptr_with_data(PTR_START_MEAS, bytes([b0, b1, crc]))

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
    devices = i2c.scan()
    if devices:
        print(f"Found devices at addresses: {[hex(addr) for addr in devices]}")
    else:
        print("No I2C devices found!")
    return devices

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

def main():
    print("Initializing I2C...")
    try:
        i2c = I2C(I2C_ID, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100_000)
    except Exception as e:
        print(f"Failed to initialize I2C: {e}")
        return
    
    # Scan for devices
    devices = scan_i2c_devices(i2c)
    
    # Check if SPS30 is present
    if ADDR not in devices:
        print(f"SPS30 not found at address {hex(ADDR)}")
        print("Check wiring:")
        print(f"- SDA: GPIO{SDA_PIN}")
        print(f"- SCL: GPIO{SCL_PIN}")
        print("- VCC: 5V (SPS30 requires 5V)")
        print("- GND: Ground")
        print("- Pull-up resistors on SDA/SCL (usually built into Pico)")
        return
    
    print(f"SPS30 found at {hex(ADDR)}")
    
    # Test basic communication
    if not test_i2c_connection(i2c, ADDR):
        print("Cannot communicate with SPS30")
        return
    
    sps = SPS30(i2c)
    
    print("Starting measurement...")
    try:
        # Start measurement in float mode
        sps.start_measurement_float()
        print("Measurement started successfully!")
    except OSError as e:
        print(f"Failed to start measurement: {e}")
        if e.errno == 5:
            print("This could indicate:")
            print("- SPS30 is already measuring (try stopping first)")
            print("- Power supply issues")
            print("- Faulty sensor")
        return

    # Warm-up: sensor specifies ~1 s cadence; stable startup may take several seconds.
    # We'll just wait for first ready flag and go.
    t0 = time.ticks_ms()
    while not sps.read_data_ready():
        if time.ticks_diff(time.ticks_ms(), t0) > 5000:
            # If the flag isn't toggling, still proceed (some stacks poll less reliably).
            break
        time.sleep_ms(100)

    # Header
    print("SPS30 number concentration (#/cm^3)")
    print("Bins: [0.3–0.5] [0.5–1] [1–2.5] [2.5–4] [4–10] | Cumulative: [>=0.3] [>=0.5] [>=1] [>=4] [>=10]")
    print("-" * 100)

    try:
        while True:
            # Optionally poll data-ready (not strictly required)
            # if not sps.read_data_ready(): time.sleep_ms(50); continue

            vals = sps.read_measured_values_float()
            # Unpack fields per datasheet order
            mass_PM1, mass_PM2_5, mass_PM4, mass_PM10, \
            num_PM0_5, num_PM1, num_PM2_5, num_PM4, num_PM10, tps_um = vals

            # Differential (disjoint) bins derived from cumulative-to-upper-edge channels:
            # B0: 0.3–0.5       = PM0.5
            # B1: 0.5–1.0       = PM1.0  - PM0.5
            # B2: 1.0–2.5       = PM2.5  - PM1.0
            # B3: 2.5–4.0       = PM4.0  - PM2.5
            # B4: 4.0–10.0      = PM10   - PM4.0
            b0 = max(num_PM0_5, 0.0)
            b1 = max(num_PM1 - num_PM0_5, 0.0)
            b2 = max(num_PM2_5 - num_PM1, 0.0)
            b3 = max(num_PM4 - num_PM2_5, 0.0)
            b4 = max(num_PM10 - num_PM4, 0.0)

            # Cumulative (>= threshold) using the available cutoffs:
            # >=0.3 = PM10, >=0.5 = PM10 - PM0.5, >=1 = PM10 - PM1.0, >=4 = PM10 - PM4.0, >=10 ~= 0 (upper edge)
            c03 = max(num_PM10, 0.0)
            c05 = max(num_PM10 - num_PM0_5, 0.0)
            c1  = max(num_PM10 - num_PM1,   0.0)
            c4  = max(num_PM10 - num_PM4,   0.0)
            c10 = 0.0  # upper limit is 10 µm; there's no ">=10" bin within SPS30's range

            # Print one line
            line = (
                f"{format_row(b0)} {format_row(b1)} {format_row(b2)} {format_row(b3)} {format_row(b4)} |"
                f" {format_row(c03)} {format_row(c05)} {format_row(c1)} {format_row(c4)} {format_row(c10)}"
            )
            print(line)

            # Optional: also show typical particle size (µm) now and then
            # print("TPS: {:.2f} µm".format(tps_um))

            time.sleep(PRINT_PERIOD_S)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sps.stop_measurement()
        except Exception:
            pass 

if __name__ == "__main__":
    main()


