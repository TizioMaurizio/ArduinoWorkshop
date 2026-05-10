"""Tests for G-code builder functions."""

from backend.gcode import (
    emergency_stop,
    fan_off,
    fan_on,
    g90_absolute_positioning,
    g91_relative_positioning,
    get_position,
    get_temperature,
    home_all,
    home_axis,
    m82_absolute_extrusion,
    m83_relative_extrusion,
    motors_off,
    move_relative,
)
import pytest


class TestBasicCommands:
    def test_g90(self):
        assert g90_absolute_positioning() == "G90"

    def test_g91(self):
        assert g91_relative_positioning() == "G91"

    def test_m82(self):
        assert m82_absolute_extrusion() == "M82"

    def test_m83(self):
        assert m83_relative_extrusion() == "M83"

    def test_home_all(self):
        assert home_all() == "G28"

    def test_home_axis_x(self):
        assert home_axis("X") == "G28 X"

    def test_home_axis_lowercase(self):
        assert home_axis("y") == "G28 Y"

    def test_home_axis_invalid(self):
        with pytest.raises(ValueError):
            home_axis("E")

    def test_get_position(self):
        assert get_position() == "M114"

    def test_get_temperature(self):
        assert get_temperature() == "M105"

    def test_emergency_stop(self):
        assert emergency_stop() == "M112"

    def test_motors_off(self):
        assert motors_off() == "M84"

    def test_fan_on_default(self):
        assert fan_on() == "M106 S255"

    def test_fan_on_speed(self):
        assert fan_on(128) == "M106 S128"

    def test_fan_on_clamped(self):
        assert fan_on(300) == "M106 S255"
        assert fan_on(-10) == "M106 S0"

    def test_fan_off(self):
        assert fan_off() == "M107"


class TestMoveRelative:
    def test_x_only(self):
        cmds = move_relative(x=1)
        assert cmds[0] == "G91"
        assert "X1.000" in cmds[1]
        assert "G90" in cmds
        assert "M114" in cmds

    def test_y_only(self):
        cmds = move_relative(y=-2.5)
        assert "Y-2.500" in cmds[1]

    def test_z_only(self):
        cmds = move_relative(z=0.1, feedrate=300)
        assert "Z0.100" in cmds[1]
        assert "F300" in cmds[1]

    def test_extruder_only_uses_m83(self):
        cmds = move_relative(e=1.0, feedrate=120)
        assert cmds[0] == "M83"
        assert "E1.000" in cmds[1]
        assert cmds[2] == "M82"
        # Should NOT contain G91 or G90
        assert "G91" not in cmds
        assert "G90" not in cmds

    def test_empty_returns_nothing(self):
        assert move_relative() == []
        assert move_relative(x=0, y=0, z=0, e=0) == []

    def test_mixed_axes_split(self):
        cmds = move_relative(x=1, e=0.5)
        # Axes come before extrusion
        assert cmds[0] == "G91"
        assert "X1.000" in cmds[1]
        assert "G90" in cmds
        assert "M83" in cmds
        assert "M82" in cmds

    def test_no_invalid_empty_commands(self):
        # Verify no command is just "G1 F1500" without axis letters
        cmds = move_relative(x=1)
        for cmd in cmds:
            if cmd.startswith("G1"):
                # Must have at least one axis letter
                assert any(c in cmd for c in "XYZE")
