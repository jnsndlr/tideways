shader_type canvas_item;

uniform sampler2D glass : filter_linear, repeat_disable;
uniform vec2 view_origin;
uniform vec2 view_size = vec2(1.0);

void fragment() {
	COLOR = texture(TEXTURE, view_origin + UV * view_size);
	COLOR.a *= texture(glass, UV).r;
}
