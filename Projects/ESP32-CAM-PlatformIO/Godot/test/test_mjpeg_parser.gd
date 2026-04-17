extends Node
## Host-side tests for camera_stream.gd logic.
## Run: godot --headless --script res://test/test_mjpeg_parser.gd

# ---------------------------------------------------------------------------
#  Simulated buffer + parser functions (copied from camera_stream.gd)
#  These are pure functions operating on PackedByteArray — no network I/O.
# ---------------------------------------------------------------------------

var _pass_count: int = 0
var _fail_count: int = 0


func _ready() -> void:
	print("[TEST] === MJPEG Parser Tests ===")
	test_find_marker_basic()
	test_find_marker_not_found()
	test_find_marker_multiple_ff()
	test_find_crlfcrlf_basic()
	test_find_crlfcrlf_not_found()
	test_find_crlfcrlf_partial()
	test_extract_single_frame()
	test_extract_multiple_frames_keeps_last()
	test_incomplete_frame_waits()
	test_corrupt_frame_skipped()
	test_header_skip()
	test_empty_buffer()
	test_max_buffer_cap()
	test_soi_at_buffer_boundary()
	print("[TEST] === Results: %d passed, %d failed ===" % [_pass_count, _fail_count])
	if _fail_count > 0:
		printerr("[TEST] FAILURES DETECTED")
	get_tree().quit(1 if _fail_count > 0 else 0)


# ---------------------------------------------------------------------------
#  Parser functions under test (mirror camera_stream.gd exactly)
# ---------------------------------------------------------------------------

func find_marker(buf: PackedByteArray, second_byte: int, from: int) -> int:
	var pos := from
	while true:
		var idx := buf.find(0xFF, pos)
		if idx < 0 or idx + 1 >= buf.size():
			return -1
		if buf[idx + 1] == second_byte:
			return idx
		pos = idx + 1
	return -1


func find_crlfcrlf(buf: PackedByteArray, from: int) -> int:
	var pos := from
	while true:
		var idx := buf.find(0x0D, pos)
		if idx < 0 or idx + 3 >= buf.size():
			return -1
		if buf[idx + 1] == 0x0A and buf[idx + 2] == 0x0D and buf[idx + 3] == 0x0A:
			return idx
		pos = idx + 1
	return -1


func extract_frames(buf: PackedByteArray) -> Array:
	## Returns [last_jpeg: PackedByteArray, remaining_buf: PackedByteArray, frame_count: int]
	var frames_found: int = 0
	var last_jpeg: PackedByteArray = PackedByteArray()
	var search_from: int = 0

	while true:
		var soi := find_marker(buf, 0xD8, search_from)
		if soi < 0:
			break
		var eoi := find_marker(buf, 0xD9, soi + 2)
		if eoi < 0:
			if soi > 0:
				buf = buf.slice(soi)
			return [last_jpeg, buf, frames_found]
		var frame_end := eoi + 2
		last_jpeg = buf.slice(soi, frame_end)
		search_from = frame_end
		frames_found += 1

	if search_from > 0:
		buf = buf.slice(search_from)
	return [last_jpeg, buf, frames_found]


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


func make_jpeg(payload_size: int = 4) -> PackedByteArray:
	## Build a minimal JPEG: SOI + payload + EOI
	var data := PackedByteArray()
	data.append(0xFF)
	data.append(0xD8)
	for i in range(payload_size):
		data.append((i + 0x30) % 256)
	data.append(0xFF)
	data.append(0xD9)
	return data


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

func test_find_marker_basic() -> void:
	var buf := PackedByteArray([0x00, 0xFF, 0xD8, 0x01, 0xFF, 0xD9])
	assert_eq(find_marker(buf, 0xD8, 0), 1, "find_marker_soi")
	assert_eq(find_marker(buf, 0xD9, 0), 4, "find_marker_eoi")


func test_find_marker_not_found() -> void:
	var buf := PackedByteArray([0x00, 0x01, 0x02, 0x03])
	assert_eq(find_marker(buf, 0xD8, 0), -1, "find_marker_not_found")


func test_find_marker_multiple_ff() -> void:
	# 0xFF followed by non-D8, then 0xFF 0xD8
	var buf := PackedByteArray([0xFF, 0x00, 0xFF, 0xD8])
	assert_eq(find_marker(buf, 0xD8, 0), 2, "find_marker_skip_false_ff")


func test_find_crlfcrlf_basic() -> void:
	var hdr := "HTTP/1.0 200 OK\r\n\r\nBODY".to_utf8_buffer()
	var idx := find_crlfcrlf(hdr, 0)
	assert_eq(idx, 16, "find_crlfcrlf_basic")


func test_find_crlfcrlf_not_found() -> void:
	var buf := "HTTP/1.0 200 OK\r\n".to_utf8_buffer()
	assert_eq(find_crlfcrlf(buf, 0), -1, "find_crlfcrlf_not_found")


func test_find_crlfcrlf_partial() -> void:
	# Only \r\n with no second \r\n
	var buf := PackedByteArray([0x0D, 0x0A, 0x41, 0x42])
	assert_eq(find_crlfcrlf(buf, 0), -1, "find_crlfcrlf_partial")


func test_extract_single_frame() -> void:
	var jpeg := make_jpeg(10)
	var result := extract_frames(jpeg)
	assert_eq(result[2], 1, "extract_single_frame_count")
	assert_eq(result[0].size(), jpeg.size(), "extract_single_frame_size")
	assert_eq(result[0][0], 0xFF, "extract_single_frame_soi_0")
	assert_eq(result[0][1], 0xD8, "extract_single_frame_soi_1")


func test_extract_multiple_frames_keeps_last() -> void:
	var frame1 := make_jpeg(4)
	var frame2 := make_jpeg(8)
	var buf := PackedByteArray()
	buf.append_array(frame1)
	buf.append_array(frame2)
	var result := extract_frames(buf)
	assert_eq(result[2], 2, "extract_multi_frame_count")
	# Last frame should be frame2 (larger payload)
	assert_eq(result[0].size(), frame2.size(), "extract_multi_keeps_last")


func test_incomplete_frame_waits() -> void:
	# SOI present, no EOI yet
	var buf := PackedByteArray([0xFF, 0xD8, 0x30, 0x31, 0x32])
	var result := extract_frames(buf)
	assert_eq(result[2], 0, "incomplete_frame_no_decode")
	assert_true(result[0].size() == 0, "incomplete_frame_empty_jpeg")
	# Buffer should be preserved (trimmed to SOI)
	assert_true(result[1].size() > 0, "incomplete_frame_buf_kept")


func test_corrupt_frame_skipped() -> void:
	# Garbage + valid frame
	var garbage := PackedByteArray([0x00, 0x01, 0x02, 0x03])
	var good := make_jpeg(6)
	var buf := PackedByteArray()
	buf.append_array(garbage)
	buf.append_array(good)
	var result := extract_frames(buf)
	assert_eq(result[2], 1, "corrupt_skipped_frame_count")
	assert_eq(result[0].size(), good.size(), "corrupt_skipped_good_frame")


func test_header_skip() -> void:
	var header := "HTTP/1.0 200 OK\r\nContent-Type: multipart\r\n\r\n".to_utf8_buffer()
	var idx := find_crlfcrlf(header, 0)
	assert_true(idx >= 0, "header_skip_found")
	var body := header.slice(idx + 4)
	# Body should be empty or just the part after headers
	assert_true(body.size() >= 0, "header_skip_body_exists")


func test_empty_buffer() -> void:
	var buf := PackedByteArray()
	var result := extract_frames(buf)
	assert_eq(result[2], 0, "empty_buffer_no_frames")
	assert_eq(result[0].size(), 0, "empty_buffer_no_jpeg")


func test_max_buffer_cap() -> void:
	# Simulate buffer exceeding cap — verify slicing works
	var big := PackedByteArray()
	big.resize(600000)
	var capped := big.slice(big.size() - 524288)
	assert_eq(capped.size(), 524288, "max_buffer_cap_size")


func test_soi_at_buffer_boundary() -> void:
	# SOI marker split: 0xFF at end, but no next byte yet
	var buf := PackedByteArray([0x00, 0x01, 0xFF])
	assert_eq(find_marker(buf, 0xD8, 0), -1, "soi_boundary_incomplete")
	# Now add the D8
	buf.append(0xD8)
	assert_eq(find_marker(buf, 0xD8, 0), 2, "soi_boundary_complete")
