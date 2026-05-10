"""Tests for the FastAPI backend API."""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig
from backend.printer_state import ThreadSafeState
from backend.safety import SafetyValidator
from backend.serial_worker import SerialWorker


@pytest.fixture()
def client():
    """Create a test client with mock-connected serial worker."""
    config = AppConfig()
    state = ThreadSafeState()
    safety = SafetyValidator(config)
    worker = SerialWorker(state, config)
    worker.connect_mock()

    import time
    time.sleep(1.0)

    app = create_app(state, worker, safety, config)
    with TestClient(app) as c:
        yield c

    worker.disconnect()


@pytest.fixture()
def disconnected_client():
    """Create a test client WITHOUT a connected printer."""
    config = AppConfig()
    state = ThreadSafeState()
    safety = SafetyValidator(config)
    worker = SerialWorker(state, config)
    app = create_app(state, worker, safety, config)
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestState:
    def test_state_returns_dict(self, client):
        r = client.get("/state")
        assert r.status_code == 200
        data = r.json()
        assert "connected" in data
        assert "x" in data


class TestPorts:
    def test_ports_returns_list(self, client):
        r = client.get("/ports")
        assert r.status_code == 200
        assert "ports" in r.json()


class TestJog:
    def test_valid_jog(self, client):
        r = client.post("/jog", json={"axis": "X", "distance_mm": 1.0})
        assert r.status_code == 200
        data = r.json()
        assert "error" not in data or data.get("status") == "jogging"

    def test_jog_validates_input(self, disconnected_client):
        r = disconnected_client.post(
            "/jog", json={"axis": "X", "distance_mm": 1.0}
        )
        assert r.status_code == 200
        data = r.json()
        assert "error" in data


class TestGcode:
    def test_valid_gcode(self, client):
        r = client.post("/gcode", json={"command": "M114"})
        assert r.status_code == 200
        assert r.json().get("status") == "sent"

    def test_denied_gcode(self, client):
        r = client.post("/gcode", json={"command": "M502"})
        assert r.status_code == 200
        assert "error" in r.json()


class TestEmergencyStop:
    def test_estop(self, client):
        r = client.post("/emergency-stop")
        assert r.status_code == 200
        assert r.json()["status"] == "emergency_stop_sent"
