extends Node
## Reads XRCamera3D head rotation and sends servo angles to the ESP32-CAM
## via UDP. The ESP32 forwards them over Serial2 to the Arduino.
##
## Discovery: listens for UDP broadcast on port 9999 from ESP32-CAM arm,
## same mechanism as the car controller. Fallback: camera_stream auto-discovery.
##
## Protocol: UDP packet to ESP32_IP:UDP_PORT containing "<ch>,<angle>\n"
## Channel 0 = Y rotation (yaw), Channel 3 = X rotation (pitch)

# --- Configurable parameters --------------------------------------------------

## Leave empty to use auto-discovery (UDP broadcast on port 9999).
@export var bridge_host: String = "10.192.119.157"  ## Arm ESP32-CAM (DHCP — rescan if changed)
@export var bridge_port: int = 9685

## Head yaw limits (degrees). Full left → SERVO_MIN, full right → SERVO_MAX.
@export var yaw_min_deg: float = -90.0
@export var yaw_max_deg: float = 90.0

## Head pitch limits (degrees). Look up → SERVO_MIN, look down → SERVO_MAX.
@export var pitch_min_deg: float = -45.0
@export var pitch_max_deg: float = 45.0

## Servo output range
@export var servo_min_angle: int = 0
@export var servo_max_angle: int = 180

## Send rate (Hz). Servos don't benefit from >50 Hz updates.
@export var send_rate_hz: float = 20.0

## Minimum angle change (degrees) to trigger an update. Reduces serial traffic.
@export var deadband_deg: float = 1.0

## Per-channel offset in servo degrees (added after mapping).
@export var ch3_offset_deg: int = -45

# --- Discovery ----------------------------------------------------------------
## UDP port for auto-discovery broadcast from ESP32 devices.
const DISCOVERY_PORT: int = 9999
## How long to wait for discovery before trying camera_stream fallback (seconds).
@export var discovery_timeout_sec: float = 8.0

# --- Channel assignments -----------------------------------------------------
const CH_YAW: int = 0
const CH_PITCH: int = 3

# --- Internal state -----------------------------------------------------------
var _udp: PacketPeerUDP = PacketPeerUDP.new()
var _camera: XRCamera3D = null
var _send_timer: float = 0.0
var _last_yaw_angle: int = -1
var _last_pitch_angle: int = -1
var _connected: bool = false
var _calibrated: bool = false
var _initial_quat: Quaternion = Quaternion.IDENTITY

# --- Discovery state ----------------------------------------------------------
var _discovery_udp: PacketPeerUDP = PacketPeerUDP.new()
var _discovery_timer: float = 0.0
var _discovered: bool = false

func _ready() -> void:
	_camera = get_node_or_null("../XROrigin3D/XRCamera3D")
	if _camera == null:
		printerr("[Servo] XRCamera3D not found — is XROrigin3D in the scene?")
		return

	# Reset calibration when the runtime recenters the pose
	var vr_main: Node = get_node_or_null("../")
	if vr_main and vr_main.has_signal("pose_recentered"):
		vr_main.pose_recentered.connect(_on_pose_recentered)

	# If host set, skip discovery and connect directly.
	if bridge_host != "":
		print("[Servo] Using configured host: %s" % bridge_host)
		_discovered = true
		_connect_udp()
		return

	# Start UDP discovery listener (same port as car)
	var err: int = _discovery_udp.bind(DISCOVERY_PORT)
	if err != OK:
		printerr("[Servo] Failed to bind UDP discovery port %d (err=%d) — trying camera fallback" % [
			DISCOVERY_PORT, err
		])
		# Port may already be bound by car_controller — fall back to camera_stream
		_discovered = true  # Skip discovery, rely on camera_stream IP
	else:
		print("[Servo] Listening for arm discovery on UDP port %d..." % DISCOVERY_PORT)


func _connect_udp() -> void:
	var err: int = _udp.connect_to_host(bridge_host, bridge_port)
	if err != OK:
		printerr("[Servo] UDP connect failed: %d" % err)
		return
	_connected = true
	print("[Servo] Sending to bridge at %s:%d  (CH%d=yaw, CH%d=pitch)" % [
		bridge_host, bridge_port, CH_YAW, CH_PITCH
	])


func _process(delta: float) -> void:
	if _camera == null:
		return

	# --- UDP discovery (runs until arm is found) ---
	if not _discovered:
		_check_discovery(delta)
		return

	# Fallback: pick up the IP from camera_stream once it finds one
	if not _connected:
		var screen: Node = get_node_or_null("../XROrigin3D/XRCamera3D/Screen")
		if screen and screen.get("_connected") == true:
			var ip: String = screen.esp_ip
			if ip != "":
				bridge_host = ip
				_connect_udp()
		return

	_send_timer += delta
	var interval: float = 1.0 / send_rate_hz
	if _send_timer < interval:
		return
	_send_timer -= interval

	# Quaternion-based angle extraction (gimbal-lock-free).
	# Euler decomposition degenerates at pitch ≈ ±90°, causing yaw/roll jumps.
	var quat: Quaternion = _camera.global_transform.basis.get_rotation_quaternion()

	# Capture the visor orientation at startup as the zero reference
	if not _calibrated:
		_initial_quat = quat
		_calibrated = true
		print("[Servo] Initial head quaternion captured")

	# Relative rotation from initial pose — purely in quaternion space
	var rel_quat: Quaternion = _initial_quat.inverse() * quat
	var rel_basis: Basis = Basis(rel_quat)

	# Extract yaw and pitch from the relative rotation basis.
	# Yaw  = atan2(basis.z.x, basis.z.z) — rotation around Y.
	# Pitch = -asin(basis.z.y)            — rotation around X (clamped to avoid NaN).
	var yaw_deg: float = rad_to_deg(atan2(rel_basis.z.x, rel_basis.z.z))
	var pitch_deg: float = rad_to_deg(-asin(clampf(rel_basis.z.y, -1.0, 1.0)))

	# Clamp and map to servo range
	var yaw_servo: int = _map_clamp(yaw_deg, yaw_min_deg, yaw_max_deg,
									servo_min_angle, servo_max_angle)
	var pitch_servo: int = _map_clamp(pitch_deg, pitch_min_deg, pitch_max_deg,
									  servo_min_angle, servo_max_angle)
	pitch_servo = clampi(pitch_servo + ch3_offset_deg, servo_min_angle, servo_max_angle)

	# Only send if angle changed beyond deadband
	if absi(yaw_servo - _last_yaw_angle) >= int(deadband_deg):
		_send_angle(CH_YAW, yaw_servo)
		_last_yaw_angle = yaw_servo

	if absi(pitch_servo - _last_pitch_angle) >= int(deadband_deg):
		_send_angle(CH_PITCH, pitch_servo)
		_last_pitch_angle = pitch_servo


func _send_angle(channel: int, angle: int) -> void:
	var msg: String = "%d,%d\n" % [channel, angle]
	_udp.put_packet(msg.to_utf8_buffer())


## Clamp input to [in_min, in_max], linearly map to [out_min, out_max], return int.
func _map_clamp(value: float, in_min: float, in_max: float,
				out_min: int, out_max: int) -> int:
	var clamped: float = clampf(value, in_min, in_max)
	var t: float = (clamped - in_min) / (in_max - in_min)
	return int(roundf(lerpf(float(out_min), float(out_max), t)))


func _on_pose_recentered() -> void:
	_calibrated = false
	print("[Servo] Pose recentered — will recapture initial angle next frame")


## Called by car_controller when it receives an arm discovery broadcast.
func on_arm_discovered(ip: String, servo_port: int) -> void:
	if _connected:
		return  # Already connected
	bridge_host = ip
	bridge_port = servo_port
	_discovered = true
	_discovery_udp.close()
	print("[Servo] Arm discovered (via shared listener) at %s:%d" % [bridge_host, bridge_port])
	_connect_udp()


# --- UDP auto-discovery -------------------------------------------------------
func _check_discovery(delta: float) -> void:
	# Check for broadcast packets from the arm ESP32-CAM
	while _discovery_udp.get_available_packet_count() > 0:
		var data: String = _discovery_udp.get_packet().get_string_from_utf8()
		var json: Variant = JSON.parse_string(data)
		if json is Dictionary and json.get("service", "") == "esp32-cam-arm":
			var ip: String = json.get("ip", "")
			var servo_port: int = int(json.get("servo", 9685))
			if ip != "":
				bridge_host = ip
				bridge_port = servo_port
				_discovered = true
				_discovery_udp.close()
				print("[Servo] Discovered arm at %s:%d" % [bridge_host, bridge_port])
				_connect_udp()
				return

	# Timeout — fall back to camera_stream discovery
	_discovery_timer += delta
	if _discovery_timer >= discovery_timeout_sec:
		print("[Servo] Discovery timeout — falling back to camera stream discovery")
		_discovered = true  # Let _process fallback logic take over
		_discovery_udp.close()
