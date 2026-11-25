shader_type spatial;
// Walk-on passengers: the model's own vertex colours, with up to five labelled
// parts swapped per passenger. The labels come from art/person_recolor.py:
// UV2.x is the part (0 fixed, 1 skin, 2 hair, 3 top, 4 bottom, 5 accent) and
// 1 - UV2.y (the glTF export flips V) is that corner's brightness against the
// part's main colour, so shades and highlights carry over. A colour with alpha 0 keeps the authored colour.

instance uniform vec4 skin_col = vec4(0.0);
instance uniform vec4 hair_col = vec4(0.0);
instance uniform vec4 top_col = vec4(0.0);
instance uniform vec4 bottom_col = vec4(0.0);
instance uniform vec4 accent_col = vec4(0.0);

void fragment() {
	vec3 c = COLOR.rgb;
	int part = int(UV2.x + 0.5);
	vec4 swap = vec4(0.0);
	if (part == 1) swap = skin_col;
	else if (part == 2) swap = hair_col;
	else if (part == 3) swap = top_col;
	else if (part == 4) swap = bottom_col;
	else if (part == 5) swap = accent_col;
	if (swap.a > 0.5) {
		c = clamp(swap.rgb * (1.0 - UV2.y), 0.0, 1.0);
	}
	ALBEDO = c;
	ROUGHNESS = 0.88;
	METALLIC = 0.0;
}
