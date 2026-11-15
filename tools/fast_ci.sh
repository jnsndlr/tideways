#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
engine=${GODOT_BIN:-godot}
log=$(mktemp)
trap 'rm -f "$log"' EXIT

check() {
  shift
  "$engine" --headless --path . "$@" 2>&1 | tee "$log"
  # Godot can still exit successfully after reporting a broken script or resource,
  # or after leaving objects behind at exit.
  awk '
    /^WARNING: [0-9]+ ObjectDB instances were leaked at exit/ { failed = 1 }
    /^[[:space:]]*(SCRIPT ERROR|ERROR):/ { failed = 1 }
    END { exit failed ? 1 : 0 }
  ' "$log"
}

check import --editor --import
check rules --script tools/fast_ferry_test.gd
check rules --script tools/fare_deck_test.gd
check menu --fixed-fps 30 --quit-after 30 res://scenes/menu.tscn
check hud --fixed-fps 30 --script tools/ferry_ui_test.gd
check launch --fixed-fps 30 --quit-after 120 res://scenes/sandbox.tscn -- --seed=123
check journey --fixed-fps 30 --script tools/vehicle_journey_test.gd -- --seed=123
check leaving-sandbox --fixed-fps 30 --script tools/scene_cycle_test.gd
