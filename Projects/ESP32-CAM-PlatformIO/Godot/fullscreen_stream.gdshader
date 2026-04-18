shader_type spatial;
render_mode depth_test_disabled, skip_vertex_transform, unshaded, cull_disabled;
// XR-aware fullscreen overlay.
// Uses PROJECTION_MATRIX offset on inner vertices for correct stereo centering.
// Requires a 2x2 QuadMesh with subdivide_width=1, subdivide_depth=1.

uniform sampler2D stream_texture : source_color, filter_linear;

void vertex() {
	vec2 vert_pos = VERTEX.xy;
	if (length(vert_pos) < 0.99) {
		vec4 offset = PROJECTION_MATRIX * vec4(0.0, 0.0, 1.0, 1.0);
		vert_pos += (offset.xy / offset.w);
	}
	POSITION = vec4(vert_pos, 1.0, 1.0);
}

void fragment() {
	// Flip UV.x for left-right mirror
	vec2 uv = vec2(1.0 - UV.x, UV.y);
	ALBEDO = texture(stream_texture, uv).rgb;
}
