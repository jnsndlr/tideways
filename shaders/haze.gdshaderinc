// Aerial perspective for everything past the map (Backdrop: land, tree cards and
// cumulus). Near the map it matches the engine's depth fog on the water; further
// out each layer sinks toward the blue of distance, with a thin band of haze lying
// on the water at the foot of the far shores, and high ground stands clear of it.
// Written to FOG, which replaces the engine's fog for these materials.

global uniform vec3 haze_fog;
global uniform vec3 haze_sky;
global uniform vec3 sky_zenith;
global uniform vec2 fog_range;

vec4 backdrop_haze(vec3 world, float depth) {
	// The blue of distance, by how far out from the map: the near bank stays clear
	// and each range behind it sinks a little further into the sky's blue. No white
	// fog lying on the water at the shore's foot.
	float r = length(world.xz);
	float far = pow(smoothstep(3400.0, 27000.0, r), 0.8) * 0.72;
	return vec4(mix(haze_sky, sky_zenith, 0.55), far);
}

// The engine's depth fog as the Sandbox sets it up (density 0.85, linear over
// fog_range), for blending into at the map's edge.
const float ENGINE_FOG_DENSITY = 0.85;
// Over this far past the map's edge (map_half: Terrain.half_size) the Backdrop
// turns from the engine's own fog, as on the terrain beside it, to its haze.
const float EDGE_HAZE = 1200.0;

float edge_near(vec3 world, float map_half) {
	return 1.0 - smoothstep(0.0, EDGE_HAZE, max(abs(world.x), abs(world.z)) - map_half);
}

vec4 edge_haze(vec3 world, float depth, float map_half) {
	float engine = clamp((depth - fog_range.x) / max(fog_range.y - fog_range.x, 1.0), 0.0, 1.0) * ENGINE_FOG_DENSITY;
	return mix(backdrop_haze(world, depth), vec4(haze_fog, engine), edge_near(world, map_half));
}
