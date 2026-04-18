"""Flash ESP32 in one shot — sync + flash without ever closing the port.

Usage: python flash_oneshot.py [COM4] [57600]

1. Opens COM4 once
2. Waits up to 120s for bootloader (you press RESET with IO0 grounded)
3. Immediately flashes without releasing the serial port
"""
import sys
import os
import time
import argparse

# Add esptool to path
ESPTOOL_DIR = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")),
    ".platformio", "packages", "tool-esptoolpy"
)
sys.path.insert(0, ESPTOOL_DIR)

import serial
from esptool.targets.esp32 import ESP32ROM
from esptool.cmds import write_flash
from esptool.loader import ESPLoader


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM4"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 57600

    build_dir = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".pio", "build", "esp32cam"
    ))
    fw_dir = os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        ".platformio", "packages", "framework-arduinoespressif32"
    )

    flash_files = [
        (0x1000, os.path.join(build_dir, "bootloader.bin")),
        (0x8000, os.path.join(build_dir, "partitions.bin")),
        (0xe000, os.path.join(fw_dir, "tools", "partitions", "boot_app0.bin")),
        (0x10000, os.path.join(build_dir, "firmware.bin")),
    ]

    for addr, path in flash_files:
        if not os.path.exists(path):
            print("MISSING: %s" % path)
            sys.exit(1)

    fw_size = os.path.getsize(flash_files[-1][1])
    print("=" * 60)
    print("ESP32 One-Shot Flasher (no-stub, %d baud)" % baud)
    print("=" * 60)
    print("Port: %s" % port)
    print("Firmware: %d bytes" % fw_size)
    print()
    print("Press ESP32 RESET with IO0 grounded. You have 120 seconds.")
    print()

    # Phase 1: Open port and create ESP32ROM loader on it
    # ESPLoader.__init__ accepts a serial port string or object
    # We pass the string and let it open the port.
    # Then connect() will send sync and wait.
    #
    # The key: connect("no_reset") tries multiple sync rounds
    # without toggling DTR/RTS, giving ~10s per attempt.
    # With connect_attempts=12, that's ~120 seconds total.

    esp = ESP32ROM(port, baud)
    esp.CHIP_DETECT_MAGIC_REG_ADDR = 0x40001000  # standard

    print("Waiting for bootloader sync (up to 120s)...")
    print(">>> PRESS RESET NOW <<<")
    print()

    try:
        esp.connect("no_reset", attempts=12)
    except Exception as e:
        print("Failed to connect: %s" % e)
        sys.exit(1)

    print()
    print("Connected! Chip: %s" % esp.get_chip_description())
    print("MAC: %s" % ':'.join('%02x' % b for b in esp.read_mac()))
    print("Flash size: %s" % esp.flash_id())
    print()

    # Mark as no-stub mode
    esp.stub_is_disabled = True

    # Phase 2: Flash
    print("Starting flash at %d baud (no-stub, will be slow)..." % baud)
    print()

    file_handles = []
    addr_filename = []
    for addr, path in flash_files:
        fh = open(path, 'rb')
        file_handles.append(fh)
        addr_filename.append((addr, fh))

    args = argparse.Namespace(
        flash_mode="dio",
        flash_freq="keep",
        flash_size="4MB",
        addr_filename=addr_filename,
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
        print("Remove IO0-GND jumper, then press RESET to boot normally.")
        print("=" * 60)
    except Exception as e:
        print()
        print("FLASH FAILED: %s" % e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        for fh in file_handles:
            fh.close()
        try:
            esp._port.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
