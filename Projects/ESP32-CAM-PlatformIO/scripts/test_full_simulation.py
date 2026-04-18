#!/usr/bin/env python3
"""Discrete simulation of the full Godot → ESP32 → Arduino → Servo chain.

No hardware, no network. Pure Python. Every component is simulated as a
class with tick()-based state machines that mirror the real firmware
line-by-line. Use this to:

  1. Verify protocol correctness before flashing
  2. Debug timing/parsing issues
  3. Test edge cases (overflow, bad packets, packet loss, etc.)

Architecture:
    GodotSim  →  [UDP buffer]  →  ESP32Sim  →  [UART buffer]  →  ArduinoSim  →  ServoBank

Usage:
    python test_full_simulation.py                     # default sweep
    python test_full_simulation.py --chaos             # inject bad packets
    python test_full_simulation.py --drop-rate 0.1     # 10% UDP packet loss
    python test_full_simulation.py --ticks 500         # run for 500 ticks
    python test_full_simulation.py --speed 0           # max speed (no delay)
"""

import argparse
import random
import sys
import time
import os
from dataclasses import dataclass, field
from typing import Optional

# Fix Windows console encoding for Unicode box-drawing characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ═══════════════════════════════════════════════════════════════════════════
#  UART buffer — simulates a serial line between two chips
# ═══════════════════════════════════════════════════════════════════════════

class UARTBuffer:
    """Byte-level FIFO simulating a serial line. Models the real 64-byte
    hardware buffer on ATmega328P and ESP32 UART."""

    def __init__(self, name: str, capacity: int = 64):
        self.name = name
        self.capacity = capacity
        self._buf = bytearray()
        self.total_bytes = 0
        self.dropped_bytes = 0

    def write(self, data: bytes):
        for b in data:
            if len(self._buf) < self.capacity:
                self._buf.append(b)
                self.total_bytes += 1
            else:
                self.dropped_bytes += 1

    def available(self) -> int:
        return len(self._buf)

    def read_byte(self) -> Optional[int]:
        if self._buf:
            return self._buf.pop(0)
        return None

    def read_line(self) -> Optional[str]:
        """Read up to and including \\n. Returns None if no complete line."""
        try:
            idx = self._buf.index(ord('\n'))
        except ValueError:
            return None
        line = bytes(self._buf[:idx]).decode('utf-8', errors='replace')
        del self._buf[:idx + 1]
        return line


# ═══════════════════════════════════════════════════════════════════════════
#  UDP buffer — simulates network packets (each packet is atomic)
# ═══════════════════════════════════════════════════════════════════════════

class UDPBuffer:
    """Packet-level FIFO simulating UDP socket. Unlike UART, packets are
    atomic — no partial delivery, but can be lost entirely."""

    def __init__(self, name: str, drop_rate: float = 0.0):
        self.name = name
        self.drop_rate = drop_rate
        self._packets: list[bytes] = []
        self.total_sent = 0
        self.total_received = 0
        self.total_dropped = 0

    def send(self, data: bytes):
        self.total_sent += 1
        if random.random() < self.drop_rate:
            self.total_dropped += 1
            return
        self._packets.append(data)

    def recv(self) -> Optional[bytes]:
        if self._packets:
            self.total_received += 1
            return self._packets.pop(0)
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  Servo bank — simulates PCA9685 + physical servos
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Servo:
    channel: int
    angle: int = 90
    target: int = 90
    update_count: int = 0
    pulse_us: int = 1500  # microseconds

    def set_angle(self, angle: int):
        self.target = angle
        self.angle = angle
        self.update_count += 1
        # PCA9685 pulse: 500µs (0°) to 2500µs (180°)
        self.pulse_us = 500 + (angle * 2000 // 180)


class ServoBank:
    """Simulates PCA9685 with 16 servo channels."""

    def __init__(self):
        self.servos = [Servo(channel=i) for i in range(16)]
        self.i2c_writes = 0

    def set_pwm(self, channel: int, angle: int):
        if 0 <= channel < 16 and 0 <= angle <= 180:
            self.servos[channel].set_angle(angle)
            self.i2c_writes += 1


# ═══════════════════════════════════════════════════════════════════════════
#  Godot simulator — sends angle commands like servo_controller.gd
# ═══════════════════════════════════════════════════════════════════════════

class GodotSim:
    """Mirrors servo_controller.gd: quaternion-to-angle, deadband, rate limit."""

    CH_YAW = 0
    CH_PITCH = 3

    def __init__(self, udp_out: UDPBuffer, send_rate_hz: float = 20.0,
                 deadband: int = 1):
        self.udp = udp_out
        self.send_interval = 1.0 / send_rate_hz
        self.deadband = deadband
        self.timer = 0.0
        self.last_yaw = -1
        self.last_pitch = -1
        self.total_sent = 0
        # Simulated head angles (degrees)
        self.yaw = 0.0
        self.pitch = 0.0
        self._yaw_speed = 1.5   # deg/tick
        self._pitch_speed = 0.7
        self._yaw_dir = 1
        self._pitch_dir = 1

    def tick(self, dt: float):
        """Called each simulation tick."""
        # Simulate head movement — sweep pattern
        self.yaw += self._yaw_speed * self._yaw_dir
        if self.yaw >= 90 or self.yaw <= -90:
            self._yaw_dir *= -1
            self.yaw += self._yaw_speed * self._yaw_dir

        self.pitch += self._pitch_speed * self._pitch_dir
        if self.pitch >= 45 or self.pitch <= -45:
            self._pitch_dir *= -1
            self.pitch += self._pitch_speed * self._pitch_dir

        # Rate limit
        self.timer += dt
        if self.timer < self.send_interval:
            return
        self.timer -= self.send_interval

        # Map to servo angles (mirrors _map_clamp in GDScript)
        yaw_servo = self._map_clamp(self.yaw, -90, 90, 0, 180)
        pitch_servo = self._map_clamp(self.pitch, -45, 45, 0, 180)

        # Deadband filter
        if abs(yaw_servo - self.last_yaw) >= self.deadband:
            self._send(self.CH_YAW, yaw_servo)
            self.last_yaw = yaw_servo

        if abs(pitch_servo - self.last_pitch) >= self.deadband:
            self._send(self.CH_PITCH, pitch_servo)
            self.last_pitch = pitch_servo

    def _send(self, channel: int, angle: int):
        msg = f"{channel},{angle}\n"
        self.udp.send(msg.encode())
        self.total_sent += 1

    @staticmethod
    def _map_clamp(value: float, in_min: float, in_max: float,
                   out_min: int, out_max: int) -> int:
        clamped = max(in_min, min(in_max, value))
        t = (clamped - in_min) / (in_max - in_min)
        return round(out_min + t * (out_max - out_min))


# ═══════════════════════════════════════════════════════════════════════════
#  ESP32 simulator — receives UDP, forwards to UART2
# ═══════════════════════════════════════════════════════════════════════════

class ESP32Sim:
    """Mirrors main.cpp: reads UDP packets, prints to ArduinoSerial (UART2)."""

    def __init__(self, udp_in: UDPBuffer, uart_out: UARTBuffer,
                 debug_uart: Optional[UARTBuffer] = None):
        self.udp = udp_in
        self.uart_out = uart_out
        self.debug = debug_uart  # UART0 debug (optional)
        self.total_forwarded = 0
        self.wifi_connected = True  # assume connected

    def tick(self, dt: float):
        """Called each simulation tick — mirrors loop() in main.cpp."""
        if not self.wifi_connected:
            return

        # Read one UDP packet per tick (like parsePacket() + read())
        packet = self.udp.recv()
        if packet is not None:
            text = packet.decode('utf-8', errors='replace')
            # Forward to Arduino UART — exact mirror of Serial.print(buf)
            self.uart_out.write(text.encode())
            self.total_forwarded += 1

            # Debug echo — mirror of Serial.printf("[FWD] %s", buf)
            if self.debug:
                self.debug.write(f"[FWD] {text}".encode())


# ═══════════════════════════════════════════════════════════════════════════
#  Arduino simulator — parses serial, drives PCA9685
# ═══════════════════════════════════════════════════════════════════════════

class ArduinoSim:
    """Mirrors PCA9685-ServoController main.cpp: serial_readline() +
    parse_and_execute()."""

    RX_BUF_SIZE = 16

    def __init__(self, uart_in: UARTBuffer, uart_out: UARTBuffer,
                 servo_bank: ServoBank):
        self.uart_in = uart_in
        self.uart_out = uart_out
        self.servos = servo_bank
        self.rx_buf = ""
        self.total_ok = 0
        self.total_err = 0

    def tick(self, dt: float):
        """Called each simulation tick — mirrors loop() in main.cpp."""
        # Non-blocking serial line reader (mirrors serial_readline)
        while self.uart_in.available() > 0:
            byte_val = self.uart_in.read_byte()
            if byte_val is None:
                break
            c = chr(byte_val)

            if c == '\n' or c == '\r':
                if len(self.rx_buf) > 0:
                    self._parse_and_execute(self.rx_buf)
                    self.rx_buf = ""
                continue

            if len(self.rx_buf) < self.RX_BUF_SIZE - 1:
                self.rx_buf += c
            else:
                self.rx_buf = ""
                self._reply("ERR:overflow")
                self.total_err += 1

    def _parse_and_execute(self, line: str):
        """Mirror of parse_and_execute() in firmware."""
        comma = line.find(',')
        if comma < 0:
            self._reply("ERR:no comma")
            self.total_err += 1
            return

        try:
            channel = int(line[:comma])
        except ValueError:
            self._reply("ERR:bad ch")
            self.total_err += 1
            return

        try:
            angle = int(line[comma + 1:])
        except ValueError:
            self._reply("ERR:bad angle")
            self.total_err += 1
            return

        if channel < 0 or channel >= 16:
            self._reply("ERR:ch 0-15")
            self.total_err += 1
            return

        if angle < 0 or angle > 180:
            self._reply("ERR:ang 0-180")
            self.total_err += 1
            return

        self.servos.set_pwm(channel, angle)
        self._reply("OK")
        self.total_ok += 1

    def _reply(self, msg: str):
        self.uart_out.write(f"{msg}\n".encode())


# ═══════════════════════════════════════════════════════════════════════════
#  Chaos injector — generates malformed packets
# ═══════════════════════════════════════════════════════════════════════════

class ChaosInjector:
    """Injects bad packets into the UDP stream to test error handling."""

    BAD_PACKETS = [
        b"hello\n",           # no comma
        b"99,90\n",           # bad channel
        b"0,999\n",           # bad angle
        b"0,-1\n",            # negative angle
        b"\n",                # empty
        b"0,90\n0,91\n",     # two commands in one packet
        b"abc,def\n",         # non-numeric
        b"0,90",              # no newline
        b",,,,\n",            # garbage
        b"0,90\n3,45\n0,91\n",  # triple command
    ]

    def __init__(self, udp: UDPBuffer, every_n_ticks: int = 50):
        self.udp = udp
        self.every_n = every_n_ticks
        self.tick_count = 0
        self.injected = 0

    def tick(self):
        self.tick_count += 1
        if self.tick_count % self.every_n == 0:
            pkt = random.choice(self.BAD_PACKETS)
            self.udp.send(pkt)
            self.injected += 1


# ═══════════════════════════════════════════════════════════════════════════
#  Dashboard renderer
# ═══════════════════════════════════════════════════════════════════════════

def render(tick: int, dt: float, godot: GodotSim, esp: ESP32Sim,
           arduino: ArduinoSim, servos: ServoBank,
           udp_net: UDPBuffer, uart_esp_ard: UARTBuffer,
           chaos: Optional[ChaosInjector] = None):
    """Render the full system state."""

    elapsed = tick * dt

    lines = []
    lines.append("\033[2J\033[H")  # clear screen
    lines.append("╔══════════════════════════════════════════════════════════════════╗")
    lines.append("║         FULL SYSTEM DISCRETE SIMULATION                        ║")
    lines.append("╠══════════════════════════════════════════════════════════════════╣")
    lines.append(f"║  Tick: {tick:>6d}  Time: {elapsed:>7.1f}s  dt={dt*1000:.0f}ms/tick"
                 f"{'':>18s}║")
    lines.append("╠══════════════════════════════════════════════════════════════════╣")

    # Godot
    lines.append(f"║  GODOT    head=({godot.yaw:>+6.1f}°, {godot.pitch:>+5.1f}°)"
                 f"  sent={godot.total_sent:>5d} pkts"
                 f"{'':>12s}║")

    # UDP
    loss_pct = (udp_net.total_dropped / udp_net.total_sent * 100
                if udp_net.total_sent > 0 else 0)
    lines.append(f"║  UDP      sent={udp_net.total_sent:>5d}  "
                 f"recv={udp_net.total_received:>5d}  "
                 f"drop={udp_net.total_dropped:>3d} ({loss_pct:.0f}%)"
                 f"{'':>9s}║")

    # ESP32
    lines.append(f"║  ESP32    fwd={esp.total_forwarded:>5d}  "
                 f"wifi={'ON ' if esp.wifi_connected else 'OFF'}"
                 f"{'':>34s}║")

    # UART
    lines.append(f"║  UART     buf={uart_esp_ard.available():>3d}/{uart_esp_ard.capacity}  "
                 f"total={uart_esp_ard.total_bytes:>6d}B  "
                 f"drop={uart_esp_ard.dropped_bytes:>3d}B"
                 f"{'':>10s}║")

    # Arduino
    lines.append(f"║  ARDUINO  ok={arduino.total_ok:>5d}  err={arduino.total_err:>3d}  "
                 f"i2c_writes={servos.i2c_writes:>5d}"
                 f"{'':>11s}║")

    if chaos:
        lines.append(f"║  CHAOS    injected={chaos.injected:>3d} bad packets"
                     f"{'':>28s}║")

    lines.append("╠══════════════════════════════════════════════════════════════════╣")
    lines.append("║  SERVOS                                                        ║")

    # Servo display
    active = [(s.channel, s) for s in servos.servos if s.update_count > 0]
    if not active:
        lines.append("║    (waiting for commands)                                      ║")
    else:
        for ch, s in active:
            name = {0: "YAW  ", 3: "PITCH"}.get(ch, f"CH{ch:>2d} ")
            w = 34
            pos = int(s.angle / 180 * w)
            bar = '─' * pos + '◆' + '─' * (w - pos)
            lines.append(f"║  {name} ├{bar}┤ {s.angle:>3d}° "
                         f"({s.pulse_us:>4d}µs) n={s.update_count:<4d}  ║")

    lines.append("╠══════════════════════════════════════════════════════════════════╣")

    # Consistency check
    issues = []
    if uart_esp_ard.dropped_bytes > 0:
        issues.append(f"UART overflow: {uart_esp_ard.dropped_bytes} bytes lost")
    if arduino.total_err > 0:
        issues.append(f"Parse errors: {arduino.total_err}")
    if udp_net.total_dropped > 0:
        issues.append(f"UDP packet loss: {udp_net.total_dropped}")

    # Success rate
    total_attempted = arduino.total_ok + arduino.total_err
    success_rate = (arduino.total_ok / total_attempted * 100
                    if total_attempted > 0 else 0)

    if not issues:
        lines.append(f"║  ✓ ALL CLEAR  success={success_rate:.0f}%"
                     f"{'':>38s}║")
    else:
        for issue in issues[:3]:
            lines.append(f"║  ⚠ {issue:<60s}║")
        lines.append(f"║  success={success_rate:.1f}%"
                     f"{'':>51s}║")

    lines.append("╚══════════════════════════════════════════════════════════════════╝")

    sys.stdout.write('\n'.join(lines))
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════════
#  Main simulation loop
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Discrete simulation: Godot → ESP32 → Arduino → Servos")
    parser.add_argument("--ticks", type=int, default=2000,
                        help="Number of simulation ticks (default 2000)")
    parser.add_argument("--dt", type=float, default=0.005,
                        help="Simulated seconds per tick (default 0.005 = 200Hz)")
    parser.add_argument("--speed", type=float, default=0.01,
                        help="Real seconds between ticks for display (0=max speed)")
    parser.add_argument("--drop-rate", type=float, default=0.0,
                        help="UDP packet loss rate 0.0-1.0 (default 0)")
    parser.add_argument("--chaos", action="store_true",
                        help="Inject malformed packets to test error handling")
    parser.add_argument("--uart-size", type=int, default=64,
                        help="UART buffer size in bytes (default 64)")
    parser.add_argument("--render-every", type=int, default=10,
                        help="Render dashboard every N ticks (default 10)")
    args = parser.parse_args()

    # --- Wire up the system ---
    udp_net = UDPBuffer("WiFi-UDP", drop_rate=args.drop_rate)
    uart_esp_to_arduino = UARTBuffer("UART2-GPIO13", capacity=args.uart_size)
    uart_arduino_to_esp = UARTBuffer("UART2-RX", capacity=args.uart_size)
    debug_uart = UARTBuffer("UART0-USB", capacity=256)

    servo_bank = ServoBank()

    godot = GodotSim(udp_out=udp_net, send_rate_hz=20.0, deadband=1)
    esp32 = ESP32Sim(udp_in=udp_net, uart_out=uart_esp_to_arduino,
                     debug_uart=debug_uart)
    arduino = ArduinoSim(uart_in=uart_esp_to_arduino,
                         uart_out=uart_arduino_to_esp,
                         servo_bank=servo_bank)

    chaos = ChaosInjector(udp_net, every_n_ticks=50) if args.chaos else None

    print(f"[SIM] Running {args.ticks} ticks, dt={args.dt}s, "
          f"drop={args.drop_rate:.0%}, chaos={'ON' if chaos else 'OFF'}")
    time.sleep(0.5)

    # --- Run ---
    try:
        for tick in range(args.ticks):
            # Tick all components in causal order
            godot.tick(args.dt)
            if chaos:
                chaos.tick()
            esp32.tick(args.dt)
            arduino.tick(args.dt)

            # Render
            if tick % args.render_every == 0:
                render(tick, args.dt, godot, esp32, arduino, servo_bank,
                       udp_net, uart_esp_to_arduino, chaos)

            if args.speed > 0:
                time.sleep(args.speed)

    except KeyboardInterrupt:
        pass

    # Final render
    render(args.ticks, args.dt, godot, esp32, arduino, servo_bank,
           udp_net, uart_esp_to_arduino, chaos)

    # --- Summary ---
    print("\n\n" + "=" * 60)
    print("  SIMULATION COMPLETE")
    print("=" * 60)
    print(f"  Ticks:          {args.ticks}")
    print(f"  Sim time:       {args.ticks * args.dt:.1f}s")
    print(f"  Godot sent:     {godot.total_sent} packets")
    print(f"  UDP delivered:  {udp_net.total_received} / {udp_net.total_sent}"
          f" ({udp_net.total_dropped} dropped)")
    print(f"  ESP forwarded:  {esp32.total_forwarded}")
    print(f"  Arduino OK:     {arduino.total_ok}")
    print(f"  Arduino ERR:    {arduino.total_err}")
    print(f"  I2C writes:     {servo_bank.i2c_writes}")
    print(f"  UART overflow:  {uart_esp_to_arduino.dropped_bytes} bytes")
    if chaos:
        print(f"  Chaos injected: {chaos.injected} bad packets")

    total = arduino.total_ok + arduino.total_err
    if total > 0:
        print(f"  Success rate:   {arduino.total_ok / total * 100:.1f}%")

    # Check for issues
    issues = []
    if uart_esp_to_arduino.dropped_bytes > 0:
        issues.append("UART buffer overflow detected — consider larger buffer or slower send rate")
    if arduino.total_err > 0 and not args.chaos:
        issues.append(f"{arduino.total_err} parse errors without chaos — protocol bug?")
    if godot.total_sent > 0 and arduino.total_ok == 0:
        issues.append("Zero successful commands — full chain broken")

    if issues:
        print("\n  ISSUES:")
        for i in issues:
            print(f"    ⚠ {i}")
    else:
        print("\n  ✓ No issues detected")

    print("=" * 60)
    sys.exit(1 if issues and not args.chaos else 0)


if __name__ == "__main__":
    main()
