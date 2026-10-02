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
  cache invalidation and retry, humidity validity/expiry, awake HR polling and the startup and wake
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
| Heart rate | Valid current API value; otherwise history at most 2 minutes old | `--`; current value is not retained after API loss |
| Humidity (0–100%) | Valid weather observation under 24 hours old | Copper ink from 2 hours; `--%` if missing, out of range, expired or timestamp invalid |
| Weather condition and dial | Observation is under 2 hours old | 2–24 hours: copper icon, mark and needle; condition word becomes `AGED nH` |
| Weather dial | Observation is under 24 hours old | `WX EXPIRED` (or `AGE UNKNOWN`/`CHECK TIME` for a missing or future timestamp); dial empty |
| Solar location | Observation older than 2 hours | Copper dot on the sunrise/sunset plate |

Current HR has no observation timestamp or guaranteed sample cadence in Garmin’s API. History keeps its original timestamp and expires on every awake update, even inside a cached minute. Weather and history reads remain once per clock minute; there is no background HR polling in AOD.

## Raster resources and memory

The Foundry background is one 416×416, 256-color indexed PNG (119,661 bytes on
disk, which is not its runtime size). API 4.0+ loads bitmaps into a separate,
managed [graphics pool](https://developer.garmin.com/connect-iq/core-topics/graphics/),
so the texture does not count toward the app heap. The face keeps only a
resource reference: no `get()` pinning and no extra full-screen buffer. Load or
draw failures fall back to the vector artwork. FR265 graphics-pool capacity is
unverified.

## Open validation

### Alignment pass — 1 October 2026

Reviewed the Foundry face in the official FR265 simulator at native resolution:

- Battery logo raised 3px to align with its percentage; Body Battery person shortened to clear the lower frame.
- Solar time lowered 4px in both formats; rise/set icons use separate origins so their different silhouettes share a visual center.
- Heart raised 2px; metric digits lowered 1px, with separate origins for smaller step-count fonts. Date lowered 1px while retaining room for month-name descenders.
- Precipitation marks shortened to leave a gap above weather text. Fixed string comparisons that had caused condition-specific weather icons to fall back to a plain cloud; verified the snow symbol in the simulator.
- Reviewed the clock, AM/PM marker, weekday rim, gauge ticks/unit, steps icon and weather label. The 59 source/asset checks pass, including updated glyph bounds and the official SDK method audit.

[Final simulator capture](screenshots/alignment-final.png) uses simulated snow/sunset data and 24-hour time; it is not watch data. Physical-watch appearance still needs confirmation.

### HR/humidity revision — 2 October 2026

58 source/layout/asset checks pass; 6 optional SDK checks skip in this environment.
No compiler, simulator, FR265 profile or configured signing key is available;
`python tools/build.py --release` stops at the required SDK/key preflight.
The earlier release’s native results and `dist/` binary do not validate this revision.

Before release, use simulated FIT HR to exercise 100 → 99 → missing; confirm
one current-value read per awake callback, no retained current value after loss,
and history expiry at 120/121 seconds. Check unchanged frames, minute rollover,
weather expiry inside a minute, wake/show/layout/settings invalidation, all four
themes and texture-loss recovery. Confirm the 71×27 HR restore leaves no ghost
digits or damage to adjacent artwork and survives framebuffer transitions.

### Remaining checks

1. **Simulator, manual:** missing/disconnected weather, observations at the
   2-hour and 24-hour boundaries, humidity at 0/100/missing/out-of-range, midnight, DST
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
