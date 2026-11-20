shader_type spatial;
render_mode cull_back;

// lit_vc with shared, smooth-normal vertices: `facet` brings back flat triangles.
#define TERRAIN
#include "res://shaders/lit_vc.gdshaderinc"
