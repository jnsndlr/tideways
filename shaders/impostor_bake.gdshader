shader_type spatial;
render_mode unshaded, cull_back;

// tools/bake_impostor.gd: a tree drawn unlit for its impostor, one property per pass.
// The viewport turns what's drawn from linear to sRGB on the way out, so each value is
// handed over in linear to come out as itself.
// mode 0: the vertex colour, as lit_vc.gdshaderinc reads it (before its sRGB decode).
// mode 1: the surface's normal in the model's frame, 0.5 + n / 2.
// mode 2: how far the surface stands towards the camera from the plane through `center`,
//         0.5 + d / (2 radius).

uniform int mode = 0;
uniform vec3 view_dir = vec3(0.0, 0.0, 1.0);
uniform vec3 center = vec3(0.0);
uniform float radius = 1.0;

varying vec3 local_pos;
varying vec3 local_n;

vec3 srgb_to_linear(vec3 c) {
	return mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92, lessThan(c, vec3(0.04045)));
}

void vertex() {
	local_pos = VERTEX;
	local_n = NORMAL;
}

void fragment() {
	vec3 v;
	if (mode == 0) {
		v = COLOR.rgb;
	} else if (mode == 1) {
		v = normalize(local_n) * 0.5 + 0.5;
	} else {
		v = vec3(clamp(dot(local_pos - center, view_dir) / radius * 0.5 + 0.5, 0.0, 1.0));
	}
	ALBEDO = srgb_to_linear(v);
}
