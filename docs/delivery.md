# CI and TestFlight delivery

## Pull request verification

Run `bash tools/fast_ci.sh` at the repository root with Godot 4.7.2 on PATH, or set GODOT_BIN to the editor executable. The script imports the project, runs focused rules tests and launches the game headlessly. Its exit status includes script and resource errors from Godot's output. GitHub Actions runs this same command on a ready PR targeting main. Drafts skip the job. Check **Godot fast check** on the commit you intend to merge.

For changes to boarding or navigation, run the relevant diagnostics on the same commit and seed.

    godot --headless --path . --fixed-fps 30 --script tools/vehicle_overlap_test.gd -- --seed=123 --frames=6000
    godot --headless --path . --fixed-fps 30 --script tools/vessel_soak_test.gd -- --seed=123 --frames=20000

Record overlap, grounding and stall results and compare with main. For touch, frame pacing or device-specific changes, record the physical iPad, build and observed behavior on the PR. See the [team workflow](workflow.md) for merge decisions.

## Manual TestFlight delivery

Either Jon or Paul owns a delivery from archive through tester availability. Open a release ticket with the intended main commit, changes and tester group. Check current main for a distribution-capable iOS preset. The initial [iPad playtest export](https://github.com/jnsndlr/Tideways/pull/6) targets a development app identity. [TID-252](https://linear.app/tideways/issue/TID-252) tracks validation of the first distribution archive. Before the first shared-repo distribution, confirm the App Store Connect app record, matching bundle ID, signing team, supported devices and next unused build number.

1. Start from the verified main commit on a Mac with the matching Godot export templates and Xcode. Export the iOS project using the distribution identity and version. Keep signing credentials on the release machine.
2. Open the exported Xcode project. Select the app scheme and a generic iOS device, then archive the Release configuration. Inspect the archive's bundle ID, version, build number and device family. Validate it and upload through Organizer to App Store Connect.
3. Wait for processing, complete any required build metadata, and assign the processed build to the intended TestFlight group. For external testing, check beta review status when applicable.
4. Confirm the exact build is available to the group and install it through TestFlight for a launch smoke check. Record commit, version/build, group and result on the release ticket. Close the ticket after availability is confirmed.

If the candidate fails, record the failure and keep the previous usable build available. Ship a corrected candidate with a new build number. The hosted PR check covers code validation. Signing, uploading and tester distribution are manual.
