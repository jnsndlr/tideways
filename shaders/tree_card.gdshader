shader_type spatial;
render_mode cull_disabled, shadows_disabled, skip_vertex_transform, specular_disabled;

// Mainland pines (Backdrop): a quad turned about its upright to face the camera,
// showing the painted pine sprite. Two triangles each instead of a modelled tree.
// Lit by the scene (and shaded by passing clouds) like the terrain beside them,
// as a cone (see cone_up).
// The instance transform's X and Y scale are the card's width and height (quad
// from y = 0 to 1); COLOR is a per-tree tint.

#include "res://shaders/clouds.gdshaderinc"

#include "res://shaders/haze.gdshaderinc"

#include "res://shaders/lod_dither.gdshaderinc"

uniform sampler2D sprite : source_color, filter_linear_mipmap, repeat_disable;
// How bright the sprite reads against the modelled pines.
uniform float brightness = 0.75;
// Takes the sprite's yellow highlights toward the modelled pines' greens.
uniform vec3 grade : source_color = vec3(0.86, 0.95, 0.8);
// Lit like a cone (as a modelled pine is) rather than a flat face: how far its surface
// tilts up, and how much of the sunlit side the tiers above leave in their own shade.
uniform float cone_up = 0.5;
uniform float self_shade = 0.6;
// The sprite's highlights are near yellow; red is held to this share of green so
// they read lime, as the modelled pines' lit faces do.
uniform float yellow_cap = 0.65;
// Far off a modelled tree's light and dark facets blur into one muted colour; the
// painted sprite keeps its punch. Its colours are drawn this far towards the sprite's
// average (1: as painted), and their saturation scaled by this.
uniform float contrast = 1.0;
uniform float saturation = 1.0;
// How much of the sky's light a card keeps with the sun at the horizon (1: all).
// Through dawn and dusk a modelled pine's tiers shade most of it from the sky, and the
// card would otherwise glow green against them.
uniform float low_sun = 1.0;
// The same for the sun's own light: a low sun lights a modelled pine's facets
// glancingly, where the card faces it square on.
uniform float low_sun_direct = 1.0;
// The sprite's average opaque colour (Models.card_material).
uniform vec3 sprite_mean = vec3(0.5);
// Terrain.half_size (haze.gdshaderinc's edge_haze).
uniform float map_half = 3000.0;

varying vec3 world_pos;
varying vec3 tint;
varying vec3 card_right;
varying vec3 card_fwd;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	float w = length(MODEL_MATRIX[0].xyz);
	float h = length(MODEL_MATRIX[1].xyz);
	vec3 to_cam = CAMERA_POSITION_WORLD - origin;
	to_cam.y = 0.0;
	vec3 fwd = normalize(to_cam + vec3(1e-4, 0.0, 0.0));
	vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), fwd));
	world_pos = origin + right * VERTEX.x * w + vec3(0.0, VERTEX.y * h, 0.0);
	tint = COLOR.rgb;
	VERTEX = (VIEW_MATRIX * vec4(world_pos, 1.0)).xyz;
	vec3 lw = lod_weights(origin, CAMERA_POSITION_WORLD);
	lod_in = lw.x;
	lod_out = lw.y;
	lod_seed = lw.z;
	if (lw.x <= 0.0 || lw.y <= 0.0) {
		VERTEX = vec3(0.0);
	}
	card_right = right;
	card_fwd = fwd;
}

// The share of the sky's light the card keeps with the sun this high.
float sky_keep() {
	return mix(low_sun, 1.0, smoothstep(0.15, 0.9, normalize(sun_direction).y));
}

void fragment() {
	lod_dither(FRAGCOORD.xy);
	vec4 t = texture(sprite, UV);
	vec3 c = t.rgb;
	c.r = min(c.r, c.g * yellow_cap);
	if (contrast != 1.0 || saturation != 1.0) {
		vec3 avg = sprite_mean;
		avg.r = min(avg.r, avg.g * yellow_cap);
		c = mix(avg, c, contrast);
		c = mix(vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))), c, saturation);
	}
	// Sky light only reaches the albedo; light() gives the sun's back.
	ALBEDO = c * grade * tint * brightness * lod_gain * sky_keep();
	ALPHA = t.a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	ROUGHNESS = 1.0;
	// Across the card is around the cone: its middle faces the camera, its edges side on.
	float sx = clamp((UV.x - 0.5) * 2.0, -1.0, 1.0);
	vec3 around = card_right * sx + card_fwd * sqrt(1.0 - sx * sx);
	NORMAL = (VIEW_MATRIX * vec4(normalize(around + vec3(0.0, cone_up, 0.0)), 0.0)).xyz;
	FOG = edge_haze(world_pos, length(VERTEX), map_half);
}

void light() {
	float shade = 1.0;
	// The cloud deck thins out past 2700-4800 m (as in backdrop.gdshader).
	float r = length(world_pos.xz);
	if (LIGHT_IS_DIRECTIONAL && r < 4800.0) {
		shade = 1.0 - cloud_shadow(world_pos, TIME) * (1.0 - smoothstep(2700.0, 4800.0, r));
	}
	if (LIGHT_IS_DIRECTIONAL) {
		shade *= self_shade;
		// The albedo was dimmed for the sky (sky_keep); the sun has its own share.
		shade *= mix(low_sun_direct, 1.0, smoothstep(0.15, 0.95, normalize(sun_direction).y)) / sky_keep();
	}
	DIFFUSE_LIGHT += clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION * LIGHT_COLOR / PI * shade;
}
