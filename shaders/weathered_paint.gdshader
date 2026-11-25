shader_type spatial;
render_mode blend_mix, cull_back, depth_draw_opaque;
// Weathered stencil paint for Label3D lettering (bound as material_override; the
// label's glyph atlas arrives in texture_albedo). Chips, thin patches and streaks
// of the paint, keyed on the lettering's own position so each face differs.

uniform sampler2D texture_albedo : source_color, filter_linear_mipmap;
uniform vec4 paint : source_color = vec4(0.08, 0.07, 0.06, 1.0);
uniform float wear = 0.35;

varying vec3 obj;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	obj = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
}

void fragment() {
	float glyph = texture(texture_albedo, UV).a;
	if (glyph < 0.01) discard;
	vec2 p = (UV * vec2(2.0, 1.0) + obj.xz * 0.37) * 9.0;
	// Patchy fade, small chips, and downward rain streaks.
	float patch = noise(p * 0.6) * 0.6 + noise(p * 1.7) * 0.4;
	float chips = step(0.78, noise(p * 6.0));
	float streak = noise(vec2(p.x * 7.0, p.y * 0.35));
	float keep = clamp(1.0 - wear * (patch * 1.1) - chips * 0.85 - smoothstep(0.65, 0.95, streak) * 0.4, 0.0, 1.0);
	ALBEDO = mix(paint.rgb, paint.rgb + vec3(0.12, 0.09, 0.05), 1.0 - keep);
	ROUGHNESS = 0.9;
	ALPHA = glyph * keep * paint.a;
	ALPHA_SCISSOR_THRESHOLD = 0.25;
}
