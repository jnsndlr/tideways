# CI and TestFlight delivery

## Pull request verification

Run `bash tools/fast_ci.sh` at the repository root with Godot 4.7.2 on PATH, or set GODOT_BIN to the editor executable. The script imports the project, runs focused rules tests and launches the game headlessly. Its exit status includes script and resource errors from Godot's output. GitHub Actions runs this same command on a ready PR targeting main and again on merged main. Drafts skip the job. **Run workflow** starts the longer traffic checks. Check **Godot fast check** on the commit you intend to merge.

For changes to boarding or navigation, run the relevant diagnostics on the same commit and seed.

    python3 tools/check_road_traffic.py -- --seed=123 --frames=6000
    godot --headless --path . --fixed-fps 30 --script tests/traffic/vessel_soak_test.gd -- --seed=123 --frames=20000

The road check allows ten minutes and 8 MiB per log. Use its `--script PATH` option for a comparison probe that prints the same test pass marker.

Record overlap, grounding and stall results and compare with main. For touch, frame pacing or device-specific changes, record the physical iPad, build and observed behavior on the PR. See the [team workflow](workflow.md) for merge decisions.

## Manual TestFlight delivery

Either Jon or Paul owns a delivery from archive through tester availability. Open a release ticket with the intended main commit, changes and tester group.

The shared game continues the existing **Tideways 3D** app (Apple ID `6829315477`, bundle `com.paulhise.tideways3d.graphicslab`, team `BC6278S7RY`). The TestFlight preset supports iPhone and iPad. The development app in [PR #6](https://github.com/jnsndlr/Tideways/pull/6) uses a separate identity.

1. On the release Mac, use Godot 4.7.2 with its matching iOS templates and Xcode with the team's signing account. In Godot's **Project → Export → TestFlight**, set the App Store team ID on this Mac. Godot stores it in the ignored local export credentials. Check the marketing version and choose an unused build number in App Store Connect. Keep generated files outside the game checkout.

       mkdir -p /tmp/tideways-release
       godot --headless --editor --path . --import
       godot --headless --path . --export-release TestFlight /tmp/tideways-release/Tideways.xcodeproj
       xcodebuild -project /tmp/tideways-release/Tideways.xcodeproj -scheme Tideways -configuration Release -destination 'generic/platform=iOS' -archivePath /tmp/tideways-release/Tideways.xcarchive -allowProvisioningUpdates archive

2. Open the archive in Xcode Organizer. Verify its identity, version, build and supported devices. Xcode archives with Apple Development under automatic signing and uses Apple Distribution for the App Store package. Choose **Validate App** for a rehearsal. If Organizer offers to create an app record, recheck the bundle and selected team. Record the validation result and any warnings. Use **Distribute App** for an authorized delivery.
3. Wait for processing, complete any required build metadata, and assign the processed build to the intended TestFlight group. For external testing, check beta review status when applicable.
4. Confirm the exact build is available to the group and install it through TestFlight for a launch smoke check. Record commit, version/build, group and result on the release ticket. Close the ticket after availability is confirmed.

If the candidate fails, record the failure and keep the previous usable build available. Ship a corrected candidate with a new build number. The hosted PR check covers code validation. Signing, uploading and tester distribution are manual.
