class_name TerminalUpgrade
extends RefCounted
## One entry in a terminal's purchase catalogue (stage 5): what it is, what it
## costs, how long it takes to build, and why it can't be bought now, if it can't.
## Terminal.upgrades() lists them and Terminal.buy() buys one, so every purchase
## at a terminal takes the same path for price, requirement and build time.

enum Kind { LANE, SLIP, TIE_UP, REFIT, TIE_UP_REFIT }

var kind := Kind.LANE
var title := ""
var price := 0
## Game minutes from purchase until it is in use (the work itself; a refit or new
## slip waits for its slip to clear first, a lane for its staging lanes).
var build_minutes := 0.0
## Why it can't be bought now ("" if it can). Lack of cash is not a reason here:
## the HUD shows that against the price.
var blocked := ""
## The research project it needs (stage 8), "" for none. Simulation.has_research()
## answers whether it is done; until research exists nothing needs any.
var research := ""
## The slip it works on (a refit), -1 otherwise.
var slip := -1
## Where a new slip goes (its lateral offset in the terminal frame).
var v := NAN
## The seabed to dredge there first (cubic metres) and what that adds to `price`.
var dredge_m3 := 0.0
var dredge_price := 0


func _init(k: Kind, t: String, p: int, minutes: float) -> void:
	kind = k
	title = t
	price = p
	build_minutes = minutes


## What it says under the price: how long it takes, or what stops it.
func detail() -> String:
	if blocked != "":
		return blocked
	var h := build_minutes / 60.0
	var time := "%d min" % roundi(build_minutes) if h < 2.0 else ("%d h" % roundi(h) if is_equal_approx(h, roundf(h)) else "%.1f h" % h)
	return "Builds in " + time + (" · includes %s of dredging" % _money(dredge_price) if dredge_price > 0 else "")


static func _money(n: int) -> String:
	var s := str(n)
	var out := ""
	while s.length() > 3:
		out = "," + s.right(3) + out
		s = s.left(s.length() - 3)
	return "$" + s + out
