shader_type spatial;
render_mode cull_disabled, skip_vertex_transform;

// The 300-triangle pine past Models.IMPOSTOR_DIST: a quad showing the model as baked
// (tools/bake_impostor.gd) from the heading and height nearest the camera's, lit
// texel by texel with the model's own colours and normals as lit_vc.gdshaderinc lights
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

varying vec3 world_pos;
varying vec2 frame_uv;
varying flat vec2 frame;
// The model's frame to the world's, for normals (inverse transpose).
varying flat vec3 n0;
varying flat vec3 n1;
varying flat vec3 n2;
// The baked view direction in the world, one radius long (depth's unit).
varying flat vec3 depth_axis;
varying float cloud_shade;

vec3 srgb_to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

void vertex() {
	mat3 m = mat3(MODEL_MATRIX[0].xyz, MODEL_MATRIX[1].xyz, MODEL_MATRIX[2].xyz)
		* mat3(vec3(variant_scale.x, 0.0, 0.0), vec3(0.0, variant_scale.y, 0.0), vec3(0.0, 0.0, variant_scale.z));
	vec3 origin = MODEL_MATRIX[3].xyz;
	vec3 c_world = origin + m * center;
	mat3 inv = inverse(m);
	// The camera's direction in the model's frame, snapped to the nearest baked frame.
	vec3 dl = normalize(inv * (CAMERA_POSITION_WORLD - c_world));
	float az = atan(dl.z, dl.x);
	float el = degrees(asin(clamp(dl.y, -1.0, 1.0)));
	float ai = mod(round(az / TAU * float(azimuths)), float(azimuths));
	float ei = clamp(round(el / elevation_step), 0.0, float(elevations - 1));
	float a = ai * TAU / float(azimuths);
	float e = radians(ei * elevation_step);
	vec3 d = vec3(cos(e) * cos(a), sin(e), cos(e) * sin(a));
	vec3 rx = normalize(cross(vec3(0.0, 1.0, 0.0), d));
	vec3 ry = cross(d, rx);
	// The quad across that frame's view, framed as the bake framed it.
	vec3 p = center + (rx * VERTEX.x + ry * VERTEX.y) * 2.0 * radius;
	world_pos = origin + m * p;
	VERTEX = (VIEW_MATRIX * vec4(world_pos, 1.0)).xyz;
	frame = vec2(ai, ei);
	frame_uv = vec2(dot(p - center, rx), -dot(p - center, ry)) / (2.0 * radius) + 0.5;
	mat3 nm = transpose(inv);
	n0 = nm[0];
	n1 = nm[1];
	n2 = nm[2];
	depth_axis = m * d * radius;
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
	// The level is capped (16 px a frame) so filtering stays inside the frame.
	vec2 local = clamp(frame_uv, 0.0, 1.0);
	vec2 uv = (frame + local) / cells;
	vec2 texels = vec2(textureSize(albedo_atlas, 0));
	float lod = clamp(log2(max(length(dFdx(uv * texels)), length(dFdy(uv * texels)))), 0.0, 4.0);
	vec4 c = textureLod(albedo_atlas, uv, lod);
	vec4 nd = textureLod(normal_atlas, uv, lod);
	// Its coverage thins as it's averaged down: the cut-off eases with the level so a
	// far tree keeps its full outline.
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = mix(0.5, 0.3, lod / 4.0);
	ALBEDO = srgb_to_linear(c.rgb * COLOR.rgb) * lod_gain;
	ROUGHNESS = 0.92;
	vec3 nl = nd.rgb * 2.0 - 1.0;
	vec3 nw = normalize(n0 * nl.x + n1 * nl.y + n2 * nl.z);
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
	LIGHT_VERTEX = VERTEX + (VIEW_MATRIX * vec4(depth_axis * (nd.a * 2.0 - 1.0), 0.0)).xyz;
}

void light() {
	float shade = 1.0;
	if (LIGHT_IS_DIRECTIONAL) {
		shade = cloud_shade;
	}
	DIFFUSE_LIGHT += clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION * LIGHT_COLOR / PI * shade;
}
