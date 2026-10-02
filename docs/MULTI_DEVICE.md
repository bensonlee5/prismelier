# Build and download packages for multiple Garmin models

The current public [FR265 download](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/Prismelier-fr265.prg)
remains the only simulator-tested model. Its [build record](../dist/build-info.json)
and [checksums](../dist/SHA256SUMS) identify source `d4d1e45`. It has not been tested on hardware.

All 14 configured targets compiled successfully from `d4d1e45`; [machine-readable results](build-matrix-results.json) record each PRG checksum. Other-model binaries remain local build outputs pending their exact-device simulator review.

## Compatibility and validation matrix

This is a practical first group from Garmin's Forerunner, epix, Venu and fēnix
families, **not a sales ranking**. Garmin's official
[compatible-device table](https://developer.garmin.com/connect-iq/compatible-devices/)
and [device reference](https://developer.garmin.com/connect-iq/device-reference/)
are the model/geometry sources. Local official device profiles and the compiler
remain authoritative for an actual build.

The default build covers ten phase-one product profiles:

| Product ID | Model | Round AMOLED size | Actual compile / simulator evidence |
|---|---|---|---|
| `fr265` | Forerunner 265 | 416px | SDK 9.2.0 compile and Foundry visual simulator review at `d4d1e45` |
| `fr265s` | Forerunner 265S | 360px | SDK 9.2.0 compiled; not simulated |
| `fr165` | Forerunner 165 | 390px | SDK 9.2.0 compiled; not simulated |
| `fr165m` | Forerunner 165 Music | 390px | SDK 9.2.0 compiled; not simulated |
| `fr965` | Forerunner 965 | 454px | SDK 9.2.0 compiled; not simulated |
| `fr970` | Forerunner 970 | 454px | SDK 9.2.0 compiled; not simulated |
| `venu3` | Venu 3 | 454px | SDK 9.2.0 compiled; not simulated |
| `venu3s` | Venu 3S | 390px | SDK 9.2.0 compiled; not simulated |
| `fenix843mm` | fēnix 8 43mm | 416px | SDK 9.2.0 compiled; not simulated |
| `fenix847mm` | fēnix 8 47mm / 51mm | 454px | SDK 9.2.0 compiled; not simulated |

The initial six candidates were `fr265`, `epix2`, `epix2pro47mm`, `venu2`,
`venu2plus`, `fenix843mm`, selected to reuse the existing 416px layout. The other
four remain explicit optional 416px targets via `--devices`; they are not default
builds; all four now compile with SDK 9.2.0 but have not been simulated. The broader default now covers the
mainstream shortlist across four resolutions rather than limiting selection to
one convenient screen size. There is no claim these are the ten best-selling watches.

### Source and resource adaptation

The 416px master is the source for the current FR265 binary. `tools/scale_layout.py`
generates separate 360/390/454 bitmap-font atlases and indexed opaque textures in
`packaging/variants/`. Each glyph is independently resized with antialiasing and
repacked, preserving the original glyph coverage, proportional placement and font
license. Smallest label size is 13px at 360px: on-device readability is still a
required acceptance check, not guaranteed by geometry tests. The bitmap texture
is resized offline, never via a runtime full-screen buffer.

For those three sizes, the packager extracts the variant **from the requested
source commit**, checks its master-asset hashes to reject stale variants, replaces
only the temporary checkout's fonts/textures, and adapts drawing coordinates in
its view source. The coordinate adapter handles every current Dc primitive,
scales polygon points in place and keeps pen width at least one pixel. It fails
on an unknown drawing API or double adaptation so a future artwork change cannot
silently bypass sizing. Decimal coordinates follow the existing Dc conversion
behavior. The adapter itself and all resulting build inputs are fingerprinted.
Extra coordinate arithmetic requires native performance measurement on each
size. There is no second framebuffer or repeated bitmap/font resource loading.

The normal manifest intentionally still declares only FR265. The packager writes
a temporary one-product manifest preserving application ID, API 4.2 minimum and
permissions. Adding a model ID or passing these offline checks does not establish
native compatibility. A source ref predating the variant assets cannot build the
new sizes; use a commit containing this change.

Offline tests cover every clock string in both time formats, AM/PM separation,
dates, weather labels, worst-case metrics, weekday circular bounds, atlas
coordinates, texture dimensions/round bounds, and AOD masks. For 360/390/454px,
the conservative lit-pixel estimates are respectively **3.10% / 3.10% / 2.85%**,
with disjoint three-band masks across all 2,880 clock strings. These include a
one-pixel halo and are asset-model results, not Garmin firmware burn-in validation.

Regenerate assets after editing the master fonts or texture (Pillow required):

```sh
python3 tools/scale_layout.py
python3 -m unittest discover -s tests -v
```

Inspect a generated project without an SDK or signing key, using a ref that
contains the variants:

```sh
python3 tools/build_devices.py prepare --ref HEAD --device fr265s --output build/inspect-360
```

Garmin documents a 131,072-byte watch-face heap for these round AMOLED classes.
API 4+ devices have a separate graphics pool; compressed PNG or PRG file size does
not measure either runtime budget. Compiler success is only the first check.
Inspect heap and graphics usage, fonts, texture load/fallback and long-running
awake/AOD cycles on each exact simulator profile. Test Weather, SensorHistory,
Body Battery availability and missing-data behavior; keep the minimum API and
real firmware capability in mind. Do not infer those capabilities from resolution.
See [Garmin graphics documentation](https://developer.garmin.com/connect-iq/core-topics/graphics/)
and [project performance notes](PERFORMANCE.md).

Explicitly outside this build matrix:

- MIP models (including FR255/955, fēnix 7 and solar variants): need an intentional
  reduced-palette design and low-power behavior, not the AMOLED texture/AOD path.
- Rectangular Venu Sq/X1 and Instinct displays: need shape-specific composition.
- Other generations, sizes and aliases: no support promise without their own
  official profile, build and validation evidence. The fēnix 8 47/51mm share
  `fenix847mm`; do not invent a `fenix851mm` target.

## Provision once on the build computer

Use Linux or macOS, Python 3.10+, Java required by the SDK, Git and (for publishing)
GitHub CLI. Install **official SDK 9.2.0** and every selected device in Garmin SDK
Manager under the same OS user that runs the script. SDK Manager sign-in/device
provisioning is a user setup step; the SDK ZIP alone is insufficient.

Set `CIQ_SDK` to the SDK folder and `CIQ_KEY` to the **existing** private developer
DER key outside this repository. Preserve the saved key for update continuity;
this script never creates, copies or uploads a signing key. It also does not
accept Garmin terms, download/redistribute profiles, register a runner or log in
on your behalf. See [existing setup guidance](CI.md).

Device fingerprints use SDK Manager's normal directory:
`~/.Garmin/ConnectIQ/Devices` on Linux, or
`~/Library/Application Support/Garmin/ConnectIQ/Devices` on macOS.
Do not redirect the compiler to a different profile library.

## Compile a specified ref

```sh
git fetch origin
python3 tools/build_devices.py build --ref HEAD --output build/models-run1
# Or just selected profiles:
python3 tools/build_devices.py build --ref abf7fd44 --devices fr265,epix2 --output build/models-run2
```

A fresh output directory is required. Dirty working-tree changes are excluded.
The script resolves the ref to a full SHA, extracts tracked source/resources into
a separate temporary directory per target, and calls official `monkeyc -d ID`
with release mode and type checking. It records the compiler and device-profile
fingerprints, modified build-input fingerprint, source SHA, application ID,
program length and SHA-256. Existing `dist/` binaries are never repackaged as a
new compile. Output must be a fresh PRG container containing the application's
UUID. Target binding comes from the official compiler invocation and single-device
manifest, then exact-device simulator review; the script does not claim a full
independent parser or cryptographic verifier for Garmin's PRG format.

Each successful target gets its own PRG, `build-info.json`, `SHA256SUMS` and
`INSTALL.txt`. `matrix-results.json` records every attempt. A failed target does
not stop the other targets, but makes the command exit nonzero. Missing global
SDK/key configuration stops before output creation. Logs stay local and are not
part of public packages. No candidate is automatically called simulator-tested.

## Validate and publish actual downloads

Run each produced PRG in the **matching** official simulator. Check all four
themes, 12/24-hour and °F/°C, missing/stale weather and sensor data, AOD/wake cycles,
heap/graphics budgets and rendering. Hardware checks remain separately recorded.
Create a local JSON evidence file using the exact source SHA and PRG hashes:

```json
{
  "sourceCommit": "FULL_COMMIT_FROM_matrix-results.json",
  "devices": {
    "fr265": {
      "programSha256": "EXACT_SHA256_FROM_build-info.json",
      "correctDevice": true,
      "allThemes": true,
      "timeAndUnits": true,
      "missingData": true,
      "aodAndWake": true,
      "memoryChecked": true,
      "hardwareTested": false,
      "notes": "Record tester, date, SDK/profile, measured memory and observed results."
    }
  }
}
```

These are human review attestations, not automated simulator results. Only set a
field true after performing that check. Include only successful reviewed devices;
failed and unreviewed devices will not be released.

```sh
python3 tools/build_devices.py publish --output build/models-run1 \
  --evidence /private/path/validation.json --tag preview-2026-10-02
```

Publishing requires an already authenticated GitHub CLI with release permissions.
The source commit must exist in `bensonlee5/prismelier`. The script creates a new
**draft prerelease**, uploads one ZIP per approved exact device, a device manifest
and release checksums, then publishes it only after uploads succeed. It refuses
stale release staging, mismatched validation hashes or a tag targeting another
commit. Existing releases are never overwritten. If upload fails, inspect/delete
the incomplete draft before retrying with a fresh output run or staging directory.
Downloaders can use the public [Releases page](https://github.com/bensonlee5/prismelier/releases)
without Actions artifact access or its retention limit. This is sideload packaging;
a multi-product `.iq` file is for Connect IQ Store submission, not USB installation.

## Current provisioning blocker

The implementation environment has no official SDK, installed device profiles or
configured saved signing key. Consequently **no new target was compiled or
published** in this change. Existing FR265 evidence remains historical, not a
substitute for compiling these packages. Provision the SDK, selected profiles and
saved key on an authorized local machine, run the commands above, and perform the
simulator reviews before publishing. No persistent runner was installed.

### Use a configured environment without sending private keys

The owner can clone/check out this PR on an already configured local Linux/macOS
computer, set `CIQ_SDK` and `CIQ_KEY` to existing local paths, and run the build and
simulator there. Do **not** paste a key into chat, commit it, upload it to an
artifact, or add it as a GitHub secret for this process. Share only the generated
PRGs, public build records/checksums and validation observations if review is
needed. Alternatively select an authorized local execution environment that
already has the SDK/profiles and saved key mounted outside the checkout; local
path configuration is sufficient. A new persistent self-hosted runner is not
required and is not configured by this PR.
