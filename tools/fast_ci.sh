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
  awk -v phase="$phase" -v expected="$expected" -f tools/godot_result.awk "$log"
  echo "Passed $phase in $((SECONDS - start))s"
}

suite=${1:-fast}
if [[ $suite != fast && $suite != traffic ]]; then
  echo "Usage: bash tools/fast_ci.sh [fast|traffic]" >&2
  exit 2
fi

check import smoke --editor --import
if [[ $suite == traffic ]]; then
  check captain-crossings test --fixed-fps 30 --script tests/traffic/captain_crossing_test.gd -- --seed=123 --ferry=1 --rounds=1
  check road-traffic test --fixed-fps 30 --script tests/traffic/vehicle_overlap_test.gd -- --verify --seed=123 --frames=6000
  check shared-slip test --fixed-fps 30 --script tests/traffic/shared_slip_test.gd -- --scenario=shared_slip
  check same-route-pass test --fixed-fps 30 --script tests/traffic/same_route_pass_test.gd -- --scenario=shared_slip
  check manual-move test --fixed-fps 30 --script tests/traffic/manual_move_test.gd -- --scenario=tie_up_pier
  check tie-up-reposition test --fixed-fps 30 --script tests/traffic/tie_up_reposition_test.gd -- --scenario=tie_up_pier
  check tie-up test --fixed-fps 30 --script tests/traffic/tie_up_test.gd -- --scenario=shared_slip
  check gap-tie-up test --fixed-fps 30 --script tests/traffic/gap_tie_up_test.gd -- --scenario=shared_slip
  check lot-lanes test --fixed-fps 30 --script tests/traffic/lot_lanes_test.gd
  check lane-sharing test --fixed-fps 30 --script tests/traffic/lane_sharing_test.gd -- --scenario=lane_sharing
  check schedule-edit test --fixed-fps 30 --script tests/traffic/schedule_edit_test.gd
  check timetable test --fixed-fps 30 --script tests/traffic/timetable_test.gd
  check daily-cost test --fixed-fps 30 --script tests/traffic/daily_cost_test.gd
  check dock-sites test --fixed-fps 30 --script tests/traffic/dock_site_test.gd
  check fleet-purchase test --fixed-fps 30 --script tests/traffic/fleet_purchase_test.gd
  check slip-conflict test --fixed-fps 30 --script tests/traffic/slip_conflict_test.gd -- --scenario=two_boats
  check tie-up-refit test --fixed-fps 30 --script tests/traffic/tie_up_refit_test.gd -- --scenario=shared_slip
  check slip-refit test --fixed-fps 30 --script tests/traffic/slip_refit_test.gd -- --scenario=opening
  check slip-purchase test --fixed-fps 30 --script tests/traffic/slip_purchase_test.gd -- --scenario=shared_slip
  check flex-slip test --fixed-fps 30 --script tests/traffic/flex_slip_test.gd -- --scenario=shared_slip
  check dredge-slip test --fixed-fps 30 --script tests/traffic/dredge_slip_test.gd -- --scenario=opening
  check marine-traffic test --fixed-fps 30 --script tests/traffic/vessel_soak_test.gd -- --verify --seed=123 --frames=20000
  exit 0
fi
check session-launch-options test --script tests/session/session_launch_options_test.gd
check persistence test --script tests/session/persistence_test.gd
check ferry-assignment test --script tests/simulation/fast_ferry_test.gd
check region-voyage test --script tests/world/art_free_region_test.gd
check terminal-refit test --script tests/rules/terminal_refit_test.gd
check dock-site-restore test --script tests/session/dock_site_snapshot_test.gd
check refit-restore test --script tests/session/terminal_refit_snapshot_test.gd
check purchased-berth-restore test --script tests/session/terminal_berth_purchase_snapshot_test.gd
check slip-completion test --script tests/simulation/slip_completion_test.gd
check ferry-lay-up test --script tests/rules/ferry_lay_up_test.gd
check ferry-voyage test --script tests/rules/ferry_voyage_test.gd
check ferry-waterline test --script tests/world/ferry_waterline_test.gd
check authored-ferry-nets test --script tests/world/ferry_net_model_test.gd
check classic-ferry-nets test --script tests/world/ferry_net_model_test.gd -- --classic-net
check authored-slip-model test --script tests/world/slip_model_test.gd
check classic-slip-model test --script tests/world/slip_model_test.gd -- --classic-slip
check ferry-view test --script tests/world/ferry_view_test.gd
check ferry-walk-on-restore test --script tests/session/ferry_walk_on_snapshot_test.gd
check fare-and-deck test --script tests/simulation/fare_deck_test.gd
check company-ledger-snapshot test --script tests/rules/company_ledger_snapshot_test.gd
check vehicle-spawn test --script tests/simulation/vehicle_spawn_test.gd
check simulation-rules test --script tests/simulation/simulation_rules_test.gd
check motor-yacht-anchor test --script tests/world/motor_yacht_anchor_test.gd
check vessel-hull test --script tests/world/vessel_hull_view_test.gd
check classic-vessel-hull test --script tests/world/vessel_hull_view_test.gd -- --classic-cargo
check authored-pilot test --script tests/world/pilot_boat_model_test.gd
check classic-pilot test --script tests/world/pilot_boat_model_test.gd -- --classic-pilot
check authored-tug test --script tests/world/tug_model_test.gd
check classic-tug test --script tests/world/tug_model_test.gd -- --classic-tug
check vessel-night-lights test --script tests/world/vessel_night_lights_test.gd
check trawler-gear test --script tests/world/trawler_gear_test.gd
check classic-trawler-gear test --script tests/world/trawler_gear_test.gd -- --classic-trawler
check sailboat-rig test --script tests/world/sailboat_rig_test.gd
check classic-sailboat-rig test --script tests/world/sailboat_rig_test.gd -- --classic-sailboat
check ferry-itinerary test --script tests/rules/ferry_itinerary_test.gd
check timetable-round test --script tests/rules/timetable_round_test.gd
check mission-goals test --script tests/simulation/mission_goals_test.gd
check land-distance-field test --script tests/world/land_distance_field_test.gd
check route-sample-grid test --script tests/world/route_sample_grid_test.gd
check route-memo test --script tests/world/route_memo_test.gd
check region-contract test --script tests/world/region_contract_test.gd
check road-grade test --script tests/world/road_grade_test.gd
check terminal-holding-restore test --script tests/session/terminal_holding_snapshot_test.gd
check terminal-walking-queue-restore test --script tests/session/terminal_walking_queue_snapshot_test.gd
check unloading-restore test --script tests/session/ferry_unloading_snapshot_test.gd
check crossing-restore test --script tests/session/ferry_crossing_snapshot_test.gd
check company-network test --script tests/session/company_network_test.gd
check company-restore test --script tests/session/company_snapshot_test.gd
check outbound-traffic-restore test --script tests/session/outbound_traffic_snapshot_test.gd
check tiny-region test --fixed-fps 30 --script tests/world/tiny_region_test.gd
check town-growth test --fixed-fps 30 --script tests/simulation/town_growth_test.gd
check coastal-town test --script tests/world/coastal_town_test.gd
check authored-tree-model test --script tests/world/tree_model_test.gd
check classic-tree-model test --script tests/world/tree_model_test.gd -- --classic-trees
check forest-proximity test --script tests/world/forest_proximity_test.gd
check schedule-slip-size test --script tests/simulation/schedule_slip_size_test.gd
check eagle-departure test --script tests/world/eagle_departure_test.gd
check shared-forecourt test --script tests/simulation/shared_forecourt_test.gd
check refit-crane test --script tests/world/refit_crane_test.gd
check model-parts test --script tests/world/model_parts_test.gd
check authored-whales test --script tests/world/whale_model_test.gd
check classic-whales test --script tests/world/whale_model_test.gd -- --classic-whales
check porpoise-models test --script tests/world/porpoise_model_test.gd
check authored-pinnipeds test --script tests/world/pinniped_model_test.gd
check classic-pinnipeds test --script tests/world/pinniped_model_test.gd -- --classic-seals
check authored-orca test --script tests/world/orca_model_test.gd
check classic-orca test --script tests/world/orca_model_test.gd -- --classic-orca
check authored-gull test --script tests/world/seagull_model_test.gd
check classic-gull test --script tests/world/seagull_model_test.gd -- --classic-gull
check trailer-paint test --script tests/world/trailer_paint_test.gd
check tie-up-pier test --script tests/world/tie_up_pier_test.gd
check trestle-profile test --script tests/world/trestle_profile_test.gd
check slip-guide-mesh test --script tests/world/slip_guide_mesh_test.gd
check lane-redistribution test --script tests/simulation/lane_redistribution_test.gd -- --scenario=lane_sharing
check terminal-inspector test --script tests/ui/terminal_inspector_test.gd
check opening-scenario test --script tests/session/opening_scenario_test.gd
check full-network-opening test --script tests/session/opening_scenario_test.gd -- --full-network
check region-load-recovery test --fixed-fps 30 --script tests/session/region_load_recovery_test.gd
check fleet-purchase-ui test --fixed-fps 30 --script tests/ui/fleet_purchase_ui_test.gd
check quick-save-ui test --fixed-fps 30 --script tests/ui/quick_save_ui_test.gd
check opening-economy-ui test --fixed-fps 30 --script tests/ui/opening_economy_ui_test.gd
check menu smoke --fixed-fps 30 --quit-after 30 res://scenes/menu.tscn
check hud test --fixed-fps 30 --script tests/ui/ferry_ui_test.gd
check touch-edit test --fixed-fps 30 --script tests/ui/touch_edit_test.gd
check sandbox smoke --fixed-fps 30 --quit-after 120 res://scenes/sandbox.tscn -- --seed=123
check holding-lane test --fixed-fps 30 --script tests/simulation/holding_lane_test.gd -- --seed=123
check wake-bounds test --script tests/world/wake_bounds_test.gd
check frame-budget test --fixed-fps 30 --script tests/world/frame_budget_test.gd -- --seed=123
check vehicle-journey test --fixed-fps 30 --script tests/simulation/vehicle_journey_test.gd -- --seed=123
check simulation-shutdown test --fixed-fps 30 --script tests/session/simulation_shutdown_test.gd
check marine-shutdown test --fixed-fps 30 --script tests/session/marine_shutdown_test.gd
check backdrop-shutdown test --fixed-fps 30 --script tests/session/backdrop_shutdown_test.gd
check world-build-shutdown test --fixed-fps 30 --script tests/session/world_build_shutdown_test.gd
check generation-shutdown test --fixed-fps 30 --script tests/session/generation_shutdown_test.gd
check leaving-sandbox test --fixed-fps 30 --script tests/session/scene_cycle_test.gd
