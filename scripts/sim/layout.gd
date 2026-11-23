class_name Layout
extends RefCounted
## Shared dimensions for terminals, ferries and vehicles. Units are metres.
##
## Terminal-local frame: origin where the pier meets the shore, +Z ("u") points out to
## sea along the pier, +X ("v") is lateral. The holding lot sits at negative u.

const LOT_Y := 3.15             # top surface of lot, piers and ferry car deck
const LOT_FRONT := -6.0         # seaward edge of the holding lot
const LOT_LENGTH := 72.0
const LOT_BACK := LOT_FRONT - LOT_LENGTH  # road entrance edge
const PIER_END := 30.0          # end of the pier / transfer span
const LANE_HEAD := -15.0         # first queue slot in each lane
const LANE_WIDTH := 7.2
const EXIT_CLEAR := 8.7         # lanes keep clear of the central exit lane
const EXIT_V := 2.4             # lateral position of the exit lane
# Ticket-plaza model origin, vehicle centres and extent of its tapered approach.
const TICKET_U := LOT_BACK - 6.0
const TICKET_LANES := [-14.4, -8.4, -EXIT_V]
const TICKET_FAN_LENGTH := 30.0
const SLOT := 7.8               # spacing between queued cars
# Far enough apart that ferries at neighbouring slips, lying alongside or
# coming and going straight in and out, never come near each other.
const SLIP_SPACING := 60.0
const FERRY_HALF := 45.0
const DOCK_U := PIER_END + FERRY_HALF + 0.4  # centre of a 90 m hull docked (route ends)
const CHANNEL_BUOY_U := PIER_END + 138.0     # each slip's pair of channel buoys
# Each slip's wing walls (u, v of the starboard one's ends, mirrored to port): one
# straight wall either side, splayed WING_ANGLE off the centreline, that takes
# any size of hull's end.
const WING_ANGLE := deg_to_rad(38.0)
const WING_LENGTH := 24.0
const WING_WALL := [Vector2(PIER_END + 0.9, 9.0),
	Vector2(PIER_END + 0.9 + WING_LENGTH * cos(WING_ANGLE), 9.0 + WING_LENGTH * sin(WING_ANGLE))]
# Guide dolphins either side of each slip (u, v off the centreline, cluster
# radius): an inner pair the longer hulls lie against, and a lit outer pair that
# lines ferries up coming in.
const DOLPHIN_INNER := Vector3(PIER_END + 51.0, 17.7, 3.15)
const DOLPHIN_OUTER := Vector3(PIER_END + 87.0, 20.7, 4.05)
# The modelled dolphins (SlipGuides) stand where each slip's size puts them (the
# widest hull it takes, as FerryClass sizes go): the inner pair in along her sides
# (slip_inner_u), and funnelled out to sea, so that hull,
# swung LIE_SWING about her landed end, lies against the inner and outer dolphins on
# that side at once. Coming in she meets the wing walls first. SLIP_FACE_MAX is about
# the widest outer face (an Issaquah's); DOLPHIN_DEPTH how far a dolphin reaches behind
# its face.
const LIE_SWING := deg_to_rad(2.0)
const INNER_REACH := 0.55
const SLIP_FACE_MAX := 20.7
const DOLPHIN_DEPTH := 5.8


## Where along the slip (u) a slip of `size`'s inner dolphins stand: INNER_REACH of the
## way down its widest hull from her landed end, where her sides run full, but never
## further out than DOLPHIN_INNER (the big boats' slips).
static func slip_inner_u(size: int) -> float:
	var fc := FerryClass.of(size)
	var end_u := SlipRamp.dock_end(fc.half_length - fc.net_z - 0.35)
	return minf(DOLPHIN_INNER.x, end_u + INNER_REACH * 2.0 * fc.half_length)


## Lateral offset of the fender face of a slip of `size`'s dolphin at `u` along it: on
## the side of its widest hull, landed and swung LIE_SWING about her landed end (past
## her far end, on the line her side makes). A slip takes every boat from the one
## after the next slip size down's largest up to `size`, so the face clears the
## widest of them there (the medium slip's Issaquah stands wider than its Evergreen).
static func slip_face_v(size: int, u: float) -> float:
	var smallest := 1
	for largest: int in MapData.Slip.LARGEST_BOAT:
		if largest < size:
			smallest = maxi(smallest, largest + 1)
	var v := -INF
	for s in range(smallest, size + 1):
		v = maxf(v, _hull_face_v(s, u))
	return v


static func _hull_face_v(size: int, u: float) -> float:
	var fc := FerryClass.of(size)
	var arm := u - SlipRamp.dock_end(fc.half_length - fc.net_z - 0.35)
	var hw := fc.half_width_at(-fc.half_length + arm)
	if hw <= 0.0:
		hw = fc.half_beam
	return hw * cos(LIE_SWING) + arm * sin(LIE_SWING)
const DECK_Y := LOT_Y

# Marina frame, like a terminal's: origin where the pier meets the shore, +Z ("u")
# out along the pier. The pier ends in a T-head; sailboats lie bow-in against its
# seaward face, side by side, and back straight out to MARINA_BACKOUT_U to leave.
const MARINA_PIER_END := 48.0
const MARINA_HEAD_U := 51.0        # centre of the T-head float
const MARINA_HEAD_HALF := 21.6      # its half length along v
const MARINA_BERTHS := 4
const MARINA_BERTH_SPACING := 9.0
const MARINA_BERTH_U := 61.8       # moored hull centre (bow just off the float)
const MARINA_BACKOUT_U := 87.0     # where a departing boat stops reversing
const MARINA_APPROACH_U := 99.0    # where an arriving boat lines up for its berth


# Fish quay frame, like a marina's. A jetty runs out to a wharf along v whose
# seaward face (at QUAY_FACE_U) the boats lie alongside, bow to stern, pointing
# the quay's `side` along v. They come and go along the lane QUAY_LANE_U out,
# running QUAY_RUN either side of the wharf, crabbing between it and the berth.
const QUAY_JETTY_END := 21.0
const QUAY_FACE_U := 39.0
const QUAY_HALF := 72.0            # the wharf's half length along v
const QUAY_BERTHS := 2
const QUAY_BERTH_SPACING := 69.0
const QUAY_FENDER := 1.5           # between the face and a hull lying alongside
const QUAY_LANE_U := 90.0
const QUAY_RUN := 180.0
# A pilot station is laid out like a fish quay, with a berth more for its
# shorter boats.
const STATION_BERTHS := 3
const STATION_BERTH_SPACING := 48.0


## Lateral lane positions grouped per slip (left → right), clear of the exit lane.
## Every lane position on a lot, in the order they are paved: out from the middle,
## the extension side (-v) first.
static func lane_opening_order(half_width: float) -> Array[float]:
	var all: Array[float] = []
	for chunk in lane_positions(half_width, 1):
		for v in chunk:
			all.append(v)
	all.sort_custom(func(a, b): return absf(a) < absf(b) or (absf(a) == absf(b) and a < b))
	return all


## The first `count` lanes paved on a lot (all of them when `count` is 0), left to right.
static func open_lanes(half_width: float, count: int) -> Array[float]:
	var order := lane_opening_order(half_width)
	var out := order.slice(0, count) if count > 0 else order
	out.sort()
	return out


static func lane_positions(half_width: float, slip_count: int) -> Array[PackedFloat32Array]:
	var all: Array[float] = []
	var v := EXIT_CLEAR
	while v <= half_width - 3.9:
		all.append(v)
		all.append(-v)
		v += LANE_WIDTH
	all.sort()
	var result: Array[PackedFloat32Array] = []
	var per := floori(float(all.size()) / maxi(slip_count, 1))
	for s in slip_count:
		var chunk := PackedFloat32Array()
		for k in per:
			chunk.append(all[s * per + k])
		result.append(chunk)
	return result


static func slots_per_lane() -> int:
	return int((LANE_HEAD - (LOT_BACK + 10.5)) / SLOT) + 1


## Fraction of the full ticket-lane spread at this distance inland from the lot.
static func ticket_spread(inland: float, road_length: float) -> float:
	return 1.0 - smoothstep(10.0, minf(TICKET_FAN_LENGTH, maxf(road_length, 11.0)), inland)
