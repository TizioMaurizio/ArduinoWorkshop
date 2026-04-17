"""
Tests for the UDP-to-Serial bridge.

Uses a mock serial port and real UDP loopback to verify the bridge
forwards packets correctly without requiring Arduino hardware.
"""

import io
import socket
import threading
import time
from typing import Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
#  Helpers: extract bridge forwarding logic for isolated testing
# ---------------------------------------------------------------------------

def bridge_forward(udp_data: bytes, serial_write: callable,
                   serial_readline: callable) -> Optional[str]:
    """
    Simulate one iteration of bridge forwarding.
    Returns the Arduino response (if any) or None.
    """
    if udp_data:
        serial_write(udp_data)
        resp = serial_readline()
        return resp
    return None


# ===========================================================================
#  Bridge forwarding logic
# ===========================================================================

class TestBridgeForward:
    """Test that UDP packets are forwarded to serial and responses are read."""

    def test_forward_valid_command(self):
        written = bytearray()

        def mock_write(data: bytes):
            written.extend(data)

        def mock_readline() -> str:
            return "OK"

        resp = bridge_forward(b"0,90\n", mock_write, mock_readline)
        assert bytes(written) == b"0,90\n"
        assert resp == "OK"

    def test_forward_multiple_channels(self):
        for ch in [0, 3]:
            written = bytearray()

            def mock_write(data: bytes):
                written.extend(data)

            resp = bridge_forward(
                f"{ch},90\n".encode("ascii"),
                mock_write,
                lambda: "OK",
            )
            assert f"{ch},90\n".encode("ascii") == bytes(written)
            assert resp == "OK"

    def test_error_response_detected(self):
        resp = bridge_forward(
            b"16,90\n",
            lambda d: None,
            lambda: "ERR:ch 0-15",
        )
        assert resp is not None
        assert resp.startswith("ERR")

    def test_empty_udp_packet_ignored(self):
        called = False

        def mock_write(data: bytes):
            nonlocal called
            called = True

        resp = bridge_forward(b"", mock_write, lambda: "")
        # Empty data should not trigger write
        assert resp is None
        assert not called


# ===========================================================================
#  UDP socket integration (loopback, no serial hardware)
# ===========================================================================

class TestUdpLoopback:
    """Verify UDP packet delivery on localhost — the Godot→bridge link."""

    BRIDGE_PORT = 0  # OS-assigned

    def test_single_packet_delivery(self):
        """A single UDP packet arrives intact."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.settimeout(1.0)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(b"0,90\n", ("127.0.0.1", port))

        data, _ = sock.recvfrom(256)
        assert data == b"0,90\n"

        sender.close()
        sock.close()

    def test_rapid_packets_ordering(self):
        """Multiple packets arrive in order (loopback, no loss expected)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.settimeout(1.0)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        expected = []
        for angle in range(0, 181, 10):
            msg = f"0,{angle}\n".encode("ascii")
            sender.sendto(msg, ("127.0.0.1", port))
            expected.append(msg)

        received = []
        for _ in range(len(expected)):
            data, _ = sock.recvfrom(256)
            received.append(data)

        assert received == expected

        sender.close()
        sock.close()

    def test_both_channels_interleaved(self):
        """Yaw and roll packets interleaved, each arrives correctly."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.settimeout(1.0)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        packets = [b"0,45\n", b"3,90\n", b"0,50\n", b"3,85\n"]
        for pkt in packets:
            sender.sendto(pkt, ("127.0.0.1", port))

        received = []
        for _ in range(len(packets)):
            data, _ = sock.recvfrom(256)
            received.append(data)

        assert received == packets

        sender.close()
        sock.close()

    def test_packet_is_ascii(self):
        """All packets must be decodable as ASCII (Arduino serial requirement)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.settimeout(1.0)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(b"3,135\n", ("127.0.0.1", port))

        data, _ = sock.recvfrom(256)
        text = data.decode("ascii")  # raises if not ASCII
        assert text == "3,135\n"

        sender.close()
        sock.close()


# ===========================================================================
#  Deadband / rate limiting (tests matching servo_controller.gd behavior)
# ===========================================================================

class TestDeadband:
    """
    servo_controller.gd only sends when angle changes by >= deadband_deg (1°).
    Verify the logic: send only if |new - last| >= deadband.
    """

    DEADBAND = 1  # matches @export default

    @staticmethod
    def should_send(new_angle: int, last_angle: int, deadband: int = 1) -> bool:
        """Replicate GDScript:  absi(yaw_servo - _last_yaw_angle) >= int(deadband_deg)"""
        if last_angle < 0:  # first send (initial _last = -1)
            return True
        return abs(new_angle - last_angle) >= deadband

    def test_first_send_always(self):
        assert self.should_send(90, -1)

    def test_same_angle_suppressed(self):
        assert not self.should_send(90, 90)

    def test_change_of_1_triggers(self):
        assert self.should_send(91, 90)

    def test_change_below_deadband_suppressed(self):
        # With deadband=1, a change of 0 is suppressed (only possible case)
        assert not self.should_send(90, 90)

    def test_large_change_triggers(self):
        assert self.should_send(0, 180)

    def test_negative_direction_triggers(self):
        assert self.should_send(89, 90)
