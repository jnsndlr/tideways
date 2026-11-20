shader_type spatial;
render_mode cull_back;

// lit_vc.gdshader for a modelled tree's level of detail, dithering into the next
// (lod_dither.gdshaderinc, Models.dither_lod).
#define TREE_LOD
#include "res://shaders/lit_vc.gdshaderinc"
