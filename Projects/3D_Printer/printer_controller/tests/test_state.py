"""Tests for printer state model and response parsers."""

from backend.printer_state import (
    PrinterState,
    ThreadSafeState,
    parse_firmware,
    parse_m105,
    parse_m114,
)


class TestParseM114:
    def test_standard_response(self):
        line = "X:10.00 Y:20.00 Z:0.30 E:0.00 Count X:800 Y:1600 Z:120"
        result = parse_m114(line)
        assert result is not None
        assert result["x"] == 10.0
        assert result["y"] == 20.0
        assert result["z"] == 0.30
        assert result["e"] == 0.0

    def test_negative_values(self):
        line = "X:-1.50 Y:-0.25 Z:0.00 E:-2.10"
        result = parse_m114(line)
        assert result is not None
        assert result["x"] == -1.5
        assert result["y"] == -0.25
        assert result["e"] == -2.1

    def test_no_match(self):
        assert parse_m114("ok") is None
        assert parse_m114("") is None


class TestParseM105:
    def test_standard_response(self):
        line = "ok T:200.1 /200.0 B:60.2 /60.0"
        result = parse_m105(line)
        assert result is not None
        assert result["hotend_temp_c"] == 200.1
        assert result["hotend_target_c"] == 200.0
        assert result["bed_temp_c"] == 60.2
        assert result["bed_target_c"] == 60.0

    def test_hotend_only(self):
        line = "ok T:25.0 /0.0"
        result = parse_m105(line)
        assert result is not None
        assert result["hotend_temp_c"] == 25.0
        assert "bed_temp_c" not in result

    def test_no_match(self):
        assert parse_m105("ok") is None
        assert parse_m105("") is None


class TestParseFirmware:
    def test_standard(self):
        line = "FIRMWARE_NAME:Marlin 2.1.2 SOURCE_CODE_URL:https://github.com/MarlinFirmware/Marlin"
        result = parse_firmware(line)
        assert result == "Marlin 2.1.2"

    def test_mock(self):
        result = parse_firmware("FIRMWARE_NAME:Mock Marlin 2.0.0")
        assert result == "Mock Marlin 2.0.0"

    def test_no_match(self):
        assert parse_firmware("ok") is None


class TestThreadSafeState:
    def test_initial_state(self):
        ts = ThreadSafeState()
        s = ts.get()
        assert s.connected is False
        assert s.x is None

    def test_update_increments_version(self):
        ts = ThreadSafeState()
        v0 = ts.version
        ts.update(connected=True)
        assert ts.version == v0 + 1

    def test_update_fields(self):
        ts = ThreadSafeState()
        ts.update(x=10.0, y=20.0, connected=True)
        s = ts.get()
        assert s.x == 10.0
        assert s.y == 20.0
        assert s.connected is True

    def test_get_returns_copy(self):
        ts = ThreadSafeState()
        ts.update(x=5.0)
        s1 = ts.get()
        s1.x = 999.0
        s2 = ts.get()
        assert s2.x == 5.0  # original unchanged

    def test_to_dict(self):
        ts = ThreadSafeState()
        ts.update(connected=True, port="COM3")
        d = ts.to_dict()
        assert d["connected"] is True
        assert d["port"] == "COM3"

    def test_lock_on_error(self):
        ts = ThreadSafeState()
        ts.update(connected=True, locked=True, last_error="Printer halted")
        s = ts.get()
        assert s.locked is True
        assert s.last_error == "Printer halted"
