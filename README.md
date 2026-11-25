# Tideways

The shared development and release repository for Tideways, a regional development game in **Godot 4.7**. The Sandbox procedurally
generates an archipelago with towns, terminals and routes. Cars drive from town to
the holding lots, queue in lanes, board double-ended ferries, cross, and drive off
at the other side.

Open the folder in Godot 4.7 and press **Play** (F5). On the title screen, **Play** starts the opening company on the authored main map. **Sandbox** generates a region from a seed. Godot imports the project assets on first open.

## Working on Tideways

- For Jon and Paul, start with the [short team handoff](docs/jon-handoff.md). Agents can use the [detailed handoff](docs/claude-gameplay-handoff.md).
- Start a gameplay change with the [design index](https://linear.app/tideways/document/tideways-design-index-first-public-ipad-release-1e6bbe392246) and [game design document](docs/tideways-gdd.md). The affected Linear ticket records current decisions.
- Use the [team workflow](docs/workflow.md) for branch handoff, verification and merge.
- Use the [architecture guide](docs/architecture.md), [verification map](docs/verification.md), system map below and the [engineering queue](https://linear.app/tideways/project/engineering-foundations-e97de6837467) when changing shared code.
- Follow the [CI and TestFlight guide](docs/delivery.md) to validate a PR or deliver a build.

## Controls

| Action | Mouse / trackpad | Keys |
|---|---|---|
| Pan | Left-drag, two-finger swipe | WASD / arrows |
| Rotate / tilt | Right- or middle-drag | Q E / R F |
| Zoom (toward cursor) | Wheel, pinch | Z X or + − |
| Select island / vessel | Click (or click an island label) | Tab = next ferry, Esc = deselect |
| Time | Speed buttons in the top bar | Space = pause, 1–3 = speed |
| New random map | | G |
| Back to menu | | M (sandbox), Esc (main map) |

Selecting a ferry, sailboat or cargo ship follows it with the camera. Selecting an
island shows its stats and the terminal status bar (queue, next departure, weather,
wind, tide).

## Architecture

| Follow this path | Start here |
| --- | --- |
| Choose a region and start a session | The [menu](scripts/ui/main_menu.gd) opens the [loading screen](scripts/ui/loading_screen.gd). [Main Map](scripts/main_map.gd) supplies an authored layout and scenario. [Sandbox](scripts/sandbox.gd) supplies a seed. Both use [WorldSession](scripts/world_session.gd) for startup and teardown. |
| Change region data or terrain | [MapGenerator](scripts/map/map_generator.gd) produces [MapData](scripts/map/map_data.gd) from a seed or layout. [WorldBuilder](scripts/world/world_builder.gd) builds the scene from that geography. |
| Change a rule or transaction | [Simulation](scripts/sim/simulation.gd) coordinates the live session. [CompanyLedger](scripts/sim/company_ledger.gd) records spending and receipts. [FleetMarket](scripts/sim/fleet_market.gd) validates purchases and sales. [FerryVoyage](scripts/sim/ferry_voyage.gd), [FerryDeck](scripts/sim/ferry_deck.gd) and [TerminalLane](scripts/sim/terminal_lane.gd) own crossing, deck and queue state. |
| Change what the player sees or controls | [HUD](scripts/ui/hud.gd) connects panels to the simulation and camera. [VehicleFactory](scripts/world/vehicle_factory.gd) and [Models](scripts/world/models.gd) assemble visible vehicles. Editable art lives in [art](art/) and game-ready assets in [assets](assets/). |
| Check a change | The [verification map](docs/verification.md) covers rule tests, seeded scenarios, UI and device checks. |

For current dependencies, the target boundaries and a worked Fleet purchase, see the [architecture guide](docs/architecture.md). The [decision record](docs/architecture-decisions.md) covers company resume, source art and legacy model flags.

## Traffic afloat

Most inhabited islands get a small marina (a pier with a T-head and four berths).
Sailboats lie there for a few game hours, then back out and sail to a free berth
elsewhere, or out and back home, in daylight only. Container ships pass through
from one map edge to another every hour or so. Both plan routes on coarse water
grids (`NavGrid`) that keep clear of land, terminals and piers, cost extra on
ferry lanes, and keep to the right so opposing traffic passes.

No two hulls ever touch. Each hull is a capsule, and every frame `MarineTraffic`
checks each moving vessel's hull at a run of poses along its path ahead against
every other hull, and against the path ahead of any higher-ranked vessel (ferries
outrank cargo ships, which outrank sailboats). The answer is a distance the vessel
may still go, and it brakes to stop within it. Where two ferry routes run too close
to pass (`Corridor`), one ferry at a time reserves the stretch; one boat at a time
backs out of or noses into a marina; a sailboat stuck nose to nose re-plans round
the other vessel.

## Wildlife

`Wildlife` rolls each species once a game day. A visiting group arrives from offshore,
circles one island (picked by `Island.wildlife_appeal`, scaled by
`Wildlife.island_attraction` for future research and policies), and leaves when the
visit is over. Orcas come every day as a pod of 2–8 for 3 game hours. The other
species (humpback, gray whale, sea lion, porpoises, harbor seal) are in the table
with their draw, but stay disabled until they have their own behaviour and models.

A visit counts as a sighting for an island only in daylight, and only if the group
comes within 150 m of that island's ferry dock or 110 m of a sailing ferry. A ferry
sighting credits both ends of its route. Each credited island's wildlife reputation
jumps by the species' draw (orca 3.0 … harbor seal 0.08), then halves every 6 days
down to a floor of 40% of the season's best, which clears when the season turns
(30 days). Clicking a surfaced animal once per visit adds a 50% photo bonus. Open
**WILDLIFE** in the sidebar for recent sightings and the islands with the most draw.

## Debug / screenshot flags

```bash
/Applications/Godot.app/Contents/MacOS/Godot --path . -- --seed=42 --select=1 --speed=2 --shot=out.png --shot-delay=10
```

Available flags: `--seed=N`, `--speed=0..3`, `--cam=x,z,dist,yaw,pitch`, `--select=K`,
`--follow=K`, `--time=H`, `--shot=path.png`, `--shot-delay=s`, `--bench=s`, `--orcas`
(start an orca visit now and follow it).

`--bench=s` prints average frame time, GPU time, draw calls and primitives over `s`
seconds and quits. Metal doesn't report GPU time, so profile with Vulkan:

```bash
/Applications/Godot.app/Contents/MacOS/Godot --path . --rendering-driver vulkan -- --seed=42 --bench=6
```

## Quick PR validation

Draft PRs skip the **Godot fast check**. Mark a PR targeting main ready for review
to run it. New commits rerun the check and cancel an older run for the same PR.
The Linux job imports the project with Godot 4.7.2, tests demand-based ferry
assignment and starts the normal game on seed 123 for 120 frames. Run the same
checks locally with `bash tools/fast_ci.sh` and Godot on PATH, or set `GODOT_BIN`.
Use the running game for visual review and the relevant longer diagnostics for
changes to traffic. An iPad playtest covers touch, rendering and device performance.
The sandbox scene reports one retained resource and up to 31 leaked objects
at shutdown on this seed. The launch check tolerates that recorded baseline;
additional leaks and other Godot errors fail the job.

## Physical iPad playtest

Use Godot 4.7.2 with the matching iOS export template and Xcode. In the
**iPad Playtest** export preset, set your Apple development team locally.
Export the release Xcode project to a folder outside this checkout, then
development-sign and run it on the connected iPad. The app installs as
**Ferry Tycoon (preview)** with a separate identifier from the Tideways3D build.

For a comparable generated-map sample, pass `-- --seed=123` to Godot.
Record device model, commit, camera and sample duration alongside measurements.
