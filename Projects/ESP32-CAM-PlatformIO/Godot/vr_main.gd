extends Node3D
## Initializes the OpenXR interface for Quest 2 via Link.
## Falls back to desktop 3D view if no headset is connected.

var xr_interface: XRInterface

func _ready() -> void:
	xr_interface = XRServer.find_interface("OpenXR")
	if xr_interface and xr_interface.is_initialized():
		print("[VR] OpenXR already initialized")
		get_viewport().use_xr = true
	elif xr_interface:
		print("[VR] Initializing OpenXR...")
		if xr_interface.initialize():
			print("[VR] OpenXR initialized — rendering to headset")
			get_viewport().use_xr = true
			DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
		else:
			printerr("[VR] OpenXR init failed — running in desktop mode")
	else:
		printerr("[VR] No OpenXR interface found — running in desktop mode")
