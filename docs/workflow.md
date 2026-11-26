# From playable idea to merged change

These are defaults Paul and Jon can adjust as they learn. On shared main, passing CI is a team convention. Either of you may verify and merge; GitHub branch protection and a second reviewer are optional by team choice.

## Quick mode

Jon and Paul can each build a feature on a branch and open a draft PR. During iteration, try the feature in the game or run the one check that answers the immediate question. Use an existing system when it already owns the behavior. For example, the HUD can show a fare computed by the simulation without maintaining its own fare table. Temporary shortcuts are fine on the branch. At handoff, call out known shortcuts and dependent branches so the verifier can address them before merge.

When picking up an existing implementation or investigation ticket, assign it to yourself and move it to **In Progress** before starting. Agents assign tickets to the contributor they are working for. Claim each ticket before dispatching parallel work. Check open PRs so you can continue existing work where appropriate. If the other contributor owns the ticket, coordinate a handoff first. Experiments can start immediately in quick mode.

When one person runs several agents, the assignee alone does not show which agent holds a ticket. Each agent adds its **Agent** label (`Claude` or `ChatGPT`) when claiming and removes it at handoff. An agent that finds another agent's label on a ticket leaves that work alone and uses the ticket's comments to pass on what it knows. A comment is read the next time that agent opens the ticket, so tell the person directly when something is urgent.

## Merge mode

Link any prototype you keep to a Linear ticket before handoff or merge. Either person can finish their own work or hand it off. Put the PR links in merge order on the ticket, explain how to try the change and what the player should experience, move it to **Ready for verification**, and clear the assignee.

Either person can claim the handoff by assigning it to themselves and moving it to **In Review**. Their agent may perform the checks, fix issues and merge without a second approval. Pause for a design decision or an unresolved failure. When explicitly asked to land their own change, the author can also verify and merge it directly.

1. Update the branch or combined stack against current main. Review the entire diff that will land. Before merging the first PR in a dependent stack, inspect the combined diff for responsibilities accumulating in shared classes. Decide which branch should carry each necessary refactor, then verify each prefix as it lands.
2. Review ownership against the [architecture guide](architecture.md). For each new responsibility, identify the owner of its state, which callers may change it and how they communicate. Check dependency direction and, for asynchronous work, who handles failure and releases resources when the caller goes away. For example, a new fare rule belongs with the accounting rules and can be tested there. The HUD reads the result.
   - Refactor on the branch when the change duplicates a rule, adds an unrelated responsibility to an existing class, or makes a rule depend on UI or rendering. Preserve the agreed behavior and test the corrected boundary. Remove temporary diagnostics and abandoned paths.
   - Fix debt the change introduces or materially worsens before merge. Track independent, pre-existing debt separately in Linear when it has a concrete cost. If a delivery constraint warrants an exception, keep the PR open until Paul or Jon explicitly accepts the tradeoff. Record the decision, owner and follow-up ticket in the PR.
3. For changed rules, add or update a focused regression check. Exercise failure cases that matter, such as a full berth, an impossible timetable or loading an existing save. For changes to appearance or feel, inspect the actual feature from a player camera.
4. Run the [fast check and relevant subsystem checks](delivery.md) on the final change. Inspect the reported results. The traffic diagnostics report overlap, grounding and stall counts. Compare these with main on the same seed when investigating regressions.
5. Mark the PR ready. Check the CI runs configured for this repository, fix failures, and repeat affected checks on the final commit. When there is no hosted workflow, say so and record the local commands and results. For touch, performance or device-specific behavior, record the device and build actually checked, or identify the outstanding device check. If that check is essential to knowing whether the change works, keep the PR open.
6. Record the outcome, tested commit and validation results in the PR. For a change to responsibilities or dependencies, also name the owning component and the check that exercises its boundary. The verifier can merge when these checks pass. Merge a passing prefix of a stack if each step is useful on its own and leaves main playable. Keep the ticket open for any remaining work. If main moved in a way that affects the change, update and retest before merging. If a merge breaks main, restore working behavior promptly, then fix the underlying problem on a branch.
7. After GitHub marks the PR merged, the verifier checks whether an open PR still uses its branch as a base or head. The author's agent can delegate remote cleanup at handoff by checking local worktrees for unpushed commits, uncommitted or untracked files and ongoing work, then recording “Remote branch can retire after merge” and the pushed commit in the ticket. If the verifier adds fixes, the delegation covers those commits when they descend from the recorded commit and land in the same PR. Keep the branch for a dependent PR, a changed history, a new tip after merge, or a request to keep it.
8. For a delegated branch in the shared repo, delete the remote branch with an explicit lease against the verified merged PR head. A lease failure means the branch moved. Record the exception on the ticket. Without a delegation, the author's agent handles cleanup on its next visit. That agent also handles local branches and worktrees after checking them again, and can run `git fetch --prune` to clear stale tracking refs. If safe local deletion refuses after a squash or rebase, inspect the remaining history.

## When to coordinate

Give the other author a heads-up before changing a save format, a shared simulation contract, build or export settings, or a system they are actively editing. Coordinate migration and compatibility before landing changes that affect their branch. Routine features do not need a second human sign-off.

Paul tends to focus on integration, portable software, CI and delivery. Jon tends to focus on gameplay and art. Either can change the game, code or launch scope. Record the decision and reason in the affected Linear ticket and update any design index entries or Ready tickets that would otherwise mislead a contributor. Use Discord for a heads-up when active work overlaps. Link those tickets and proceed independently unless a change would break the other work.

Keep gameplay rules independent of iPad-specific code. Test other platforms when the change affects them. Use a physical iPad before merge when touch, performance or device-specific behavior determines whether the feature works. File a minor bug and merge when the agreed outcome works. Hold for broken core behavior, crashes or save loss.

## Board and delivery

Jon and his agents start with his current gameplay, design or art priority. When choosing from the board, use **Ready to pick up** and check active work for overlap. After a playable handoff, continue with the next design priority. Paul and his agents usually pick up unassigned **Ready for verification** tickets, pending deliveries and integration work. Either person can take a different task or verify and ship their own change. Keep the board current as work happens. Once a week, either contributor or their agent can clear stale reviews, identify blocked handoffs, and check Ready priorities and prerequisites.

Mark a feature **Done** when its outcome is verified and merged to main in jnsndlr/Tideways, the shared development and release repository. Use paulhise1/tideways-3d as an earlier reference. For stacks, use contributing PR links for partial work and reserve a closing reference for the PR that delivers the full verified outcome on main.

Track TestFlight delivery on a separate release ticket. Either person can ship once the release checks pass. Record the build, included changes and tester group, and close the release ticket once the build is available to that group.

[Linear release planning and pickup queues](https://linear.app/tideways/document/start-here-tideways-release-planning-5ecd09fccfe5)

## Keeping the repo tidy

One reviewable outcome per branch works well for this team. Keep an exploratory stack if it helps the author iterate. Before pickup, compare Linear and open PRs so nobody starts a second implementation. Before merge, check current main, the actual diff and the final check result. Rebase or merge main into the work branch when another change affects the same paths. Keep art references under docs, generated release products outside the checkout and signing material local. Close or remove your own merged branches when you are through with them. A weekly look at blocked or conflicting PRs is usually enough for two contributors.
