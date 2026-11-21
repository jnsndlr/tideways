# Tideways

## Game Design Document (v0.5, 2026-11-18)

**Changed in v0.5 (Jon, 2026-11-18):** the opening state, slip sizes and tie-up slips, automatic lane sharing, the fuel model, weekly town growth, what gates expansion, and the [game loop build stages](#game-loop-build-stages). Where v0.5 text differs from older text further down, such as the Phase 1 lists, v0.5 wins.

**Added 2026-11-19 (Jon):** how running costs reach the ledger, the per-boat pace setting and how routing shows it, crew staffing levels with loading inefficiencies, and per-crew experience.

**Reading this design today.** This is the October design baseline. Use the [Linear design index](https://linear.app/tideways/document/tideways-design-index-first-public-ipad-release-1e6bbe392246) for current public iPad release scope and the issues that own later changes. In particular, captain and crew management are included in the public release. The earlier Phase 1 list below describes the first-playable milestone. The opening timetable modes, economy, first expansion and presentation choices are tracked together in [TID-241](https://linear.app/tideways/issue/TID-241).

Built from GDD v0.3 in the Tideways prototype repo, the systems on the "Ferry game" FigJam board, and the October 2026 design review.

**How to read this document**

- This GDD is the master design. Anything not marked otherwise is decided.
- **Default** marks a suggestion that was not explicitly confirmed. It stands until someone changes it.
- All numbers are starting points for tuning unless a rule says otherwise.
- The TypeScript prototype is a reference, not a spec. Its scheduling and terminal ideas are useful, but its numbers are not canonical. Real cars in real lanes and real space on boats, as in [Jon's Tideways Godot project](https://github.com/jnsndlr/tideways), are what matter.

---

## High Concept

Tideways is a cozy but deep ferry management sim for computer and iPad, inspired by Washington State Ferries, SimAirport, Mini Metro, RollerCoaster Tycoon, Port Royale and Lemonade Tycoon.

The player builds a region and a ferry fleet together. They start with two small terminals and one basic boat, and grow a network that changes the islands it serves. Logistics is the main activity, with direct building for terminals, moorings and upgrades.

The player could be a private company or a public agency. It doesn't matter. Their job is to serve the region and thrive.

---

## Design Pillars

**Meaningful logistics.** Every decision ripples through the simulation. A new sailing can raise revenue, raise fuel costs, cut waits, tire crews and help a town grow. The game rewards thoughtful optimization, not perfect execution.

**Real things in the world.** Each vehicle is a real trip, and each lane and deck space is physical. Problems are visible in the world: a long queue, a blocked slip, a driver giving up and turning around.

**Human management.** Transportation is about people. Pay, staffing, fatigue and captains all affect how well the network runs.

**Organic community growth.** Players don't build towns directly. They create the conditions for towns to grow, and each town shows who it has been served by.

**Calm strategy.** No combat and no twitch mechanics. The challenge comes from balancing connected systems and watching the network evolve.

**Regular progress.** Building and upgrading are part of the fun, so there should always be something worth buying soon.

---

## Core Loop

1. See what a town needs.
2. Buy, build or research something that helps.
3. Assign boats and set schedules, fares and staffing.
4. Carry vehicles and collect revenue.
5. Pay for fuel, crew and upkeep.
6. Watch towns respond with more demand, new buildings and new needs.
7. Expand to the next dock, boat or island.

The core feedback loop is: community growth, travel demand, revenue, fleet and terminal expansion, better service, more community growth.

---

## Game Structure

- **Start:** $50,000, one size 2 ferry (the Hiyu model) and three terminals with one small slip each: Port Rosario, Madrona Island and Gullrock Island. Nothing is connected until a schedule connects it. The game opens with an example schedule between Port Rosario and Madrona. Other islands are present but not built out. Other opening scenarios can come later.
- **Any map:** every system works on an authored or a generated region. An opening scenario is data (terminals, boats, cash and example schedule) that either kind of map can supply.
- **What gates expansion:** money alone gates a new terminal. Research gates upgrades and improvements. Milestones stay recognition. A later idea is a milestone that attracts talent able to sail to harder islands.
- **Length:** open-ended. A full region should take 20–30 hours.
- **Direction:** milestones give sessions purpose, such as serving every island or growing a town to a given size. They are recognition, not gates.
- **Failure:** bankruptcy is the only loss, and the route to it is generous (see Finance).
- **Test scene:** the current tech demo stays as a hidden scene that developers can switch to inside Godot. Players never see it.

### Time

- 1 real second is 1 game minute at 1x.
- A game day is 24 minutes at 1x, 8 at 3x and 3 at 8x.
- A season lasts about 7 days, so a game year is 28 days.
- 3x is normal play, 1x is for watching, and 8x is for skipping ahead. Test builds should also run at about 20x.

At 3x, a year takes about 3.7 hours, so a full region spans about 6–8 game years.

### Pacing Targets

| Reward | Target at 3x | In game time | Over 25 hours |
|---|---|---|---|
| Something new | Every 3 minutes | About 9 hours | About 500 |
| Bigger purchase | Every 5–10 minutes | About 15–30 hours | About 150–300 |
| Visible change | Every 10 minutes | About 30 hours | About 150 |

Each week triggers town growth, based on the previous week's service level and improvements (see Towns). **Default:** the growth a town earns appears as small steps spread across the following week, so visible changes keep to the target above.

With 10 towns, 150 visible changes means about 14 per town. Towns need small steps, such as a new house, shop or dock shed, with larger authored stages as milestones. Terminal construction also counts as a visible change.

---

## The Region

- One curated map with fictional names. Random generation remains for testing.
- One mainland edge and 10 islands, with one town per island to start.
- Each island has 2–3 authored terminal sites, so the map has about 20–30 sites.
- Water is divided into authored zones. Passages can have their own events and delays.
- Unconnected islands show small settlements with no travel until they are connected.
- Later, players can place a terminal along a shoreline to change a route's length.
- This map size is a planning target that must be confirmed on an M1 iPad.

---

## Terminals

Developing a terminal site costs money. After that, terminals upgrade one purchase at a time.

| Track | Rule |
|---|---|
| Lanes | Start at 3 on a small terminal, then add one at a time. About 10 is a large terminal. |
| Slips | Up to 3 per terminal, added one at a time. Each slip has its own size. |
| Slip size | Three sizes per slip, upgraded slip by slip, so larger boats can dock. **Default:** small takes boat sizes 1–2, medium 3–4, large 5. |
| Tie-up slips | Up to 2 per terminal. They load no cars. They park ferries that are not in use, so an idle boat never blocks a working slip. They upgrade through the same three sizes. These replace the earlier "moorings". |
| Passenger-only dock | A separate purchase built beside the normal slips. It arrives with walk-on passengers. |
| Amenities | Add one by one for satisfaction and side income. |
| Truck staging | Extra lanes for commercial traffic. |

- Amenity examples are a coffee shop, restaurant, gift shop, covered waiting area, restrooms, expanded parking, bike storage and tourist information.
- A slip belongs to the terminal, not to a route. Slips serve whatever combination of routes the player schedules.
- When a slip is busy, arriving boats hold offshore.

### Holding lanes

- A terminal divides its lanes among destinations automatically, from the routes scheduled to call there.
- A boat on a multi-stop route loads from every lane that holds traffic for its stops.
- **Sharing:** when a destination's lane is full, its traffic can queue in the spare space of another destination's lane, provided the next boat loading that lane serves both destinations.
- If that next boat does not serve the overflowing destination, the extra traffic is turned away.
- Example at Madrona: lane 1 holds Port Rosario traffic and fills. The next boat sails to Gullrock and then Port Rosario, and Gullrock traffic only part-fills its lane, so Port Rosario traffic queues behind it. If the next boat sailed to Gullrock and somewhere other than Port Rosario, that traffic would be turned away.
- **Default:** construction takes game time, stays visible, and the terminal stays open.
- **Slip size upgrades take that slip out of service** (decided 2026-11-20, TID-44). A pusher brings a crane scow into the closed slip and the crew drives new dolphins and wing walls sized for the bigger boats. Boats on their way hold offshore until the slip reopens, and cars keep queueing. Building another slip first keeps the service running, so it is a tradeoff, not a penalty.
- A docked boat lies over against the dolphins on whichever side the tide sets her, and changes side when the tide turns. A less sure captain sometimes rides a wing wall in on landing.

---

## Routes and Scheduling

Any two docks can be connected. A connection exists only because a schedule sails it: there are no built-in links between terminals. Distance comes naturally from where they are. Players can build whatever network they like, and hub-versus-direct play is not a separate mechanic.

A route's running cost comes from:

- **Fuel:** distance and speed.
- **Staffing:** the level set on the boats serving it.

Scheduling offers three depths, so players can do as much as they enjoy:

1. **Auto:** assign a boat to a route and it schedules itself.
2. **Frequency:** set how often it sails.
3. **Manual:** build complex multi-leg schedules for each boat.

All three are in Phase 1. Frequency and granular control matter from the start, with easy configuration, because the timetable is a large part of running at a profit. Manual scheduling is the largest UI job in that phase, and it must work on touch screens. The [2D scheduling prototype](https://github.com/jnsndlr/tideways-2d-concept) is a starting point for the logic, not its screens.

Schedules show projected fuel and crew cost per day, calculated from the boat's schedule. That makes the timetable a financial tool: players see the cost before a sailing runs.

Each boat's pace sets its leg times. A slower pace visibly lengthens every leg in its schedule, and a faster one shortens them. The schedule shows each boat's pace beside its legs and can change it there. It is the same per-boat setting as on the boat's own panel. Changing it updates the leg times and the projected cost at once, and flags any leg that no longer fits its departure slot instead of quietly pushing the timetable back. **Default:** pace stays per boat; a per-leg override, such as running slow at night, is possible later.

**Default:** players can run separate weekday and weekend schedules, so the weekly rhythm is a real planning choice.

---

## Demand and Vehicles

Towns generate real trips. Every vehicle has an origin, destination, type and patience. The types of traveller are commuter, tourist and freight.

Vehicles that run out of patience visibly give up, and this counts against service in that town.

| Vehicle | Fare relative to a car | Notes |
|---|---|---|
| Car | 1x | Base fare |
| Big van | 1.5x | Takes more deck space |
| Box truck | 2x | Commercial |
| Large truck | 3x | Commercial |

Deck space and fares follow vehicle length and height. Commercial traffic needs to travel, so it pays more and is less likely to give up.

**Weekly rhythm:** commuters peak on weekdays, tourists surge on weekends and freight runs steadily on weekdays.

**Seasonal rhythm:** tourism swells in summer and falls in winter.

**Service-induced demand:** frequency, reliability, short waits, travel time, satisfaction and capacity all create more travel.

### Walk-on Passengers

Walk-ons are not in Phase 1, but they will become an integral core system on every boat, even without passenger-only vessels.

### Fares

- Players set fares per route for each vehicle type.
- The game suggests a starting fare based on distance.
- High fares reduce trips and satisfaction.
- **Default:** a company-wide control can adjust all fares at once.
- Research can reveal price tolerance and market segments.

### Satisfaction

Satisfaction emerges from play.

- **Improved by:** reliable schedules, short waits, friendly crews, safe operation and comfortable terminals.
- **Reduced by:** delays, crowding, breakdowns, long queues, poor service and strikes.

---

## Towns

Each town needs service in several categories. Towns grow by having specific needs met, or more slowly through general surplus capacity. Growth is decided once a week, from the previous week's service level and improvements.

- **Town card:** shows 3–4 current needs and how well each is being met. Research adds more detail.
- **Example needs:** commuters want morning and evening capacity, tourists want weekend frequency, and lumber towns want reliable truck space.
- **Identity:** each town starts with a leaning, and service shapes what it unlocks.
- **No decline:** towns never lose buildings. Unhappiness lowers demand, and better service restores it.
- **Growth is visible:** town changes reflect who has been served.

| Leaning | Example unlocks |
|---|---|
| Lumber and industry | Sawmill, factory, shipyard |
| Tourism | Resort, marina, whale tours |
| Commuter | Suburbs, business parks, university |
| Other | Dairy, fishing, agriculture and more, varying by island |

A town can change direction. A fishing town served well for tourists could become a resort. Second towns on an island can come after launch.

---

## Fleet

Five size classes are planned, with fictional names. **Default:** players can name their boats and sell them later.

Owning a boat is cheap. Most cost comes from running it. A boat can sit idle if the player can't afford its crew or fuel, so selling isn't forced.

Every boat tracks capacity, fuel efficiency, speed, age, condition, staffing level and tank size.

### Fuel

- At the start, fuel is automatic. The company pays one average price per gallon.
- A sailing's fuel use comes from speed, distance and boat size. A large boat run fast burns the most.
- Those are the player's levers: which boat, how fast and how far.
- **Pace:** each boat has a pace setting: Economy, Service or Full ahead. Burn per mile goes as the square of speed, so big boats run slower for the savings, at the cost of longer crossings. Switching pace immediately shows what a whole trip at that pace costs.
- **Posting:** fuel and wages are metered as the boat runs and go on the ledger once per trip, when it docks, so each trip's line shows what it actually used. Anything left at midnight is posted then, so each day's lines are whole.
- **Floating costs:** an option in Settings floats each trip's fuel and crew cost up off the boat as it docks, for players who want to see expenses as they happen.
- A boat with no fuel money can always move to a tie-up slip at the same terminal, if there is one.
- Warn the player before money stops a boat.
- **Later, through research:** the player can run fuel purchasing, buying when the market is good and holding it in storage. Tank levels and refuelling stops belong to that later layer.

### Laying Up

- The player can move a boat to a mooring. This takes no ramp.
- Laying up costs nothing beyond building the mooring.
- A boat stuck at a slip with no fuel money blocks that slip until the player pays or moves it.
- **Default:** a laid-up boat's crew goes unpaid, and bringing it back takes about a game day.

### Condition and Maintenance

- Condition is a percentage that falls slightly with each trip.
- Wear depends mostly on how hard a boat is run, and on captain skill and the boat's engineering score. Rough passages are not the main cause.
- Overhauls cost money and take the boat out of service, so maintenance collides with the timetable. Overhauls happen at one mainland yard, and the boat must sail there.
- A shipyard unlocked in a lumber town could later add a second yard.
- Used boats are cheaper and start with reduced condition, such as 50%. They need yard time and money to restore.

### Breakdowns

Breakdowns become more likely as condition falls. A broken boat limps to the next dock and blocks a slip. There are no rescues at sea.

Failure types include engine, hydraulics, electrical, loading ramp and navigation.

---

## Crew

Phase 1 uses one staffing level per boat: meager, adequate or well staffed. Meager is the Certificate of Inspection (COI) minimum crew, the legal floor. **Default:** adequate is about 1.3× the minimum and well staffed about 1.6×.

Staffing works through loading inefficiencies. A thin crew boards and unloads more slowly and less smoothly, so dwell times stretch and departures slip. Better staffing smooths that out. The inefficiencies feed customer satisfaction and what riders will pay for a ticket: people don't want to sail with an unhappy crew. Meager costs less, but adds fatigue and risk.

### Crew Experience

Each crew carries an experience level, like veteran units in Total War. Experience builds with service. An experienced crew handles random events more gracefully, such as breakdowns, weather, medical calls and near misses, with shorter delays and fewer knock-on problems.

Later phases build on the board's chain:

1. **Inputs:** pay per role, benefits tier, staffing level, schedule intensity and captain.
2. **Crew state:** fatigue and happiness.
3. **Performance:** per-boat crew scores.
4. **Results:** delays, call-outs, service quality, safety events and strikes.
5. **Effect on the network:** satisfaction, trips and willingness to pay.

### Crew Scores

Each boat has scores for Reliability, Morale, Safety, Service and engineering. Individual deckhands are not named or managed, and engineers are not named. Engineering is a per-boat score.

### Captains

Each boat has one named captain, with five stats: Seamanship, Leadership, Efficiency, Hospitality and Safety. Personalities such as Old Salt, Mentor or Strict add character. Worse captains can wear a boat faster.

### Pay and Events

- Players set pay per role and pick a benefits tier: minimal, standard or excellent.
- On-call and relief crews come from the board and are planned for later.
- Delays and call-outs arrive first, followed by safety events and strikes. Strikes always have warning signs.

---

## Finance

Revenue comes from vehicle fares, commercial traffic, amenities and bonuses. Walk-on fares come later.

Costs include fuel, wages, benefits, overhauls, repairs, upgrades and research.

Running out of money follows three steps:

1. The game warns the player.
2. Loans become available, once loans exist in a later phase.
3. Bankruptcy arrives only after a generous grace period. **Default:** about a full game week, or about an hour at 3x.

Loans are not in Phase 1.

---

## Research

Research costs money and time. There is no separate research currency. Operating routes also builds some passive information for free.

Research covers everything:

- **Information:** peak windows, price tolerance, demand types, hidden shortages, forecasts, latent potential and route profitability. Research can add this detail to town cards.
- **Purchase unlocks:** larger buildings, new boat classes and new terminal options.
- **Capabilities:** reservations and fleet analytics.
- **Direct improvements:** fuel efficiency, speed and faster ramps.

This replaces the old rule that research should avoid stat bonuses.

---

## Requests and Events

**Requests** are bonus side quests from towns, such as bringing the circus or delivering lumber. They have deadlines, and the only penalty for missing one is losing the bonus. There are no named representatives for now, though a mayor may come later.

Recurring requests such as mail or a school run can use the same system, with no penalties.

**Weather** can cause slow sailings and delays. Seasons change how the world looks and bring more bad weather in winter.

**Calendar events** come with seasons and will be designed later. They can be positive or negative, and should be announced early enough to react.

---

## Interface

The map is the main view. Every other view is a panel over it, and panels must work on desktop, tablet and phone.

Panels cover the board's Home Office functions: hiring, revenue and expenses, research, fleet purchasing, regional reports, scheduling and routing.

- Touch comes first. Hovering on PC for more information must also work as a tap.
- Touch targets should be at least 44 pixels.
- Queues and terminal problems should be readable directly on the map.

### Onboarding

Teaching happens through integrated popups and callouts during the main mission, not a separate tutorial.

### Saves

Saves are local to each platform, with no accounts or cloud management to start. **Default:** the game autosaves regularly, because iPad sessions get interrupted.

---

## Platforms and Graphics

- **Primary:** computer and iPad.
- **Secondary:** phone.
- **Performance floor:** M1 iPad at 30+ fps. Desktop targets 60 fps. Phone support does not lower the iPad floor.
- Use one scalable quality system, with graphics that vary by platform.
- Test the Mobile renderer early, and reduce polygon counts where needed.

---

## Game Loop Build Stages

The order for building the game loop and progression systems, agreed 2026-11-18. "Stage 3" in a ticket, PR or conversation means the row below. Every stage must work on authored and generated maps.

| Stage | What the player gets | Main work |
|---|---|---|
| 1. Company ledger | Start with $50,000. Every sailing costs fuel and crew. A Finances panel shows the day. | One ledger for income and expenses. Fuel is price per gallon × distance × a burn rate that rises with boat size and speed. A per-boat speed setting is the lever. |
| 2. Opening scenario | Port Rosario, Madrona and Gullrock each have one small slip. One Hiyu. An example schedule connects Port Rosario and Madrona. | A scenario is data: terminals, boat, cash and example schedule, named by island key. No link exists without a schedule, so the simulation owns a minimal schedule from here on. A generated map supplies the same data. |
| 3. Slips and lanes | Boats share slips, hold offshore when one is busy, and park at tie-up slips. Lanes divide themselves by destination and share when a boat serves both. | Separate slips from routes and give each a size. Add tie-up slips. Automatic lane allocation and the sharing rule under Terminals. |
| 4. Timetables | Set frequency, build multi-stop schedules by hand, and see the projected daily cost. | The schedule editor, built on the stage 2 schedule. It is also how stage 3 gets tested, so the two are worked together. |
| 5. Purchase catalogue | Buy lanes, a second and third slip, slip size upgrades and tie-up slips. | One shared path for price, requirement and build time, generalised from the existing lane extension. Research requirements plug in here. |
| 6. Fleet | Buy and sell boats and assign them to schedules. | Boat prices, and slip size limits on where each boat can call. |
| 7. New terminals | Develop an undeveloped site and schedule service to it. Only money gates it. | Terminal sites recorded per island in the map data, for both kinds of map. |
| 8. Towns and research | Weekly growth from last week's service. Research unlocks the upgrades. | A service score per town per week. Research projects that cost money and time. |

Decided in stage 1 (2026-11-19): fuel and wages post to the ledger once per trip, when the boat docks, with any remainder at midnight. Pace is set per boat, and switching it shows a whole trip's cost at the new pace straight away. Floating costs over boats are a Settings option, off by default.

Decided in stage 2 (2026-11-20): the opening scenario is `maps/opening.json`, naming terminals by island key. A schedule is a boat and its stops, shuttled as fast as loading allows until stage 4 adds times. A terminal with no scheduled stop gets one idle slip that draws no traffic, a minimal split of slips from routes ahead of stage 3. Sandbox keeps its planned network with a boat per route, and Play takes `--full-network` for the same.

Later, noted in stage 3 (2026-11-20):

- Manual lane assignment: the player sets how many lanes each destination gets, e.g. 5 lanes for a busy route and 1 for a small one, or a single lane split between two destinations.
- A terminal upgrades view that shows every upgrade a terminal can take in one place: lanes, slip count, slip sizes, tie-up slips, amenities and the rest. This is the UI for stage 5's purchase catalogue.

Decided in stage 3 (2026-11-20):

- Slips belong to the terminal. A scenario lists each terminal's slips and their sizes, one small slip by default, and the routes calling there share them. A planned network (Sandbox) still gives each route its own large slip.
- A boat coming in to a slip another boat holds waits offshore, clear of the other route, until the slip is free. The hold point is where the two approaches stop being clear of each other.
- A terminal's lanes divide evenly among the destinations its boats serve from there. A destination is any later stop the boat reaches before it is back at this terminal, so a through car can board for a stop beyond the next one. Each car has a destination and queues in that destination's lane.
- Sharing follows the rule under Terminals. "The next boat to load that lane" is a boat alongside, then one coming in, then the soonest due.
- A schedule of more than two stops runs round them in turn. For example, Port Rosario → Madrona → Gullrock → Madrona runs out and back, as WSF does with Fauntleroy, Vashon and Southworth. At each stop only the cars for that stop drive off.
- Deck order, first version: a boat boards cars for her first stop first. They park deepest, at the end that opens at that stop, and through cars park behind them. A double-ended boat never turns, so this works without spinning cars on deck.
- Multi-stop boats are set in the scenario file until the stage 4 editor.
- The opening terminals start with 2 paved holding lanes on a lot graded for 8. Each lane bought paves the next lot position, working out from the middle, and closes no working lanes while it is built. Once the lot is full, the next lane goes alongside it as before. Sandbox lots start fully paved.
- Tie-up slips sit along the shore beside the working slips. A scenario lists them per terminal. Laying a boat up (ferry panel) makes her finish her crossing, unload, then move to a free tie-up slip she fits at the first terminal on her route that has one. Her crew is stood down while she lies there, so she costs no wages. Returning to service brings her back to her working slip once it and the water round it are clear. A scenario schedule can start its boat laid up.
- Overflow cars left in another destination's lane when the shared boat has gone move back to their own lane once it has space, or are turned away.
- Multi-stop deck order follows Washington State Ferries practice. Cars for the intermediate stop board first and lap the deck to face the end that opens there, with through traffic loaded behind them. Big vehicles and late arrivals back on instead. Large boats can keep through traffic on upper ramps or wings. Small single-deck boats park cars nose-to-nose or tail-to-tail in one lane, so each stop drives off its own end. The simplest of these to build first is still to be chosen.

Decided in stage 4 (2026-11-21):

- A scenario map plans a route between every pair of its terminals in reach, so a schedule can be edited onto any of them in play. Only routes a schedule sails are in service: they show on the map and draw traffic. This replaces the stage 2 rule that no link exists without a schedule. The rule is now that no service exists without one.
- The stop editor (ferry panel, Edit stops) lists a boat's stops in turn. A terminal she can't call at next is greyed out with the reason: no route, or a slip too small for her. A new list must keep the terminal she calls at next. She finishes her crossing and takes the new stops there. Cars aboard for a stop she no longer reaches drive off there, and the lanes at every terminal divide again among the new destinations.
- On the authored map (any scenario), routes have no distance limit. Where land lies between two terminals, the route goes round it in as few straight legs as it can, keeping 0.3 mi off land in open water and tapering in near each terminal. Where no route can keep that much, it keeps 60% of it, then 30%. The clearance and taper are constants in `MapGenerator` to tune by eye. Sandbox's generated networks keep their old rules for now: links within 3,100 m, direct routes only.
- The authored map's routes are planned once and saved per scenario in `maps/routes/`, so Play loads them instead of planning. They are planned again only when the islands, a scenario's terminals or links, or the planner change: `tools/bake_routes.gd`, or automatically on the next desktop run.

---

## Phase 1: First Playable

A 2–3 hour game on one corner of the map, starting with 2 docks and one basic boat.

**In scope:**

- Cars and trucks as real trips, using lanes and deck space
- Auto, frequency and manual multi-leg scheduling
- Fare setting
- Fuel and staffing costs
- Laying up and moorings
- Town needs, town cards and visible growth
- A third dock and second boat
- A small research list for purchase unlocks
- Onboarding callouts
- Local saves
- Bankruptcy

**Not in scope:**

- Walk-ons
- Named captains and crew scores
- Requests and contracts
- Loans
- Breakdowns
- Used boats

### Purchase List

This draft assumes 3 terminals in the Phase 1 corner.

| Purchase | Count | Size |
|---|---|---|
| Lanes, added one at a time | 15 | Small |
| Terminal amenities | 9 | Small |
| Mooring spots | 3 | Small |
| Truck staging lanes | 3 | Small |
| Research unlocks | 8 | Mixed |
| Second and third slips | 3 | Bigger |
| Dock size upgrades | 3 | Bigger |
| New terminal sites | 2 | Major |
| Additional boats | 2 | Major |

That is 48 purchases, or one every 3–4 minutes over 2–3 hours. Phase 1 also needs about 12–18 visible changes.

Research unlocks can include bigger docks, a larger boat class, faster ramps, fuel efficiency and more town card detail.

### Later Phases

Later phases will be chosen by what the game needs once Phase 1 is playable. Likely candidates are walk-ons, captains and crew scores, requests, loans, breakdowns, used boats, the full region and weather.

---

## From Tech Demo to Game

The Tideways Godot project already has terminals, lanes, real vehicles, shuttling boats, five ferry sizes, fares, seasons and working Fleet, Wildlife, Routes and Map panels.

It does not yet have expenses, breakdowns, foot passengers, audio or saves. Company, Research and Finances are placeholders.

The tech demo uses 30-day seasons, and the game uses about 7. Town population is also set once, so growth is new work.

---

## Open Issues

- **Advertising:** v0.3 has paid campaigns to raise demand for a while, such as tourism or freight. Whether the game needs this is undecided, and nothing in Phase 1 depends on it.

### Possible Later

Environmental rules, carbon tracking, a mayor, regional fuel prices, passenger-only boats and second towns on an island.

### Cut

Rival companies, historical eras and a story campaign.

---

## Vision

The player begins with one basic boat serving two small communities.

Over time they build a regional network where every schedule, crew, boat and town influences the others. Success isn't the number of ferries owned. It's a resilient, thriving transport system that shapes the future of an entire island region.
