extends Node3D
## Comprehensive XR input diagnostic — attaches to XRCamera3D, logs everything.
## Replace OrientationGizmo temporarily or add as sibling under XRCamera3D.
##
## Tests:
## 0. OpenXR runtime info
## 1. XRServer tracker enumeration
## 2. All known action names (poll + signal)
## 3. Raw tracker get_input() bypassing XRController3D
## 4. Joypad fallback check
## 5. Always-print analog inputs (trigger, grip, primary_touch)

## Actions that are ALWAYS printed, even if zero — critical for diagnosing
## whether analog/float/Vector2 types work at all.
const ALWAYS_PRINT: Array[String] = [
	"primary", "secondary",
	"trigger", "grip",
	"primary_touch", "primary_click",
	"ax_button", "by_button",
]

var ACTION_NAMES: Array[String] = [
	"primary", "primary_click", "primary_touch",
	"secondary", "secondary_click", "secondary_touch",
	"trigger", "trigger_click", "trigger_touch",
	"grip", "grip_click", "grip_force",
	"ax_button", "ax_touch", "by_button", "by_touch",
	"menu_button", "select_button",
	"default_pose", "aim_pose", "grip_pose", "palm_pose",
	"haptic",
]

var _right_hand: XRController3D = null
var _left_hand: XRController3D = null
var _timer: float = 0.0
var _dump_count: int = 0


func _ready() -> void:
	_right_hand = get_node_or_null("../../RightHand") as XRController3D
	_left_hand = get_node_or_null("../../LeftHand") as XRController3D

	print("=" .repeat(70))
	print("[XR-DIAG] === XR Input Diagnostic Started ===")
	print("=" .repeat(70))

	# --- Test 0: OpenXR runtime info ---
	print("\n[TEST 0] OpenXR runtime info:")
	var xr_interface: XRInterface = XRServer.find_interface("OpenXR")
	if xr_interface:
		print("  interface: %s" % xr_interface.get_name())
		print("  initialized: %s" % xr_interface.is_initialized())
		print("  passthrough_supported: %s" % xr_interface.is_passthrough_supported())
		# Try getting system info (Godot 4.6+)
		if xr_interface.has_method("get_system_info"):
			var info: Dictionary = xr_interface.call("get_system_info")
			for k: String in info:
				print("  system_info[%s] = %s" % [k, str(info[k])])
	else:
		print("  [WARNING] OpenXR interface NOT found!")

	# --- Test 1: XRServer tracker enumeration ---
	print("\n[TEST 1] XRServer trackers:")
	var trackers: Dictionary = XRServer.get_trackers(0xFF)  # all types
	if trackers.size() == 0:
		print("  (no trackers found)")
	for key: Variant in trackers:
		var tracker: XRPositionalTracker = trackers[key] as XRPositionalTracker
		if tracker:
			print("  tracker: name='%s' type=%d hand=%d profile='%s'" % [
				tracker.name, tracker.type, tracker.hand,
				tracker.profile if tracker.has_method("get_profile") else "n/a"
			])

	# --- Test 2: Controller node state ---
	print("\n[TEST 2] Controller nodes:")
	_dump_controller("RightHand", _right_hand)
	_dump_controller("LeftHand", _left_hand)

	# --- Connect signals on right hand ---
	if _right_hand:
		_right_hand.input_vector2_changed.connect(
			func(n: String, v: Vector2) -> void:
				print("[SIGNAL-R] vector2_changed: '%s' = %s" % [n, str(v)])
		)
		_right_hand.input_float_changed.connect(
			func(n: String, v: float) -> void:
				print("[SIGNAL-R] float_changed: '%s' = %.4f" % [n, v])
		)
		_right_hand.button_pressed.connect(
			func(n: String) -> void:
				print("[SIGNAL-R] button_pressed: '%s'" % n)
		)
		_right_hand.button_released.connect(
			func(n: String) -> void:
				print("[SIGNAL-R] button_released: '%s'" % n)
		)
		_right_hand.profile_changed.connect(
			func(role: String) -> void:
				print("[SIGNAL-R] profile_changed: role='%s'" % role)
		)
		_right_hand.tracking_changed.connect(
			func(has_tracking: bool) -> void:
				print("[SIGNAL-R] tracking_changed: %s" % str(has_tracking))
		)

	# --- Connect signals on left hand ---
	if _left_hand:
		_left_hand.input_vector2_changed.connect(
			func(n: String, v: Vector2) -> void:
				print("[SIGNAL-L] vector2_changed: '%s' = %s" % [n, str(v)])
		)
		_left_hand.button_pressed.connect(
			func(n: String) -> void:
				print("[SIGNAL-L] button_pressed: '%s'" % n)
		)

	print("\n[XR-DIAG] Signals connected. Will poll all actions every 2 seconds.")
	print("[XR-DIAG] Move BOTH thumbsticks, squeeze triggers, press A/B/X/Y.")
	print("=" .repeat(70))


func _dump_controller(label: String, ctrl: XRController3D) -> void:
	if ctrl == null:
		print("  %s: NULL" % label)
		return
	print("  %s: tracker='%s' has_tracking=%s hand=%d" % [
		label, ctrl.tracker, ctrl.get_has_tracking_data(), ctrl.get_tracker_hand()
	])


func _process(delta: float) -> void:
	_timer += delta
	if _timer < 2.0:
		return
	_timer -= 2.0
	_dump_count += 1

	if _dump_count > 15:
		return  # Stop after 30 seconds

	print("\n--- Poll #%d (t=%.0f) ---" % [_dump_count, _dump_count * 2.0])

	# --- Test 3: Poll all action names on right hand ---
	if _right_hand:
		var rh_tracker: XRPositionalTracker = XRServer.get_tracker(
			_right_hand.tracker) as XRPositionalTracker
		var rh_profile: String = rh_tracker.profile if rh_tracker else "?"
		print("[RIGHT HAND] tracking=%s  profile='%s'" % [
			_right_hand.get_has_tracking_data(), rh_profile
		])
		for action_name: String in ACTION_NAMES:
			var raw: Variant = _right_hand.get_input(action_name)
			if raw == null:
				if action_name in ALWAYS_PRINT:
					print("  get_input('%s') = NULL" % action_name)
				continue
			# Always print ALWAYS_PRINT actions (even if zero), plus any non-default
			var dominated: bool = action_name in ALWAYS_PRINT
			if dominated or _is_nonzero(raw):
				print("  get_input('%s') = %s [type=%s]" % [
					action_name, str(raw), type_string(typeof(raw))
				])

	# --- Poll LEFT hand too (always print key actions) ---
	if _left_hand:
		var lp: Variant = _left_hand.get_input("primary")
		var ls: Variant = _left_hand.get_input("secondary")
		var lt: Variant = _left_hand.get_input("trigger")
		var la: Variant = _left_hand.get_input("ax_button")
		print("[LEFT HAND] primary=%s  secondary=%s  trigger=%s  ax_button=%s" % [
			str(lp), str(ls), str(lt), str(la)
		])

	# --- Test 4: Direct tracker access (bypasses XRController3D) ---
	var tracker: XRPositionalTracker = XRServer.get_tracker("right_hand") as XRPositionalTracker
	if tracker:
		var primary_direct: Variant = tracker.get_input("primary")
		var secondary_direct: Variant = tracker.get_input("secondary")
		print("[TRACKER DIRECT] primary=%s  secondary=%s" % [
			str(primary_direct), str(secondary_direct)
		])
	else:
		print("[TRACKER DIRECT] right_hand tracker not found in XRServer")

	# --- Test 5: Godot joypad system (Quest controllers sometimes appear here) ---
	var joy_count: int = Input.get_connected_joypads().size()
	if joy_count > 0:
		print("[JOYPAD] %d joypad(s) connected" % joy_count)
		for joy_id: int in Input.get_connected_joypads():
			var name: String = Input.get_joy_name(joy_id)
			var lx: float = Input.get_joy_axis(joy_id, JOY_AXIS_LEFT_X)
			var ly: float = Input.get_joy_axis(joy_id, JOY_AXIS_LEFT_Y)
			var rx: float = Input.get_joy_axis(joy_id, JOY_AXIS_RIGHT_X)
			var ry: float = Input.get_joy_axis(joy_id, JOY_AXIS_RIGHT_Y)
			if absf(lx) > 0.01 or absf(ly) > 0.01 or absf(rx) > 0.01 or absf(ry) > 0.01:
				print("  joy[%d] '%s': L=(%.3f,%.3f) R=(%.3f,%.3f)" % [
					joy_id, name, lx, ly, rx, ry
				])
			else:
				print("  joy[%d] '%s': all axes ~0" % [joy_id, name])


func _is_nonzero(v: Variant) -> bool:
	if v is float:
		return absf(v as float) > 0.001
	if v is bool:
		return v as bool
	if v is Vector2:
		return (v as Vector2).length() > 0.001
	return v != null
