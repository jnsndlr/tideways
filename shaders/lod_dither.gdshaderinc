// Dithered swap between a tree's levels of detail (Models.dither_lod). Each tree, by
// its own distance from the camera, takes this level over lod_fade metres centred on
// lod_begin and hands it on over lod_fade centred on lod_end (0: no limit). Across a
// swap the two levels split the screen's pixels by the same ordered pattern, one
// taking the pixels the other drops, so the tree stays solid all the way through:
// never see-through, never doubled up.

uniform float lod_begin = 0.0;
uniform float lod_end = 0.0;
uniform float lod_fade = 0.0;
// Brightens this level's albedo to match the full model's: simpler levels show more of
// their shaded sides and read darker.
uniform vec3 lod_gain = vec3(1.0);

varying flat float lod_in;
varying flat float lod_out;
varying flat float lod_seed;

// This level's share of the tree at `origin` coming in (x) and going out (y), and
// where the tree starts the pattern (z). The caller hands them to the fragment as
// lod_in, lod_out and lod_seed, and collapses the tree when either share is 0.
vec3 lod_weights(vec3 origin, vec3 cam) {
	float d = distance(origin, cam);
	float f = max(lod_fade, 1e-3);
	float w_in = lod_begin > 0.0 ? clamp((d - lod_begin) / f + 0.5, 0.0, 1.0) : 1.0;
	float w_out = lod_end > 0.0 ? clamp((lod_end - d) / f + 0.5, 0.0, 1.0) : 1.0;
	// Neighbours start the pattern at different places, so a stand of trees mid-swap
	// doesn't show one grid running through all of them.
	return vec3(w_in, w_out, fract(dot(origin.xz, vec2(0.0731, 0.1173))));
}

float lod_bayer2(vec2 a) {
	a = floor(a);
	return fract(a.x / 2.0 + a.y * a.y * 0.75);
}

// 8 x 8 ordered dither: 64 steps, evenly spread.
float lod_bayer8(vec2 a) {
	return lod_bayer2(0.25 * a) * 0.0625 + lod_bayer2(0.5 * a) * 0.25 + lod_bayer2(a);
}

void lod_dither(vec2 frag) {
	float t = fract(lod_bayer8(frag) + lod_seed);
	if (t < 1.0 - lod_in || t >= lod_out) {
		discard;
	}
}
