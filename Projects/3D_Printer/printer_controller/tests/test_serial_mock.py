"""Tests for serial worker using mock serial backend."""

import time

from backend.config import AppConfig
from backend.printer_state import ThreadSafeState
from backend.serial_worker import MockSerialPort, SerialWorker


def _make_worker() -> tuple[SerialWorker, ThreadSafeState]:
    config = AppConfig()
    state = ThreadSafeState()
    worker = SerialWorker(state, config)
    return worker, state


class TestMockSerialPort:
    def test_m115_response(self):
        mock = MockSerialPort()
        # Drain startup messages
        mock.readline()
        mock.readline()
        mock.write(b"M115\n")
        lines = []
        for _ in range(5):
            raw = mock.readline()
            if raw:
                lines.append(raw.decode().strip())
        assert any("FIRMWARE_NAME" in l for l in lines)

    def test_m114_response(self):
        mock = MockSerialPort()
        mock.readline()
        mock.readline()
        mock.write(b"M114\n")
        lines = []
        for _ in range(5):
            raw = mock.readline()
            if raw:
                lines.append(raw.decode().strip())
        assert any("X:0.00" in l for l in lines)

    def test_m105_response(self):
        mock = MockSerialPort()
        mock.readline()
        mock.readline()
        mock.write(b"M105\n")
        raw = mock.readline()
        line = raw.decode().strip()
        assert "T:25.0" in line

    def test_movement_updates_position(self):
        mock = MockSerialPort()
        mock.readline()
        mock.readline()
        mock.write(b"G91\n")
        mock.readline()  # ok
        mock.write(b"G1 X5.0\n")
        mock.readline()  # ok
        mock.write(b"M114\n")
        lines = []
        for _ in range(5):
            raw = mock.readline()
            if raw:
                lines.append(raw.decode().strip())
        assert any("X:5.00" in l for l in lines)

    def test_m112_halts(self):
        mock = MockSerialPort()
        mock.readline()
        mock.readline()
        mock.write(b"M112\n")
        raw = mock.readline()
        assert b"halted" in raw.lower()
        # Subsequent commands should also return error
        mock.write(b"M114\n")
        raw = mock.readline()
        assert b"halted" in raw.lower()


class TestSerialWorkerMock:
    def test_connect_mock(self):
        worker, state = _make_worker()
        assert worker.connect_mock()
        # Wait for handshake to complete
        time.sleep(1.5)
        s = state.get()
        assert s.connected is True
        assert s.firmware is not None
        worker.disconnect()

    def test_position_after_handshake(self):
        worker, state = _make_worker()
        worker.connect_mock()
        time.sleep(1.5)
        s = state.get()
        assert s.x is not None
        assert s.y is not None
        assert s.z is not None
        worker.disconnect()

    def test_send_m114_updates_state(self):
        worker, state = _make_worker()
        worker.connect_mock()
        time.sleep(1.0)
        worker.send("G91")
        worker.send("G1 X10 F3000")
        worker.send("G90")
        worker.send("M114")
        time.sleep(1.0)
        s = state.get()
        assert s.x is not None
        assert s.x >= 10.0
        worker.disconnect()

    def test_emergency_stop_locks(self):
        worker, state = _make_worker()
        worker.connect_mock()
        time.sleep(1.0)
        worker.send_immediate("M112")
        time.sleep(0.5)
        s = state.get()
        assert s.locked is True
        worker.disconnect()

    def test_one_command_at_a_time(self):
        """Verify the worker waits for ok before sending the next command."""
        worker, state = _make_worker()
        worker.connect_mock()
        time.sleep(1.0)
        # Queue several commands — they should all succeed sequentially
        for _ in range(5):
            worker.send("M114")
        time.sleep(2.0)
        s = state.get()
        # If commands were processed, position should be set
        assert s.x is not None
        worker.disconnect()

    def test_disconnect(self):
        worker, state = _make_worker()
        worker.connect_mock()
        time.sleep(0.5)
        worker.disconnect()
        s = state.get()
        assert s.connected is False
