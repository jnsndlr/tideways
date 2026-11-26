shader_type canvas_item;

uniform sampler2D glass : filter_linear, repeat_disable;

void fragment() {
	COLOR.a *= texture(glass, UV).r;
}
