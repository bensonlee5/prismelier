# QA

Current build and test status lives in the [README](../README.md#status). This
page explains what the automated checks cover and what still needs validating.

## Running the checks

```sh
python -m unittest discover -s tests -v
```

The standard-library run needs neither an SDK nor Pillow. Two optional extras
enable more checks:

- **Pillow** enables raster checks: font atlases, the AOD burn-in model and the
  Foundry texture's circular safe area
- **An SDK path** (`CONNECTIQ_SDK`, `CIQ_SDK` or `CIQ_HOME`) enables the
  official `monkeydoc` parser run, the API name/arity audit against the SDK's
  method IDs and constants, the texture XML schema check and the FR265 device
  reference (131,072 bytes of watch-face memory, 416×416)

```sh
CONNECTIQ_SDK=/path/to/connectiq-sdk python -m unittest discover -s tests -v
```

## What the checks cover

- **Project structure:** FR265-only manifest, minimum API level, permissions,
  resource references, settings options, font pages and required glyphs
- **Layout:** every 12/24-hour clock string, month/day label, weather condition
  word, solar time and metric is measured against its panel using the committed
  font metrics. The dial's unit label is checked to stay in the needle-free gap
- **Data contracts:** calendar/DST/timezone handling, weather freshness, solar
  cache invalidation and retry, Body Battery expiry, and the startup and wake
  read paths
- **Palettes:** all four themes map every color in `resources/themes.json`, and
  ambient ink and black are never recolored
- **AOD model:** for all 1,440 times in both formats, lit pixels stay under 10%
  of the circular screen, and the three repositioning bands never overlap

These are source, metric and asset checks. They do not execute Monkey C; only a
compile, the simulator and the watch do that.

## Data freshness policies

These are app policies, not Garmin refresh guarantees.

| Value | Shown while | Then |
|---|---|---|
| Heart rate | Sample is at most 2 minutes old | `--` |
| Body Battery (0–100) | Sample is at most 15 minutes old | `--` |
| Weather condition and dial | Observation is under 2 hours old | 2–24 hours: copper icon, mark and needle; condition word becomes `AGED nH` |
| Weather dial | Observation is under 24 hours old | `WX EXPIRED` (or `AGE UNKNOWN`/`CHECK TIME` for a missing or future timestamp); dial empty |
| Solar location | Observation older than 2 hours | Copper dot on the sunrise/sunset plate |

Body Battery comes from on-device `SensorHistory`. Garmin documents no
guaranteed sampling interval, and synced data is not included. Expired, invalid
or unsupported readings show placeholders, never invented values.

## Raster resources and memory

The Foundry background is one 416×416, 256-color indexed PNG (119,661 bytes on
disk, which is not its runtime size). API 4.0+ loads bitmaps into a separate,
managed [graphics pool](https://developer.garmin.com/connect-iq/core-topics/graphics/),
so the texture does not count toward the app heap. The face keeps only a
resource reference: no `get()` pinning and no extra full-screen buffer. Load or
draw failures fall back to the vector artwork. FR265 graphics-pool capacity is
unverified.

## Open validation

1. **Simulator, manual:** missing/disconnected weather, observations at the
   2-hour and 24-hour boundaries, Body Battery at 0/100/missing, midnight, DST
   and timezone changes, clock rollback, location changes, polar or failed
   solar events, settings changes, AOD transitions and the heat-map check, and
   returning from other apps without a blank or stale screen
2. **Graphics pool:** usage in the simulator's memory viewer
3. **Physical FR265:** font rendering on AMOLED, alignment and clipping, wrist
   activation, AOD transitions, texture reloads under pool pressure and
   recovery paths
4. **Battery:** matched 24–48-hour drain comparisons against another face, per
   [PERFORMANCE](PERFORMANCE.md#acceptance-checks-before-release)

API 5.0+ firmware enforces a less-than-10% AOD luminance rule according to
Garmin's [System 7 announcement](https://forums.garmin.com/developer/connect-iq/b/news-announcements/posts/welcome-to-system-7).
The sparse, moving ambient time is designed to stay well under it, but only
firmware can confirm this.
