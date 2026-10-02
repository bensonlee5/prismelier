# Build and download packages for multiple Garmin models

The current public [FR265 download](https://github.com/bensonlee5/prismelier/raw/abf7fd44a5ec74b8b697d260f2a0913826f19de4/dist/Prismelier-fr265.prg)
remains the only simulator-tested model. Its [build record](../dist/build-info.json)
and [checksums](../dist/SHA256SUMS) are unchanged. It has not been tested on hardware.

## Compatibility and validation matrix

This is a practical first group from Garmin's Forerunner, epix, Venu and fēnix
families, **not a sales ranking**. Garmin's official
[compatible-device table](https://developer.garmin.com/connect-iq/compatible-devices/)
and [device reference](https://developer.garmin.com/connect-iq/device-reference/)
are the model/geometry sources. Local official device profiles and the compiler
remain authoritative for an actual build.

| Product ID | Model | Layout | Actual compile / simulator evidence |
|---|---|---|---|
| `fr265` | Forerunner 265 | 416 × 416 round AMOLED | Existing SDK 9.2.0 build and simulator review at `abf7fd4`; no new compile in this change |
| `epix2` | epix (Gen 2) | 416 × 416 round AMOLED | Candidate only; not compiled or simulated |
| `epix2pro47mm` | epix Pro (Gen 2) 47mm | 416 × 416 round AMOLED | Candidate only; not compiled or simulated |
| `venu2` | Venu 2 | 416 × 416 round AMOLED | Candidate only; not compiled or simulated |
| `venu2plus` | Venu 2 Plus | 416 × 416 round AMOLED | Candidate only; not compiled or simulated |
| `fenix843mm` | fēnix 8 43mm | 416 × 416 round AMOLED | Candidate only; not compiled or simulated |

The renderer, bitmap fonts, 416px texture and sparse repositioning AOD have fixed
coordinates. These candidates reuse that geometry without resampling. The source
manifest intentionally still declares only FR265: the packager writes a temporary
one-product manifest for each candidate, preserving the application ID, API 4.2
minimum and permissions. Adding an ID does **not** establish compatibility.

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

- FR265S (360px), FR165/165 Music and Venu 3S (390px): need smaller layout, fonts,
  texture and renewed AOD lit-pixel checks.
- FR965/970, Venu 3 and fēnix 8 47/51mm (454px): need larger layout/resources and
  graphics-memory checks. The fēnix 8 47/51mm share `fenix847mm`; no `fenix851mm`.
- MIP models (including FR255/955, fēnix 7 and solar variants): need an intentional
  reduced-palette design and low-power behavior, not the AMOLED texture/AOD path.
- Rectangular Venu Sq/X1 and Instinct displays: need shape-specific composition.
- Other generations, sizes and aliases: no support promise without their own
  official profile, build and validation evidence.

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
python3 tools/build_devices.py build --ref origin/main --output build/models-run1
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
