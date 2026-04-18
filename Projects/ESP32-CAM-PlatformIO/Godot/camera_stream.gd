extends MeshInstance3D
## Auto-discovers ESP32-CAM on all local subnets, then streams MJPEG.
## Discovery: parallel TCP probes to port 80 /status on each /24 subnet.
## Streaming: SOI/EOI JPEG marker scanning via native find(), frame skipping.

@export var esp_ip: String = "10.192.119.157"  ## Arm ESP32-CAM (DHCP — rescan if changed)
@export var esp_port: int = 81
@export var reconnect_interval: float = 3.0

# ---------------------------------------------------------------------------
#  Discovery state
# ---------------------------------------------------------------------------
const _PROBE_BATCH: int = 32
const _PROBE_TIMEOUT: float = 2.0

var _discovering: bool = false
var _subnets: Array[String] = []
var _probe_ip_idx: int = 1
var _probe_subnet_idx: int = 0
var _probes: Array[Dictionary] = []
var _discovered_ip: String = ""

# ---------------------------------------------------------------------------
#  Stream state — SOI/EOI based (no Content-Length dependency)
# ---------------------------------------------------------------------------
var _tcp: StreamPeerTCP = StreamPeerTCP.new()
var _buf: PackedByteArray = PackedByteArray()
var _http_sent: bool = false
var _header_skipped: bool = false
var _connected: bool = false
var _reconnect_timer: float = 0.0
var _connect_timer: float = 0.0
var _stall_timer: float = 0.0
var _direct_retry_elapsed: float = 0.0
var _in_direct_retry: bool = false
var _texture: ImageTexture = null
var _shader_mat: ShaderMaterial = null
var _frame_count: int = 0
var _overlay_label: Label = null

const _MAX_BUF: int = 524288
const _CONNECT_TIMEOUT: float = 5.0
const _STALL_TIMEOUT: float = 8.0
const _DIRECT_RETRY_WINDOW: float = 10.0  # retry same IP for 10s before rediscovery


func _ready() -> void:
	_shader_mat = get_surface_override_material(0) as ShaderMaterial
	_create_overlay_label()

	if esp_ip != "":
		_show_overlay("Connecting to %s:%d ..." % [esp_ip, esp_port])
		_start_stream()
	else:
		_begin_discovery()


func _process(delta: float) -> void:
	if _discovering:
		_process_discovery(delta)
	else:
		_process_stream(delta)


# ===========================================================================
#  DISCOVERY — scan /24 subnets from all local interfaces
# ===========================================================================

func _begin_discovery() -> void:
	_discovering = true
	_subnets.clear()
	_probes.clear()
	_probe_ip_idx = 1
	_probe_subnet_idx = 0

	var addrs := IP.get_local_addresses()
	for addr in addrs:
		if ":" in addr:
			continue  # skip IPv6
		var parts := addr.split(".")
		if parts.size() != 4:
			continue
		# skip loopback and link-local 169.254.x.x
		if parts[0] == "127":
			continue
		if parts[0] == "169" and parts[1] == "254":
			continue
		var subnet := "%s.%s.%s" % [parts[0], parts[1], parts[2]]
		if subnet not in _subnets:
			_subnets.append(subnet)

	if _subnets.is_empty():
		_set_status("No network interfaces found")
		return

	var subnet_list := ", ".join(_subnets)
	print("[Discovery] Subnets to scan: ", subnet_list)
	_set_status("Scanning %d subnet(s): %s ..." % [_subnets.size(), subnet_list])
	_launch_probe_batch()


func _launch_probe_batch() -> void:
	# Launch up to _PROBE_BATCH parallel probes
	while _probes.size() < _PROBE_BATCH:
		if _probe_subnet_idx >= _subnets.size():
			return  # exhausted all subnets

		var ip := "%s.%d" % [_subnets[_probe_subnet_idx], _probe_ip_idx]
		var tcp := StreamPeerTCP.new()
		tcp.set_no_delay(true)
		tcp.connect_to_host(ip, 80)
		_probes.append({"tcp": tcp, "ip": ip, "sent": false, "age": 0.0})

		_probe_ip_idx += 1
		if _probe_ip_idx > 254:
			_probe_ip_idx = 1
			_probe_subnet_idx += 1


func _process_discovery(delta: float) -> void:
	var to_remove: Array[int] = []

	for i in range(_probes.size()):
		var p: Dictionary = _probes[i]
		var tcp: StreamPeerTCP = p["tcp"]
		tcp.poll()
		p["age"] += delta

		match tcp.get_status():
			StreamPeerTCP.STATUS_CONNECTED:
				if not p["sent"]:
					var req := "GET /status HTTP/1.0\r\nHost: %s\r\n\r\n" % p["ip"]
					tcp.put_data(req.to_utf8_buffer())
					p["sent"] = true
					print("[Discovery] Connected to %s — sent request" % p["ip"])
				if tcp.get_available_bytes() > 0:
					var res := tcp.get_data(tcp.get_available_bytes())
					if res[0] == OK:
						var text: String = (res[1] as PackedByteArray).get_string_from_ascii()
						if _is_esp_cam_response(text):
							_discovered_ip = p["ip"]

			StreamPeerTCP.STATUS_ERROR, StreamPeerTCP.STATUS_NONE:
				to_remove.append(i)

			StreamPeerTCP.STATUS_CONNECTING:
				if p["age"] > _PROBE_TIMEOUT:
					to_remove.append(i)

		# Timeout connected probes that sent request but got no useful response
		if p["sent"] and p["age"] > _PROBE_TIMEOUT:
			if not to_remove.has(i):
				to_remove.append(i)

	# Found it?
	if _discovered_ip != "":
		_finish_discovery(_discovered_ip)
		return

	# Remove dead/timed-out probes (reverse order to keep indices valid)
	to_remove.sort()
	for i in range(to_remove.size() - 1, -1, -1):
		var p: Dictionary = _probes[to_remove[i]]
		p["tcp"].disconnect_from_host()
		_probes.remove_at(to_remove[i])

	# Refill the batch
	_launch_probe_batch()

	# Check if we're done scanning with nothing found
	if _probes.is_empty() and _probe_subnet_idx >= _subnets.size():
		_set_status("ESP32-CAM not found — retrying in 3s ...")
		await get_tree().create_timer(3.0).timeout
		_begin_discovery()


func _is_esp_cam_response(text: String) -> bool:
	# /status returns JSON with camera-specific keys like "framesize", "quality"
	var lower := text.to_lower()
	return lower.find("framesize") >= 0 and lower.find("quality") >= 0


func _finish_discovery(ip: String) -> void:
	# Clean up all probes
	for p in _probes:
		p["tcp"].disconnect_from_host()
	_probes.clear()

	esp_ip = ip
	_discovering = false
	_set_status("Found ESP32-CAM at %s — connecting stream ..." % ip)
	_start_stream()


# ===========================================================================
#  STREAMING — SOI/EOI marker scanning, reconnect with 10s same-IP retry
# ===========================================================================

func _start_stream() -> void:
	_tcp.disconnect_from_host()
	_buf.clear()
	_http_sent = false
	_header_skipped = false
	_connected = false
	_connect_timer = 0.0
	_stall_timer = 0.0
	_tcp = StreamPeerTCP.new()
	_tcp.set_no_delay(true)
	_tcp.connect_to_host(esp_ip, esp_port)


func _send_http_get() -> void:
	var req := "GET /stream HTTP/1.0\r\nHost: %s\r\n\r\n" % esp_ip
	_tcp.put_data(req.to_utf8_buffer())


func _process_stream(delta: float) -> void:
	_tcp.poll()

	match _tcp.get_status():
		StreamPeerTCP.STATUS_CONNECTED:
			if not _http_sent:
				_send_http_get()
				_http_sent = true
				_connected = true
				_in_direct_retry = false
				_direct_retry_elapsed = 0.0
				_hide_overlay()
				_set_status("Streaming from %s:%d" % [esp_ip, esp_port])

			var had_data := _read_stream()
			if had_data:
				_stall_timer = 0.0
			else:
				_stall_timer += delta
				if _stall_timer > _STALL_TIMEOUT:
					_set_status("Stream stalled — reconnecting ...")
					_begin_reconnect()

			_reconnect_timer = 0.0
			_connect_timer = 0.0

		StreamPeerTCP.STATUS_CONNECTING:
			_connect_timer += delta
			if _connect_timer > _CONNECT_TIMEOUT:
				_set_status("Connection timeout")
				_begin_reconnect()

		StreamPeerTCP.STATUS_ERROR, StreamPeerTCP.STATUS_NONE:
			if _connected:
				_set_status("Connection lost")
				_connected = false
			_begin_reconnect_tick(delta)


func _begin_reconnect() -> void:
	_tcp.disconnect_from_host()
	_connected = false
	_reconnect_timer = 0.0
	if not _in_direct_retry:
		_in_direct_retry = true
		_direct_retry_elapsed = 0.0
	# Will be handled by _begin_reconnect_tick on next frame


func _begin_reconnect_tick(delta: float) -> void:
	if _in_direct_retry:
		_direct_retry_elapsed += delta
		_reconnect_timer += delta
		var remaining := _DIRECT_RETRY_WINDOW - _direct_retry_elapsed
		if remaining <= 0:
			_in_direct_retry = false
			_show_overlay("Lost %s — scanning network ..." % esp_ip)
			_begin_discovery()
			return
		if _reconnect_timer >= reconnect_interval:
			_reconnect_timer = 0.0
			_show_overlay("Reconnecting to %s ... (%.0fs)" % [esp_ip, remaining])
			_start_stream()
	else:
		_reconnect_timer += delta
		if _reconnect_timer >= reconnect_interval:
			_reconnect_timer = 0.0
			_show_overlay("Lost %s — scanning network ..." % esp_ip)
			_begin_discovery()


func _read_stream() -> bool:
	var avail := _tcp.get_available_bytes()
	if avail <= 0:
		return false

	var res := _tcp.get_data(avail)
	if res[0] != OK:
		return false
	_buf.append_array(res[1])

	if not _header_skipped:
		var hdr_end := _find_crlfcrlf(0)
		if hdr_end < 0:
			return true  # got data, header not complete yet
		_buf = _buf.slice(hdr_end + 4)
		_header_skipped = true

	if _buf.size() > _MAX_BUF:
		_buf = _buf.slice(_buf.size() - _MAX_BUF)

	var last_jpeg: PackedByteArray = PackedByteArray()
	var search_from: int = 0

	while true:
		var soi := _find_marker(0xD8, search_from)
		if soi < 0:
			break
		var eoi := _find_marker(0xD9, soi + 2)
		if eoi < 0:
			if soi > 0:
				_buf = _buf.slice(soi)
			return true
		var frame_end := eoi + 2
		last_jpeg = _buf.slice(soi, frame_end)
		search_from = frame_end
		_frame_count += 1

	if search_from > 0:
		_buf = _buf.slice(search_from)

	if last_jpeg.size() > 2:
		_apply_frame(last_jpeg)

	return true


func _find_marker(second_byte: int, from: int) -> int:
	var pos := from
	while true:
		var idx := _buf.find(0xFF, pos)
		if idx < 0 or idx + 1 >= _buf.size():
			return -1
		if _buf[idx + 1] == second_byte:
			return idx
		pos = idx + 1
	return -1


func _find_crlfcrlf(from: int) -> int:
	var pos := from
	while true:
		var idx := _buf.find(0x0D, pos)
		if idx < 0 or idx + 3 >= _buf.size():
			return -1
		if _buf[idx + 1] == 0x0A and _buf[idx + 2] == 0x0D and _buf[idx + 3] == 0x0A:
			return idx
		pos = idx + 1
	return -1


func _apply_frame(jpeg_data: PackedByteArray) -> void:
	var image := Image.new()
	var err := image.load_jpg_from_buffer(jpeg_data)
	if err != OK:
		if _frame_count < 5:
			print("[CameraStream] JPEG decode failed: ", err, " size=", jpeg_data.size())
		return

	if _texture == null:
		_texture = ImageTexture.create_from_image(image)
		if _shader_mat:
			_shader_mat.set_shader_parameter("stream_texture", _texture)
		print("[CameraStream] First frame: %dx%d" % [image.get_width(), image.get_height()])
	else:
		_texture.update(image)


# ===========================================================================
#  OVERLAY — fullscreen text message via CanvasLayer + Label
# ===========================================================================

func _create_overlay_label() -> void:
	var canvas := CanvasLayer.new()
	canvas.layer = 100
	canvas.name = "OverlayCanvas"
	add_child(canvas)

	_overlay_label = Label.new()
	_overlay_label.name = "OverlayLabel"
	_overlay_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_overlay_label.anchors_preset = Control.PRESET_FULL_RECT
	_overlay_label.anchor_right = 1.0
	_overlay_label.anchor_bottom = 1.0
	_overlay_label.add_theme_font_size_override("font_size", 28)
	_overlay_label.add_theme_color_override("font_color", Color(1, 1, 1, 0.9))
	_overlay_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	_overlay_label.add_theme_constant_override("shadow_offset_x", 2)
	_overlay_label.add_theme_constant_override("shadow_offset_y", 2)
	_overlay_label.visible = false
	canvas.add_child(_overlay_label)


func _show_overlay(text: String) -> void:
	print("[CameraStream] ", text)
	if _overlay_label:
		_overlay_label.text = text
		_overlay_label.visible = true


func _hide_overlay() -> void:
	if _overlay_label:
		_overlay_label.visible = false


func _set_status(text: String) -> void:
	print("[CameraStream] ", text)
