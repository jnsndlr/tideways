#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
engine=${GODOT_BIN:-godot}
log=$(mktemp)
trap 'rm -f "$log"' EXIT

check() {
  local phase=$1 expected=$2 start=$SECONDS
  shift 2
  echo "Running $phase"
  "$engine" --headless --path . "$@" 2>&1 | tee "$log"
  # Godot can exit zero after a script error or before an asynchronous test finishes.
  awk -v phase="$phase" -v expected="$expected" '
    { gsub(/\033\[[0-9;]*m/, ""); sub(/\r$/, "") }
    /^TEST PASSED$/ { completed = 1 }
    /^[[:space:]]*WARNING: .*ObjectDB instances .*leaked at exit/ { failed = 1 }
    /^[[:space:]]*(SCRIPT ERROR|ERROR):/ { failed = 1 }
    END {
      if (expected == "test" && !completed) {
        print phase " ended without a test pass marker." > "/dev/stderr"
        failed = 1
      }
      exit failed ? 1 : 0
    }
  ' "$log"
  echo "Passed $phase in $((SECONDS - start))s"
}

suite=${1:-fast}
if [[ $suite != fast && $suite != traffic ]]; then
  echo "Usage: bash tools/fast_ci.sh [fast|traffic]" >&2
  exit 2
fi

check import smoke --editor --import
if [[ $suite == traffic ]]; then
  check captain-crossings test --fixed-fps 30 --script tools/captain_crossing_test.gd -- --seed=123 --ferry=1 --rounds=1
  check road-traffic test --fixed-fps 30 --script tools/vehicle_overlap_test.gd -- --verify --seed=123 --frames=6000
  check shared-slip test --fixed-fps 30 --script tools/shared_slip_test.gd -- --scenario=shared_slip
  check tie-up test --fixed-fps 30 --script tools/tie_up_test.gd -- --scenario=shared_slip
  check lot-lanes test --fixed-fps 30 --script tools/lot_lanes_test.gd
  check lane-sharing test --fixed-fps 30 --script tools/lane_sharing_test.gd -- --scenario=lane_sharing
  check schedule-edit test --fixed-fps 30 --script tools/schedule_edit_test.gd
  check slip-refit test --fixed-fps 30 --script tools/slip_refit_test.gd -- --scenario=opening
  check marine-traffic test --fixed-fps 30 --script tools/vessel_soak_test.gd -- --verify --seed=123 --frames=20000
  exit 0
fi
check ferry-assignment test --script tools/fast_ferry_test.gd
check ferry-voyage test --script tools/ferry_voyage_test.gd
check fare-and-deck test --script tools/fare_deck_test.gd
check vehicle-spawn test --script tools/vehicle_spawn_test.gd
check simulation-rules test --script tools/simulation_rules_test.gd
check region-contract test --script tools/region_contract_test.gd
check company-network test --script tools/company_network_test.gd
check tiny-region test --fixed-fps 30 --script tools/tiny_region_test.gd
check model-parts test --script tools/model_parts_test.gd
check menu smoke --fixed-fps 30 --quit-after 30 res://scenes/menu.tscn
check hud test --fixed-fps 30 --script tools/ferry_ui_test.gd
check sandbox smoke --fixed-fps 30 --quit-after 120 res://scenes/sandbox.tscn -- --seed=123
check holding-lane test --fixed-fps 30 --script tools/holding_lane_test.gd -- --seed=123
check wake-bounds test --script tools/wake_bounds_test.gd
check frame-budget test --fixed-fps 30 --script tools/frame_budget_test.gd -- --seed=123
check vehicle-journey test --fixed-fps 30 --script tools/vehicle_journey_test.gd -- --seed=123
check leaving-sandbox test --fixed-fps 30 --script tools/scene_cycle_test.gd
