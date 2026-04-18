extends Node3D
## Initializes the OpenXR interface for Quest 2 via Link.
## Falls back to desktop 3D view if no headset is connected.
## Based on Godot "A better XR start script" best practices.

signal focus_lost
signal focus_gained
signal pose_recentered

@export var maximum_refresh_rate: int = 90

var xr_interface: OpenXRInterface
var xr_is_focussed: bool = false

func _ready() -> void:
	xr_interface = XRServer.find_interface("OpenXR") as OpenXRInterface
	if xr_interface and xr_interface.is_initialized():
		print("[VR] OpenXR already initialized")
		_setup_xr()
	elif xr_interface:
		print("[VR] Initializing OpenXR...")
		if xr_interface.initialize():
			print("[VR] OpenXR initialized — rendering to headset")
			_setup_xr()
		else:
			printerr("[VR] OpenXR init failed — running in desktop mode")
	else:
		printerr("[VR] No OpenXR interface found — running in desktop mode")


func _setup_xr() -> void:
	var vp: Viewport = get_viewport()
	vp.use_xr = true

	# V-sync MUST be off — OpenXR does its own frame sync.
	# Leaving it on caps output to 60 Hz and causes black-frame blinking.
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)

	# Enable foveated rendering if available
	if RenderingServer.get_rendering_device():
		vp.vrs_mode = Viewport.VRS_XR
	elif int(ProjectSettings.get_setting("xr/openxr/foveation_level")) == 0:
		push_warning("[VR] Recommend setting Foveation level to High in Project Settings")

	# Connect OpenXR session lifecycle signals
	xr_interface.session_begun.connect(_on_openxr_session_begun)
	xr_interface.session_visible.connect(_on_openxr_visible_state)
	xr_interface.session_focussed.connect(_on_openxr_focused_state)
	xr_interface.session_stopping.connect(_on_openxr_stopping)
	xr_interface.pose_recentered.connect(_on_openxr_pose_recentered)


func _on_openxr_session_begun() -> void:
	# Match physics tick rate to headset refresh rate to avoid stutter
	var current_rate: float = xr_interface.get_display_refresh_rate()
	if current_rate > 0:
		print("[VR] Refresh rate reported as ", current_rate)
	else:
		print("[VR] No refresh rate given by XR runtime")

	var new_rate: float = current_rate
	var available_rates: Array = xr_interface.get_available_display_refresh_rates()
	if available_rates.size() == 0:
		print("[VR] Target does not support refresh rate extension")
	elif available_rates.size() == 1:
		new_rate = available_rates[0]
	else:
		for rate in available_rates:
			if rate > new_rate and rate <= maximum_refresh_rate:
				new_rate = rate

	if current_rate != new_rate:
		print("[VR] Setting refresh rate to ", new_rate)
		xr_interface.set_display_refresh_rate(new_rate)
		current_rate = new_rate

	if current_rate > 0:
		Engine.physics_ticks_per_second = int(current_rate)
		print("[VR] Physics tick rate set to ", Engine.physics_ticks_per_second)


func _on_openxr_visible_state() -> void:
	if xr_is_focussed:
		print("[VR] Lost focus")
		xr_is_focussed = false
		process_mode = Node.PROCESS_MODE_DISABLED
		emit_signal("focus_lost")


func _on_openxr_focused_state() -> void:
	print("[VR] Gained focus")
	xr_is_focussed = true
	process_mode = Node.PROCESS_MODE_INHERIT
	emit_signal("focus_gained")


func _on_openxr_stopping() -> void:
	print("[VR] OpenXR is stopping")


func _on_openxr_pose_recentered() -> void:
	print("[VR] Pose recentered")
	emit_signal("pose_recentered")
