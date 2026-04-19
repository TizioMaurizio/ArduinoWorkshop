extends Node
## Drives the ELEGOO Smart Robot Car V4.0 using the right VR controller joystick.
## Keyboard fallback: I/J/K/L = fwd/left/back/right (for testing without VR input).
##
## The car's ESP32-WROVER connects to the local WiFi network (STA mode).
## Auto-discovery via UDP broadcast on port 9999, or set car_ip manually.
##
## Protocol: TCP JSON to ESP32 on port 100
##   N:3  — movement: {"N":3,"D1":<dir>,"D2":<speed>,"H":"<seq>"}
##            D1: 1=Left, 2=Right, 3=Forward, 4=Backward
##   N:100 — stop:     {"N":100,"H":"<seq>"}
##   Heartbeat:        {Heartbeat} every ~1s

# --- Configuration -----------------------------------------------------------

## Car IP — leave empty to use auto-discovery. Set manually as fallback.
@export var car_ip: String = ""
@export var car_port: int = 100

## Maximum motor speed sent to the car (0–255). Keep low for gentle control.
@export var max_speed: int = 40

## Maximum rotation speed for left/right turns (0–255). Separate from drive speed.
@export var max_rotation_speed: int = 30

## Joystick deadband — ignore stick deflection below this threshold.
@export var deadband: float = 0.15

## How often to send commands (Hz).
@export var send_rate_hz: float = 10.0

## Seconds before auto-reconnect after disconnect.
@export var reconnect_delay_sec: float = 3.0

# --- Discovery ----------------------------------------------------------------
## UDP port for auto-discovery broadcast from the car.
const DISCOVERY_PORT: int = 9999
## How long to wait for discovery before falling back to car_ip (seconds).
@export var discovery_timeout_sec: float = 8.0

# --- ELEGOO direction codes (N:3, D1) ----------------------------------------
const DIR_LEFT: int = 1
const DIR_RIGHT: int = 2
const DIR_FORWARD: int = 3
const DIR_BACKWARD: int = 4

# --- Internal state -----------------------------------------------------------
var _tcp: StreamPeerTCP = StreamPeerTCP.new()
var _right_hand: XRController3D = null
var _send_timer: float = 0.0
var _heartbeat_timer: float = 0.0
var _reconnect_timer: float = 0.0
var _cmd_counter: int = 0
var _last_action: String = "none"
var _connected: bool = false
var _connecting: bool = false
var _gave_up: bool = false  # stop retry after too many failures
var _connect_attempts: int = 0
const MAX_CONNECT_ATTEMPTS: int = 5

# --- Discovery state ----------------------------------------------------------
var _discovery_udp: PacketPeerUDP = PacketPeerUDP.new()
var _discovery_timer: float = 0.0
var _discovered: bool = false

func _ready() -> void:
	_right_hand = get_node_or_null("../XROrigin3D/RightHand")
	if _right_hand == null:
		printerr("[Car] RightHand XRController3D not found in scene tree")
		return
	print("[Car] Right joystick → car control (max_speed=%d, deadband=%.2f)" % [
		max_speed, deadband
	])

	# If car_ip is set, skip discovery and connect directly.
	if car_ip != "":
		print("[Car] Using configured IP: %s" % car_ip)
		_discovered = true
		_start_connect()
		return

	# Start UDP discovery listener
	var err: int = _discovery_udp.bind(DISCOVERY_PORT)
	if err != OK:
		printerr("[Car] Failed to bind UDP discovery port %d (err=%d)" % [
			DISCOVERY_PORT, err
		])
	else:
		print("[Car] Listening for car discovery on UDP port %d..." % DISCOVERY_PORT)


func _start_connect() -> void:
	if _gave_up:
		return
	_connecting = true
	_connected = false
	var err: int = _tcp.connect_to_host(car_ip, car_port)
	if err != OK:
		printerr("[Car] connect_to_host error: %d" % err)
		_connecting = false
	else:
		_connect_attempts += 1
		print("[Car] Connecting to %s:%d (attempt %d)..." % [
			car_ip, car_port, _connect_attempts
		])


func _process(delta: float) -> void:
	# --- UDP discovery (runs until car is found) ---
	if not _discovered:
		_check_discovery(delta)
		return

	_tcp.poll()
	var status: StreamPeerTCP.Status = _tcp.get_status() as StreamPeerTCP.Status

	# --- Connection state machine ---
	if _connecting:
		if status == StreamPeerTCP.STATUS_CONNECTED:
			_connecting = false
			_connected = true
			_connect_attempts = 0
			print("[Car] Connected to %s:%d" % [car_ip, car_port])
		elif status == StreamPeerTCP.STATUS_NONE or status == StreamPeerTCP.STATUS_ERROR:
			_connecting = false
			_connected = false
			printerr("[Car] Connection failed (attempt %d)" % _connect_attempts)
			if _connect_attempts >= MAX_CONNECT_ATTEMPTS:
				_gave_up = true
				printerr("[Car] Giving up after %d attempts. Reconnect manually." %
					MAX_CONNECT_ATTEMPTS)
			else:
				_reconnect_timer = 0.0
		return

	# --- Reconnect timer ---
	if not _connected and not _gave_up:
		_reconnect_timer += delta
		if _reconnect_timer >= reconnect_delay_sec:
			_start_connect()
		return

	if not _connected:
		return

	# --- Check for disconnect ---
	if status != StreamPeerTCP.STATUS_CONNECTED:
		_connected = false
		_connect_attempts = 0
		_reconnect_timer = 0.0
		printerr("[Car] Disconnected — will retry in %.0fs" % reconnect_delay_sec)
		return

	# --- Heartbeat (keep-alive) ---
	_heartbeat_timer += delta
	if _heartbeat_timer >= 1.0:
		_heartbeat_timer -= 1.0
		_tcp.put_data("{Heartbeat}".to_utf8_buffer())

	# --- Rate-limited joystick read ---
	_send_timer += delta
	var interval: float = 1.0 / send_rate_hz
	if _send_timer < interval:
		return
	_send_timer -= interval

	# Read the right-hand thumbstick.
	# In Godot OpenXR, each hand's "primary" = that hand's thumbstick.
	var joy: Vector2 = Vector2.ZERO
	if _right_hand:
		joy = _right_hand.get_vector2("primary")

	# Keyboard fallback: I/J/K/L = fwd/left/back/right
	if joy.is_zero_approx():
		if Input.is_key_pressed(KEY_I):
			joy.y += 1.0
		if Input.is_key_pressed(KEY_K):
			joy.y -= 1.0
		if Input.is_key_pressed(KEY_J):
			joy.x -= 1.0
		if Input.is_key_pressed(KEY_L):
			joy.x += 1.0

	# Apply deadband
	if absf(joy.x) < deadband:
		joy.x = 0.0
	if absf(joy.y) < deadband:
		joy.y = 0.0

	# OpenXR thumbstick: Y+ = push forward, Y- = pull back, X+ = right, X- = left
	# Dominant axis wins — this avoids unintentional diagonal drift
	if absf(joy.y) >= absf(joy.x) and absf(joy.y) > 0.0:
		var speed: int = int(absf(joy.y) * float(max_speed))
		if joy.y > 0.0:
			_send_move(DIR_FORWARD, speed)
		else:
			_send_move(DIR_BACKWARD, speed)
	elif absf(joy.x) > 0.0:
		var speed: int = int(absf(joy.x) * float(max_rotation_speed))
		if joy.x > 0.0:
			_send_move(DIR_RIGHT, speed)
		else:
			_send_move(DIR_LEFT, speed)
	else:
		# Joystick centred — stop
		if _last_action != "stop":
			_send_stop()


func _send_move(direction: int, speed: int) -> void:
	_cmd_counter += 1
	var cmd: String = '{"N":3,"D1":%d,"D2":%d,"H":"%d"}' % [
		direction, speed, _cmd_counter
	]
	_tcp.put_data(cmd.to_utf8_buffer())

	var names: Dictionary = {
		DIR_FORWARD: "fwd", DIR_BACKWARD: "bwd",
		DIR_LEFT: "left", DIR_RIGHT: "right"
	}
	_last_action = names.get(direction, "?")


func _send_stop() -> void:
	_cmd_counter += 1
	var cmd: String = '{"N":100,"H":"%d"}' % _cmd_counter
	_tcp.put_data(cmd.to_utf8_buffer())
	_last_action = "stop"


func _exit_tree() -> void:
	if _connected:
		_send_stop()
	_tcp.disconnect_from_host()
	_discovery_udp.close()


# --- UDP auto-discovery -------------------------------------------------------
func _check_discovery(delta: float) -> void:
	# Check for broadcast packets (handles both car and arm discovery)
	while _discovery_udp.get_available_packet_count() > 0:
		var data: String = _discovery_udp.get_packet().get_string_from_utf8()
		var json: Variant = JSON.parse_string(data)
		if not (json is Dictionary):
			continue

		var service: String = json.get("service", "")

		# Car discovery
		if service == "elegoo-car" and not _discovered:
			var ip: String = json.get("ip", "")
			var port: int = int(json.get("port", 100))
			if ip != "":
				car_ip = ip
				car_port = port
				_discovered = true
				print("[Car] Discovered car at %s:%d" % [car_ip, car_port])
				_start_connect()

		# Arm discovery — dispatch to ServoController
		if service == "esp32-cam-arm":
			var ip: String = json.get("ip", "")
			var servo_port: int = int(json.get("servo", 9685))
			if ip != "":
				var servo_ctrl: Node = get_node_or_null("../ServoController")
				if servo_ctrl and servo_ctrl.has_method("on_arm_discovered"):
					servo_ctrl.on_arm_discovered(ip, servo_port)

	# Close socket only after both are done (or timeout)
	if _discovered:
		# Keep listening for arm broadcasts too — don't close yet
		# Close when scene exits (_exit_tree)
		return

	# Timeout — try mDNS hostname resolution as fallback
	_discovery_timer += delta
	if _discovery_timer >= discovery_timeout_sec:
		print("[Car] Discovery timeout — trying elegoo-car.local via mDNS...")
		var resolved: String = IP.resolve_hostname("elegoo-car.local")
		if resolved != "" and resolved != "0.0.0.0":
			car_ip = resolved
			_discovered = true
			print("[Car] Resolved elegoo-car.local → %s" % car_ip)
			_start_connect()
		else:
			printerr("[Car] mDNS resolution failed. Set car_ip manually in the inspector.")
