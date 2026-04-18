extends Node3D
## Head-locked 3-axis gizmo that shows current orientation relative to the
## calibration (startup) pose. Parented to XRCamera3D — position is fixed
## in the user's peripheral view; the inner axes rotate to indicate how far
## the head has turned from center.

# --- Configurable parameters -------------------------------------------------

## Distance from the eye (meters). Kept inside the near-clip guard.
@export var gizmo_distance: float = 0.38

## Offset in the camera's local XY plane (right, down).
@export var gizmo_offset: Vector2 = Vector2(0.22, -0.16)

## Half-length of each axis bar (meters).
@export var axis_length: float = 0.02

## Thickness of each axis bar (meters).
@export var axis_thickness: float = 0.002

# --- Internal state -----------------------------------------------------------

var _camera: XRCamera3D = null
var _axes_node: Node3D = null
var _calibrated: bool = false
var _initial_quat: Quaternion = Quaternion.IDENTITY


func _ready() -> void:
	_camera = get_parent() as XRCamera3D
	if _camera == null:
		printerr("[Gizmo] Must be a child of XRCamera3D")
		return

	# Fixed position in bottom-right of the user's view
	position = Vector3(gizmo_offset.x, gizmo_offset.y, -gizmo_distance)

	# Inner node holds axis meshes and receives the relative rotation
	_axes_node = Node3D.new()
	_axes_node.name = "Axes"
	add_child(_axes_node)

	_create_axis(Vector3.RIGHT, Color(0.95, 0.22, 0.22))   # X = red
	_create_axis(Vector3.UP,    Color(0.22, 0.90, 0.25))   # Y = green
	_create_axis(Vector3.BACK,  Color(0.30, 0.45, 0.95))   # Z = blue

	# Sync calibration reset with vr_main pose recenter
	var vr_main: Node = get_node_or_null("/root/Main")
	if vr_main and vr_main.has_signal("pose_recentered"):
		vr_main.pose_recentered.connect(_on_pose_recentered)


func _create_axis(direction: Vector3, color: Color) -> void:
	var mesh_instance := MeshInstance3D.new()
	var box := BoxMesh.new()

	var size := Vector3(axis_thickness, axis_thickness, axis_thickness)
	if direction.x != 0.0:
		size.x = axis_length
	elif direction.y != 0.0:
		size.y = axis_length
	else:
		size.z = axis_length
	box.size = size

	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.no_depth_test = true
	mat.render_priority = 10

	mesh_instance.mesh = box
	mesh_instance.material_override = mat
	mesh_instance.position = direction * (axis_length * 0.5)
	_axes_node.add_child(mesh_instance)


func _process(_delta: float) -> void:
	if _camera == null:
		return

	var quat: Quaternion = _camera.global_transform.basis.get_rotation_quaternion()

	if not _calibrated:
		_initial_quat = quat
		_calibrated = true

	# Show the calibration frame's axes as seen from the current viewpoint.
	# Since this node is parented to the camera, setting the inner rotation
	# to (current⁻¹ · initial) counter-rotates the camera movement and
	# keeps the axes pointing toward the calibration "center."
	_axes_node.basis = Basis(quat.inverse() * _initial_quat)


func _on_pose_recentered() -> void:
	_calibrated = false
