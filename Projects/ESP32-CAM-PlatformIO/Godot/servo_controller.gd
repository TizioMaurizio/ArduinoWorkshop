extends Node
## Reads XRCamera3D head rotation and sends servo angles to Arduino
## via a local UDP-to-serial bridge.
##
## Protocol: UDP packet to localhost:BRIDGE_PORT containing "<ch>,<angle>\n"
## Channel 0 = Y rotation (yaw), Channel 3 = Z rotation (roll)

# --- Configurable parameters --------------------------------------------------

@export var bridge_host: String = "127.0.0.1"
@export var bridge_port: int = 9685

## Head yaw limits (degrees). Full left → SERVO_MIN, full right → SERVO_MAX.
@export var yaw_min_deg: float = -90.0
@export var yaw_max_deg: float = 90.0

## Head roll limits (degrees). Full left tilt → SERVO_MIN, full right → SERVO_MAX.
@export var roll_min_deg: float = -45.0
@export var roll_max_deg: float = 45.0

## Servo output range
@export var servo_min_angle: int = 0
@export var servo_max_angle: int = 180

## Send rate (Hz). Servos don't benefit from >50 Hz updates.
@export var send_rate_hz: float = 20.0

## Minimum angle change (degrees) to trigger an update. Reduces serial traffic.
@export var deadband_deg: float = 1.0

## Per-channel offset in servo degrees (added after mapping).
@export var ch3_offset_deg: int = -45

# --- Channel assignments -----------------------------------------------------
const CH_YAW: int = 0
const CH_ROLL: int = 3

# --- Internal state -----------------------------------------------------------
var _udp: PacketPeerUDP = PacketPeerUDP.new()
var _camera: XRCamera3D = null
var _send_timer: float = 0.0
var _last_yaw_angle: int = -1
var _last_roll_angle: int = -1
var _connected: bool = false

func _ready() -> void:
	_camera = get_node_or_null("../XROrigin3D/XRCamera3D")
	if _camera == null:
		printerr("[Servo] XRCamera3D not found — is XROrigin3D in the scene?")
		return

	var err: int = _udp.connect_to_host(bridge_host, bridge_port)
	if err != OK:
		printerr("[Servo] UDP connect failed: %d" % err)
		return

	_connected = true
	print("[Servo] Sending to bridge at %s:%d  (CH%d=yaw, CH%d=roll)" % [
		bridge_host, bridge_port, CH_YAW, CH_ROLL
	])


func _process(delta: float) -> void:
	if not _connected or _camera == null:
		return

	_send_timer += delta
	var interval: float = 1.0 / send_rate_hz
	if _send_timer < interval:
		return
	_send_timer -= interval

	# Euler rotation in radians (Godot uses YXZ order by default)
	var rot: Vector3 = _camera.global_rotation
	var yaw_deg: float = rad_to_deg(rot.y)
	var roll_deg: float = rad_to_deg(rot.z)

	# Clamp and map to servo range
	var yaw_servo: int = _map_clamp(yaw_deg, yaw_min_deg, yaw_max_deg,
									servo_min_angle, servo_max_angle)
	var roll_servo: int = _map_clamp(roll_deg, roll_min_deg, roll_max_deg,
									 servo_min_angle, servo_max_angle)
	roll_servo = clampi(roll_servo + ch3_offset_deg, servo_min_angle, servo_max_angle)

	# Only send if angle changed beyond deadband
	if absi(yaw_servo - _last_yaw_angle) >= int(deadband_deg):
		_send_angle(CH_YAW, yaw_servo)
		_last_yaw_angle = yaw_servo

	if absi(roll_servo - _last_roll_angle) >= int(deadband_deg):
		_send_angle(CH_ROLL, roll_servo)
		_last_roll_angle = roll_servo


func _send_angle(channel: int, angle: int) -> void:
	var msg: String = "%d,%d\n" % [channel, angle]
	_udp.put_packet(msg.to_utf8_buffer())


## Clamp input to [in_min, in_max], linearly map to [out_min, out_max], return int.
func _map_clamp(value: float, in_min: float, in_max: float,
				out_min: int, out_max: int) -> int:
	var clamped: float = clampf(value, in_min, in_max)
	var t: float = (clamped - in_min) / (in_max - in_min)
	return int(roundf(lerpf(float(out_min), float(out_max), t)))
