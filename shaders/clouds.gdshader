shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_never, shadows_disabled, specular_disabled, diffuse_lambert_wrap, skip_vertex_transform;

// Visible clouds: thousands of soft, camera-facing puffs (CloudLayer's MultiMesh).
// Each drifts with the wind and sizes and lifts itself from the shared cloud field,
// so puffs heap up into cumulus where the field is dense, thin out at its edges and
// vanish in clear sky, always over the ground shadows that field casts. Each puff
// is shaded as a soft sphere lit by the sun (so clouds blush at sunset), greyer low
// down with flat bases, and the deck fades near the camera so it never blocks the
// view when zoomed in.

#include "res://shaders/clouds.gdshaderinc"

uniform float opacity = 0.92;
uniform float tile = 10400.0;
uniform sampler2D puff_noise : filter_linear_mipmap, repeat_enable;
uniform float near_fade_start = 540.0;
uniform float near_fade_end = 1560.0;
// How high the densest heaps stand above the cloud base.
uniform float thickness = 240.0;
// Two rings share this shader: dense, small puffs near the map and sparser, bigger
// ones out over the mainland, crossfading between them. Past the outer ring the
// backdrop's cumulus take over (keep the fade in sync with backdrop.gdshader and
// tree_card.gdshader).
uniform float size_scale = 1.0;
uniform vec2 fade_in = vec2(-2.0, -1.0); // radius where this ring fades in (none by default)
uniform vec2 fade_out = vec2(3000.0, 4900.0);

varying vec3 world_pos;
varying vec2 corner;
varying float body;
varying float seed;

void vertex() {
	vec4 c = INSTANCE_CUSTOM;
	// Drift with the wind and wrap round the tile, out beyond the far fade.
	vec2 p = MODEL_MATRIX[3].xz + cloud_wind * cloud_time;
	p = mod(p + tile * 0.5, tile) - tile * 0.5;
	float cov = cloud_local_coverage(p, cloud_time);
	float n = cloud_octaves(p, cloud_time, 0, COARSE_OCTAVES) * 0.5 + 0.5;
	float lo = cloud_lo(cov);
	// Wider than the shadow's edge, so heaps round off into small puffs at the fringe.
	body = smoothstep(lo - 0.03, lo + 0.3, n);
	// The outer ring's puffs start at the near ring's size and only grow to full
	// size_scale well past the crossfade, so there's no seam where big puffs begin.
	float grow = mix(1.0, size_scale, smoothstep(fade_in.x, fade_in.y + 2500.0, length(p)));
	float size = body > 0.0 ? mix(330.0, 470.0, c.r) * (0.3 + 0.7 * body) * grow : 0.0;
	vec3 centre = vec3(p.x, CLOUD_ALTITUDE + body * thickness + (c.g - 0.5) * 50.0, p.y);

	vec3 right = INV_VIEW_MATRIX[0].xyz;
	vec3 up = INV_VIEW_MATRIX[1].xyz;
	world_pos = centre + (right * VERTEX.x + up * VERTEX.y) * size;
	corner = VERTEX.xy * 2.0;
	seed = c.b;
	VERTEX = (VIEW_MATRIX * vec4(world_pos, 1.0)).xyz;
	NORMAL = vec3(0.0, 0.0, 1.0);
}

void fragment() {
	float r2 = dot(corner, corner);
	if (r2 >= 1.0 || body <= 0.0) {
		discard;
	}
	float fall = 1.0 - r2;
	// Noise eats into the rim so overlapping puffs merge into one ragged mass
	// instead of reading as discs.
	float tex = texture(puff_noise, corner * 0.4 + vec2(seed * 3.7, seed * 1.9)).r;
	float a = smoothstep(0.0, 0.4, fall - (0.62 - tex) * 0.9);

	// Shade as a soft sphere, leaning toward world up so a heap reads as one mass
	// rather than a pile of balls.
	vec3 up_v = (VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz;
	vec3 sphere = normalize(vec3(corner, sqrt(fall) * 1.3));
	NORMAL = normalize(mix(sphere, up_v, 0.3));

	// Greyer and cooler low in the heap, with flat bases.
	float hfrac = clamp((world_pos.y - CLOUD_ALTITUDE) / (thickness + 120.0), 0.0, 1.0);
	ALBEDO = mix(vec3(0.62, 0.66, 0.75), vec3(1.0), smoothstep(0.0, 0.75, hfrac));
	// Storm cloud: slate grey, darkest low in the heap.
	ALBEDO *= mix(vec3(1.0), mix(vec3(0.17, 0.18, 0.22), vec3(0.4, 0.42, 0.47), hfrac), cloud_storm);
	float base = smoothstep(CLOUD_ALTITUDE - 50.0, CLOUD_ALTITUDE + 30.0, world_pos.y);

	float near = mix(0.12, 1.0, smoothstep(near_fade_start, near_fade_end, length(VERTEX)));
	float r = length(world_pos.xz);
	float far = smoothstep(fade_in.x, fade_in.y, r) * (1.0 - smoothstep(fade_out.x, fade_out.y, r));
	ALPHA = a * base * smoothstep(0.0, 0.2, body) * opacity * near * far;
}
