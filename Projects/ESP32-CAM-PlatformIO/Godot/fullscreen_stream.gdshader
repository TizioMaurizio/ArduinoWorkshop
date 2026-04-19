shader_type spatial;
render_mode depth_test_disabled, skip_vertex_transform, unshaded, cull_disabled;
// XR-aware stream overlay with adjustable scale.
// Stereo: extracts per-eye offset from PROJECTION_MATRIX and shifts the
// entire quad so both eyes converge correctly at any scale.
// Requires a 2x2 QuadMesh with subdivide_width=1, subdivide_depth=1.

uniform sampler2D stream_texture : source_color, filter_linear;
uniform float screen_scale : hint_range(0.1, 1.0) = 1.0;

void vertex() {
	// Per-eye stereo offset (nonzero in XR, zero on desktop)
	vec4 proj_offset = PROJECTION_MATRIX * vec4(0.0, 0.0, 1.0, 1.0);
	vec2 eye_shift = proj_offset.xy / proj_offset.w;

	// Scale quad then shift entire quad for correct stereo convergence.
	// At scale=1.0 the shift extends past clip edges — GPU clips naturally.
	// At scale<1.0 the smaller quad is fully visible and correctly offset.
	vec2 vert_pos = VERTEX.xy * screen_scale + eye_shift;

	POSITION = vec4(vert_pos, 1.0, 1.0);
}

void fragment() {
	// Flip UV.x for left-right mirror
	vec2 uv = vec2(1.0 - UV.x, UV.y);
	ALBEDO = texture(stream_texture, uv).rgb;
}
