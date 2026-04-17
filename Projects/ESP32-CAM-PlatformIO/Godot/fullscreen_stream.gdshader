shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, depth_test_disabled;
// Renders the quad as a fullscreen overlay in clip space.
// Ignores 3D transform — always fills the entire viewport.

uniform sampler2D stream_texture : source_color, filter_linear;

void vertex() {
	// Map quad vertices (-0.5..0.5) to NDC (-1..1), z=0 (front)
	POSITION = vec4(VERTEX.xy * 2.0, 0.0, 1.0);
}

void fragment() {
	// Flip UV.x for left-right mirror, UV.y for screen space
	vec2 uv = vec2(1.0 - UV.x, 1.0 - UV.y);
	ALBEDO = texture(stream_texture, uv).rgb;
}
