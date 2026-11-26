# Town layouts and roads: plan

Draft for Jon, 2026-11-25. This is a plan only, and nothing is built yet. It builds on the earlier technical road plan (`road-plan.md` in session local_c36d8e68's notes), whose steps 1–2 have since landed: graded road profiles, `RoadMesh` and the road shader. This plan covers the part that plan left open: **where** streets and buildings go so that a town reads as a real harbour town.

## What feels unrealistic now

From `MapGenerator._layout_towns` and `WorldBuilder._build_towns`:

1. **Every town is the same cross.** One straight road runs inland from the lot to a centre point (48–168 m in), with one straight cross street each side and maybe a short spur beyond. Every dock town has the same plus-sign plan.
2. **Houses sit on a 16.5 m grid**, rotated to the cross street, with grid rows left empty where the streets go. Buildings face grid directions, not the road, and lots far from any street are filled just as readily as frontage.
3. **The town turns its back on the water.** The centre sits inland of the ferry lot, and nothing runs *along* the shore. Real harbour towns are strung along a front street.
4. **No density gradient.** Shops and houses are spread by distance from one point (`sort_r`), so there is no tight core, no terraces, and no thinning out into the country.
5. **Sparse.** At 100 people per house (`TownGrowth.PEOPLE_PER_HOUSE`), a town of 3000 has about 30 buildings. Jon called towns "too sleepy".
6. **The terminal is a cul-de-sac.** The road to the lot is the only road. Nothing links the ferry to the rest of the island, to other docks' towns on the same island, or to the countryside.
7. **Dockless towns are a random grid on the highest ground**, with no roads at all.

## How real island and harbour towns are laid out

These are the patterns to copy (Puget Sound and San Juan towns, Maine and Nova Scotia harbours, Scottish and Norwegian island villages):

- **Front street.** One street runs along the shore just above high water, following the curve of the bay. Its sea side holds the working waterfront: sheds, fish docks, the chandlery, the ferry. Its land side holds the densest buildings: shops, a pub and a hotel, in continuous or near-continuous rows.
- **Lanes climbing from the water.** Short, steep streets run up from the front street, roughly perpendicular to the contours. They curve or zig-zag where the slope is steep, and houses step up them.
- **Upper street.** A second street, parallel to the front street, runs along the contour higher up and links the tops of the lanes. The result is a ladder or a loose irregular grid that bends with the shore.
- **The ferry landing is an anchor, not the centre.** The landing is at one end of the front street or just off it. The lot queue spills onto a short approach road. The main square often sits where the ferry road meets the front street.
- **A square or green at the meeting point**, with the landmark buildings: church, hall, store.
- **Organic, not grid.** Older cores are irregular, with streets following the shore and the contours. A small grid sometimes appears on flat ground behind the core in later growth. Kinks, T-junctions and dead-end lanes are normal. Four-way crossroads are rare.
- **A density gradient.** Terraces and shopfronts on the front street, then detached houses with gardens on the lanes, then scattered farms and houses on long lots along the island road.
- **The island road.** One road leaves town, follows the easiest ground across the island, and links every settlement and landing. Farms are strung along it. A second landing on the same island is reached by this road.

## The approach

A **harbour-town template** with a few parameters, run by the baked `TownPlan` from the earlier plan. It is not a general city generator. Each town is grown from a few roles:

| Role | How it is placed | Class / width |
|---|---|---|
| **Ferry approach** | Straight apron from the lot (existing), then turns into the front street within 40–80 m | main, 10 m |
| **Front street** | Follows a contour line 6–12 m above sea level along the shore either side of the landing, as far as land and slope allow (the town's "length") | main, 10 m |
| **Square** | At the approach/front-street junction, or the flattest pad within 60 m of it | plaza pad |
| **Climbing lanes** | Every 50–80 m off the front street, uphill; switchback once when the grade passes 12% | street 8 m, lane 6.5 m |
| **Upper street** | Joins the lane tops along a higher contour; the plan's ring | street, 8 m |
| **Back grid** (optional) | Only where flat ground lies behind the upper street: 2–4 short parallel streets | street, 8 m |
| **Island road** | From the end of the front street or the square, routed (A*, low slope) to the island's other towns and to a far point; carries a farm frontage | main, 10 m, rural shoulders |

Contour following is the key trick. Tracing a terrain iso-height gives the bendy, shore-hugging streets for free, and the lanes are just short climbs between two contours. Corners are smoothed with the spline from the earlier plan.

**Lots are frontage, not grid.** Walk each edge and drop lots on both sides at a width set by zone: 7–9 m terraces on the front street, 12–16 m on lanes and the upper street, 25–40 m farm lots on the island road. Each building faces its road and is set back by its zone. The sea side of the front street gets waterfront kinds (sheds, piers, boathouses) rather than houses.

**Density gradient = rank.** Lot rank (build order) is front street near the square first, then outward along the front street, then lanes bottom to top, then upper street, back grid, and finally island-road farms. As population rises, the town fills out from the square and along the shore, then climbs. That matches how these towns actually grew, and it means a small town looks like a real small village (a front street and a square) instead of a thin plus sign.

## Population-driven reveal

- The whole plan, roads and lots, is baked and graded at map generation (agreed). Unbuilt lots are level grass.
- `built lots = lots with rank < population / PEOPLE_PER_BUILDING`. Edges appear when their first lot does, so a road never leads nowhere for long. Only the approach, the square and the first stretch of front street exist at the start; everything else, the island road included, is revealed and its construction animated.
- **Density:** 75 people per building (decision A). Capacity comes from the land (see Capacity below).
- `TownGrowth` keeps deciding *when* to build. Instead of searching for a free lot, it takes the next lot by rank. `TownConstruction` animates it as now.
- Kinds come from the zone, with the town's leaning picking among variants (for example, a fishing town's waterfront lots become fish sheds, a resort's become boathouses and cafés).

## Docks, terminals and towns

Every locked dock is its own town, all baked up front (agreed):

- **Each dock town gets its own front street and square.** Two docks on one island give two villages.
- **The island road joins them.** It is routed between every pair of towns on an island (a minimum spanning tree, plus the nearest dockless town). Revealed in stretches as the towns grow (decision C). This is where future cross-island drivers (TID-319 stage 5) will drive.
- **Unbought docks:** the town is already there, at its starting population, served by the road. Buying the dock builds the terminal and its approach. It also has a small public dock and approach lane from the start (decision D).
- **Dockless islands** run the same template, centred where the island road meets the shore at the best cove, or at a crossroads inland if there is no cove. They have a smaller cap, lanes only and no sidewalks.

## Steps (ticket-sized, each one playable)

| # | Step | Size | What Jon sees |
|---|---|---|---|
| 1 | **Dev population slider** in Sandbox, plus a debug overlay of plan edges and lot ranks. | S | Can drag any town's size and watch the plan. Needed to tune everything below. |
| 2 | **TownPlan data and the front street.** `MapData.TownPlan` (edges with class and unlock rank, lots with rank, zone and kind). The ferry approach turns into a contour-following front street with a square at the junction. Grade the whole plan at generation. Replaces the plus sign. | M–L | Each dock town has a bending street along the shore and a square by the ferry. |
| 3 | **Frontage lots and ranked reveal.** Lots along the edges, facing the road, zoned widths; `_build_towns` places on lots instead of the grid; `TownGrowth` takes the next lot by rank; 75 people per building, capacity from the land fill. | M–L | Dense rows along the front street, filling out from the square as the slider moves. |
| 4 | **Climbing lanes and upper street**, with switchbacks on steep ground and the optional back grid. | M | Lanes up the hill, houses stepping up them, a loop that cars can use. |
| 5 | **Island road** between an island's towns and out to the farms, with rural lots. | M | Towns on one island are linked; farms along the road. |
| 6 | **Waterfront kinds and leaning.** Sea-side lots on the front street get sheds, piers and boathouses; leaning picks variants. | M (some art) | A fishing town and a resort look different along the water. |
| 7 | **Junctions and car paths** (earlier plan's step 5): fillets, crosswalks, cars using new streets and driving to built lots. | M–L | Rounded junctions, busy streets. |
| 8 | **Sidewalks, lamps per edge, LOD and an iPad performance pass** (earlier plan's steps 6 and 8). | M | Tidy streets; holds frame rate at the new density. |

Steps 1–3 are the core and go in order. Steps 4, 5 and 6 can run in parallel after 3. Step 7 follows 4. Step 8 runs last but needs an early iPad check after step 3, because density is the main performance risk.

Main risks: contour streets on awkward coastlines (cliffs, narrow spits), where the fallback is a short straight front street; grading conflicts between neighbouring towns' plans; and instance count on iPad.

## Decisions (Jon, 2026-11-25)

- **A. Density:** 75 people per building, residential and commercial alike (was 100 and 333). Starting towns stay modest; the density comes from growth, not the opening.
- **B. Plan size:** no fixed multiple. Each town grows as far as its land allows (see capacity below).
- **C. Reveal:** roads and buildings, the island road included, appear as the town grows, with construction animated. Only the approach, the square and the first stretch of front street exist at the start.
- **D. Docks:** every town gets a small public dock, and several dock-kit pieces along its waterfront (floats, gangways, fishing pier, marina), whether or not its ferry dock is bought.
- **E. Layout:** mix organic and grid, as real towns do: organic front street and lanes, a short grid on flat ground behind.
- **F. References:** Jon's set (Friday Harbor, Roche Harbor, La Conner, Port Townsend, Portsmouth NH, Bar Harbor, plus three concept images). See below.

## Capacity: how big a town can grow

At generation, before planning, measure each town's buildable land:

1. Flood-fill outward from the square over terrain cells (≈4 m) that are land, above the beach, under ~18% slope, not a lot, slip zone or landmark pad, and not already claimed by another town. Stop at a max radius (~400 m) or where another town's fill meets it (split at the midpoint).
2. Grow the road plan into that region only. Lots fill the frontage the roads reach.
3. Capacity = sum of lot sizes × 75 people. The town card can show it ("room for ~4,200") and research could reveal it, which fits "latent potential" in the GDD.

So a town on a broad gentle bay becomes a Bar Harbor; one on a cliffy point stays a Roche Harbor. The land decides, with no tuning per town.

## What the references add

All ten are achievable with this plan. Most of the look comes from layout and density; the rest is new kit pieces:

- **Buildings over the water.** Restaurants, sheds and shops on piles and a boardwalk along the front (Friday Harbor, La Conner, Port Townsend, Roche Harbor). Needs a *waterfront deck* lot type: a pile-supported pad built out from the front street, with pier-style buildings on it. New art, and the biggest win for the look.
- **Main street running down to the water** (Friday Harbor's Spring Street, Bar Harbor): the ferry approach can carry on straight up the hill as the main shopping street, with angle or parallel parking and shopfronts on both sides, before the front street branches off. Make this the default for a dock town whose approach meets the slope head-on.
- **Two- and three-storey commercial blocks** in brick and clapboard, close-packed with shared walls (Port Townsend, Bar Harbor). Needs a few terrace and block kit models; houses alone won't read as a town.
- **A landmark on the slope above the core:** a white church with a steeple, a hotel, a Victorian on the bluff. Reserve the best-viewed pad uphill of the square for it.
- **Trees mixed through the houses**, thicker uphill. Keep forest between lots on the lanes and clear it only in the core.
- **The island beyond:** farms, fields, a radio mast on the summit, an airstrip on flat ground, reached by the island road (concept 3). These are late growth stages on the island road.
- **Marina beside the ferry** with floats and masts (Friday Harbor, Bar Harbor). Part of D: a marina is one of the town's dock-kit pieces.

Steps update: step 3 uses 75 people per building and the capacity fill; step 6 becomes "waterfront decks, marina and public dock"; new step 9 is "commercial blocks and landmark art", which can run in parallel from the start.

## Art list for modelling

Grouped by the step that needs it, most valuable first. All pieces sit on flat pads; the generator handles grading. Sizes are footprints (frontage × depth). Two or three colour variants each through the existing wall/roof recolour tags.

**Core, needed for step 3 (dense front street)**

1. **Two-storey shopfront, narrow** (7 × 12 m), clapboard, false front, awning, big ground-floor windows (Bar Harbor, Friday Harbor). 3 variants.
2. **Three-storey brick commercial block** (10–14 × 16 m), cornice, arched upper windows, shopfronts at street level (Port Townsend). 2 variants, designed to sit wall-to-wall.
3. **Terrace / row house** (6 × 10 m), two storeys, shares side walls; reads as a continuous row when repeated.
4. **Corner building** (12 × 12 m), shopfront on two faces, for junctions and the square.
5. **Small café / restaurant with outdoor seating** (10 × 10 m) and separate umbrella/table clusters as props.

**Waterfront, step 6**

6. **Pile deck kit**: a deck module (10 × 10 m) on timber piles with railing edges, tileable along the shore, with stair and ramp pieces down to the beach.
7. **Over-water restaurant / shop** (14 × 14 m) for the deck, lots of glass, gabled roof (Roche Harbor, La Conner).
8. **Net shed / boathouse** (8 × 12 m), red or weathered shingle, big door to the water (Portsmouth NH).
9. **Fish dock warehouse** (16 × 24 m), long gable, roll-up doors, crates and pallets as props.
10. **Public float + gangway**: a float (4 × 20 m) and an aluminium truss gangway (2 × 18 m) that hinges at the deck; matches the dock kit.
11. **Marina finger piers** module (floats with 4–6 slips) plus 2–3 moored sailboat and runabout props.
12. **Waterfront boardwalk railing** in white picket and timber versions (Roche Harbor).

**Landmarks and town life, step 9**

13. **White clapboard church with steeple** (14 × 24 m, steeple ~25 m) — the town's silhouette from the water.
14. **Grand hotel** (30 × 14 m), three storeys, verandas (Hotel de Haro).
15. **Town hall / library with cupola** (16 × 16 m) for the square.
16. **Victorian house on the bluff** (14 × 14 m), turret, for the best uphill pad.
17. **Square kit**: paving pad, bandstand or gazebo, flagpole, benches, planters, a big shade tree.

**Streets, steps 7–8**

18. **Parked cars** along the main street (existing vehicles as static instances may do).
19. **Street furniture**: hanging-basket lamp posts, banner poles, benches, bins, bike rack, fire hydrant.
20. **Picket fence and garden hedge** strips for house lots.

**Island beyond, step 5**

21. **Farmhouse + barn + silo** set (Concept 3), field fence, hay bales.
22. **Airstrip** pad with two hangars and a windsock (the hangar exists; needs runway markings).
23. **Summit radio mast** (exists as `RADIO_TOWER`; check it reads at distance).

Already have: kit houses (5 families), 5 shop shells, the dock kit, lighthouse, keeper's house, hangar, windsock.

## Progress (2026-11-25)

- **Step 1 done:** F7 in Sandbox opens the town growth dev panel (`TownDevPanel`).
- **Step 2 first pass:** the square now sits just inland of the ticket plaza. Front streets follow the contour each way from it with a gentle wander. Lanes climb off the front street, and side streets branch off the main street. Lots line every street and face it, with back lots filling within 90 m of a street. Every lot the land gives is reserved, with no fixed caps, at 75 people per house and 250 per commercial building. On seed 123 most dock towns can now reach 8–14k people. Still to do: the winding main road for hemmed-in towns such as Bramble Bay, back lots facing their street, and a real `TownPlan` data type.
