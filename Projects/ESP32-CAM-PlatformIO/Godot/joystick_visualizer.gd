extends Node3D
## Head-locked joystick visualizer for VR HUD.
## Shows a small circle with a dot indicating the right-thumbstick deflection.
## Placed near the orientation gizmo in the bottom-right peripheral view.

# --- Configurable parameters -------------------------------------------------

## Distance from the eye (meters).
@export var hud_distance: float = 0.38

## Offset in camera local XY (right, down). Left of the orientation gizmo.
@export var hud_offset: Vector2 = Vector2(0.14, -0.16)

## Radius of the outer ring (meters in world space at hud_distance).
@export var ring_radius: float = 0.018

## Radius of the moving dot (meters).
@export var dot_radius: float = 0.004

## Number of segments for the outer ring.
@export var ring_segments: int = 32

## Thickness of the ring line (meters — thin box cross-section).
@export var ring_thickness: float = 0.001

## Color of outer ring, crosshair, and dot (idle / deflected).
@export var ring_color: Color = Color(0.6, 0.6, 0.6, 0.8)
@export var dot_idle_color: Color = Color(0.4, 0.4, 0.4, 0.8)
@export var dot_active_color: Color = Color(0.2, 0.85, 1.0, 1.0)
@export var crosshair_color: Color = Color(0.35, 0.35, 0.35, 0.5)

# --- Internal -----------------------------------------------------------------
var _right_hand: XRController3D = null
var _dot: MeshInstance3D = null
var _mat_ring: StandardMaterial3D = null
var _mat_dot: StandardMaterial3D = null
var _debug_timer: float = 0.0
var _debug_printed: bool = false


func _ready() -> void:
	var cam: XRCamera3D = get_parent() as XRCamera3D
	if cam == null:
		printerr("[JoyVis] Must be a child of XRCamera3D")
		return

	# Fixed head-locked position
	position = Vector3(hud_offset.x, hud_offset.y, -hud_distance)

	_right_hand = get_node_or_null("../../RightHand") as XRController3D
	if _right_hand == null:
		printerr("[JoyVis] RightHand node not found at ../../RightHand")
	else:
		print("[JoyVis] RightHand found: tracker='%s' has_pose=%s" % [
			_right_hand.tracker, _right_hand.get_has_tracking_data()
		])
		# Connect signals for event-driven diagnostics
		_right_hand.input_vector2_changed.connect(_on_vector2_changed)
		_right_hand.input_float_changed.connect(_on_float_changed)
		_right_hand.profile_changed.connect(_on_profile_changed)
		_right_hand.button_pressed.connect(_on_button_pressed)

	# --- Materials (unshaded, no depth test so they overlay everything) ---
	_mat_ring = _make_material(ring_color)
	var mat_cross: StandardMaterial3D = _make_material(crosshair_color)
	_mat_dot = _make_material(dot_idle_color)

	# --- Outer ring ---
	_build_ring(_mat_ring)

	# --- Crosshair (two thin bars) ---
	_build_crosshair(mat_cross)

	# --- Moving dot ---
	_dot = MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = dot_radius
	sphere.height = dot_radius * 2.0
	sphere.radial_segments = 12
	sphere.rings = 6
	_dot.mesh = sphere
	_dot.material_override = _mat_dot
	add_child(_dot)


func _process(delta: float) -> void:
	# Periodic debug: print raw input values for first 5 seconds
	_debug_timer += delta
	if _right_hand and _debug_timer >= 1.0 and _debug_timer < 6.0 and not _debug_printed:
		var has_data: bool = _right_hand.get_has_tracking_data()
		var primary_raw: Variant = _right_hand.get_input("primary")
		var primary_v2: Vector2 = _right_hand.get_vector2("primary")
		print("[JoyVis] t=%.0f tracking=%s  get_input('primary')=%s  get_vector2='%s'" % [
			_debug_timer, has_data, str(primary_raw), str(primary_v2)
		])
		if _debug_timer >= 5.0:
			_debug_printed = true
			print("[JoyVis] (debug logging stopped)")

	var joy: Vector2 = Vector2.ZERO
	if _right_hand:
		joy = _right_hand.get_vector2("primary")

	# Keyboard fallback: I/J/K/L (matches car_controller.gd)
	if joy.is_zero_approx():
		if Input.is_key_pressed(KEY_I):
			joy.y += 1.0
		if Input.is_key_pressed(KEY_K):
			joy.y -= 1.0
		if Input.is_key_pressed(KEY_J):
			joy.x -= 1.0
		if Input.is_key_pressed(KEY_L):
			joy.x += 1.0

	if _dot == null:
		return

	# Move the dot proportional to stick deflection within the ring radius
	_dot.position = Vector3(joy.x * ring_radius, joy.y * ring_radius, 0.0)

	# Change dot color when deflected
	var magnitude: float = joy.length()
	if magnitude > 0.1:
		_mat_dot.albedo_color = dot_active_color
	else:
		_mat_dot.albedo_color = dot_idle_color


# --- Build helpers ------------------------------------------------------------

func _make_material(color: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.no_depth_test = true
	mat.render_priority = 10
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return mat


func _build_ring(mat: StandardMaterial3D) -> void:
	# Approximate a circle with small box segments
	for i in range(ring_segments):
		var angle: float = TAU * float(i) / float(ring_segments)
		var next_angle: float = TAU * float(i + 1) / float(ring_segments)
		var mid_angle: float = (angle + next_angle) * 0.5

		# Segment center on the ring
		var cx: float = cos(mid_angle) * ring_radius
		var cy: float = sin(mid_angle) * ring_radius

		# Segment length = chord between consecutive points
		var seg_len: float = 2.0 * ring_radius * sin(TAU / float(ring_segments) * 0.5)

		var box := BoxMesh.new()
		box.size = Vector3(seg_len, ring_thickness, ring_thickness)

		var mi := MeshInstance3D.new()
		mi.mesh = box
		mi.material_override = mat
		mi.position = Vector3(cx, cy, 0.0)
		mi.rotation.z = mid_angle  # align tangent to ring
		add_child(mi)


func _build_crosshair(mat: StandardMaterial3D) -> void:
	# Horizontal bar
	var h_bar := MeshInstance3D.new()
	var h_box := BoxMesh.new()
	h_box.size = Vector3(ring_radius * 2.0, ring_thickness * 0.6, ring_thickness * 0.6)
	h_bar.mesh = h_box
	h_bar.material_override = mat
	add_child(h_bar)

	# Vertical bar
	var v_bar := MeshInstance3D.new()
	var v_box := BoxMesh.new()
	v_box.size = Vector3(ring_thickness * 0.6, ring_radius * 2.0, ring_thickness * 0.6)
	v_bar.mesh = v_box
	v_bar.material_override = mat
	add_child(v_bar)


# --- Signal-based diagnostics (fires even when polling misses it) -------------

var _vec2_event_count: int = 0

func _on_vector2_changed(action_name: String, value: Vector2) -> void:
	_vec2_event_count += 1
	if _vec2_event_count <= 5:
		print("[JoyVis] SIGNAL input_vector2_changed: '%s' = %s" % [action_name, str(value)])
	elif _vec2_event_count == 6:
		print("[JoyVis] (suppressing further vector2 logs)")


func _on_float_changed(action_name: String, value: float) -> void:
	print("[JoyVis] SIGNAL input_float_changed: '%s' = %.3f" % [action_name, value])


func _on_profile_changed(role: String) -> void:
	print("[JoyVis] SIGNAL profile_changed: role='%s'" % role)


func _on_button_pressed(action_name: String) -> void:
	print("[JoyVis] SIGNAL button_pressed: '%s'" % action_name)
