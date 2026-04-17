extends Node
## Tests for VR initialization logic from vr_main.gd.
## Run: godot --headless --script res://test/test_vr_init.gd

var _pass_count: int = 0
var _fail_count: int = 0


func _ready() -> void:
	print("[TEST] === VR Init Tests ===")
	test_openxr_interface_lookup()
	test_viewport_xr_default_off()
	print("[TEST] === Results: %d passed, %d failed ===" % [_pass_count, _fail_count])
	if _fail_count > 0:
		printerr("[TEST] FAILURES DETECTED")
	get_tree().quit(1 if _fail_count > 0 else 0)


func assert_true(condition: bool, test_name: String) -> void:
	if condition:
		print("[PASS] %s" % test_name)
		_pass_count += 1
	else:
		printerr("[FAIL] %s: condition is false" % test_name)
		_fail_count += 1


func test_openxr_interface_lookup() -> void:
	# In headless mode, OpenXR won't be available — that's expected
	var xr := XRServer.find_interface("OpenXR")
	# This should not crash; it returns null in headless
	assert_true(true, "openxr_lookup_no_crash")
	if xr == null:
		print("  (OpenXR not available in headless — expected)")


func test_viewport_xr_default_off() -> void:
	# Viewport should not have XR enabled by default
	var vp := get_viewport()
	assert_true(not vp.use_xr, "viewport_xr_default_off")
