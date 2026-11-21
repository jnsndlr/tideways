shader_type spatial;
render_mode cull_disabled, skip_vertex_transform;

// The 300-triangle pine past Models.IMPOSTOR_DIST: a quad facing the camera, showing
// the model as baked (tools/bake_impostor.gd) from the two headings and two heights
// round the camera's, each reprojected onto the quad and blended by how near the
// camera is to it, so the tree turns smoothly instead of jumping frame to frame. Each
// texel is lit with the model's own colours and normals as lit_vc.gdshaderinc lights
// the model, so it reads the same at any hour. Its baked depth puts each texel back
// where the model's surface is for shadows (LIGHT_VERTEX): the model's shadow caster
// shades it as it shades the model, its tiers included.
// The instance transform places it as it would the model; COLOR is the per-tree tint.

#include "res://shaders/clouds.gdshaderinc"
#include "res://shaders/lod_dither.gdshaderinc"

// rgb the model's vertex colours, a its coverage.
uniform sampler2D albedo_atlas : filter_linear_mipmap, repeat_disable;
// rgb its normals in its own frame (0.5 + n / 2), a its depth (0.5 + d / (2 radius)).
uniform sampler2D normal_atlas : filter_linear_mipmap, repeat_disable;
// The sphere each frame was baked in (Models.impostor_base), in the model's frame.
uniform vec3 center = vec3(0.0);
uniform float radius = 1.0;
// The variant's rescaling of the baked model (Models.LPINE_SCALE).
uniform vec3 variant_scale = vec3(1.0);
uniform int azimuths = 16;
uniform int elevations = 4;
uniform float elevation_step = 20.0;

// The quad's point in the model's frame, relative to the centre.
varying vec3 local_pos;
// The camera's direction in the model's frame.
varying flat vec3 view_dir;
// The two headings (x, y) and two heights (z, w) round the camera's, and how far it
// is from the first toward the second (blend.x heading, blend.y height).
varying flat vec4 frames;
varying flat vec2 blend;
// The model's frame to the world's, for normals (inverse transpose).
varying flat vec3 n0;
varying flat vec3 n1;
varying flat vec3 n2;
// The view direction in the world, one radius long (depth's unit).
varying flat vec3 depth_axis;
varying float cloud_shade;

vec3 srgb_to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

// The baked view direction of heading `ai`, height `ei`.
vec3 frame_dir(float ai, float ei) {
	float a = ai * TAU / float(azimuths);
	float e = radians(ei * elevation_step);
	return vec3(cos(e) * cos(a), sin(e), cos(e) * sin(a));
}

// Where the ray along the view through the quad's point `p` is `h` (m) in front of
// frame `d`'s plane, in that frame's 0..1 square.
vec2 frame_uv(vec3 p, vec3 v, vec3 d, float h) {
	vec3 rx = normalize(cross(vec3(0.0, 1.0, 0.0), d));
	vec3 ry = cross(d, rx);
	vec3 q = p - v * ((dot(p, d) - h) / max(dot(v, d), 0.2));
	return vec2(dot(q, rx), -dot(q, ry)) / (2.0 * radius) + 0.5;
}

void vertex() {
	mat3 m = mat3(MODEL_MATRIX[0].xyz, MODEL_MATRIX[1].xyz, MODEL_MATRIX[2].xyz)
		* mat3(vec3(variant_scale.x, 0.0, 0.0), vec3(0.0, variant_scale.y, 0.0), vec3(0.0, 0.0, variant_scale.z));
	vec3 origin = MODEL_MATRIX[3].xyz;
	vec3 c_world = origin + m * center;
	mat3 inv = inverse(m);
	// The camera's direction in the model's frame, between which baked frames.
	vec3 dl = normalize(inv * (CAMERA_POSITION_WORLD - c_world));
	float az = atan(dl.z, dl.x) / TAU * float(azimuths);
	float el = clamp(degrees(asin(clamp(dl.y, -1.0, 1.0))) / elevation_step, 0.0, float(elevations - 1));
	float a0 = floor(az);
	float e0 = min(floor(el), float(elevations - 2));
	frames = vec4(mod(a0, float(azimuths)), mod(a0 + 1.0, float(azimuths)), e0, e0 + 1.0);
	blend = vec2(az - a0, el - e0);
	// The quad across the camera's own view. Its sideways axis is level (from the
	// heading alone), so it holds steady even looking straight down.
	float a = atan(dl.z, dl.x);
	vec3 rx = vec3(-sin(a), 0.0, cos(a));
	vec3 ry = normalize(cross(dl, rx));
	vec3 p = (rx * VERTEX.x + ry * VERTEX.y) * 2.0 * radius;
	local_pos = p;
	view_dir = dl;
	vec3 world_pos = origin + m * (center + p);
	VERTEX = (VIEW_MATRIX * vec4(world_pos, 1.0)).xyz;
	mat3 nm = transpose(inv);
	n0 = nm[0];
	n1 = nm[1];
	n2 = nm[2];
	depth_axis = m * dl * radius;
	vec3 lw = lod_weights(origin, CAMERA_POSITION_WORLD);
	lod_in = lw.x;
	lod_out = lw.y;
	lod_seed = lw.z;
	if (lw.x <= 0.0 || lw.y <= 0.0) {
		VERTEX = vec3(0.0);
	}
	// Cloud shadow once per corner: a tree is far smaller than a cloud's shadow.
	cloud_shade = 1.0 - cloud_shadow(world_pos, cloud_time);
}

void fragment() {
	lod_dither(FRAGCOORD.xy);
	vec2 cells = vec2(float(azimuths), float(elevations));
	vec2 texels = vec2(textureSize(albedo_atlas, 0));
	// The level is capped (16 px a frame) so filtering stays inside the frame; one level
	// for all four, from the quad's own footprint.
	vec2 base = clamp(frame_uv(local_pos, view_dir, frame_dir(frames.x, frames.z), 0.0), 0.0, 1.0) / cells;
	float lod = clamp(log2(max(length(dFdx(base * texels)), length(dFdy(base * texels)))), 0.0, 4.0);
	vec4 c = vec4(0.0);
	vec4 nd = vec4(0.0);
	for (int j = 0; j < 2; j++) {
		for (int i = 0; i < 2; i++) {
			float ai = i == 0 ? frames.x : frames.y;
			float ei = j == 0 ? frames.z : frames.w;
			float w = (i == 0 ? 1.0 - blend.x : blend.x) * (j == 0 ? 1.0 - blend.y : blend.y);
			vec3 d = frame_dir(ai, ei);
			// One parallax step: where the view crosses this frame's plane, how far the
			// baked surface stands in front of it, and where the view meets it there, so
			// the frames' tiers line up before they're blended.
			vec2 local = frame_uv(local_pos, view_dir, d, 0.0);
			float h = textureLod(normal_atlas, (vec2(ai, ei) + clamp(local, 0.0, 1.0)) / cells, lod).a * 2.0 - 1.0;
			local = frame_uv(local_pos, view_dir, d, h * radius);
			// Off its own square, a frame shows nothing (rather than a neighbour's edge).
			float inside = step(0.0, local.x) * step(local.x, 1.0) * step(0.0, local.y) * step(local.y, 1.0);
			vec2 uv = (vec2(ai, ei) + clamp(local, 0.0, 1.0)) / cells;
			vec4 ci = textureLod(albedo_atlas, uv, lod);
			vec4 ni = textureLod(normal_atlas, uv, lod);
			float cw = w * ci.a * inside;
			c += vec4(ci.rgb * cw, w * ci.a * inside);
			nd += vec4((ni.rgb * 2.0 - 1.0) * cw, ni.a * cw);
		}
	}
	float cover = max(c.a, 1e-4);
	// Its coverage thins as it's averaged down: the cut-off eases with the level so a
	// far tree keeps its full outline.
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = mix(0.5, 0.3, lod / 4.0);
	ALBEDO = srgb_to_linear(c.rgb / cover * COLOR.rgb) * lod_gain;
	ROUGHNESS = 0.92;
	vec3 nl = nd.rgb / cover;
	vec3 nw = normalize(n0 * nl.x + n1 * nl.y + n2 * nl.z);
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
	float depth = nd.a / cover;
	LIGHT_VERTEX = VERTEX + (VIEW_MATRIX * vec4(depth_axis * (depth * 2.0 - 1.0), 0.0)).xyz;
}

void light() {
	float shade = 1.0;
	if (LIGHT_IS_DIRECTIONAL) {
		shade = cloud_shade;
	}
	DIFFUSE_LIGHT += clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION * LIGHT_COLOR / PI * shade;
}
