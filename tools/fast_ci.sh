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
    /^[[:space:]]*WARNING: .*ObjectDB instances? .*leaked at exit/ { failed = 1 }
    # This test deliberately loads a scene whose external dependency is missing.
    phase == "region-load-recovery" {
      if ($0 ~ /^ERROR: Cannot open file \047user:\/\/region_part_[0-9]+\.tscn\047\.$/ ||
          $0 ~ /^ERROR: Failed loading resource: user:\/\/region_(part|retry)_[0-9]+\.tscn\.$/ ||
          $0 ~ /^ERROR: user:\/\/region_retry_[0-9]+\.tscn:3 - Parse Error: \[ext_resource\] referenced non-existent resource at: user:\/\/region_part_[0-9]+\.tscn\.$/) next
    }
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
  check same-route-pass test --fixed-fps 30 --script tools/same_route_pass_test.gd -- --scenario=shared_slip
  check tie-up test --fixed-fps 30 --script tools/tie_up_test.gd -- --scenario=shared_slip
  check gap-tie-up test --fixed-fps 30 --script tools/gap_tie_up_test.gd -- --scenario=shared_slip
  check lot-lanes test --fixed-fps 30 --script tools/lot_lanes_test.gd
  check lane-sharing test --fixed-fps 30 --script tools/lane_sharing_test.gd -- --scenario=lane_sharing
  check schedule-edit test --fixed-fps 30 --script tools/schedule_edit_test.gd
  check timetable test --fixed-fps 30 --script tools/timetable_test.gd
  check daily-cost test --fixed-fps 30 --script tools/daily_cost_test.gd
  check dock-sites test --fixed-fps 30 --script tools/dock_site_test.gd
  check slip-conflict test --fixed-fps 30 --script tools/slip_conflict_test.gd -- --scenario=two_boats
  check tie-up-refit test --fixed-fps 30 --script tools/tie_up_refit_test.gd -- --scenario=shared_slip
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
check forest-proximity test --script tools/forest_proximity_test.gd
check schedule-slip-size test --script tools/schedule_slip_size_test.gd
check eagle-departure test --script tools/eagle_departure_test.gd
check shared-forecourt test --script tools/shared_forecourt_test.gd
check refit-crane test --script tools/refit_crane_test.gd
check model-parts test --script tools/model_parts_test.gd
check slip-guide-mesh test --script tools/slip_guide_mesh_test.gd
check lane-redistribution test --script tools/lane_redistribution_test.gd -- --scenario=lane_sharing
check opening-scenario test --script tools/opening_scenario_test.gd
check full-network-opening test --script tools/opening_scenario_test.gd -- --full-network
check region-load-recovery test --fixed-fps 30 --script tools/region_load_recovery_test.gd
check opening-economy-ui test --fixed-fps 30 --script tools/opening_economy_ui_test.gd
check menu smoke --fixed-fps 30 --quit-after 30 res://scenes/menu.tscn
check hud test --fixed-fps 30 --script tools/ferry_ui_test.gd
check touch-edit test --fixed-fps 30 --script tools/touch_edit_test.gd
check sandbox smoke --fixed-fps 30 --quit-after 120 res://scenes/sandbox.tscn -- --seed=123
check holding-lane test --fixed-fps 30 --script tools/holding_lane_test.gd -- --seed=123
check wake-bounds test --script tools/wake_bounds_test.gd
check frame-budget test --fixed-fps 30 --script tools/frame_budget_test.gd -- --seed=123
check vehicle-journey test --fixed-fps 30 --script tools/vehicle_journey_test.gd -- --seed=123
check simulation-shutdown test --fixed-fps 30 --script tools/simulation_shutdown_test.gd
check marine-shutdown test --fixed-fps 30 --script tools/marine_shutdown_test.gd
check backdrop-shutdown test --fixed-fps 30 --script tools/backdrop_shutdown_test.gd
check world-build-shutdown test --fixed-fps 30 --script tools/world_build_shutdown_test.gd
check generation-shutdown test --fixed-fps 30 --script tools/generation_shutdown_test.gd
check leaving-sandbox test --fixed-fps 30 --script tools/scene_cycle_test.gd
