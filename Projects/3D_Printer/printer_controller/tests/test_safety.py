"""Tests for the safety validation layer."""

from backend.config import AppConfig, BedConfig, ExtruderConfig, PrinterConfig, SafetyConfig
from backend.printer_state import PrinterState
from backend.safety import DENIED_COMMANDS, SafetyValidator


def _make_config(**overrides) -> AppConfig:
    """Create an AppConfig with optional overrides."""
    cfg = AppConfig()
    for k, v in overrides.items():
        if hasattr(cfg.printer, k):
            setattr(cfg.printer, k, v)
        elif hasattr(cfg.printer.safety, k):
            setattr(cfg.printer.safety, k, v)
    return cfg


def _connected_state(**kwargs) -> PrinterState:
    """Return a connected PrinterState with optional field overrides."""
    defaults = dict(
        connected=True,
        x=100.0,
        y=100.0,
        z=50.0,
        e=0.0,
        homed_x=True,
        homed_y=True,
        homed_z=True,
        hotend_temp_c=25.0,
    )
    defaults.update(kwargs)
    return PrinterState(**defaults)


class TestJogValidation:
    def test_reject_when_disconnected(self):
        v = SafetyValidator(AppConfig())
        state = PrinterState(connected=False)
        r = v.validate_jog(state, "X", 1.0)
        assert not r.allowed

    def test_reject_when_locked(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state(locked=True)
        r = v.validate_jog(state, "X", 1.0)
        assert not r.allowed

    def test_reject_x_beyond_max(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state(x=219.0)
        r = v.validate_jog(state, "X", 5.0)
        assert not r.allowed
        assert "limits" in r.reason

    def test_reject_y_below_min(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state(y=0.5)
        r = v.validate_jog(state, "Y", -1.0)
        assert not r.allowed

    def test_reject_z_below_zero(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state(z=0.0)
        r = v.validate_jog(state, "Z", -0.1)
        assert not r.allowed

    def test_allow_valid_move(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state()
        r = v.validate_jog(state, "X", 1.0)
        assert r.allowed

    def test_reject_cold_extrusion(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state(hotend_temp_c=25.0)
        r = v.validate_jog(state, "E", 1.0)
        assert not r.allowed
        assert "Cold extrusion" in r.reason

    def test_allow_hot_extrusion(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state(hotend_temp_c=200.0)
        r = v.validate_jog(state, "E", 1.0)
        assert r.allowed

    def test_allow_cold_extrusion_when_configured(self):
        cfg = AppConfig()
        cfg.printer.extruder.cold_extrusion_allowed = True
        v = SafetyValidator(cfg)
        state = _connected_state(hotend_temp_c=25.0)
        r = v.validate_jog(state, "E", 1.0)
        assert r.allowed

    def test_reject_unhomed_when_not_allowed(self):
        cfg = AppConfig()
        cfg.printer.safety.allow_unhomed_relative_jog = False
        v = SafetyValidator(cfg)
        state = _connected_state(homed_x=False)
        r = v.validate_jog(state, "X", 1.0)
        assert not r.allowed

    def test_allow_unhomed_when_configured(self):
        cfg = AppConfig()
        cfg.printer.safety.allow_unhomed_relative_jog = True
        v = SafetyValidator(cfg)
        state = _connected_state(homed_x=False)
        r = v.validate_jog(state, "X", 1.0)
        assert r.allowed

    def test_allow_move_when_position_unknown(self):
        """When position is None, soft limits can't be checked — allow."""
        v = SafetyValidator(AppConfig())
        state = _connected_state(x=None)
        r = v.validate_jog(state, "X", 1.0)
        assert r.allowed


class TestRawGcodeValidation:
    def test_reject_empty(self):
        v = SafetyValidator(AppConfig())
        r = v.validate_raw_gcode("")
        assert not r.allowed

    def test_reject_comment_only(self):
        v = SafetyValidator(AppConfig())
        r = v.validate_raw_gcode("; just a comment")
        assert not r.allowed

    def test_allow_m114(self):
        v = SafetyValidator(AppConfig())
        r = v.validate_raw_gcode("M114")
        assert r.allowed

    def test_always_allow_m112(self):
        v = SafetyValidator(AppConfig())
        r = v.validate_raw_gcode("M112")
        assert r.allowed

    def test_reject_denied_commands(self):
        v = SafetyValidator(AppConfig())
        for cmd in DENIED_COMMANDS:
            r = v.validate_raw_gcode(cmd)
            assert not r.allowed, f"{cmd} should be denied"

    def test_strip_inline_comment(self):
        v = SafetyValidator(AppConfig())
        r = v.validate_raw_gcode("M114 ; query position")
        assert r.allowed


class TestRawMoveValidation:
    def test_reject_when_disconnected(self):
        v = SafetyValidator(AppConfig())
        state = PrinterState(connected=False)
        r = v.validate_raw_move(state, "G1 X100")
        assert not r.allowed

    def test_reject_exceeding_x(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state()
        r = v.validate_raw_move(state, "G1 X500 F3000")
        assert not r.allowed

    def test_allow_valid_raw_move(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state()
        r = v.validate_raw_move(state, "G1 X100 Y100 F3000")
        assert r.allowed

    def test_non_move_always_passes(self):
        v = SafetyValidator(AppConfig())
        state = _connected_state()
        r = v.validate_raw_move(state, "M105")
        assert r.allowed


class TestEmergencyStop:
    def test_always_allowed(self):
        v = SafetyValidator(AppConfig())
        state = PrinterState(connected=False, locked=True)
        r = v.can_emergency_stop(state)
        assert r.allowed
