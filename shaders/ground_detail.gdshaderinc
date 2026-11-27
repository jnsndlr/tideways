// Procedural surface detail for the terrain (lit_vc.gdshaderinc, TERRAIN): mottled
// grass and forest floor, and cliffs broken into big shaded boulders. All in world
// space with no textures, and every layer fades to its average once its cells get
// near a pixel across, so zoomed out it costs little and never shimmers.

float gd_hash(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec2 gd_hash2(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}

float gd_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(gd_hash(i), gd_hash(i + vec2(1.0, 0.0)), u.x),
		mix(gd_hash(i + vec2(0.0, 1.0)), gd_hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// One octave of value noise around 0, faded out as its cells (1 / freq metres)
// shrink towards a pixel (mpp: metres per pixel).
float gd_octave(vec2 p, float freq, float mpp) {
	float fade = 1.0 - smoothstep(0.3, 0.7, mpp * freq);
	if (fade <= 0.0) {
		return 0.0;
	}
	return (gd_noise(p * freq) - 0.5) * fade;
}

// Nearest and second-nearest cell centres. Returns (F1, F2 - F1, cell hash) and the
// offset from the nearest centre in `off`.
vec3 gd_voronoi(vec2 p, out vec2 off) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float d1 = 8.0;
	float d2 = 8.0;
	float id = 0.0;
	off = vec2(0.0);
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 c = g + 0.15 + 0.7 * gd_hash2(i + g);
			vec2 r = f - c;
			float d = dot(r, r);
			if (d < d1) {
				d2 = d1;
				d1 = d;
				id = gd_hash(i + g + 17.0);
				off = r;
			} else if (d < d2) {
				d2 = d;
			}
		}
	}
	d1 = sqrt(d1);
	return vec3(d1, sqrt(d2) - d1, id);
}

// Crags seen side-on in one projection: angular blocks wider than they are tall,
// each split by a fracture into two flat faces tipped different ways, with a crisp
// dark crack between blocks and a lit lip along their tops. `uv` in metres. Adds to
// `tilt` (in the projection's u, v) and returns the colour factor.
vec3 gd_crags(vec2 uv, float mpp, inout vec2 tilt) {
	const vec2 SIZE = vec2(6.0, 3.4);
	float cells = mpp / SIZE.y;
	float fade = 1.0 - smoothstep(0.1, 0.4, cells);
	if (fade <= 0.0) {
		return vec3(1.0);
	}
	// A slight shear and only a little warp keep the blocks straight-edged.
	vec2 q = uv / SIZE;
	q.x += q.y * 0.35;
	q += (vec2(gd_noise(uv * 0.09), gd_noise(uv * 0.09 + 7.3)) - 0.5) * 0.5;
	vec2 off;
	vec3 v = gd_voronoi(q, off);
	float edge = v.y;
	float h1 = v.z;
	float h2 = fract(h1 * 13.7);
	float h3 = fract(h1 * 71.3);
	// The fracture: a line through the block at its own angle, one face either side.
	float ang = h2 * 3.1416;
	float side = step(0.0, dot(off, vec2(cos(ang), sin(ang))) + (h3 - 0.5) * 0.3);
	vec2 face = vec2(h2, h3) - 0.5 + (side - 0.5) * vec2(sin(ang), -cos(ang)) * 0.9;
	face.y += 0.25;
	float w = max(0.035, cells * 1.2);
	float crack = 1.0 - smoothstep(w * 0.5, w, edge);
	// A thin bright lip where a block's top meets the crack above it.
	float lip = (1.0 - smoothstep(w, w * 3.0, edge)) * step(0.05, off.y) * (1.0 - crack);
	float shade = mix(0.8, 1.14, fract(h1 * 5.3 + side * 0.37)) * (1.0 - crack * 0.6) * (1.0 + lip * 0.18);
	vec3 tint = mix(vec3(0.95, 0.97, 1.03), vec3(1.05, 1.0, 0.93), h2);
	tilt += face * 1.1 * (1.0 - crack) * fade;
	return mix(vec3(1.0), shade * tint, fade);
}

// Inland rock, hand-painted: big wobbly slabs, each dabbed in a few flat tones with a
// dry-brush grunge over them, a dark seam between slabs and a pale lit edge just
// inside each outline. `uv` in metres on the wall it faces. Adds to `tilt` and
// returns the colour factor.
vec3 gd_painted(vec2 uv, float mpp, inout vec2 tilt) {
	const float SIZE = 9.0;
	float fade = 1.0 - smoothstep(0.08, 0.3, mpp / SIZE);
	if (fade <= 0.0) {
		return vec3(1.0);
	}
	// Heavy warp: loose, hand-drawn outlines rather than cells.
	vec2 w = vec2(gd_noise(uv * 0.05), gd_noise(uv * 0.05 + 5.2)) - 0.5;
	w += (vec2(gd_noise(uv * 0.19 + 2.0), gd_noise(uv * 0.19 + 9.1)) - 0.5) * 0.4;
	vec2 q = uv / SIZE + w * 1.1;
	q.y *= 1.4;
	vec2 off;
	vec3 v = gd_voronoi(q, off);
	float h1 = v.z;
	float h2 = fract(h1 * 13.7);
	float h3 = fract(h1 * 71.3);
	// Only some of the outlines get drawn, in broken strokes, so it reads as painted
	// fractures over one mass of rock rather than paving.
	float drawn = smoothstep(0.42, 0.6, gd_noise(uv * 0.11 + 3.7)) * smoothstep(0.25, 0.45, gd_noise(uv * 0.7 + h1));
	// Roughly metres in from the slab's outline.
	float e = v.y * SIZE * 0.5;
	float sw = max(0.07, mpp * 1.1);
	float seam = (1.0 - smoothstep(sw, sw * 1.8, e)) * drawn;
	float lit = smoothstep(sw, sw * 1.8, e) * (1.0 - smoothstep(sw * 1.8, sw * 1.8 + 0.45, e)) * drawn;
	// Strongest along the tops of slabs, where the sun would catch the lip.
	lit *= mix(0.35, 1.0, smoothstep(-0.1, 0.2, off.y));

	// Broad dabs of tone, snapped towards a few steps like a loaded brush.
	float n = 0.5 + 1.2 * gd_octave(uv + h1 * 40.0, 1.0 / 5.0, mpp) + 0.8 * gd_octave(uv * 1.3 + 11.0, 1.0 / 2.0, mpp);
	float dab = mix(n, floor(n * 3.0 + 0.5) / 3.0, 0.7);
	// Grunge: dark blotches, dry-brush streaks along each slab's stroke direction,
	// and fine flecks.
	float blot = gd_octave(uv + 21.0, 1.0 / 3.0, mpp) + 0.6 * gd_octave(uv + 5.0, 1.0 / 1.2, mpp);
	float ang = h2 * 3.1416;
	mat2 rot = mat2(vec2(cos(ang), sin(ang)), vec2(-sin(ang), cos(ang)));
	float streak = gd_octave((rot * uv) * vec2(1.0, 4.0), 1.0 / 2.2, mpp * 4.0);
	float fleck = gd_octave(uv + 3.0, 1.0 / 0.7, mpp) + 0.5 * gd_octave(uv + 8.0, 1.0 / 0.3, mpp);
	float grunge = -smoothstep(0.1, 0.3, blot) * 1.2;
	grunge += smoothstep(0.06, 0.25, streak) * 0.8 - smoothstep(0.1, 0.3, -streak) * 0.6;
	grunge += smoothstep(0.15, 0.38, fleck) * 0.7 - smoothstep(0.18, 0.4, -fleck) * 0.7;

	float shade = mix(0.86, 1.08, h1) * mix(0.72, 1.18, dab);
	shade *= 1.0 + clamp(off.y, -0.5, 0.5) * 0.12 * drawn;
	shade *= 1.0 + grunge * 0.26;
	shade *= 1.0 - seam * 0.4;
	vec3 tint = mix(vec3(0.96, 0.98, 1.04), vec3(1.05, 1.0, 0.93), h3);
	// The blotches go a touch green-grey, like damp or lichen.
	tint *= mix(vec3(1.0), vec3(0.9, 0.98, 0.86), smoothstep(0.1, 0.3, blot));
	vec3 c = shade * tint + lit * vec3(0.3, 0.28, 0.22);
	tilt += (vec2(h2, h3) - 0.5 + vec2(0.0, 0.15)) * 0.25 * drawn * (1.0 - seam) * fade;
	return mix(vec3(1.0), c, fade);
}

// Grass and forest floor: big damp and dry patches, tufts, and a fine grain. Grass
// blades (grass.gdshader) take the same patches, so they match the ground below.
vec3 gd_soil(vec2 p, float mpp, vec3 albedo, float grass) {
	float patches = gd_octave(p + 31.0, 1.0 / 22.0, mpp) + 0.5 * gd_octave(p, 1.0 / 9.0, mpp);
	float tufts = gd_octave(p, 1.0 / 2.6, mpp) + 0.6 * gd_octave(p + 7.0, 1.0 / 1.1, mpp);
	float grain = gd_octave(p, 1.0 / 0.45, mpp);
	// Dark ground (the woods' floor) gets deeper shadows and fewer dry patches.
	float lum = dot(albedo, vec3(0.3, 0.55, 0.15));
	float wood = 1.0 - smoothstep(0.03, 0.12, lum);
	vec3 dry = albedo * vec3(1.1, 1.05, 0.86);
	vec3 lush = albedo * vec3(0.74, 0.92, 0.84);
	vec3 c = mix(lush, dry, clamp(0.42 + patches * 1.6 * (1.0 - wood * 0.6), 0.0, 1.0));
	// Bare sand keeps its own colour and has subtler ripples and grain.
	vec3 sand = albedo * (1.0 + tufts * 0.18 + grain * 0.24);
	return mix(sand, c * (1.0 + tufts * mix(0.55, 0.8, wood) + grain * 0.35), grass);
}

// Cliff faces: crags projected on whichever wall they face most, the colour pulled
// to grey-brown stone by `pull` and laid over it by `rock` (both 0..1). Changes
// `albedo` and returns the normal to light with.
vec3 gd_cliff(vec3 wp, vec3 wn, float mpp, float rock, float pull, inout vec3 albedo) {
	vec2 wx = vec2(abs(wn.x), abs(wn.z));
	wx = pow(wx, vec2(4.0));
	wx /= max(wx.x + wx.y, 1e-4);
	vec2 tx = vec2(0.0);
	vec2 tz = vec2(0.0);
	vec3 bx = wx.x > 0.02 ? gd_crags(vec2(wp.z, wp.y), mpp, tx) : vec3(1.0);
	vec3 bz = wx.y > 0.02 ? gd_crags(vec2(wp.x, wp.y) + 91.0, mpp, tz) : vec3(1.0);
	vec3 b = bx * wx.x + bz * wx.y;
	float grain = gd_octave(wp.xz + wp.y, 1.0 / 0.8, mpp) + 0.6 * gd_octave(wp.zx - wp.y, 1.0 / 2.4, mpp);
	// Warm and a shade dark: up close it shows mostly in the gaps between the shore
	// rocks (Models.rock_kit), so it should read as the same stone in shadow.
	vec3 stone = mix(albedo, vec3(dot(albedo, vec3(0.33))) * vec3(1.16, 0.98, 0.82) * 0.8, pull);
	vec3 c = stone * b * (1.0 + grain * 0.4);
	// Lichen on the faces that look up.
	c = mix(c, c * vec3(0.92, 1.02, 0.86), smoothstep(0.35, 0.7, wn.y) * 0.6);
	albedo = mix(albedo, c, rock);
	vec3 lean = vec3(0.0, tx.y, tx.x) * wx.x + vec3(tz.x, tz.y, 0.0) * wx.y;
	return normalize(wn + lean * rock);
}

// Inland cliffs and rocky slopes: the painted slabs on whichever wall they face most.
// Changes `albedo` and returns the normal to light with.
// `top` (0..1) lets the stone lie across flat tops too (the boulders'); the
// terrain's rock is all slope, so it leaves that out.
vec3 gd_land_rock(vec3 wp, vec3 wn, float mpp, float rock, float rim, float top, inout vec3 albedo) {
	vec3 wx = pow(vec3(abs(wn.x), abs(wn.z), abs(wn.y) * top), vec3(4.0));
	wx /= max(wx.x + wx.y + wx.z, 1e-4);
	vec2 tx = vec2(0.0);
	vec2 tz = vec2(0.0);
	vec2 ty = vec2(0.0);
	vec3 bx = wx.x > 0.02 ? gd_painted(vec2(wp.z, wp.y), mpp, tx) : vec3(1.0);
	vec3 bz = wx.y > 0.02 ? gd_painted(vec2(wp.x, wp.y) + 91.0, mpp, tz) : vec3(1.0);
	vec3 by = wx.z > 0.02 ? gd_painted(wp.xz + 47.0, mpp, ty) : vec3(1.0);
	vec3 b = bx * wx.x + bz * wx.y + by * wx.z;
	// A set warm grey, not the vertex colour, so no grass green bleeds up the face.
	vec3 stone = vec3(0.2, 0.163, 0.132);
	vec3 c = stone * b;
	// A pale painted edge where the rock gives way to grass.
	c = mix(c, c * 1.45 + vec3(0.02, 0.02, 0.015), rim * 0.8);
	c = mix(c, c * vec3(0.92, 1.02, 0.86), smoothstep(0.45, 0.7, wn.y) * 0.5);
	albedo = mix(albedo, c, rock);
	vec3 lean = vec3(0.0, tx.y, tx.x) * wx.x + vec3(tz.x, tz.y, 0.0) * wx.y + vec3(ty.x, 0.0, ty.y) * wx.z;
	return normalize(wn + lean * rock);
}

// Rock meshes (Models.rock_kit, ROCK): the painted stone down the sides, as on the
// cliffs behind them, and grassy ground on their caps.
vec3 rock_detail(vec3 wp, vec3 wn, float mpp, inout vec3 albedo) {
	float side = 1.0 - smoothstep(0.72, 0.86, wn.y);
	vec3 n = wn;
	vec3 cap = gd_soil(wp.xz, mpp, albedo, 1.0);
	if (side > 0.0) {
		vec3 a = albedo;
		// The inland rock's painted stone, drawn a little smaller: these are a few
		// metres to a dozen across, so at full size a face would hold one slab.
		n = gd_land_rock(wp * 1.5, wn, mpp * 1.5, 1.0, 0.0, 0.0, a);
		albedo = mix(cap, a, side);
		n = normalize(mix(wn, n, side));
	} else {
		albedo = cap;
	}
	return n;
}

// The land boulders (Models.rock, BOULDER): the inland rock's painted stone down the
// sides and over the top, with a lit edge along the top's outline. `edge`: metres in
// from that outline, down a side or across the top.
vec3 boulder_detail(vec3 wp, vec3 wn, float mpp, float edge, inout vec3 albedo) {
	float w = max(0.3, mpp * 1.5);
	float rim = 1.0 - smoothstep(w * 0.5, w, edge);
	// The stone's features drawn smaller than on the hills: a boulder's only a few
	// metres across, and at full size it would be one flat tone.
	return gd_land_rock(wp * 2.0, wn, mpp * 2.0, 1.0, rim, 1.0, albedo);
}

// Detail for one terrain pixel. `wn`: the smooth world normal. Changes `albedo`
// (linear) and returns the world normal to light with.
vec3 ground_detail(vec3 wp, vec3 wn, float mpp, inout vec3 albedo) {
	// A ragged, fairly crisp edge between rock and grass, with a rim just inside it.
	float rag = gd_octave(wp.xz + 4.0, 1.0 / 7.0, mpp) + 0.6 * gd_octave(wp.xz, 1.0 / 2.4, mpp);
	// Cut at 0.76, past where the vertex colour turns rock (ny 0.72), so no brown
	// shows through the grass. Metres in from the edge, from how fast t changes.
	float t = wn.y + rag * 0.12;
	float in_m = (0.76 - t) * mpp / max(fwidth(t), 1e-5);
	float rock = smoothstep(-0.5, 0.5, in_m / max(mpp, 0.02));
	float rim = rock * (1.0 - smoothstep(max(0.35, mpp), max(0.8, mpp * 2.0), in_m));
	// Low dock pads can carry the same grass colour as upland fields.
	// Follow the painted sand/grass blend there, and fade at the waterline.
	float land = smoothstep(0.0, 1.0, wp.y);
	vec3 n = wn;

	// Grass and forest floor.
	float soil = land * (1.0 - rock);
	if (soil > 0.0) {
		float grass = max(smoothstep(3.2, 4.2, wp.y),
			smoothstep(-0.04, 0.035, albedo.g - albedo.r));
		albedo = mix(albedo, gd_soil(wp.xz, mpp, albedo, grass), soil);
	}

	if (rock > 0.0) {
		n = gd_land_rock(wp, wn, mpp, rock, rim, 0.0, albedo);
	}
	return n;
}
