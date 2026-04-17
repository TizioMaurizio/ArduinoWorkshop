"""
Tests for the angle mapping logic.

Replicates the GDScript _map_clamp() function from servo_controller.gd
and verifies correctness across the full input range.
"""

import math

import pytest


# ---------------------------------------------------------------------------
#  Replicate GDScript _map_clamp exactly
# ---------------------------------------------------------------------------

def map_clamp(value: float, in_min: float, in_max: float,
              out_min: int, out_max: int) -> int:
    """Port of servo_controller.gd _map_clamp()."""
    clamped = max(in_min, min(in_max, value))
    t = (clamped - in_min) / (in_max - in_min)
    return round(out_min + (out_max - out_min) * t)


# Default ranges from servo_controller.gd @export vars
YAW_MIN = -90.0
YAW_MAX = 90.0
ROLL_MIN = -45.0
ROLL_MAX = 45.0
SERVO_MIN = 0
SERVO_MAX = 180


# ===========================================================================
#  Yaw mapping (Y rotation → CH 0)
# ===========================================================================

class TestYawMapping:
    """Head yaw (Y rotation) mapped to servo 0–180 on channel 0."""

    def test_center_yaw_maps_to_90(self):
        assert map_clamp(0.0, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX) == 90

    def test_full_left_maps_to_0(self):
        assert map_clamp(-90.0, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX) == 0

    def test_full_right_maps_to_180(self):
        assert map_clamp(90.0, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX) == 180

    def test_half_left(self):
        assert map_clamp(-45.0, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX) == 45

    def test_half_right(self):
        assert map_clamp(45.0, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX) == 135

    def test_beyond_max_clamps(self):
        """Head turned past 90° should clamp to servo 180."""
        assert map_clamp(120.0, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX) == 180

    def test_beyond_min_clamps(self):
        """Head turned past -90° should clamp to servo 0."""
        assert map_clamp(-120.0, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX) == 0

    def test_monotonic_increasing(self):
        """Servo angle must increase monotonically with yaw."""
        prev = -1
        for deg_x10 in range(-900, 901):
            deg = deg_x10 / 10.0
            result = map_clamp(deg, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX)
            assert result >= prev
            prev = result


# ===========================================================================
#  Roll mapping (Z rotation → CH 3)
# ===========================================================================

class TestRollMapping:
    """Head roll (Z rotation) mapped to servo 0–180 on channel 3."""

    def test_center_roll_maps_to_90(self):
        assert map_clamp(0.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX) == 90

    def test_full_left_tilt_maps_to_0(self):
        assert map_clamp(-45.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX) == 0

    def test_full_right_tilt_maps_to_180(self):
        assert map_clamp(45.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX) == 180

    def test_small_tilt_resolution(self):
        """1° of head roll = 2° of servo travel (90°/45° mapping ratio)."""
        a = map_clamp(0.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX)
        b = map_clamp(1.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX)
        assert b - a == 2  # 180/90 = 2:1 ratio

    def test_beyond_roll_limits_clamps(self):
        assert map_clamp(-90.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX) == 0
        assert map_clamp(90.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX) == 180

    def test_monotonic_increasing(self):
        prev = -1
        for deg_x10 in range(-450, 451):
            deg = deg_x10 / 10.0
            result = map_clamp(deg, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX)
            assert result >= prev
            prev = result


# ===========================================================================
#  Output range guarantees
# ===========================================================================

class TestOutputBounds:
    """Servo output must always be within [0, 180]."""

    @pytest.mark.parametrize("value", [-999.0, -90.0, 0.0, 90.0, 999.0])
    def test_yaw_output_in_range(self, value: float):
        result = map_clamp(value, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX)
        assert 0 <= result <= 180

    @pytest.mark.parametrize("value", [-999.0, -45.0, 0.0, 45.0, 999.0])
    def test_roll_output_in_range(self, value: float):
        result = map_clamp(value, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX)
        assert 0 <= result <= 180

    def test_integer_output(self):
        """Servo angles must be integers (no fractional degrees over serial)."""
        for deg_x10 in range(-900, 901, 7):  # odd step to hit non-round values
            deg = deg_x10 / 10.0
            result = map_clamp(deg, YAW_MIN, YAW_MAX, SERVO_MIN, SERVO_MAX)
            assert isinstance(result, int)


# ===========================================================================
#  Channel 3 offset (ch3_offset_deg = -45 in servo_controller.gd)
# ===========================================================================

class TestCh3Offset:
    """servo_controller.gd applies ch3_offset_deg after mapping for CH3."""

    CH3_OFFSET = -45  # from @export var ch3_offset_deg: int = -45

    @staticmethod
    def apply_offset(servo_angle: int, offset: int) -> int:
        """Replicate: clampi(roll_servo + ch3_offset_deg, servo_min, servo_max)"""
        return max(SERVO_MIN, min(SERVO_MAX, servo_angle + offset))

    def test_center_with_offset(self):
        raw = map_clamp(0.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX)  # 90
        assert self.apply_offset(raw, self.CH3_OFFSET) == 45

    def test_full_left_with_offset_clamps_to_0(self):
        raw = map_clamp(-45.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX)  # 0
        assert self.apply_offset(raw, self.CH3_OFFSET) == 0  # 0 + (-45) → clamped 0

    def test_full_right_with_offset(self):
        raw = map_clamp(45.0, ROLL_MIN, ROLL_MAX, SERVO_MIN, SERVO_MAX)  # 180
        assert self.apply_offset(raw, self.CH3_OFFSET) == 135  # 180 + (-45) = 135
