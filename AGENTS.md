# Working on Tideways

Use **quick mode** by default. Work on a branch and get the gameplay change into the running game quickly. Use the smallest check that tells you whether the idea works. Defer comprehensive testing, naming polish and unrelated cleanup while the design is moving. Draft PRs and short stacks are welcome.

Follow the priority your contributor gives you. By default, Jon and his agents move gameplay, design and art forward. Use **Ready to pick up** for scoped work and hand off playable changes when ready. Paul and his agents start with **Ready for verification** and upcoming deliveries, then integration, CI and architecture. Either contributor can take work in either area.

Before starting an existing implementation or investigation ticket, assign it to the person you are working for (Paul Hise or Jon Sandler) and move it to **In Progress**. Claim each ticket before dispatching parallel work. Check linked PRs for work already underway. If the other contributor owns the ticket, coordinate a handoff before taking it over.

Paul and Jon may each run more than one agent under their own name. When you claim a ticket, add your **Agent** label (`Claude` or `ChatGPT`), and remove it when you hand off. Do not start on a ticket that carries another agent's label. Read its comments, leave a comment with anything that agent should know, and stop.

Link work you keep to a Tideways Linear ticket before handoff or merge. To hand off, link PRs in merge order, give the steps to try the feature and the expected player experience, move the ticket to **Ready for verification**, and clear the assignee.

Switch to **merge mode** when asked to land work or when Paul or Jon claims a verification handoff. Claiming means assigning the ticket to the verifier and moving it to **In Review**. Their agent can fix, test and merge passing changes. Pause on an unresolved failure or a change to the intended design.

Squash-merge, so main gets one commit per ticket. After the merge, delete the branch on GitHub and in your local clone, and run `git fetch --prune`. Delete only branches whose PR has merged; leave anyone else's branch to its owner.

Read [the team workflow](docs/workflow.md) for verification, release and board upkeep.

For owner responsibilities, test selection and worked examples, see [architecture](docs/architecture.md), [verification](docs/verification.md) and [the agent handoff](docs/claude-gameplay-handoff.md). These are team defaults that Paul and Jon may revise together or in the relevant ticket.
