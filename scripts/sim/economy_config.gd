class_name EconomyConfig
extends RefCounted
## Reads optional numeric rates without coercing strings or accepting nonfinite prices.


static func nonnegative_rate(settings: Variant, key: String, fallback: float) -> float:
	if not settings is Dictionary:
		return fallback
	var value: Variant = settings.get(key)
	if (value is float or value is int) and is_finite(value) and value >= 0:
		return float(value)
	return fallback
