# How the running game fits together

Start in [Sandbox](../scripts/sandbox.gd). It generates the region, builds the world, wires up the simulation, camera and HUD, and owns their scene lifetime. The authored map has its own entry point. Treat a result seen in Sandbox as evidence for that scene until it also runs in the authored region.

| System | Owner and dependency direction | Where changes belong |
| --- | --- | --- |
| Region and terrain | MapGenerator produces MapData with islands, slips, routes and harbours. Terrain supplies heights. WorldBuilder consumes geography for meshes. Simulation consumes it for traffic. | An authored region should supply the same facts to both clients. A change to an island mesh alone cannot add terminal service. |
| Clock, demand and money | Simulation owns time and composes the live actors. TrafficDemand computes arrival intensity from population and hour. Terminal consumes the rate. FareLedger owns credits and daily rollover. | Change the rule once and let inspectors read the result. VehicleFactory assembles the scene model. Simulation attaches each vehicle to its world and owns that world’s moving-vehicle registry. Boats, clouds and birds consume the same simulation wind direction. |
| Queues and boarding | Terminal owns typed holding lanes, including approaching vehicles’ reserved space, and the approach paths. Ferry chooses the loading, sailing and unloading phase. FerryDeck owns space reservations for that crossing. Vehicle drives its path and reports arrival. | Put fit and reservation rules in FerryDeck. Keep animation and dispatch timing on the actors. Terminal queue slots and ferry deck slots are separate capacities. |
| Marine navigation | NavGrid finds navigable water. NavPath samples a route by distance. Helm steers individual boats. MarineTraffic arbitrates shared corridors, berths and harbour entry. | A vessel can request access. The shared traffic owner decides who holds it. Test release, cancellation or competing arrivals when changing that decision. |
| Wildlife and scenery | Wildlife owns visits, photo eligibility and island reputation. World actors draw and animate animals. ModelParts reads Blender mesh groups; Models composes their game-facing meshes. DayCycle, WakeField and NightLights take simulation and scene inputs to update presentation. | Change sighting or photo credit at the visit owner. Check a visual change from a player camera. An art file can stay large while its contents serve one job. |
| Input, panels and camera | CameraRig owns the view. FleetPanel displays the list and emits the selected ferry. Hud owns active selection, asks the rig to follow a target and reads simulated state for labels. Scenes handles transitions and time-scale reset. | Add a panel in its own file when it starts managing a distinct interaction. Keep one active selection and one source for the value displayed. |
| Persistence and platforms | Sandbox currently creates a fresh simulation. Local company save/resume is tracked in [TID-239](https://linear.app/tideways/issue/TID-239). Export, signing and distribution live at the application boundary. | Proposed save data includes durable company, schedule, progress and simulation facts identified by stable IDs. Rebuild meshes and scene references on load. Choose schema and migration cases with the save slice. |

## Two changes traced through the design

**A captain changes crossing behavior.** The [captain PR](https://github.com/jnsndlr/Tideways/pull/14) provides a concrete example. A player selects a ferry and chooses a named captain. The ferry applies the assignment to sailing; the panel explains the resulting tradeoff. Compare the same route under each captain, including when the effect starts. A future save should retain the assignment. Check whether that PR has landed before depending on its types.

**A player changes a timetable.** Today the Sandbox ferry shuttles on its assigned route and decides locally when to cast off. The proposed editor in [TID-23](https://linear.app/tideways/issue/TID-23) needs a schedule owned by the simulation. The editor submits stop and time choices, the schedule validates them, and the ferry consumes the accepted departure. The inspector and cost preview can then read that same plan. Test invalid stop order and a complete edited sailing. Confirm which schedule modes ship through [TID-241](https://linear.app/tideways/issue/TID-241) before committing to an editor design.

## Refactoring while the game grows

Start with the behavior that has to survive the change. Protect it with the smallest meaningful check, then move the state and the decisions that change it together. A second copy of a rule, a dependency on an unrelated scene, or two authors repeatedly colliding in a file are good reasons to split code. Keep the next change small enough to compare before and after. Use the [coverage map](verification.md) to choose that comparison.

## Boundaries to watch

- The departure board queries the live fleet for ferries serving that terminal; equal times retain fleet order. Shared-route navigation is still separate work. The generated map creates one ferry per route, and MarineTraffic computes crossing conflicts from one hull on each of two distinct routes. Test two hull sizes, approaches to the same slip and opposing traffic before enabling shared-route service.
- MarineTraffic still combines spawn coordination, reservations and collision assessment. Protect the contested resource before moving one of those responsibilities. The regression for a removed harbour holder is an example. Splitting all vessels at once would make a change in traffic behavior harder to locate.
- Hud still owns several panels and the minimap. FleetPanel demonstrates the direction for another panel when its responsibilities start to interfere with selection or camera code. Keep the screen-coordinate UI flow green across the supported layouts.


## Identity at the authored-region and save boundary

The generator assigns each island and route its array position as an integer ID. Slips refer to route IDs; route endpoints, marinas and wildlife sites refer to island IDs. The runtime reads those arrays directly. The region contract check verifies generated data and rejects a reordered runtime array or dangling slip. Keep the dense arrays for live simulation.

Generated islands receive a key when created. A terminal shares its island’s key; the order of its slips remains significant. Each generated route has a key and two island endpoints, and each hull has a fleet key independent of its name and assignment. A generated network save records these facts under its region seed. Loading resolves the keys against a freshly generated map and rejects missing, duplicate or mismatched records before creating any simulation children.

The [company network test](../tools/company_network_test.gd) writes a live fleet to a temporary JSON file, reverses its records, reindexes regenerated routes and restores two distinct hulls assigned to one crossing. This proves the identity slice of [TID-257](https://linear.app/tideways/issue/TID-257). A complete company save, authored-region keys and migration of changed regions remain separate work.
