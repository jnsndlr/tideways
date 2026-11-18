shader_type spatial;
render_mode cull_back, specular_disabled;

// The mainland past the map (Backdrop): vertex-coloured land lit like the terrain
// by the map, turning further out into smooth, painted ranges. Bare rock and snow
// are painted per pixel (the mesh only carries forest and shore colours), with a
// tiling ridged normal map streaked downhill into gullies and ribs, and lit in a
// few flat painted values with brushy edges and cool lavender shade. Its own aerial perspective
// (haze.gdshaderinc) instead of the depth fog, so the ranges read as flat painted
// layers fading into the distance.

#include "res://shaders/clouds.gdshaderinc"

#include "res://shaders/haze.gdshaderinc"

// The visible cloud deck (and so its shadows) thins out past this radius
// (keep in sync with clouds.gdshader).
const float DECK_FADE_START = 10500.0;
const float DECK_FADE_END = 13500.0;

// Backdrop.ALPINE / ALPINE_LIGHT / SNOW (sRGB).
const vec3 ROCK = vec3(0.36, 0.4, 0.48);
const vec3 ROCK_LIGHT = vec3(0.5, 0.5, 0.55);
const vec3 SNOW = vec3(0.95, 0.96, 0.99);

// Terrain.half_size: by the map's edge the land is lit and fogged like the
// terrain it carries on from, so the two meet without a seam.
uniform float map_half = 3000.0;
// Mainland.snowline (Backdrop._snowline wanders it along the ranges).
uniform float snowline = 1680.0;
// Ridged noise as a normal map (Backdrop._detail_texture).
uniform sampler2D detail : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
// Metres per tile across the slope; tiles run DETAIL_STRETCH times longer downhill.
uniform float detail_scale = 1400.0;
uniform float detail_strength = 0.45;
const float DETAIL_STRETCH = 3.5;

varying vec3 world_pos;
varying vec3 world_n;
// Brushwork (-1..1): long strokes down the slope, nudging where light turns to
// shade so the edges between values read as painted, not computed.
varying float stroke;

vec3 srgb_to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

float snow_height(vec3 p) {
	return snowline + sin(p.x * 0.0010333 + 1.7) * sin(p.z * 0.0009 + 0.4) * 270.0;
}

float tree_height(vec3 p) {
	return snow_height(p) - 660.0 + sin(p.x * 0.0023333 + p.z * 0.0016667) * 120.0;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_n = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

// The detail normal map sampled in a frame turned to the slope: its ridges run
// downhill (gullies, ribs, avalanche chutes) rather than lying about at random.
vec3 slope_detail(vec3 n, float amount, out float mottle, out float brush) {
	vec2 down = n.xz;
	float steep = length(down);
	down = steep > 1e-4 ? down / steep : vec2(0.0, 1.0);
	vec2 across = vec2(-down.y, down.x);
	vec2 uv = vec2(dot(world_pos.xz, across), dot(world_pos.xz, down) / DETAIL_STRETCH) / detail_scale;
	vec2 g1 = texture(detail, uv).rg * 2.0 - 1.0;
	vec2 g2 = texture(detail, uv * 2.7 + 0.31).rg * 2.0 - 1.0;
	vec2 g = g1 + g2 * 0.45;
	mottle = g1.x * 0.6 + g2.y * 0.4;
	// Finer and longer than the gullies: single strokes of the brush.
	vec2 b = texture(detail, vec2(uv.x * 4.0, uv.y * 0.9) + 0.53).rg * 2.0 - 1.0;
	brush = b.x;
	// Back into the world: g.x tilts the face across the slope, g.y along it.
	vec3 w = vec3(across.x, 0.0, across.y) * g.x + vec3(down.x, 0.0, down.y) * g.y / DETAIL_STRETCH;
	// Flat ground hardly shows it; steep faces most.
	return normalize(n + w * amount * smoothstep(0.05, 0.4, steep));
}

void fragment() {
	float out_dist = max(abs(world_pos.x), abs(world_pos.z)) - map_half;
	float far = smoothstep(800.0, 3000.0, out_dist);
	vec3 n = normalize(world_n);
	float mottle = 0.0;
	float brush = 0.0;
	if (far > 0.0) {
		n = slope_detail(n, detail_strength * far, mottle, brush);
	}
	stroke = brush * far;

	vec3 col = COLOR.rgb;
	float h = world_pos.y;
	// Bare rock above the trees, and on cliffs high up.
	float tl = tree_height(world_pos) + mottle * 90.0;
	float rock = smoothstep(-0.03, 0.03, (h - tl) / 500.0 + (0.72 - n.y) * 1.2 * step(tl - 500.0, h));
	// Gullies a shade darker than the ribs between them, like dry-brushed strokes.
	vec3 rock_col = mix(ROCK, ROCK_LIGHT, clamp(0.5 + mottle * 0.8, 0.0, 1.0)) * (0.82 + 0.3 * clamp(mottle + 0.5, 0.0, 1.0));
	col = mix(col, rock_col, rock * far);
	// Snow: lower on gentle ground, only the highest crags hold none; its edge is
	// broken up along the gullies like brushwork.
	float sl = snow_height(world_pos) + mottle * 220.0;
	// Height only lifts it so far: steep faces stay bare rock however high.
	float lift = clamp((h - sl) / 600.0, -1.0, 0.3);
	float snow = smoothstep(-0.03, 0.03, lift + (n.y - 0.62) * 1.3 + mottle * 0.12);
	col = mix(col, SNOW, snow * max(far, step(1.0, h - sl)));
	// Broad washes of warmer and cooler colour across the ranges, and a faint
	// stroke texture in each, as if laid on with a loaded brush.
	float wash = sin(world_pos.x * 0.00031 + 0.8) * sin(world_pos.z * 0.00027 + 2.3);
	col *= mix(vec3(1.0), mix(vec3(0.95, 0.97, 1.05), vec3(1.04, 1.0, 0.96), wash * 0.5 + 0.5) * (1.0 + brush * 0.035), far);

	ALBEDO = srgb_to_linear(col);
	ROUGHNESS = 0.95;
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
	FOG = edge_haze(world_pos, length(VERTEX), map_half);
}

void light() {
	float shade = 1.0;
	if (LIGHT_IS_DIRECTIONAL) {
		float r = length(world_pos.xz);
		if (r < DECK_FADE_END) {
			shade = 1.0 - cloud_shadow(world_pos, cloud_time) * (1.0 - smoothstep(DECK_FADE_START, DECK_FADE_END, r));
		}
	}
	float near = edge_near(world_pos, map_half);
	float ndl = dot(NORMAL, LIGHT);
	// By the map: lit like the terrain beside it.
	float soft = clamp(ndl, 0.0, 1.0);
	// Out on the ranges: a painter's three values (shade, half light, full sun),
	// each a flat wash, their edges dragged ragged along the brush strokes.
	float b = ndl + stroke * 0.07;
	float lit = smoothstep(-0.03, 0.03, b);
	float painted = lit * 0.58 + smoothstep(0.34, 0.4, b) * 0.42;
	// Shade isn't grey: it takes the sky's cool lavender-blue.
	float sun = dot(LIGHT_COLOR, vec3(0.3, 0.59, 0.11));
	vec3 cool = vec3(0.42, 0.45, 0.78) * sun * 0.16 * (1.0 - lit);
	vec3 ranges = painted * LIGHT_COLOR + cool;
	DIFFUSE_LIGHT += mix(ranges, soft * LIGHT_COLOR, near) * ATTENUATION / PI * shade;
}
