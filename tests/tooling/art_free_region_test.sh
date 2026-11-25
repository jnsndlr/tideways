#!/usr/bin/env bash
# Run production GDScript in a fresh project with no imported assets or game autoloads.
set -euo pipefail
cd "$(dirname "$0")/../.."
engine=${GODOT_BIN:-godot}
project=$(mktemp -d)
trap 'rm -rf "$project"' EXIT
mkdir -p "$project/scripts/map" "$project/scripts/sim"
cp scripts/map/*.gd "$project/scripts/map/"
cp scripts/saved_text.gd scripts/units.gd "$project/scripts/"
cp scripts/sim/{economy_config,ferry_class,ferry_deck,ferry_operating_costs,ferry_voyage,ferry_waterline_profiles,hull_waterline,slip_guides,slip_ramp,vessel_spec,vessel_types,wake_trail}.gd "$project/scripts/sim/"
cp tests/world/art_free_region_test.gd "$project/"
echo 'config_version=5' > "$project/project.godot"

# Build only the global script class cache for this project. Godot can report
# compilation errors without setting a failing exit code.
log="$project/engine.log"
"$engine" --headless --path "$project" --editor --import 2>&1 | tee "$log"
awk -v phase=art-free-import -v expected=smoke -f tools/godot_result.awk "$log"
"$engine" --headless --path "$project" --quit-after 5 --script res://art_free_region_test.gd 2>&1 | tee "$log"
awk -v phase=art-free-region -v expected=test -f tools/godot_result.awk "$log"
