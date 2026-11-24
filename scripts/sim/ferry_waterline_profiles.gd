class_name FerryWaterlineProfiles
extends RefCounted
## Measured outlines for the five authored, double-ended ferry hulls, in model metres.
## Each row holds the half-length followed by half-widths from the tip to midships.
## tools/ferry_waterline_measurement.gd measures the same stations on the imported hulls.

const MEASUREMENTS := {
	1: [  # Guemes
		18.9, 1.5572711, 5.10725, 6.3374953, 7.0551744, 7.4792047, 7.7460127,
		7.879208, 7.916228, 7.93, 7.93, 7.93, 7.93,
	],
	2: [  # Hiyu
		26.65, 0.7184095, 3.585145, 5.089246, 6.3123317, 7.365076, 8.213497,
		8.801897, 9.217291, 9.514421, 9.696212, 9.76, 9.76,
	],
	3: [  # Evergreen State
		47.25, 1.0579722, 6.929214, 8.804688, 9.923925, 10.595273, 10.979636,
		11.132742, 11.15, 11.15, 11.15, 11.15, 11.15,
	],
	4: [  # Issaquah
		55.95, 1.089706, 8.43464, 10.561675, 11.62826, 12.097333, 12.2,
		12.2, 12.2, 12.2, 12.2, 12.2, 12.2,
	],
	5: [  # Jumbo Mk II
		79.1, 0.15954137, 6.8873496, 9.936512, 12.336467, 13.893743, 14.834968,
		15.347179, 15.471648, 15.471648, 15.471648, 15.471648, 15.471648,
	],
}


static func profile(size: int, half_length: float) -> PackedFloat32Array:
	var row := PackedFloat32Array(MEASUREMENTS[size])
	var half := row[0] * FerryHullDimensions.MID_SCALE
	var result := PackedFloat32Array([half_length - half, 2.0 * half])
	for i in HullWaterline.STATIONS:
		var station := mini(i, HullWaterline.STATIONS - 1 - i)
		result.append(row[1 + station] * FerryHullDimensions.MID_SCALE)
	return result
