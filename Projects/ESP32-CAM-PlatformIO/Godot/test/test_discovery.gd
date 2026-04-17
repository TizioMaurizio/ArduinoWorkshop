extends Node
## Tests for network discovery logic from camera_stream.gd.
## Run: godot --headless --script res://test/test_discovery.gd

var _pass_count: int = 0
var _fail_count: int = 0


func _ready() -> void:
	print("[TEST] === Discovery Logic Tests ===")
	test_subnet_extraction()
	test_skip_loopback()
	test_skip_link_local()
	test_skip_ipv6()
	test_deduplicate_subnets()
	test_esp_cam_response_positive()
	test_esp_cam_response_negative()
	test_esp_cam_response_partial()
	print("[TEST] === Results: %d passed, %d failed ===" % [_pass_count, _fail_count])
	if _fail_count > 0:
		printerr("[TEST] FAILURES DETECTED")
	get_tree().quit(1 if _fail_count > 0 else 0)


# ---------------------------------------------------------------------------
#  Functions under test (mirror camera_stream.gd discovery logic)
# ---------------------------------------------------------------------------

func extract_subnets(addrs: Array[String]) -> Array[String]:
	var subnets: Array[String] = []
	for addr in addrs:
		if ":" in addr:
			continue
		var parts := addr.split(".")
		if parts.size() != 4:
			continue
		if parts[0] == "127":
			continue
		if parts[0] == "169" and parts[1] == "254":
			continue
		var subnet := "%s.%s.%s" % [parts[0], parts[1], parts[2]]
		if subnet not in subnets:
			subnets.append(subnet)
	return subnets


func is_esp_cam_response(text: String) -> bool:
	var lower := text.to_lower()
	return lower.find("framesize") >= 0 and lower.find("quality") >= 0


# ---------------------------------------------------------------------------
#  Test helpers
# ---------------------------------------------------------------------------

func assert_eq(actual: Variant, expected: Variant, test_name: String) -> void:
	if actual == expected:
		print("[PASS] %s" % test_name)
		_pass_count += 1
	else:
		printerr("[FAIL] %s: expected %s, got %s" % [test_name, str(expected), str(actual)])
		_fail_count += 1


func assert_true(condition: bool, test_name: String) -> void:
	if condition:
		print("[PASS] %s" % test_name)
		_pass_count += 1
	else:
		printerr("[FAIL] %s: condition is false" % test_name)
		_fail_count += 1


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

func test_subnet_extraction() -> void:
	var addrs: Array[String] = ["10.105.54.252", "192.168.1.100"]
	var result := extract_subnets(addrs)
	assert_eq(result.size(), 2, "subnet_extraction_count")
	assert_true(result.has("10.105.54"), "subnet_extraction_has_10")
	assert_true(result.has("192.168.1"), "subnet_extraction_has_192")


func test_skip_loopback() -> void:
	var addrs: Array[String] = ["127.0.0.1", "10.0.0.5"]
	var result := extract_subnets(addrs)
	assert_eq(result.size(), 1, "skip_loopback_count")
	assert_eq(result[0], "10.0.0", "skip_loopback_kept")


func test_skip_link_local() -> void:
	var addrs: Array[String] = ["169.254.1.1", "10.0.0.5"]
	var result := extract_subnets(addrs)
	assert_eq(result.size(), 1, "skip_link_local_count")
	assert_eq(result[0], "10.0.0", "skip_link_local_kept")


func test_skip_ipv6() -> void:
	var addrs: Array[String] = ["::1", "fe80::1", "10.0.0.5"]
	var result := extract_subnets(addrs)
	assert_eq(result.size(), 1, "skip_ipv6_count")


func test_deduplicate_subnets() -> void:
	var addrs: Array[String] = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
	var result := extract_subnets(addrs)
	assert_eq(result.size(), 1, "deduplicate_subnets")
	assert_eq(result[0], "10.0.0", "deduplicate_subnet_value")


func test_esp_cam_response_positive() -> void:
	var resp := '{"framesize":5,"quality":10,"brightness":0}'
	assert_true(is_esp_cam_response(resp), "esp_cam_response_positive")


func test_esp_cam_response_negative() -> void:
	var resp := '{"status":"ok","version":"1.0"}'
	assert_true(not is_esp_cam_response(resp), "esp_cam_response_negative")


func test_esp_cam_response_partial() -> void:
	# Has framesize but not quality
	var resp := '{"framesize":5,"brightness":0}'
	assert_true(not is_esp_cam_response(resp), "esp_cam_response_partial")
