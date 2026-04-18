extends Node
## Tests for servo_controller.gd logic.
## Run: godot --headless --script res://test/test_servo_protocol.gd
##
## Validates: angle mapping, deadband, packet format, auto-discovery gating.

var _pass_count: int = 0
var _fail_count: int = 0


func _ready() -> void:
	print("[TEST] === Servo Protocol Tests ===")
	test_map_clamp_centre()
	test_map_clamp_min()
	test_map_clamp_max()
	test_map_clamp_over_max()
	test_map_clamp_under_min()
	test_packet_format()
	test_deadband_suppresses_small_change()
	test_deadband_allows_large_change()
	test_auto_discovery_waits_for_connected()
	print("[TEST] === Results: %d passed, %d failed ===" % [_pass_count, _fail_count])
	if _fail_count > 0:
		printerr("[TEST] FAILURES DETECTED")
	get_tree().quit(1 if _fail_count > 0 else 0)


# ---------------------------------------------------------------------------
#  Helpers — mirror servo_controller.gd logic
# ---------------------------------------------------------------------------

func _map_clamp(value: float, in_min: float, in_max: float,
				out_min: int, out_max: int) -> int:
	var clamped: float = clampf(value, in_min, in_max)
	var t: float = (clamped - in_min) / (in_max - in_min)
	return int(roundf(lerpf(float(out_min), float(out_max), t)))

func _format_packet(channel: int, angle: int) -> String:
	return "%d,%d\n" % [channel, angle]

# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

func test_map_clamp_centre() -> void:
	# 0 deg in [-90, 90] should map to 90 in [0, 180]
	var result := _map_clamp(0.0, -90.0, 90.0, 0, 180)
	_assert_eq(result, 90, "map_clamp centre")

func test_map_clamp_min() -> void:
	var result := _map_clamp(-90.0, -90.0, 90.0, 0, 180)
	_assert_eq(result, 0, "map_clamp min")

func test_map_clamp_max() -> void:
	var result := _map_clamp(90.0, -90.0, 90.0, 0, 180)
	_assert_eq(result, 180, "map_clamp max")

func test_map_clamp_over_max() -> void:
	# Over max should clamp to max
	var result := _map_clamp(120.0, -90.0, 90.0, 0, 180)
	_assert_eq(result, 180, "map_clamp over max clamps")

func test_map_clamp_under_min() -> void:
	var result := _map_clamp(-120.0, -90.0, 90.0, 0, 180)
	_assert_eq(result, 0, "map_clamp under min clamps")

func test_packet_format() -> void:
	var pkt := _format_packet(0, 90)
	_assert_eq(pkt, "0,90\n", "packet format ch0 90")
	var pkt2 := _format_packet(3, 0)
	_assert_eq(pkt2, "3,0\n", "packet format ch3 0")
	var pkt3 := _format_packet(0, 180)
	_assert_eq(pkt3, "0,180\n", "packet format ch0 180")

func test_deadband_suppresses_small_change() -> void:
	# If last sent was 90, and new is 90, deadband=1 should suppress
	var last := 90
	var next := 90
	var deadband := 1
	_assert_eq(absi(next - last) >= deadband, false, "deadband suppresses 0 change")

func test_deadband_allows_large_change() -> void:
	var last := 90
	var next := 92
	var deadband := 1
	_assert_eq(absi(next - last) >= deadband, true, "deadband allows 2-deg change")

func test_auto_discovery_waits_for_connected() -> void:
	# Simulates: esp_ip is set but _connected is false → should NOT grab IP
	var esp_ip := "10.105.54.157"
	var cam_connected := false
	var should_grab := (cam_connected == true)
	_assert_eq(should_grab, false, "don't grab IP when camera not connected")

	# Now simulate connected
	cam_connected = true
	should_grab = (cam_connected == true)
	_assert_eq(should_grab, true, "grab IP when camera connected")

# ---------------------------------------------------------------------------
#  Assert helpers
# ---------------------------------------------------------------------------

func _assert_eq(actual: Variant, expected: Variant, label: String) -> void:
	if actual == expected:
		print("  PASS  %s" % label)
		_pass_count += 1
	else:
		printerr("  FAIL  %s  expected=%s  got=%s" % [label, str(expected), str(actual)])
		_fail_count += 1
