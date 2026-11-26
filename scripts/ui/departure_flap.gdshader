shader_type canvas_item;
render_mode unshaded;

// The three surveyed rails follow the hinge in the original illustration.
uniform vec4 top_rail;
uniform vec4 axle;
uniform vec4 bottom_rail;
uniform sampler2D blank_plate : source_color, filter_linear, repeat_disable;
uniform sampler2D painted_type : source_color, filter_linear, repeat_disable;
uniform sampler2D live_type : source_color, filter_linear, repeat_disable;
uniform bool printed = true;
uniform bool has_type = true;
uniform bool title_row = false;
uniform bool has_hinge = true;
uniform int cell_count = 10;
uniform float elapsed = 2.0;
uniform float row_delay = 0.0;
const vec2 PLATE = vec2(1448.0, 1086.0);
const vec2 INK_ORIGIN = vec2(80.0);
const vec2 INK_SIZE = vec2(720.0, 696.0);
const float TITLE_EDGES[9] = {100.0,196.0,289.0,380.0,467.0,548.0,624.0,703.0,772.0};

vec2 rail(vec4 ends, float x) {
	return mix(ends.xy, ends.zw, x);
}

vec2 art_pixel(vec2 uv) {
	vec2 hinge = rail(axle, uv.x);
	if (uv.y < 0.5) {
		return mix(rail(top_rail, uv.x), hinge, 2.0 * uv.y);
	}
	return mix(hinge, rail(bottom_rail, uv.x), 2.0 * uv.y - 1.0);
}

vec4 final_face(vec2 uv) {
	vec2 p = art_pixel(uv);
	if (printed) {
		return texture(painted_type, (p - INK_ORIGIN) / INK_SIZE);
	}
	vec4 base = texture(blank_plate, p / PLATE);
	if (has_type) {
		vec4 ink = texture(live_type, uv);
		// The narrow mechanical split interrupts ink on both halves.
		float gap = smoothstep(0.002, 0.012, abs(uv.y - 0.5));
		base.rgb = mix(base.rgb, ink.rgb, ink.a * (has_hinge ? mix(0.2, 1.0, gap) : 1.0));
	}
	return base;
}

vec4 moving_face(vec2 uv, int cell, float across, int step_index, int steps) {
	if (step_index >= steps) { return final_face(uv); }
	vec2 p = art_pixel(uv);
	vec4 base = texture(blank_plate, p / PLATE);
	if (step_index < 0) { return base; }
	// Borrow the painted title's glyphs, preserving their ink wear as cards turn.
	int glyph = (cell * 3 + step_index + 1) % 8;
	float gx = mix(TITLE_EDGES[glyph], TITLE_EDGES[glyph + 1], across);
	float tx = (gx - 100.0) / 672.0;
	float gy = uv.y < 0.5
		? mix(mix(110.0,162.0,tx), mix(185.0,229.0,tx), uv.y*2.0)
		: mix(mix(185.0,229.0,tx), mix(261.0,291.0,tx), uv.y*2.0-1.0);
	vec3 ink = texture(painted_type, (vec2(gx,gy) - INK_ORIGIN) / INK_SIZE).rgb;
	float mask = smoothstep(0.43, 0.78, ink.r);
	base.rgb = mix(base.rgb, ink, mask);
	return base;
}

void fragment() {
	vec2 uv = UV;
	vec2 p = art_pixel(uv);
	int cell = min(int(uv.x * float(cell_count)), cell_count - 1);
	float across = fract(uv.x * float(cell_count));
	if (title_row) {
		for (int i = 0; i < 8; i++) {
			if (p.x <= TITLE_EDGES[i+1]) {
				cell = i;
				across = clamp((p.x-TITLE_EDGES[i]) / (TITLE_EDGES[i+1]-TITLE_EDGES[i]),0.0,1.0);
				break;
			}
		}
	}
	int steps = 2 + (cell % 3);
	float turns = (elapsed - row_delay - float(cell)*0.034) / 0.138;
	if (turns >= float(steps+1)) {
		COLOR = final_face(uv);
	} else if (turns < 0.0) {
		COLOR = texture(blank_plate, p / PLATE);
	} else {
		int next = int(floor(turns));
		float angle = fract(turns) * PI;
		float projection = cos(angle);
		float y = 2.0 * uv.y - 1.0;
		vec4 face = moving_face(uv,cell,across,y < 0.0 ? next : next-1,steps);
		// Old upper leaf falls towards the axle; its reverse opens onto the lower half.
		if ((projection > 0.001 && y <= 0.0 && y >= -projection)
			|| (projection < -0.001 && y >= 0.0 && y <= -projection)) {
			vec2 projected = vec2(uv.x, (1.0 + y / abs(projection)) * 0.5);
			face = moving_face(projected,cell,across,projection > 0.0 ? next-1 : next,steps);
			face.rgb *= mix(0.49,1.0,abs(projection));
		}
		float edge = smoothstep(0.008,0.035,min(across,1.0-across));
		face.rgb = mix(texture(blank_plate,p / PLATE).rgb,face.rgb,edge);
		COLOR = face;
	}
}
