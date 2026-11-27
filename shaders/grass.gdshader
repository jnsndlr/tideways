shader_type spatial;
render_mode cull_disabled;

// Grass (Grass.gd): one MultiMesh of identical blade clumps on a grid round the
// camera's focus, placed entirely here. Each clump finds its spot from its instance
// id, its height from the terrain grid and its colour and density from the ground
// below (WorldBuilder.ground_rgba), so the CPU sets one vector a frame. Clumps with
// no grass, or past the patch's edge, collapse to nothing.

#include "res://shaders/clouds.gdshaderinc"
#include "res://shaders/ground_detail.gdshaderinc"

uniform sampler2D ground : filter_linear, repeat_disable;
uniform sampler2D heights : filter_nearest, repeat_disable;
uniform float half_size = 3300.0;
// The shore rocks' grassy caps (WorldBuilder.grass_lift): 0 none, else (h + 4) / 64.
uniform sampler2D lift : filter_nearest, repeat_disable;
uniform int lift_side = 0;
uniform float lift_cell = 2.0;
uniform vec3 lift_color : source_color = vec3(0.5, 0.58, 0.24);
uniform float cell = 4.125;
// The point the patch is centred on (the camera's focus), world x, z.
uniform vec2 centre;
uniform int side = 180;
uniform float spacing = 0.8;
// Clumps thin out from reach * 0.5 and are gone by reach.
uniform float reach = 70.0;
uniform float blade_height = 0.55;
// Where the wind blows towards (x, z), and how hard (0 calm, 1 a gale).
uniform vec2 wind_dir = vec2(1.0, 0.0);
uniform float wind_strength = 0.4;

varying vec3 tint;
varying float tip;
varying vec3 wpos;

vec3 srgb_to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

// Same alternating triangulation as Terrain.height_at().
float ground_height(vec2 p) {
	float count = half_size * 2.0 / cell;
	vec2 grid = clamp((p + half_size) / cell, vec2(0.0), vec2(count - 0.001));
	vec2 i = floor(grid);
	vec2 f = fract(grid);
	vec2 uv = (i + 0.5) / (count + 1.0);
	float s = 1.0 / (count + 1.0);
	float a = texture(heights, uv).r;
	float b = texture(heights, uv + vec2(s, 0.0)).r;
	float c = texture(heights, uv + vec2(0.0, s)).r;
	float d = texture(heights, uv + vec2(s)).r;
	if (mod(i.x + i.y, 2.0) < 1.0) {
		return f.x >= f.y ? a + (b - a) * f.x + (d - b) * f.y : a + (c - a) * f.y + (d - c) * f.x;
	}
	return f.x + f.y <= 1.0 ? a + (b - a) * f.x + (c - a) * f.y : d + (c - d) * (1.0 - f.x) + (b - d) * (1.0 - f.y);
}

void vertex() {
	tip = UV.y;
	vec2 g = vec2(float(INSTANCE_ID % side), float(INSTANCE_ID / side)) - float(side / 2);
	// The clump's own cell of the world grid, so it stays put as the patch moves.
	vec2 key = floor(centre / spacing) + g;
	vec2 jitter = gd_hash2(key);
	vec2 p = (key + 0.1 + 0.8 * jitter) * spacing;
	float d = length(p - centre);
	float count = half_size * 2.0 / cell;
	vec4 gr = texture(ground, ((p + half_size) / cell + 0.5) / (count + 1.0));
	float cap = lift_side > 0 ? texture(lift, (p + half_size) / (float(lift_side) * lift_cell)).r : 0.0;
	if (cap > 0.0) {
		gr = vec4(lift_color, 0.85);
	}
	float keep = gr.a * (1.0 - smoothstep(reach * 0.5, reach, d));
	float r = gd_hash(key + 5.31);
	if (r >= keep) {
		VERTEX = vec3(p.x, -1000.0, p.y);
	} else {
		float a = r * 41.0;
		float ca = cos(a);
		float sa = sin(a);
		vec3 v = vec3(VERTEX.x * ca - VERTEX.z * sa, VERTEX.y, VERTEX.x * sa + VERTEX.z * ca);
		// Thinner grass is shorter; the ones further out a little wider to fill in.
		float h = blade_height * mix(0.65, 1.25, jitter.y) * mix(0.55, 1.0, smoothstep(0.0, 0.7, gr.a));
		float widen = 1.0 + 1.2 * smoothstep(reach * 0.3, reach, d);
		v.xz *= widen;
		v.y *= h;
		// Leaning and swaying downwind, more at the tip.
		float t = TIME * (1.4 + wind_strength * 1.6);
		float phase = dot(p, wind_dir) * 0.22 + r * 6.0;
		float sway = 0.55 + 0.3 * sin(t + phase) + 0.15 * sin(t * 2.3 + phase * 1.7);
		v.xz += wind_dir * (0.08 + wind_strength * 0.5) * sway * tip * tip * h;
		VERTEX = vec3(p.x, (cap > 0.0 ? cap * 255.0 / 4.0 - 4.0 : ground_height(p)) - 0.04, p.y) + v;
		vec3 base = cap > 0.0 ? gr.rgb : srgb_to_linear(gr.rgb);
		tint = gd_soil(p, 0.0, base, 1.0) * mix(0.9, 1.1, jitter.x);
	}
	NORMAL = vec3(0.0, 1.0, 0.0);
	// The node sits at the origin with identity instances: local is world.
	wpos = VERTEX;
}

void fragment() {
	// Darker at the root, sunlit and a touch yellower at the tip.
	ALBEDO = tint * mix(0.55, 1.15, tip) * mix(vec3(1.0), vec3(1.06, 1.04, 0.9), tip);
	ROUGHNESS = 0.9;
	// Lit as the ground is (its normal straight up), whichever side faces the camera.
	NORMAL = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
}

void light() {
	float shade = 1.0;
	if (LIGHT_IS_DIRECTIONAL) {
		shade = 1.0 - cloud_shadow(wpos, cloud_time);
	}
	DIFFUSE_LIGHT += clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION * LIGHT_COLOR / PI * shade;
}
