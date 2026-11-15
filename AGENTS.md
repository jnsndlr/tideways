# Working on Tideways

Use **quick mode** by default. Work on a branch and get the gameplay change into the running game quickly. Use the smallest check that tells you whether the idea works. Defer comprehensive testing, naming polish and unrelated cleanup while the design is moving. Draft PRs and short stacks are welcome.

Link work you keep to a Tideways Linear ticket before handoff or merge. To hand off, link PRs in merge order, give the steps to try the feature and the expected player experience, move the ticket to **Ready for verification**, and clear the assignee.

Switch to **merge mode** when asked to land work or when Paul or Jon claims a verification handoff. Claiming means assigning the ticket to the verifier and moving it to **In Review**. Their agent can fix, test and merge passing changes. Pause on an unresolved failure or a change to the intended design.

Read [the team workflow](docs/workflow.md) for verification, release and board upkeep.

For owner responsibilities, test selection and worked examples, see [architecture](docs/architecture.md), [verification](docs/verification.md) and [the agent handoff](docs/claude-gameplay-handoff.md). These are team defaults that Paul and Jon may revise together or in the relevant ticket.
