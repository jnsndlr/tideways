shader_type spatial;
render_mode cull_back;

// lit_vc for the town roads: asphalt, markings, shoulders and wet weather
// (road_detail.gdshaderinc), on RoadMesh strips.
#define ROAD
#include "res://shaders/lit_vc.gdshaderinc"
