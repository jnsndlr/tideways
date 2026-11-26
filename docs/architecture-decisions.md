# Architecture decisions

## What survives closing the app

**Release requirement.** Reopening a company mid-crossing should resume the ferry at the saved voyage position with the same vehicles aboard. Fares and purchases post exactly once, including a fare already collected while a vehicle is driving onto the ferry. Stable town, route and hull keys reconnect durable records to the rebuilt region. [Decision and engineering work](https://linear.app/tideways/issue/TID-312) · [iPad reopen acceptance](https://linear.app/tideways/issue/TID-239)

**Verified scope.** The ledger, an ordinary two-stop ferry and a terminal’s settled holding lot have separate round-trip checks. A restored rig completes its paid boarding through the live callback. A purchased holding lane finishes paving with its original charge, and queued vehicles and walk-ons keep their order and destinations. The company snapshot still needs to coordinate these records with the clock, other active traffic and terminal upgrades, then restore through the player-facing save flow and verify reopening on device. [Ledger](../tests/rules/company_ledger_snapshot_test.gd) · [Voyage](../tests/session/ferry_crossing_snapshot_test.gd) · [Holding lot](../tests/session/terminal_holding_snapshot_test.gd)

**Purchased berth sites.** Restore the first added working slip or tie-up at the purchased offset before applying fitted berth sizes. The original survey recreates necessary dredging. The crane resumes its saved phase and opens outstanding work once. The ledger restores the original payment. Multiple successive berth purchases and route reassignment still need coverage. [New berth and dredging checks](../tests/session/terminal_berth_purchase_snapshot_test.gd)

## Where editable art lives

**Current convention.** Version editable Blender sources and export scripts under `art/`, which Godot skips via `.gdignore`. Check in the runtime exports used by the game under `assets/`. Keeping both in this repository lets an art change and the matching export travel in one review, at the cost of binary history in clones. A source-storage migration such as Git LFS would add checkout and retrieval requirements for contributors and CI. Treat that as a separate decision with the art owner. Check references before removing backups or alternate assets. [Art sources](../art/) · [Worked export example](coastal-house-kit.md) · [Artifact cleanup](https://linear.app/tideways/issue/TID-315)

## Who retires a legacy rendering flag

**Review responsibility.** The art owner confirms the replacement family’s appearance. The contributor retiring the flag inventories its callers and tool usage, compares the accepted render and removes the fallback in a family-sized PR. A supported comparison or fallback path needs a documented use and a check. Keeping both paths preserves an option for review but adds code and test obligations. Removing a flag before checking capture scripts can break a contributor’s workflow. The [model selection inventory](model-selection.md) lists the switches, active callers and review evidence for each family. [Models](../scripts/world/models.gd) · [FerryClass](../scripts/sim/ferry_class.gd) · [Model-family inventory](https://linear.app/tideways/issue/TID-314)
