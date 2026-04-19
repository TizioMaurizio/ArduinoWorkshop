extends MeshInstance3D
## ESP32-CAM stream receiver with UDP (default) and TCP MJPEG fallback.
## Discovery: parallel TCP probes to port 80 /status on each /24 subnet.
##
## UDP protocol (port 82):
##   Send "STREAM_UDP" to register + start, resend every 2s as keepalive.
##   Send "STREAM_STOP" to stop.
##   Fragments: [frame_id:u16LE][frag_idx:u8][frag_count:u8][frame_len:u32LE][payload]
##
## TCP fallback (port 81):
##   MJPEG multipart stream with SOI/EOI marker scanning.

## OV2640 framesize values matching esp_camera.h framesize_t enum.
enum CamResolution {
	QQVGA_160x120  = 0,
	HQVGA_240x176  = 3,
	QVGA_320x240   = 5,
	CIF_400x296    = 6,
	VGA_640x480    = 8,
	SVGA_800x600   = 9,
	XGA_1024x768   = 10,
	SXGA_1280x1024 = 11,
	UXGA_1600x1200 = 12,
}

@export var esp_ip: String = "10.224.248.157"
@export var esp_port_tcp: int = 81
@export var esp_port_udp: int = 82
@export var use_udp: bool = true  ## true=UDP fragments (default), false=TCP MJPEG
@export var reconnect_interval: float = 3.0
@export var max_decode_fps: float = 15.0
@export var resolution: CamResolution = CamResolution.VGA_640x480  ## Applied on connect via HTTP
@export_range(4, 63) var jpeg_quality: int = 20  ## 4=best/largest, 63=worst/smallest. Applied on connect via HTTP
@export_range(0.1, 1.0, 0.05) var screen_scale: float = 1.0:  ## 1.0=fullscreen, smaller=further away
	set(value):
		screen_scale = value
		if _shader_mat:
			_shader_mat.set_shader_parameter("screen_scale", screen_scale)

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
#  Shared state
# ---------------------------------------------------------------------------
var _texture: ImageTexture = null
var _shader_mat: ShaderMaterial = null
var _frame_count: int = 0
var _overlay_label: Label = null
var _connected: bool = false
var _reconnect_timer: float = 0.0
var _direct_retry_elapsed: float = 0.0
var _in_direct_retry: bool = false
var _last_decode_usec: int = 0

const _CONNECT_TIMEOUT: float = 5.0
const _STALL_TIMEOUT: float = 8.0
const _DIRECT_RETRY_WINDOW: float = 10.0

# ---------------------------------------------------------------------------
#  UDP stream state
# ---------------------------------------------------------------------------
var _udp: PacketPeerUDP = null
var _udp_keepalive_timer: float = 0.0
var _udp_stall_timer: float = 0.0
var _udp_cur_frame_id: int = -1
var _udp_cur_frag_count: int = 0
var _udp_cur_frame_len: int = 0
var _udp_frags: Dictionary = {}
var _udp_frags_received: int = 0
var _udp_frame_age: float = 0.0  ## time since first fragment of current frame
var _udp_stream_age: float = 0.0  ## seconds since stream (re)started
var _udp_frames_at_start: int = 0  ## _frame_count snapshot when stream started

const _UDP_KEEPALIVE_SEC: float = 2.0
const _UDP_FRAME_TIMEOUT_SEC: float = 0.5  ## abandon incomplete frame after this
const _UDP_MAX_FRAME_BYTES: int = 200000  ## skip frames >200KB to avoid stalls
const _UDP_FIRST_FRAME_TIMEOUT: float = 3.0  ## restart stream if no frame decoded in this time
const _WARMUP_FRAMES: int = 5  ## discard first N frames after stream start (sensor AEC/AWB stabilization)

# ---------------------------------------------------------------------------
#  TCP stream state (fallback)
# ---------------------------------------------------------------------------
var _tcp: StreamPeerTCP = StreamPeerTCP.new()
var _tcp_buf: PackedByteArray = PackedByteArray()
var _http_sent: bool = false
var _header_skipped: bool = false
var _connect_timer: float = 0.0
var _tcp_stall_timer: float = 0.0

const _MAX_BUF: int = 65536

# ---------------------------------------------------------------------------
#  HTTP resolution control
# ---------------------------------------------------------------------------
var _http: HTTPRequest = null
var _resolution_applied: bool = false
var _quality_applied: bool = false
var _pending_settings: Array[String] = []  ## queued HTTP URLs to apply sequentially


func _ready() -> void:
	_shader_mat = get_surface_override_material(0) as ShaderMaterial
	if _shader_mat:
		_shader_mat.set_shader_parameter("screen_scale", screen_scale)
	_create_overlay_label()
	_http = HTTPRequest.new()
	_http.timeout = 5.0
	add_child(_http)
	_http.request_completed.connect(_on_resolution_response)
	if esp_ip != "":
		_show_overlay("Connecting to %s (%s) ..." % [esp_ip, "UDP" if use_udp else "TCP"])
		_apply_camera_settings()
		# Stream starts after settings are applied — see _on_settings_complete()
	else:
		_begin_discovery()


func _process(delta: float) -> void:
	if _discovering:
		_process_discovery(delta)
	elif use_udp:
		_process_udp_stream(delta)
	else:
		_process_tcp_stream(delta)


# ===========================================================================
#  DISCOVERY
# ===========================================================================

func _begin_discovery() -> void:
	_stop_stream()
	_discovering = true
	_subnets.clear()
	_probes.clear()
	_probe_ip_idx = 1
	_probe_subnet_idx = 0
	var addrs := IP.get_local_addresses()
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
	while _probes.size() < _PROBE_BATCH:
		if _probe_subnet_idx >= _subnets.size():
			return
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
					print("[Discovery] Connected to %s" % p["ip"])
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
		if p["sent"] and p["age"] > _PROBE_TIMEOUT:
			if not to_remove.has(i):
				to_remove.append(i)
	if _discovered_ip != "":
		_finish_discovery(_discovered_ip)
		return
	to_remove.sort()
	for i in range(to_remove.size() - 1, -1, -1):
		_probes[to_remove[i]]["tcp"].disconnect_from_host()
		_probes.remove_at(to_remove[i])
	_launch_probe_batch()
	if _probes.is_empty() and _probe_subnet_idx >= _subnets.size():
		_set_status("ESP32-CAM not found \u2014 retrying in 3s ...")
		await get_tree().create_timer(3.0).timeout
		_begin_discovery()


func _is_esp_cam_response(text: String) -> bool:
	var lower := text.to_lower()
	return lower.find("framesize") >= 0 and lower.find("quality") >= 0


func _finish_discovery(ip: String) -> void:
	for p in _probes:
		p["tcp"].disconnect_from_host()
	_probes.clear()
	esp_ip = ip
	_discovering = false
	_set_status("Found ESP32-CAM at %s" % ip)
	_apply_camera_settings()
	# Stream starts after settings are applied — see _on_settings_complete()


# ===========================================================================
#  STREAM START / STOP
# ===========================================================================

func _start_stream() -> void:
	_connected = false
	_reconnect_timer = 0.0
	if use_udp:
		_start_udp_stream()
	else:
		_start_tcp_stream()


func _stop_stream() -> void:
	if _udp != null:
		_udp.put_packet("STREAM_STOP".to_utf8_buffer())
		_udp.close()
		_udp = null
	_tcp.disconnect_from_host()
	_connected = false


# ===========================================================================
#  UDP STREAMING
# ===========================================================================

func _start_udp_stream() -> void:
	if _udp != null:
		_udp.put_packet("STREAM_STOP".to_utf8_buffer())
		_udp.close()
	_udp = PacketPeerUDP.new()
	_udp.bind(0)
	_udp.set_dest_address(esp_ip, esp_port_udp)
	_udp.put_packet("STREAM_UDP".to_utf8_buffer())
	_udp_keepalive_timer = 0.0
	_udp_stall_timer = 0.0
	_udp_stream_age = 0.0
	_udp_frames_at_start = _frame_count
	_udp_cur_frame_id = -1
	_udp_frags.clear()
	_udp_frags_received = 0
	_connected = true
	_in_direct_retry = false
	_direct_retry_elapsed = 0.0
	_hide_overlay()
	_set_status("UDP stream from %s:%d" % [esp_ip, esp_port_udp])


func _process_udp_stream(delta: float) -> void:
	if _udp == null:
		_begin_reconnect_tick(delta)
		return
	_udp_keepalive_timer += delta
	if _udp_keepalive_timer >= _UDP_KEEPALIVE_SEC:
		_udp_keepalive_timer = 0.0
		_udp.put_packet("STREAM_UDP".to_utf8_buffer())

	# If no frame has been decoded since stream start, restart after 3s.
	# This catches first-launch stalls where fragments arrive but never
	# assemble (corrupt sensor output, lost final fragment, etc.).
	_udp_stream_age += delta
	if _frame_count == _udp_frames_at_start and _udp_stream_age > _UDP_FIRST_FRAME_TIMEOUT:
		print("[CameraStream] No frame decoded in %.1fs — restarting UDP stream" % _udp_stream_age)
		_start_udp_stream()
		return

	# Age out incomplete frames to prevent stalls
	if _udp_cur_frame_id >= 0:
		_udp_frame_age += delta
		if _udp_frame_age > _UDP_FRAME_TIMEOUT_SEC:
			_udp_frags.clear()
			_udp_frags_received = 0
			_udp_cur_frame_id = -1
	var got_data: bool = false
	while _udp.get_available_packet_count() > 0:
		var pkt: PackedByteArray = _udp.get_packet()
		if pkt.size() < 8:
			continue
		got_data = true
		_process_udp_fragment(pkt)
	if got_data:
		_udp_stall_timer = 0.0
	else:
		_udp_stall_timer += delta
		if _udp_stall_timer > _STALL_TIMEOUT:
			_set_status("UDP stream stalled")
			_udp.close()
			_udp = null
			_connected = false
			_begin_reconnect()


func _process_udp_fragment(pkt: PackedByteArray) -> void:
	var frame_id: int = pkt.decode_u16(0)
	var frag_idx: int = pkt[2]
	var frag_count: int = pkt[3]
	var frame_len: int = pkt.decode_u32(4)
	var payload: PackedByteArray = pkt.slice(8)
	if frame_id != _udp_cur_frame_id:
		var is_newer: bool = false
		if _udp_cur_frame_id < 0:
			is_newer = true
		elif frame_id > _udp_cur_frame_id:
			is_newer = true
		elif _udp_cur_frame_id > 60000 and frame_id < 5000:
			is_newer = true
		if is_newer:
			# Skip oversized frames to avoid stalling _process()
			if frame_len > _UDP_MAX_FRAME_BYTES:
				return
			_udp_cur_frame_id = frame_id
			_udp_cur_frag_count = frag_count
			_udp_cur_frame_len = frame_len
			_udp_frags.clear()
			_udp_frags_received = 0
			_udp_frame_age = 0.0
		else:
			return
	if frame_id != _udp_cur_frame_id:
		return
	if not _udp_frags.has(frag_idx):
		_udp_frags[frag_idx] = payload
		_udp_frags_received += 1
	if _udp_frags_received >= _udp_cur_frag_count:
		# Bulk reassembly using PackedByteArray.append_array() — engine-native,
		# avoids O(n) byte-by-byte GDScript loop that blocks _process().
		var jpeg: PackedByteArray = PackedByteArray()
		for i in range(_udp_cur_frag_count):
			if _udp_frags.has(i):
				jpeg.append_array(_udp_frags[i])
		_udp_frags.clear()
		_udp_frags_received = 0
		_udp_cur_frame_id = -1
		_frame_count += 1
		_apply_frame(jpeg)


# ===========================================================================
#  TCP STREAMING (fallback)
# ===========================================================================

func _start_tcp_stream() -> void:
	_tcp.disconnect_from_host()
	_tcp_buf.clear()
	_http_sent = false
	_header_skipped = false
	_connect_timer = 0.0
	_tcp_stall_timer = 0.0
	_tcp = StreamPeerTCP.new()
	_tcp.set_no_delay(true)
	_tcp.connect_to_host(esp_ip, esp_port_tcp)


func _process_tcp_stream(delta: float) -> void:
	_tcp.poll()
	match _tcp.get_status():
		StreamPeerTCP.STATUS_CONNECTED:
			if not _http_sent:
				var req := "GET /stream HTTP/1.0\r\nHost: %s\r\n\r\n" % esp_ip
				_tcp.put_data(req.to_utf8_buffer())
				_http_sent = true
				_connected = true
				_in_direct_retry = false
				_direct_retry_elapsed = 0.0
				_hide_overlay()
				_set_status("TCP stream from %s:%d" % [esp_ip, esp_port_tcp])
			var had_data := _read_tcp_stream()
			if had_data:
				_tcp_stall_timer = 0.0
			else:
				_tcp_stall_timer += delta
				if _tcp_stall_timer > _STALL_TIMEOUT:
					_set_status("TCP stream stalled")
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


func _read_tcp_stream() -> bool:
	var avail := _tcp.get_available_bytes()
	if avail <= 0:
		return false
	var res := _tcp.get_data(avail)
	if res[0] != OK:
		return false
	_tcp_buf.append_array(res[1])
	if not _header_skipped:
		var hdr_end := _find_crlfcrlf(0)
		if hdr_end < 0:
			return true
		_tcp_buf = _tcp_buf.slice(hdr_end + 4)
		_header_skipped = true
	if _tcp_buf.size() > _MAX_BUF:
		_tcp_buf = _tcp_buf.slice(_tcp_buf.size() - _MAX_BUF)
	var last_jpeg: PackedByteArray = PackedByteArray()
	var search_from: int = 0
	while true:
		var soi := _find_marker(0xD8, search_from)
		if soi < 0:
			break
		var eoi := _find_marker(0xD9, soi + 2)
		if eoi < 0:
			if soi > 0:
				_tcp_buf = _tcp_buf.slice(soi)
			return true
		var frame_end := eoi + 2
		last_jpeg = _tcp_buf.slice(soi, frame_end)
		search_from = frame_end
		_frame_count += 1
	if search_from > 0:
		_tcp_buf = _tcp_buf.slice(search_from)
	if last_jpeg.size() > 2:
		_apply_frame(last_jpeg)
	return true


func _find_marker(second_byte: int, from: int) -> int:
	var pos := from
	while true:
		var idx := _tcp_buf.find(0xFF, pos)
		if idx < 0 or idx + 1 >= _tcp_buf.size():
			return -1
		if _tcp_buf[idx + 1] == second_byte:
			return idx
		pos = idx + 1
	return -1


func _find_crlfcrlf(from: int) -> int:
	var pos := from
	while true:
		var idx := _tcp_buf.find(0x0D, pos)
		if idx < 0 or idx + 3 >= _tcp_buf.size():
			return -1
		if _tcp_buf[idx + 1] == 0x0A and _tcp_buf[idx + 2] == 0x0D and _tcp_buf[idx + 3] == 0x0A:
			return idx
		pos = idx + 1
	return -1


# ===========================================================================
#  RECONNECT
# ===========================================================================

func _begin_reconnect() -> void:
	_stop_stream()
	_reconnect_timer = 0.0
	if not _in_direct_retry:
		_in_direct_retry = true
		_direct_retry_elapsed = 0.0


func _begin_reconnect_tick(delta: float) -> void:
	if _in_direct_retry:
		_direct_retry_elapsed += delta
		_reconnect_timer += delta
		var remaining := _DIRECT_RETRY_WINDOW - _direct_retry_elapsed
		if remaining <= 0:
			_in_direct_retry = false
			_show_overlay("Lost %s \u2014 scanning ..." % esp_ip)
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
			_show_overlay("Lost %s \u2014 scanning ..." % esp_ip)
			_begin_discovery()


# ===========================================================================
#  FRAME DECODE + TEXTURE UPDATE
# ===========================================================================

func _apply_frame(jpeg_data: PackedByteArray) -> void:
	# Discard early frames — OV2640 needs several captures after a resolution
	# change for auto-exposure/white-balance to stabilize (white/corrupt frames).
	var frames_since_start: int = _frame_count - _udp_frames_at_start
	if frames_since_start <= _WARMUP_FRAMES:
		if frames_since_start == 1:
			print("[CameraStream] Discarding first %d frames (sensor warmup)" % _WARMUP_FRAMES)
		return
	var now_usec: int = Time.get_ticks_usec()
	var min_interval_usec: int = int(1_000_000.0 / max_decode_fps)
	if (now_usec - _last_decode_usec) < min_interval_usec:
		return
	_last_decode_usec = now_usec
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
		print("[CameraStream] First frame: %dx%d (%s)" % [image.get_width(), image.get_height(), "UDP" if use_udp else "TCP"])
	else:
		_texture.update(image)


# ===========================================================================
#  OVERLAY
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


# ===========================================================================
#  CAMERA SETTINGS (resolution + quality via HTTP)
# ===========================================================================

func _apply_camera_settings() -> void:
	if esp_ip == "":
		_on_settings_complete()
		return
	_pending_settings.clear()
	_pending_settings.append("http://%s/control?var=framesize&val=%d" % [esp_ip, int(resolution)])
	_pending_settings.append("http://%s/control?var=quality&val=%d" % [esp_ip, jpeg_quality])
	var res_name: String = CamResolution.keys()[CamResolution.values().find(int(resolution))]
	print("[CameraStream] Applying camera settings: %s, quality=%d" % [res_name, jpeg_quality])
	_send_next_setting()


func _send_next_setting() -> void:
	if _pending_settings.is_empty():
		_on_settings_complete()
		return
	var url: String = _pending_settings[0]
	var err: int = _http.request(url)
	if err != OK:
		print("[CameraStream] HTTP request failed for %s: %d" % [url, err])
		_pending_settings.pop_front()
		_send_next_setting()


func _on_resolution_response(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	var url: String = _pending_settings.pop_front() if not _pending_settings.is_empty() else ""
	if result == HTTPRequest.RESULT_SUCCESS and response_code == 200:
		print("[CameraStream] Setting applied: %s" % url)
	else:
		print("[CameraStream] Setting failed: %s (result=%d code=%d)" % [url, result, response_code])
	if _pending_settings.is_empty():
		_on_settings_complete()
	else:
		_send_next_setting()


func _on_settings_complete() -> void:
	print("[CameraStream] All settings applied — starting stream")
	_start_stream()
