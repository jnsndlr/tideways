# Gameplay handoff for Claude

## Start in the right game

Develop and release from [jnsndlr/Tideways](https://github.com/jnsndlr/Tideways), the Godot repository formerly called lowpoly. Start a feature branch from current main. Open **Sandbox** on the title screen for the working generated region. **Play** is the entry point for Jon’s authored region. Earlier Tideways3D and native iOS builds are references for accepted behavior and art. Check that a feature exists in this repo before building on an older ticket marked Done.

Jon and Paul are equal contributors. Work with Jon on gameplay implementation, gameplay design and art. Paul and his agent are prioritizing architecture, code cleanliness, tests, CI and delivery. Either person can work in any area, make design decisions, verify a change or ship to TestFlight.

## Choosing gameplay work

Start with the live pickup queue and check open PRs before claiming a gameplay ticket. The [captain assignment change](https://github.com/jnsndlr/Tideways/pull/14) is an example of a small playable slice with a rule the player can observe on the next crossing. Check the [crew effects ticket](https://linear.app/tideways/issue/TID-67) for its prerequisites before extending that system.

## Pick up, implement and hand off

1. Open the [Linear workflow guide](https://linear.app/tideways/document/start-here-tideways-release-planning-5ecd09fccfe5). The shared pickup order is verification handoffs first, then Ready work by priority. For a gameplay session, check Jon’s active work and claim the chosen card in **In Progress**. Exploratory prototypes can start immediately. Link anything you keep to a ticket before handoff or merge.
2. Use quick mode. Get the change running and use the smallest check that answers the design question. Keep game rules independent of iPad input, rendering and UI. Reuse the existing owner of a rule. Clean the paths you touch. Broader cleanup with a concrete payoff belongs in [Engineering foundations](https://linear.app/tideways/project/engineering-foundations-e97de6837467).
3. When a decision changes, update the affected Linear ticket with what changed and why. Update any Ready ticket or design-index entry that would now send someone in the wrong direction. Link overlapping work. Use Discord for a timely heads-up if another person is actively editing that system.
4. For a handoff, put the PR links in merge order, give the steps to try it and describe the expected player experience. Move the ticket to **Ready for verification** and clear the assignee. Either person can claim it and move it to **In Review**. Claiming authorizes their agent to fix, test and merge. Pause for a design choice or an unresolved failure.
5. Follow the [team workflow](workflow.md) at merge time. Run fast CI and the checks appropriate to the change. Physical iPad verification is needed when touch, performance or device behavior determines success. A minor bug can get a follow-up ticket if the agreed feature works. Broken core behavior, crashes or save loss hold the merge. Passing parts of a stack may land independently when each delivers a useful change and keeps main playable.
6. Mark a feature **Done** once verified and merged to shared main. Track TestFlight delivery separately through availability to the tester group. Either person can ship after the release checks pass. Keep the board current as work happens. Either contributor or agent can do the weekly pass for stale reviews, blocked handoffs, priorities and Ready prerequisites.

## Product and engineering context

The first public iPad release includes the authored region, playable scheduling, research, terminal expansion, captain and crew management, local save/resume and device checks. The [design index](https://linear.app/tideways/document/tideways-design-index-first-public-ipad-release-1e6bbe392246) maps ideas to issues, including later ideas and explicit cuts. The [opening-playthrough ticket](https://linear.app/tideways/issue/TID-241) tracks unsettled choices about fares and onboarding, operating costs and idle boats, the first expansion and visible town change, and minimum readability and audio.

Paul’s [code and testing audit](https://linear.app/tideways/document/code-architecture-cleanliness-and-test-audit-tideways-main-5ca0b8b57074) prioritizes protecting fare and deck-allocation rules, testing a complete vehicle journey and real UI controls, and fixing Sandbox teardown. Accounting and deck refactors follow their tests. These are coordination points for gameplay work. The goal is to keep behavior testable and preserve Jon’s visuals while features move quickly.
