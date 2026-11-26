shader_type canvas_item;

uniform sampler2D glass : filter_linear, repeat_disable;
uniform vec2 view_origin;
uniform vec2 view_size = vec2(1.0);
uniform sampler2D gull_atlas : source_color, filter_linear, repeat_disable;
uniform vec2 gull_anchor;
uniform float gull_size = 0.0;
uniform float gull_facing = 1.0;
uniform vec3 gull_frames;

vec4 gull_pose(vec2 local, float frame) {
	vec2 cell = vec2(mod(frame, 4.0), floor(frame / 4.0));
	return texture(gull_atlas, (cell + local) / 4.0);
}

void fragment() {
	vec2 camera_uv = view_origin + UV * view_size;
	COLOR = texture(TEXTURE, camera_uv);
	if (gull_size > 0.0) {
		vec2 local = (camera_uv * vec2(1280.0, 720.0) - gull_anchor) / gull_size;
		local = local * vec2(gull_facing, 1.0) + vec2(0.5, 0.75);
		if (all(greaterThanEqual(local, vec2(0.0))) && all(lessThan(local, vec2(1.0)))) {
			vec4 a = gull_pose(local, gull_frames.x);
			vec4 b = gull_pose(local, gull_frames.y);
			COLOR.rgb = mix(mix(COLOR.rgb, a.rgb, a.a), mix(COLOR.rgb, b.rgb, b.a), gull_frames.z);
		}
	}
	COLOR.a *= texture(glass, UV).r;
}
