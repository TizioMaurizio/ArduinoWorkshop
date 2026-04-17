"""
Tests for the servo control protocol format.

Verifies that the "<channel>,<angle>\n" protocol matches what the Arduino
firmware expects, without touching the firmware itself.
"""

import re

import pytest

# Protocol constants (must match Arduino main.cpp)
MAX_CHANNELS = 16
MAX_ANGLE = 180
PROTOCOL_RE = re.compile(r"^(\d{1,2}),(\d{1,3})\n$")


def make_command(channel: int, angle: int) -> str:
    """Produce a protocol command string, same as Godot servo_controller.gd."""
    return f"{channel},{angle}\n"


def parse_command(raw: str) -> tuple[int, int]:
    """Parse a protocol command. Returns (channel, angle) or raises ValueError."""
    m = PROTOCOL_RE.match(raw)
    if not m:
        raise ValueError(f"Malformed command: {raw!r}")
    ch, ang = int(m.group(1)), int(m.group(2))
    if ch < 0 or ch >= MAX_CHANNELS:
        raise ValueError(f"Channel out of range: {ch}")
    if ang < 0 or ang > MAX_ANGLE:
        raise ValueError(f"Angle out of range: {ang}")
    return ch, ang


# ===========================================================================
#  Format tests
# ===========================================================================

class TestProtocolFormat:
    """Verify ASCII protocol format: '<channel>,<angle>\\n'"""

    def test_basic_format(self):
        cmd = make_command(0, 90)
        assert cmd == "0,90\n"

    def test_channel_0_angle_0(self):
        ch, ang = parse_command(make_command(0, 0))
        assert ch == 0
        assert ang == 0

    def test_channel_15_angle_180(self):
        ch, ang = parse_command(make_command(15, 180))
        assert ch == 15
        assert ang == 180

    def test_yaw_channel(self):
        """CH_YAW = 0 per servo_controller.gd"""
        cmd = make_command(0, 45)
        ch, _ = parse_command(cmd)
        assert ch == 0

    def test_roll_channel(self):
        """CH_ROLL = 3 per servo_controller.gd"""
        cmd = make_command(3, 135)
        ch, _ = parse_command(cmd)
        assert ch == 3

    def test_all_valid_channels(self):
        for ch in range(MAX_CHANNELS):
            cmd = make_command(ch, 90)
            parsed_ch, parsed_ang = parse_command(cmd)
            assert parsed_ch == ch
            assert parsed_ang == 90

    def test_all_boundary_angles(self):
        for ang in [0, 1, 89, 90, 91, 179, 180]:
            cmd = make_command(0, ang)
            _, parsed_ang = parse_command(cmd)
            assert parsed_ang == ang

    def test_newline_terminated(self):
        cmd = make_command(0, 90)
        assert cmd.endswith("\n")

    def test_no_carriage_return(self):
        cmd = make_command(3, 45)
        assert "\r" not in cmd

    def test_ascii_encodable(self):
        """Protocol must be pure ASCII for Arduino serial."""
        cmd = make_command(15, 180)
        cmd.encode("ascii")  # Raises UnicodeEncodeError if not ASCII


class TestProtocolReject:
    """Verify parser rejects invalid commands."""

    def test_channel_too_high(self):
        with pytest.raises(ValueError, match="Channel out of range"):
            parse_command("16,90\n")

    def test_negative_angle_format(self):
        """Negative angles don't match the regex (no minus sign)."""
        with pytest.raises(ValueError, match="Malformed"):
            parse_command("-1,90\n")

    def test_angle_too_high(self):
        with pytest.raises(ValueError, match="Angle out of range"):
            parse_command("0,181\n")

    def test_missing_newline(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_command("0,90")

    def test_missing_comma(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_command("090\n")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_command("")

    def test_extra_fields(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_command("0,90,1\n")

    def test_float_angle(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_command("0,90.5\n")
