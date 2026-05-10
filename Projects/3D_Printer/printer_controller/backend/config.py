"""Configuration loader for printer controller.

Loads printer profile and serial settings from config.yaml.
Falls back to defaults if no config file exists.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BedConfig:
    x_min: float = 0.0
    x_max: float = 220.0
    y_min: float = 0.0
    y_max: float = 220.0
    z_min: float = 0.0
    z_max: float = 250.0


@dataclass
class ExtruderConfig:
    cold_extrusion_allowed: bool = False
    minimum_extrude_temp_c: float = 180.0


@dataclass
class JogConfig:
    xy_step_mm: float = 1.0
    z_step_mm: float = 0.1
    e_step_mm: float = 1.0
    feedrate_xy: int = 3000
    feedrate_z: int = 300
    feedrate_e: int = 120


@dataclass
class SafetyConfig:
    allow_unhomed_relative_jog: bool = True
    require_homing_for_absolute_moves: bool = True
    max_jog_rate_hz: float = 5.0
    locked_after_error: bool = True


@dataclass
class SerialConfig:
    timeout_s: float = 2.0
    write_timeout_s: float = 2.0


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class PrinterConfig:
    name: str = "generic_marlin_fdm"
    baud_candidates: list[int] = field(default_factory=lambda: [115200, 250000])
    bed: BedConfig = field(default_factory=BedConfig)
    extruder: ExtruderConfig = field(default_factory=ExtruderConfig)
    jog: JogConfig = field(default_factory=JogConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    serial: SerialConfig = field(default_factory=SerialConfig)


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    printer: PrinterConfig = field(default_factory=PrinterConfig)


def load_config(config_path: str | None = None) -> AppConfig:
    """Load configuration from YAML file.

    If no config file exists, copies config.example.yaml if available,
    otherwise returns defaults.
    """
    if config_path is None:
        config_path = "config.yaml"

    path = Path(config_path)

    if not path.exists():
        example = Path("config.example.yaml")
        if example.exists():
            shutil.copy(example, path)
        else:
            return AppConfig()

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return _parse_config(raw)


def _parse_config(raw: dict[str, Any]) -> AppConfig:
    """Parse raw YAML dict into typed AppConfig."""
    server_raw = raw.get("server", {})
    printer_raw = raw.get("printer", {})

    server = ServerConfig(
        host=server_raw.get("host", "127.0.0.1"),
        port=server_raw.get("port", 8765),
    )

    bed_raw = printer_raw.get("bed", {})
    bed = BedConfig(
        x_min=float(bed_raw.get("x_min", 0.0)),
        x_max=float(bed_raw.get("x_max", 220.0)),
        y_min=float(bed_raw.get("y_min", 0.0)),
        y_max=float(bed_raw.get("y_max", 220.0)),
        z_min=float(bed_raw.get("z_min", 0.0)),
        z_max=float(bed_raw.get("z_max", 250.0)),
    )

    ext_raw = printer_raw.get("extruder", {})
    extruder = ExtruderConfig(
        cold_extrusion_allowed=bool(ext_raw.get("cold_extrusion_allowed", False)),
        minimum_extrude_temp_c=float(ext_raw.get("minimum_extrude_temp_c", 180.0)),
    )

    jog_raw = printer_raw.get("jog", {})
    jog = JogConfig(
        xy_step_mm=float(jog_raw.get("xy_step_mm", 1.0)),
        z_step_mm=float(jog_raw.get("z_step_mm", 0.1)),
        e_step_mm=float(jog_raw.get("e_step_mm", 1.0)),
        feedrate_xy=int(jog_raw.get("feedrate_xy", 3000)),
        feedrate_z=int(jog_raw.get("feedrate_z", 300)),
        feedrate_e=int(jog_raw.get("feedrate_e", 120)),
    )

    safety_raw = printer_raw.get("safety", {})
    safety = SafetyConfig(
        allow_unhomed_relative_jog=bool(
            safety_raw.get("allow_unhomed_relative_jog", True)
        ),
        require_homing_for_absolute_moves=bool(
            safety_raw.get("require_homing_for_absolute_moves", True)
        ),
        max_jog_rate_hz=float(safety_raw.get("max_jog_rate_hz", 5.0)),
        locked_after_error=bool(safety_raw.get("locked_after_error", True)),
    )

    serial_raw = printer_raw.get("serial", {})
    serial_cfg = SerialConfig(
        timeout_s=float(serial_raw.get("timeout_s", 2.0)),
        write_timeout_s=float(serial_raw.get("write_timeout_s", 2.0)),
    )

    printer = PrinterConfig(
        name=printer_raw.get("name", "generic_marlin_fdm"),
        baud_candidates=printer_raw.get("baud_candidates", [115200, 250000]),
        bed=bed,
        extruder=extruder,
        jog=jog,
        safety=safety,
        serial=serial_cfg,
    )

    return AppConfig(server=server, printer=printer)
