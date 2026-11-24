class_name FerryHullDimensions
extends RefCounted
## Hull dimensions in game metres shared by route planning and ferry construction.

const MID_SCALE := Units.VEHICLE_MODEL_SCALE
const JUMBO_STRETCH := 1.128
# The Jumbo Mk II sets the fleet envelope in both modelled and classic mode.
const MAX_HALF_LENGTH := 70.13 * JUMBO_STRETCH * MID_SCALE
const MAX_HALF_BEAM := 13.716 * JUMBO_STRETCH * MID_SCALE
