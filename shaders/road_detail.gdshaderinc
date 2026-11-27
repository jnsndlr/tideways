// Asphalt, lane markings and gravel shoulders for the town roads (lit_vc.gdshaderinc,
// ROAD; RoadMesh builds the strips). No textures: world-space noise for the grain,
// patches and wear, and the markings drawn from the strip's UVs:
//   UV.x   metres across from the centreline (+ right), out to the shoulder's edge
//   UV.y   metres along the road
//   UV2.x  how strongly the markings show (0 at junctions and the lot, so they fade out)
//   UV2.y  marking style (RoadMesh.Style): 0 none, 1 dashed yellow centre, 2 dashed
//          yellow and white edge lines, 3 double yellow and white edge lines
// Every layer fades to its average once its detail nears a pixel, so it doesn't
// shimmer zoomed out.

// 0..1: how wet the roads are (CloudLayer, from the weather's storm).
global uniform float road_wet;

// Must match RoadMesh.ASPHALT_HALF.
const float RD_ASPHALT_HALF = 3.7;
const float RD_EDGE_LINE = 3.42;
const float RD_DASH = 3.0;
const float RD_DASH_PERIOD = 12.0;

uniform vec3 gravel_color : source_color = vec3(0.5, 0.47, 0.42);
uniform vec3 yellow_line : source_color = vec3(0.86, 0.66, 0.16);
uniform vec3 white_line : source_color = vec3(0.86, 0.86, 0.83);
uniform vec3 sidewalk_color : source_color = vec3(0.62, 0.61, 0.58);
uniform vec3 verge_color : source_color = vec3(0.55, 0.68, 0.25);
uniform vec3 dirt_color : source_color = vec3(0.46, 0.36, 0.25);
// How far a street has come as its town grows (WorldBuilder.set_street_stage):
// 0 a dirt track, 1 gravel, 2 paved (its zone's look, from UV2.y).
instance uniform float road_stage = 2.0;

// A line `hw` either side of 0, box-filtered over a pixel `fw` wide: its share of
// the pixel, so a thin line far off fades to its average rather than sparkling.
float rd_band(float d, float hw, float fw) {
	fw = max(fw, 1e-4);
	return clamp((d + hw) / fw + 0.5, 0.0, 1.0) - clamp((d - hw) / fw + 0.5, 0.0, 1.0);
}

// The road surface at world position `wp`: albedo (linear, in and out), roughness,
// how glossy it is for the sun's highlight, and any glow of its own.
void road_detail(vec3 wp, vec2 uv, vec2 uv2, vec2 fw, float mpp, inout vec3 albedo,
		out float rough, out float gloss, out vec3 emit) {
	float x = uv.x;
	float ax = abs(x);
	float s = uv.y;
	float show = clamp(uv2.x, 0.0, 1.0);
	int style = int(round(uv2.y));
	vec2 p = wp.xz;
	emit = vec3(0.0);

	if (road_stage < 1.5) {
		// Unpaved: a dirt track with two worn ruts and grass up the middle, or packed
		// gravel; both narrower than tarmac and fraying into the grass at the sides.
		float g_grain = gd_octave(p, 2.6, mpp) + 0.7 * gd_octave(p, 6.5, mpp);
		float g_mottle = gd_octave(p, 0.11, mpp) + 0.5 * gd_octave(p, 0.37, mpp);
		float g_edge = gd_noise(p * 0.45) * 0.6 + gd_noise(p * 1.6) * 0.4;
		bool dirt = road_stage < 0.5;
		float half_w = (dirt ? 2.4 : 3.2) - 0.6 * g_edge;
		vec3 base = dirt ? dirt_color * (1.0 + 0.25 * g_grain + 0.18 * g_mottle)
			: gravel_color * (1.0 + 0.4 * g_grain + 0.12 * g_mottle);
		float rut = 1.0 - smoothstep(0.15, 0.45, abs(ax - 0.95));
		base *= 1.0 - (dirt ? 0.18 : 0.08) * rut;
		float mid_grass = dirt ? (1.0 - smoothstep(0.25, 0.5, ax + 0.25 * g_edge)) * 0.8 : 0.0;
		float side_grass = smoothstep(half_w - 0.3, half_w + 0.3, ax);
		vec3 grass = verge_color * (1.0 + 0.3 * g_grain + 0.2 * g_mottle);
		float g_cover = clamp(side_grass + mid_grass, 0.0, 1.0);
		albedo = mix(base, grass, g_cover);
		float w0 = clamp(road_wet, 0.0, 1.0);
		float g_low = gd_noise(p * 0.3) * 0.7 + gd_noise(p * 0.9) * 0.3;
		float g_puddle = w0 * smoothstep(0.62, 0.74, g_low + 0.3 * rut) * (1.0 - side_grass);
		albedo *= mix(1.0, 0.7, w0 * (1.0 - side_grass));
		rough = mix(1.0, 0.1, g_puddle);
		gloss = w0 * g_puddle;
		// Where grass takes over, let the ground itself show (lit_vc discards on -1):
		// a ragged, dithered edge rather than a strip of the wrong green.
		if (g_cover > 0.35 + 0.3 * gd_noise(p * 2.3)) { rough = -1.0; }
		return;
	}

	// Gravel shoulders, paved over where the markings fade out (junction mouths,
	// the lot's apron).
	float shoulder = step(RD_ASPHALT_HALF, ax) * step(0.5, show);
	float grain = gd_octave(p, 2.6, mpp) + 0.7 * gd_octave(p, 6.5, mpp);
	float mottle = gd_octave(p, 0.11, mpp) + 0.5 * gd_octave(p, 0.37, mpp);

	// Asphalt: broad mottling, fine aggregate, darker newer patches and the polished
	// tracks the tyres wear into each lane.
	vec3 asphalt = albedo * (1.0 + 0.16 * mottle + 0.22 * grain);
	vec2 off;
	vec3 cell = gd_voronoi(p * 0.16, off);
	float repair = step(0.84, cell.z) * smoothstep(0.02, 0.08, cell.y) * (1.0 - smoothstep(0.5, 0.9, mpp * 0.16));
	asphalt *= 1.0 - 0.14 * repair;
	float track = 1.0 - smoothstep(0.12, 0.5, min(abs(ax - 0.95), abs(ax - 2.75)));
	track *= 1.0 - shoulder;
	asphalt *= 1.0 - 0.07 * track;

	// Street types by marking style: 2/3 the main street (kerb and concrete sidewalk
	// on the shoulders), 1 side streets and lanes (older, unmarked, paler asphalt
	// crumbling into a gravel-and-grass verge), 0 anything else (plain gravel).
	// 4: core street (kerb and sidewalk, no lines); 5: outer lane (narrow, gravelly).
	bool main_st = style >= 2 && style <= 4;
	bool side_st = style == 1 || style == 5;
	float edge_n = gd_noise(p * 0.45) * 0.6 + gd_noise(p * 1.6) * 0.4;

	if (side_st) {
		// Faded, patchier tarmac; the edge eats in unevenly, so no ruler-straight line.
		asphalt = mix(asphalt, asphalt * vec3(1.12, 1.1, 1.05), 0.6) * (1.0 + 0.1 * mottle);
		float ragged = (style == 5 ? 2.7 : RD_ASPHALT_HALF) - 0.55 * edge_n;
		shoulder = smoothstep(ragged - 0.12, ragged + 0.12, ax) * step(0.5, show);
	}

	vec3 gravel = gravel_color * (1.0 + 0.35 * grain + 0.12 * mottle);
	// Grass takes over the outer half of the verge, so the road blends into the ground.
	float grass = smoothstep(3.9, 4.6, ax + 0.6 * (edge_n - 0.5));
	vec3 verge = mix(gravel, verge_color * (1.0 + 0.3 * grain + 0.2 * mottle), grass);
	float verge_rough = 1.0;

	if (main_st) {
		// Kerb: a light concrete line with a dark gutter on the road side, then a
		// jointed sidewalk slab out to a narrow grass edge.
		float kerb = smoothstep(3.7, 3.74, ax) * (1.0 - smoothstep(3.86, 3.9, ax));
		float gutter = rd_band(ax - 3.62, 0.08, fw.x);
		float joint = rd_band(mod(s, 1.5) - 0.75, 0.02, fw.y) * (1.0 - kerb);
		vec3 walk = sidewalk_color * (1.0 + 0.1 * grain + 0.1 * mottle) * (1.0 - 0.35 * joint);
		walk = mix(walk, sidewalk_color * 1.12, kerb);
		float edge_grass = smoothstep(4.85, 5.05, ax);
		verge = mix(walk, verge_color * (1.0 + 0.3 * grain), edge_grass);
		verge_rough = 0.85;
		asphalt *= 1.0 - 0.3 * gutter;
	}

	albedo = mix(asphalt, verge, shoulder);
	rough = mix(mix(0.9, 0.8, track), verge_rough, shoulder);
	if (!main_st) { track *= 0.5; }

	// Markings, worn in places.
	float wear = mix(0.5, 1.0, smoothstep(0.25, 0.6, gd_noise(p * 1.7 + vec2(s * 0.05, 0.0))));
	wear *= mix(0.8, 1.0, gd_noise(p * 0.21));
	float yellow = 0.0;
	if (style == 2) {
		float along = mod(s, RD_DASH_PERIOD) - RD_DASH * 0.5;
		yellow = rd_band(x, 0.07, fw.x) * rd_band(along, RD_DASH * 0.5, fw.y);
	} else if (style == 3) {
		yellow = rd_band(x - 0.16, 0.06, fw.x) + rd_band(x + 0.16, 0.06, fw.x);
	}
	float white = 0.0;
	if (style == 2 || style == 3) {
		white = rd_band(ax - RD_EDGE_LINE, 0.07, fw.x);
	}
	// Markings use the upper half of `show`; below 0.5 the shoulders are paved over too.
	float paint_k = clamp(show * 2.0 - 1.0, 0.0, 1.0);
	yellow *= paint_k * wear;
	white *= paint_k * wear * (1.0 - shoulder);
	vec3 paint_y = yellow_line;
	vec3 paint_w = white_line;
	albedo = mix(albedo, paint_y, yellow);
	albedo = mix(albedo, paint_w, white);
	float paint = max(yellow, white);
	rough = mix(rough, 0.7, paint);

	// Wet: darker, glossy, with water standing in the tyre tracks and low spots.
	float w = clamp(road_wet, 0.0, 1.0) * (1.0 - 0.6 * shoulder);
	float low = gd_noise(p * 0.3) * 0.7 + gd_noise(p * 0.9) * 0.3;
	float puddle = w * smoothstep(0.6, 0.72, low + 0.3 * track) * (1.0 - shoulder);
	albedo *= mix(1.0, mix(0.6, 0.85, paint), w);
	albedo *= 1.0 - 0.25 * puddle;
	rough = mix(rough, 0.32, w);
	rough = mix(rough, 0.06, puddle);
	gloss = w * (0.35 + 0.65 * puddle);

	// The paint's glass beads catch the light at night, just enough to show the lanes.
	emit = (paint_y * yellow + paint_w * white) * night_lights * 0.05;
}
