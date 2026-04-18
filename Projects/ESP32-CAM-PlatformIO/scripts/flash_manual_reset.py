"""Flash ESP32 via Arduino passthrough with manual RESET timing.

Waits indefinitely for the bootloader to respond (user presses RESET
whenever ready), then flashes using esptool's internal API WITHOUT
releasing the serial port.

Usage:
    python flash_manual_reset.py [COM4] [baud]
"""

import sys
import os
import struct
import time
import argparse
import serial

# Add esptool to path
ESPTOOL_DIR = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")),
    ".platformio", "packages", "tool-esptoolpy"
)
sys.path.insert(0, ESPTOOL_DIR)

from esptool.targets.esp32 import ESP32ROM
from esptool.cmds import write_flash


def build_sync_packet():
    """Build a SLIP-encoded sync packet for ESP32 ROM bootloader."""
    sync_payload = b'\x07\x07\x12\x20' + (b'\x55' * 32)
    size = len(sync_payload)
    hdr = struct.pack('<BBHI', 0x00, 0x08, size, 0)
    raw = hdr + sync_payload
    slip = b'\xc0'
    for b in raw:
        if b == 0xc0:
            slip += b'\xdb\xdc'
        elif b == 0xdb:
            slip += b'\xdb\xdd'
        else:
            slip += bytes([b])
    slip += b'\xc0'
    return slip


def wait_for_bootloader(ser, timeout=120):
    """Send sync packets on an open serial port until bootloader responds."""
    sync = build_sync_packet()
    ser.read(ser.in_waiting)  # flush

    print("Sending sync... press ESP32 RESET with IO0 grounded.")
    print("(Waiting up to %d seconds)" % timeout)

    start = time.time()
    attempt = 0
    while time.time() - start < timeout:
        attempt += 1
        ser.write(sync)
        time.sleep(0.05)
        resp = ser.read(200)
        if len(resp) > 0:
            print("\nBootloader responded at attempt %d! (%d bytes)" %
                  (attempt, len(resp)))
            return True
        if attempt % 20 == 0:
            elapsed = int(time.time() - start)
            print("  ...%ds elapsed, still waiting for RESET..." % elapsed)

    return False


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

    build_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", ".pio", "build", "esp32cam"
    )
    fw_dir = os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        ".platformio", "packages", "framework-arduinoespressif32"
    )

    firmware_bin = os.path.join(build_dir, "firmware.bin")
    bootloader_bin = os.path.join(build_dir, "bootloader.bin")
    partitions_bin = os.path.join(build_dir, "partitions.bin")
    boot_app0_bin = os.path.join(fw_dir, "tools", "partitions", "boot_app0.bin")

    for f in [firmware_bin, bootloader_bin, partitions_bin, boot_app0_bin]:
        if not os.path.exists(f):
            print("ERROR: Missing file: %s" % f)
            sys.exit(1)

    fw_size = os.path.getsize(firmware_bin)
    print("=" * 60)
    print("ESP32 Manual-Reset Flasher (no-stub, %d baud)" % baud)
    print("=" * 60)
    print("Port: %s" % port)
    print("Firmware: %s (%d bytes)" % (os.path.basename(firmware_bin), fw_size))
    print()

    # Open serial port ONCE — keep it open for the entire process
    ser = serial.serial_for_url(port)
    ser.baudrate = baud
    ser.timeout = 0.3
    time.sleep(0.1)

    # Phase 1: Wait for bootloader
    if not wait_for_bootloader(ser):
        print("ERROR: Bootloader did not respond. Check wiring.")
        ser.close()
        sys.exit(1)

    # Phase 2: Create ESP32ROM with the SAME serial port (no reopen!)
    print()
    print("Creating ESP32 loader on same connection...")

    # Flush any remaining sync responses
    ser.timeout = 0.1
    ser.read(1000)
    ser.timeout = 3.0

    esp = ESP32ROM(port=ser, baud=baud)
    esp.stub_is_disabled = True  # no-stub mode

    print("Connecting via esptool...")
    try:
        esp.connect(mode="no_reset_no_sync")
    except Exception as e:
        print("connect(no_reset_no_sync) failed: %s" % e)
        print("Trying no_reset...")
        try:
            ser.timeout = 0.3
            ser.read(1000)
            ser.timeout = 3.0
            esp._slip_reader = esp._slip_reader.__class__(ser, esp.trace)
            esp.connect(mode="no_reset")
        except Exception as e2:
            print("connect(no_reset) also failed: %s" % e2)
            ser.close()
            sys.exit(1)

    print("Chip: %s" % esp.get_chip_description())
    print("MAC: %s" % ':'.join('%02x' % b for b in esp.read_mac()))
    print()

    # Phase 3: Flash
    print("Starting flash (this will take a while at %d baud)..." % baud)
    print()

    # Build args namespace that write_flash expects
    flash_files = [
        (0x1000, bootloader_bin),
        (0x8000, partitions_bin),
        (0xe000, boot_app0_bin),
        (0x10000, firmware_bin),
    ]

    args = argparse.Namespace(
        flash_mode="dio",
        flash_freq="keep",
        flash_size="4MB",
        addr_filename=[(addr, open(fn, 'rb')) for addr, fn in flash_files],
        no_stub=True,
        compress=True,
        no_compress=False,
        no_progress=False,
        verify=False,
        encrypt=False,
        encrypt_files=None,
        force=False,
    )

    try:
        write_flash(esp, args)
        print()
        print("=" * 60)
        print("FLASH SUCCESSFUL!")
        print("Now: remove IO0-GND jumper, then press RESET to boot.")
        print("=" * 60)
    except Exception as e:
        print("\nFLASH FAILED: %s" % e)
        sys.exit(1)
    finally:
        for addr, fh in args.addr_filename:
            fh.close()
        ser.close()


if __name__ == "__main__":
    main()
