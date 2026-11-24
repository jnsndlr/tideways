class_name RegionPlan
extends RefCounted
## Snapshot of the terminal facilities and scheduled links used to build a region.
## A null plan lets the generator choose the network.

var terminals: Array[String] = []
var slips := {}
var tie_ups := {}
var lanes := {}
var links: Array[PackedStringArray] = []


## The slip sizes for the terminal at `key`: one small slip unless listed.
func slip_sizes(key: String) -> Array[int]:
	var sizes: Array[int] = [1]
	sizes.assign(slips.get(key, sizes))
	return sizes
