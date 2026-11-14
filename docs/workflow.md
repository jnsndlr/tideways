# From playable idea to merged change

## Quick mode

Jon and Paul can each build a feature on a branch and open a draft PR. During iteration, try the feature in the game or run the one check that answers the immediate question. Use an existing system when it already owns the behavior. For example, the HUD can show a fare computed by the simulation without maintaining its own fare table. Temporary shortcuts are fine on the branch. Identify any that would become a second source of truth if shipped.

## Merge mode

Link any prototype you keep to a Linear ticket before handoff or merge. Either person can finish their own work or hand it off. Put the PR links in merge order on the ticket, explain how to try the change and what the player should experience, move it to **Ready for verification**, and clear the assignee.

Either person can claim the handoff by assigning it to themselves and moving it to **In Review**. Their agent may perform the checks, fix issues and merge without a second approval. Pause for a design decision or an unresolved failure. When explicitly asked to land their own change, the author can also verify and merge it directly.

1. Update the branch or combined stack against current main. Review the entire diff that will land. If several branches depend on one another, validate the combined change.
2. Clean up the touched paths. Remove temporary diagnostics, duplicated rules and abandoned experiments. Keep the change readable for the next person. Put unrelated cleanup in Linear if it has a specific cost.
3. For changed rules, add or update a focused regression check. Exercise failure cases that matter, such as a full berth, an impossible timetable or loading an existing save. For changes to appearance or feel, inspect the actual feature from a player camera.
4. From the repository root with Godot 4.7, run the headless import and a short game launch. Inspect output for script and resource errors. Run the relevant longer checks for the affected subsystem.

       godot --headless --editor --path . --import
       godot --headless --path . --quit-after 120

   For changes to loading or traffic, the existing diagnostics include:

       godot --headless --path . --fixed-fps 30 --script tools/vehicle_overlap_test.gd -- --seed=123 --frames=6000
       godot --headless --path . --fixed-fps 30 --script tools/vessel_soak_test.gd -- --seed=123 --frames=20000

   Read the overlap, grounding and stall summaries. If a finding also occurs on main, record the comparison and any change in severity. A successful process exit alone does not establish safe traffic.
5. Mark the PR ready. Check the CI runs configured for this repository, fix failures, and repeat affected checks on the final commit. When there is no hosted workflow, say so and record the local commands and results. For touch, performance or device-specific behavior, record the device and build actually checked, or identify the outstanding device check. If that check is essential to knowing whether the change works, keep the PR open.
6. Record the gameplay outcome, tested commit, validation results and remaining observations in the PR. The verifier can merge when these checks pass. Merge a passing prefix of a stack if each step is useful on its own and leaves main playable. Keep the ticket open for any remaining work. If main moved in a way that affects the change, update and retest before merging. If a merge breaks main, restore working behavior promptly, then fix the underlying problem on a branch.

## When to coordinate

Give the other author a heads-up before changing a save format, a shared simulation contract, build or export settings, or a system they are actively editing. Coordinate migration and compatibility before landing changes that affect their branch. Routine features do not need a second human sign-off.

Paul tends to focus on integration, portable software, CI and delivery. Jon tends to focus on gameplay and art. Either can change the game, code or launch scope. Record the decision and reason in the affected Linear ticket and update any design index entries or Ready tickets that would otherwise mislead a contributor. Use Discord for a heads-up when active work overlaps. Link those tickets and proceed independently unless a change would break the other work.

Keep gameplay rules independent of iPad-specific code. Test other platforms when the change affects them. Use a physical iPad before merge when touch, performance or device-specific behavior determines whether the feature works. File a minor bug and merge when the agreed outcome works. Hold for broken core behavior, crashes or save loss.

## Board and delivery

Start with unassigned verification handoffs, then check Ready tickets by priority. Either person can choose another task. Keep the board current as work happens. Once a week, either contributor or their agent can clear stale reviews, identify blocked handoffs, and check Ready priorities and prerequisites.

Mark a feature **Done** when its outcome is verified and merged to main in jnsndlr/Tideways, the shared development and release repository. Use paulhise1/tideways-3d as an earlier reference. For stacks, use contributing PR links for partial work and reserve a closing reference for the PR that delivers the full verified outcome on main.

Track TestFlight delivery on a separate release ticket. Either person can ship once the release checks pass. Record the build, included changes and tester group, and close the release ticket once the build is available to that group.

[Linear release planning and pickup queues](https://linear.app/tideways/document/start-here-tideways-release-planning-5ecd09fccfe5)
