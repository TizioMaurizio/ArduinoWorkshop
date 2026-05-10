## PrinterViewer.gd — Read-only WebSocket client for printer state visualization.
##
## This script connects to the Python backend via WebSocket and renders:
##   - Printer bed (XZ plane)
##   - Build volume (wireframe box)
##   - Nozzle position (sphere)
##   - UI labels: connection, position, temperature, errors
##
## Coordinate mapping:
##   Printer X → Godot X
##   Printer Y → Godot Z
##   Printer Z → Godot Y
##
## Scale: 1 Godot unit = 10 mm
##
## THIS SCRIPT MUST NOT:
##   - Open the serial port
##   - Generate G-code
##   - Decide whether a move is safe

extends Node3D

const WS_URL := "ws://127.0.0.1:8765/ws/state"
const SCALE_FACTOR := 0.1  # 1 Godot unit = 10 mm
const RECONNECT_DELAY := 3.0

# -- node references (assigned in _ready) --
var _bed: MeshInstance3D
var _volume: MeshInstance3D
var _nozzle: MeshInstance3D
var _connection_label: Label
var _position_label: Label
var _temp_label: Label
var _error_label: Label

# -- WebSocket --
var _ws := WebSocketPeer.new()
var _ws_connected := false
var _reconnect_timer := 0.0

# -- bed dimensions (updated from backend on first message) --
var _bed_x_max := 220.0
var _bed_y_max := 220.0
var _bed_z_max := 250.0


func _ready() -> void:
	_bed = $PrinterBed as MeshInstance3D
	_volume = $BuildVolume as MeshInstance3D
	_nozzle = $Nozzle as MeshInstance3D
	_connection_label = $UI/VBox/ConnectionLabel as Label
	_position_label = $UI/VBox/PositionLabel as Label
	_temp_label = $UI/VBox/TempLabel as Label
	_error_label = $UI/VBox/ErrorLabel as Label

	_setup_bed()
	_setup_nozzle()
	_setup_build_volume()
	_try_connect()


func _process(delta: float) -> void:
	_ws.poll()

	var state := _ws.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		if not _ws_connected:
			_ws_connected = true
			_connection_label.text = "Connected to backend"
			_connection_label.add_theme_color_override("font_color", Color.GREEN)
		while _ws.get_available_packet_count() > 0:
			var text := _ws.get_packet().get_string_from_utf8()
			_handle_message(text)

	elif state == WebSocketPeer.STATE_CLOSED or state == WebSocketPeer.STATE_CLOSING:
		if _ws_connected:
			_ws_connected = false
			_connection_label.text = "Disconnected — reconnecting…"
			_connection_label.add_theme_color_override("font_color", Color.RED)
		_reconnect_timer += delta
		if _reconnect_timer >= RECONNECT_DELAY:
			_reconnect_timer = 0.0
			_try_connect()


func _try_connect() -> void:
	var err := _ws.connect_to_url(WS_URL)
	if err != OK:
		_connection_label.text = "Connection failed (err %d)" % err
		_connection_label.add_theme_color_override("font_color", Color.RED)


func _handle_message(text: String) -> void:
	var json := JSON.new()
	var parse_err := json.parse(text)
	if parse_err != OK:
		return
	var data: Dictionary = json.data
	if not data.has("type"):
		return

	var msg_type: String = data["type"]

	if msg_type == "state":
		_update_state(data)
	elif msg_type == "log":
		# Could display in a log panel — for now just update error label on warnings/errors
		var level: String = data.get("level", "")
		if level in ["error", "warning"]:
			_error_label.text = str(data.get("message", ""))
			_error_label.add_theme_color_override("font_color", Color.ORANGE if level == "warning" else Color.RED)

	# Update bed dimensions if provided
	if data.has("bed"):
		var bed_cfg: Dictionary = data["bed"]
		_bed_x_max = float(bed_cfg.get("x_max", _bed_x_max))
		_bed_y_max = float(bed_cfg.get("y_max", _bed_y_max))
		_bed_z_max = float(bed_cfg.get("z_max", _bed_z_max))
		_setup_bed()
		_setup_build_volume()


func _update_state(data: Dictionary) -> void:
	# Position
	var px: float = float(data.get("x", 0.0)) if data.get("x") != null else 0.0
	var py: float = float(data.get("y", 0.0)) if data.get("y") != null else 0.0
	var pz: float = float(data.get("z", 0.0)) if data.get("z") != null else 0.0

	# Map printer coords to Godot: X→X, Y→Z, Z→Y
	_nozzle.position = Vector3(
		px * SCALE_FACTOR,
		pz * SCALE_FACTOR,
		py * SCALE_FACTOR
	)

	_position_label.text = "Position: X=%.2f  Y=%.2f  Z=%.2f" % [px, py, pz]

	# Temperature
	var hotend: float = float(data.get("hotend_temp_c", 0.0)) if data.get("hotend_temp_c") != null else 0.0
	var hotend_target: float = float(data.get("hotend_target_c", 0.0)) if data.get("hotend_target_c") != null else 0.0
	var bed_t: float = float(data.get("bed_temp_c", 0.0)) if data.get("bed_temp_c") != null else 0.0
	var bed_target: float = float(data.get("bed_target_c", 0.0)) if data.get("bed_target_c") != null else 0.0
	_temp_label.text = "Hotend: %.1f/%.1f°C  Bed: %.1f/%.1f°C" % [hotend, hotend_target, bed_t, bed_target]

	# Connection / error state
	var connected: bool = data.get("connected", false)
	var locked: bool = data.get("locked", false)
	var last_error = data.get("last_error")

	if locked:
		_error_label.text = "LOCKED: %s" % str(last_error)
		_error_label.add_theme_color_override("font_color", Color.RED)
		# Tint nozzle red when locked
		var mat := _nozzle.get_surface_override_material(0) as StandardMaterial3D
		if mat:
			mat.albedo_color = Color.RED
	elif not connected:
		_connection_label.text = "Printer disconnected"
		_connection_label.add_theme_color_override("font_color", Color.YELLOW)
	else:
		_error_label.text = ""
		var mat := _nozzle.get_surface_override_material(0) as StandardMaterial3D
		if mat:
			mat.albedo_color = Color(0.2, 0.8, 1.0)


# ---------------------------------------------------------------------------
# Scene setup helpers
# ---------------------------------------------------------------------------

func _setup_bed() -> void:
	var bed_mesh := PlaneMesh.new()
	bed_mesh.size = Vector2(_bed_x_max * SCALE_FACTOR, _bed_y_max * SCALE_FACTOR)
	_bed.mesh = bed_mesh

	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.3, 0.3, 0.3, 0.6)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_bed.set_surface_override_material(0, mat)

	# Center the bed so origin is at corner (0,0)
	_bed.position = Vector3(
		_bed_x_max * SCALE_FACTOR / 2.0,
		0.0,
		_bed_y_max * SCALE_FACTOR / 2.0
	)


func _setup_nozzle() -> void:
	var sphere := SphereMesh.new()
	sphere.radius = 0.3
	sphere.height = 0.6
	_nozzle.mesh = sphere

	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.2, 0.8, 1.0)
	mat.emission_enabled = true
	mat.emission = Color(0.1, 0.4, 0.8)
	mat.emission_energy_multiplier = 0.5
	_nozzle.set_surface_override_material(0, mat)
	_nozzle.position = Vector3.ZERO


func _setup_build_volume() -> void:
	var box := BoxMesh.new()
	box.size = Vector3(
		_bed_x_max * SCALE_FACTOR,
		_bed_z_max * SCALE_FACTOR,
		_bed_y_max * SCALE_FACTOR
	)
	_volume.mesh = box

	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1.0, 1.0, 1.0, 0.05)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_volume.set_surface_override_material(0, mat)

	_volume.position = Vector3(
		_bed_x_max * SCALE_FACTOR / 2.0,
		_bed_z_max * SCALE_FACTOR / 2.0,
		_bed_y_max * SCALE_FACTOR / 2.0
	)
