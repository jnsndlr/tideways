# Architecture decisions

## What survives closing the app

**Release requirement.** Reopen the same local company with its region, fleet, earnings and service progress. A completed fare or purchase must be accounted for exactly once. Use stable IDs to reconnect durable records to a rebuilt world. The generated-company network record already resolves fleet and route identity. A versioned snapshot covering clock, money, purchases, queues and service progress is still to be built. [Current identity format](../scripts/sim/company_network.gd) · [Snapshot work](https://linear.app/tideways/issue/TID-312) · [iPad reopen acceptance](https://linear.app/tideways/issue/TID-239)

**Open decision for TID-312.** Restoring the exact point of a mid-crossing close requires a durable description of the voyage, cars aboard and pending transactions. Restoring from a defined safe point reduces that state, but may repeat part of a sailing. Paul and Jon need to agree what the player sees after reopening in the middle of a crossing. Either choice must preserve committed money and company progress. Test an older supported snapshot, damaged data and the first transaction after a restore.

## Where editable art lives

**Current convention.** Version editable Blender sources and export scripts under `art/`, which Godot skips via `.gdignore`. Check in the runtime exports used by the game under `assets/`. Keeping both in this repository lets an art change and the matching export travel in one review, at the cost of binary history in clones. A source-storage migration such as Git LFS would add checkout and retrieval requirements for contributors and CI. Treat that as a separate decision with the art owner. Check references before removing backups or alternate assets. [Art sources](../art/) · [Worked export example](coastal-house-kit.md) · [Artifact cleanup](https://linear.app/tideways/issue/TID-315)

## Who retires a legacy rendering flag

**Review responsibility.** The art owner confirms the replacement family’s appearance. The contributor retiring the flag inventories its callers and tool usage, compares the accepted render and removes the fallback in a family-sized PR. A supported comparison or fallback path needs a documented use and a check. Keeping both paths preserves an option for review but adds code and test obligations. Removing a flag before checking capture scripts can break a contributor’s workflow. The classic vehicle option in Models and the classic ferry option in FerryClass are examples for the inventory. [Models](../scripts/world/models.gd) · [FerryClass](../scripts/sim/ferry_class.gd) · [Model-family inventory](https://linear.app/tideways/issue/TID-314)
