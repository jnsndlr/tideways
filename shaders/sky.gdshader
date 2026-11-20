shader_type sky;
render_mode use_half_res_pass;

// The sky: Godot's procedural gradient and sun (same uniforms as
// ProceduralSkyMaterial, driven by DayCycle) with two cheap 2.5D cloud layers.
//
// 1. The far deck. CloudLayer's puffs stop about 13.5 km out; from under the deck
//    the sky carries the same cloud field (clouds.gdshaderinc) on out to the
//    horizon as a flat layer at the deck's altitude, fading in exactly as the
//    puffs fade out, so there's no ring of clear sky between them. Seen from
//    below: dark, thick middles and bright, thin edges, shrinking and hazing
//    toward the horizon.
// 2. Distant cumulus. Separate heaps standing on the horizon round the compass,
//    with clear sky between them, bright sunny tops, cool bases and haze at their
//    feet. A 2D skyline of heights per direction, roughed up by billowy noise.
//
// Both are computed in the half-resolution pass and composited at full
// resolution. They animate from global uniforms (cloud_time, cloud_wind,
// horizon_clouds), not TIME or material parameters, so their drift never forces
// the radiance cubemap to re-render; reflections pick them up when DayCycle next
// refreshes the sky.

#include "res://shaders/clouds.gdshaderinc"

uniform vec4 sky_top_color : source_color = vec4(0.36, 0.56, 0.8, 1.0);
uniform vec4 sky_horizon_color : source_color = vec4(0.74, 0.83, 0.9, 1.0);
uniform float sky_curve : hint_range(0, 1) = 0.15;
uniform vec4 ground_bottom_color : source_color = vec4(0.12, 0.28, 0.36, 1.0);
uniform vec4 ground_horizon_color : source_color = vec4(0.74, 0.83, 0.9, 1.0);
uniform float ground_curve : hint_range(0, 1) = 0.02;
uniform float sun_angle_max = 30.0; // degrees: the sun's halo
uniform float sun_curve : hint_range(0, 1) = 0.15;

// Distant cumulus, from Weather via CloudLayer: x coverage (0..1, how much of the
// horizon has heaps), y height (sin of the tallest towers' elevation), z density
// (opacity, also of the far deck), w haze.
global uniform vec4 horizon_clouds;

// Where CloudLayer's outer puff ring fades out (CloudLayer.FAR_FADE).
const vec2 DECK_FADE = vec2(10500.0, 13500.0);
// The cumulus lie on a ring this many noise units round (one unit is ~7 degrees)...
const float RING = 8.0;
// ...this far away (m), which sets how fast the wind carries them.
const float RING_DISTANCE = 60000.0;

float hash3(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

float vnoise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), u.x),
			mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), u.x), u.y),
		mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), u.x),
			mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), u.x), u.y), u.z);
}

// 0..1 fbm.
float fbm(vec3 p, int octaves) {
	float n = 0.0;
	float a = 0.5;
	float total = 0.0;
	for (int i = 0; i < octaves; i++) {
		n += a * vnoise(p);
		total += a;
		p = p * 2.03 + vec3(17.1, 9.2, 4.7);
		a *= 0.5;
	}
	return n / total;
}

// Premultiplied colour and alpha of the deck where it continues past the puffs.
vec4 far_deck(vec3 dir, vec3 cam, vec3 sky_top, vec3 sky_horizon, vec3 light_dir, vec3 light) {
	if (cam.y >= CLOUD_ALTITUDE - 50.0 || dir.y <= 0.004 || cloud_coverage <= 0.0) {
		return vec4(0.0);
	}
	float d = (CLOUD_ALTITUDE - cam.y) / dir.y;
	vec2 hit = cam.xz + dir.xz * d;
	float fade = smoothstep(DECK_FADE.x, DECK_FADE.y, length(hit));
	if (fade <= 0.0) {
		return vec4(0.0);
	}
	// 0 just past the puffs .. 1 far out toward the horizon.
	float far = smoothstep(14000.0, 90000.0, d);
	float cov = cloud_local_coverage(hit, cloud_time);
	// Only the broad octaves: out here the finer ones (and the puffs that soften
	// them on the deck) are under a pixel and just speckle. The third fades out
	// with distance, and the edges soften to match.
	float n = cloud_octaves(hit, cloud_time, 0, 2);
	float lo = cloud_lo(cov);
	if (n * 0.5 + 0.5 < lo - 0.15) {
		return vec4(0.0);
	}
	n += cloud_octaves(hit, cloud_time, 2, 3) * (1.0 - smoothstep(14000.0, 35000.0, d));
	float w = 0.04 + far * 0.12;
	// Same shape as the puffs' body in clouds.gdshader.
	float body = smoothstep(lo - 0.03 - w, lo + 0.3 + w, n * 0.5 + 0.5);
	float a = smoothstep(0.0, 0.35, body) * fade * horizon_clouds.z;

	// From below: thick middles in their own shade, thin edges lit through. Far
	// off we see more of their sunlit sides.
	float sun_up = clamp(light_dir.y * 3.0 + 0.2, 0.0, 1.0);
	vec3 shade = mix(sky_top, sky_horizon, 0.45) * 0.55 + light * 0.08;
	vec3 lit = mix(sky_top, sky_horizon, 0.6) * 0.6 + light * 0.75 * sun_up;
	float thick = smoothstep(0.15, 0.85, body) * (1.0 - far * 0.55);
	vec3 col = mix(lit, shade, thick);
	// Storm cloud: slate grey through and through.
	col *= mix(1.0, mix(0.45, 0.28, thick), cloud_storm);
	// A brighter rim toward the sun.
	col += light * 0.5 * pow(max(dot(dir, light_dir), 0.0), 8.0) * (1.0 - thick);
	// Aerial haze, thickening toward the horizon.
	col = mix(col, sky_horizon, smoothstep(12000.0, 110000.0, d) * mix(0.55, 0.9, horizon_clouds.w));
	return vec4(col * a, a);
}

// Premultiplied colour and alpha of the distant cumulus heaps along the horizon.
vec4 horizon_heaps(vec3 dir, vec3 sky_top, vec3 sky_horizon, vec3 light_dir, vec3 light) {
	float e = dir.y;
	float cov = horizon_clouds.x;
	float height = horizon_clouds.y;
	if (e > height * 1.4 + 0.03 || e < -0.02 || horizon_clouds.z <= 0.0) {
		return vec4(0.0);
	}
	vec2 ring = normalize(dir.xz + vec2(1e-5)) * RING;
	// The wind carries the ring's pattern across the world: on the flanks it slides
	// along the horizon, up- and downwind it slowly churns.
	vec2 q = ring - cloud_wind * cloud_time * (RING / RING_DISTANCE);
	float t = cloud_time * 0.002;

	// Separate groups of heaps with clear sky between them.
	float group = fbm(vec3(q * 0.45, 1.7 + t * 0.3), 3);
	float thr = 0.72 - cov * 0.4;
	float c = smoothstep(thr, thr + 0.12, group);
	if (c <= 0.0) {
		return vec4(0.0);
	}
	// Each group has a tallest head or two and lower shoulders.
	float tower = fbm(vec3(q * 0.7, 5.3 + t * 0.5), 2);
	float top = height * c * mix(0.35, 1.0, smoothstep(0.3, 0.7, tower));

	// Billowy detail (isotropic in angle) eats into the outline for rounded heads,
	// and lifts the base off the horizon in places.
	vec3 dp = vec3(q.x, e * RING, q.y) * 2.2;
	float d = fbm(dp + vec3(0.0, -t * 2.0, t), 5);
	float edge = top - e + (d - 0.5) * (0.012 + top * 0.9);
	float soft = 0.004 + top * 0.05;
	float base = 0.004 + (1.0 - d) * 0.012 * c;
	float a = smoothstep(0.0, soft, edge) * smoothstep(base - 0.008, base + 0.004, e);
	if (a <= 0.0) {
		return vec4(0.0);
	}

	// Bright sunny tops, cool flat-lit bases, faces toward the sun darker with a
	// bright rim. With the sun low only the tops catch it.
	float hfrac = clamp(e / max(top, 0.004), 0.0, 1.0);
	float toward = dot(normalize(dir.xz + vec2(1e-5)), normalize(light_dir.xz + vec2(1e-5)));
	float sun_up = clamp(light_dir.y * 4.0 + 0.3, 0.0, 1.0);
	float low_sun = 1.0 - smoothstep(0.05, 0.35, light_dir.y);
	float body = mix(0.15, 1.0, smoothstep(0.05, 0.85, hfrac));
	body *= mix(1.0, 0.65, max(toward, 0.0) * sun_up);
	body *= mix(0.7, 1.15, smoothstep(0.35, 0.75, d));
	body *= mix(1.0, smoothstep(0.35, 1.0, hfrac), low_sun * 0.85);
	float rim = (1.0 - smoothstep(0.0, soft * 3.0, edge)) * pow(max(dot(dir, light_dir), 0.0), 6.0) * 1.6;
	vec3 under = mix(sky_top, sky_horizon, 0.4) * 0.6;
	vec3 col = under * mix(1.0, 0.75, low_sun) + light * 0.7 * mix(1.0, 0.5, low_sun) * (body + rim);
	// Grey, flat-lit banks under an overcast sky.
	float grey = smoothstep(0.75, 1.0, cov);
	col = mix(col, mix(sky_horizon, vec3(dot(col, vec3(0.33))), 0.6) * 0.9, grey * 0.6);

	// Aerial haze: their feet melt into the horizon.
	float haze = horizon_clouds.w * (1.0 - smoothstep(0.0, 0.012 + height * 0.2, e));
	col = mix(col, sky_horizon, clamp(haze + horizon_clouds.w * 0.08, 0.0, 1.0));
	a *= horizon_clouds.z * (1.0 - haze * 0.5);
	return vec4(col * a, a);
}

vec4 clouds(vec3 dir, vec3 cam, vec3 sky_top, vec3 sky_horizon, vec3 light_dir, vec3 light) {
	vec4 heaps = horizon_heaps(dir, sky_top, sky_horizon, light_dir, light);
	vec4 deck = far_deck(dir, cam, sky_top, sky_horizon, light_dir, light);
	// The deck is nearer, so it lies over the heaps.
	return deck + heaps * (1.0 - deck.a);
}

vec3 sky_gradient(vec3 dir, vec3 top, vec3 horizon) {
	float v_angle = acos(clamp(dir.y, -1.0, 1.0));
	if (dir.y >= 0.0) {
		float c = 1.0 - v_angle / (PI * 0.5);
		vec3 sky = mix(horizon, top, clamp(1.0 - pow(1.0 - c, 1.0 / sky_curve), 0.0, 1.0));
		if (LIGHT0_ENABLED) {
			float sun_angle = acos(clamp(dot(LIGHT0_DIRECTION, dir), -1.0, 1.0));
			float glow = radians(sun_angle_max);
			vec3 sun = LIGHT0_COLOR * LIGHT0_ENERGY;
			if (sun_angle < LIGHT0_SIZE) {
				sky = sun;
			} else if (sun_angle < glow) {
				float c2 = (sun_angle - LIGHT0_SIZE) / (glow - LIGHT0_SIZE);
				sky = mix(sun, sky, clamp(1.0 - pow(1.0 - c2, 1.0 / sun_curve), 0.0, 1.0));
			}
		}
		return sky;
	}
	float c = (v_angle - PI * 0.5) / (PI * 0.5);
	return mix(ground_horizon_color.rgb, ground_bottom_color.rgb, clamp(1.0 - pow(1.0 - c, 1.0 / ground_curve), 0.0, 1.0));
}

void sky() {
	vec3 light_dir = LIGHT0_ENABLED ? LIGHT0_DIRECTION : vec3(0.0, -1.0, 0.0);
	vec3 light = LIGHT0_ENABLED ? LIGHT0_COLOR * LIGHT0_ENERGY : vec3(0.0);
	if (AT_HALF_RES_PASS) {
		vec4 c = clouds(EYEDIR, POSITION, sky_top_color.rgb, sky_horizon_color.rgb, light_dir, light);
		COLOR = c.rgb;
		ALPHA = c.a;
	} else {
		vec3 sky = sky_gradient(EYEDIR, sky_top_color.rgb, sky_horizon_color.rgb);
		vec4 c = AT_CUBEMAP_PASS
			? clouds(EYEDIR, POSITION, sky_top_color.rgb, sky_horizon_color.rgb, light_dir, light)
			: HALF_RES_COLOR;
		COLOR = sky * (1.0 - c.a) + c.rgb;
	}
}
