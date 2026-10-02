# Battery and performance review

CPU and memory work on the watch face, measured in the FR265 simulator. These
are not battery-life measurements; see the [README status](../README.md#status).

## Changes since `7b1ac81`

- **Startup:** retain the data constructor's initial read; remove the immediate
  second settings load and forced read in the view constructor
- **Wrist wake:** request a redraw without forcing sensor-history, weather and
  activity reads. The existing awake refresh still reads once per clock minute
  and checks freshness every update. Settings changes still refresh immediately
- **Solar events:** reuse today's/tomorrow's calculations for up to an hour at
  unchanged coordinates and local midnight. Coordinate changes, local day or
  timezone changes, clock rollback and missing/expired location invalidate the
  cache. Failed calculations clear results and retry after five minutes; valid
  null/polar results use the hourly cache. Sunrise/sunset selection and stale
  markers are still evaluated each awake update, independently of the cache
- **Temperature dial:** calculate its 73 fixed band vertices once. Each awake
  draw avoids 288 sine/cosine calls and 144 temporary two-element point arrays.
  Two retained flat arrays hold 146 numeric coordinates. This trades a small,
  unmeasured heap allocation for less repeated CPU work and allocation churn
- **Theme colors:** each view memoizes `PrismelierPalette.color()` results in a
  small dictionary, cleared when settings change. The 67-case palette switch now
  runs once per distinct color per theme instead of on every draw call

No full-screen backing buffer or new raster is added. All 72 cached band
segments have the same endpoint formula as before.

## Existing safeguards retained

The face uses local history and Garmin's weather cache. It activates no sensor,
GPS or network request, and adds no timer, animation or partial-second update.
Ambient rendering returns before data refresh and detailed artwork, leaving
only dim, repositioning time. The Foundry bitmap remains a managed resource
reference, without pinning or a duplicate full-screen buffer.

Garmin documents once-per-second updates while awake and once-per-minute updates
in low-power mode in its [WatchFace API](https://developer.garmin.com/connect-iq/api-docs/Toybox/WatchUi/WatchFace.html).
Every requested full redraw still paints the screen: this review deliberately
does not assume that skipping a callback preserves the framebuffer across view,
layout or power transitions. [Location.toDegrees](https://developer.garmin.com/connect-iq/api-docs/Toybox/Position/Location.html#toDegrees-instance_function)
provides the cache coordinates; [Weather](https://developer.garmin.com/connect-iq/api-docs/Toybox/Weather.html)
provides the location/date-specific solar events. Resource-reference behavior
is described in Garmin's [graphics documentation](https://developer.garmin.com/connect-iq/core-topics/graphics/).

Tests in `tests/test_performance.py` guard the cache invalidation and retry,
the wake/startup read paths, the fixed dial geometry and the absence of timers
or sensor activation.

## Simulator profile, 1 October 2026

Local Linux run, official SDK 9.2.0 FR265 simulator. Throwaway copies of the
baseline (`7b1ac81`) and this revision (`6747f6b`) were wrapped with identical
`System.getTimer()`/`getSystemStats()` logging; the repository source is not
instrumented. Garmin's GUI profiler was not used. Each figure is the mean of
three alternating 120-frame runs. One measurement ran per frame, because the
watchdog tripped ("Code Executed Too Long") on both builds when one full
redraw plus four extra `drawTemperature` calls shared a callback.

| Metric | `7b1ac81` | `6747f6b` | Change |
|---|---|---|---|
| Full awake `onUpdate` | 25.9 ms | 25.7 ms | within noise (about ±1 ms between runs) |
| `drawTemperature` | 6.29 ms | 5.90 ms | about 6% faster |
| `onExitSleep` (wrist wake) | 1.07 ms | ~0.02 ms | forced refresh removed |
| `data.refresh(false)` within a cached minute | 0.188 ms | 0.237 ms | +0.05 ms from solar-cache checks |
| App heap used while running | 31,168 B | 32,424 B | +1,256 B (cached band vertices) |

Reference faces under the same `onUpdate` timer, two 60-frame runs each:

| Build | `onUpdate` | App heap used |
|---|---|---|
| Prismelier with `onUpdate` reduced to `dc.clear()` | 2.3–2.8 ms | 31.7 KB |
| Garmin SDK `Analog` sample, retargeted to `fr265` | 16.8–17.1 ms | 13.0 KB |
| Prismelier, vector theme (`Palette=0`, no bitmap) | 26.6–26.7 ms | 31.8 KB |
| Prismelier, Foundry bitmap theme | 26.4–26.5 ms | 31.8 KB |

Interpretation:

- The full-screen Foundry bitmap costs no more than the vector theme's
  artwork. Redraw time is dominated by many small vector calls, each of which
  resolved a color through `PrismelierPalette.color()`. Memoizing those colors
  (below) was the follow-up
- Wake and temperature-dial savings are real but small relative to a full
  redraw; the cached-minute refresh became slightly slower
- These are host-CPU simulator timings, valid only for comparing builds. They
  do not predict watch timing or battery life. The SDK `AnimationWatchFace`
  (no FR265 animation mapping) and `ConfigurableWatchFace` (`WatchFaceConfig`
  unsupported on FR265) samples could not serve as references

### Theme-color cache

Same harness, Foundry theme with the current layout, two alternating 60-frame
runs per build:

| Build | `onUpdate` | App heap used |
|---|---|---|
| Palette lookup on every draw call | 26.1–27.2 ms | 31,784 B |
| Memoized theme colors | 24.0–24.3 ms | 32,232 B |

That is about 9% less redraw time for 448 bytes of heap.

## Acceptance checks before release

1. Done in the simulator for heap and `onUpdate` timing (above). Still to do:
   inspect graphics-pool usage in Garmin's memory viewer
2. Check all themes and unit/time settings; repeated gestures in one minute;
   awake/ambient transitions and interruptions; midnight/DST/timezone changes;
   clock rollback; location changes; expired/missing weather; polar events and
   failed solar reads. Check solar-event rollover while the cache is reused
3. Run the simulator's always-on checks and confirm no blank/stale screens after
   returning from other apps. Confirm readable metrics and matching dial geometry
4. Compare the baseline and new face on an actual FR265 over matched 24–48-hour
   periods with the same brightness, AOD, gesture, connection, activity and
   notification settings. Record drain/hour, wake responsiveness, crashes and
   missing data; repeat to separate normal workload variability from improvement

No runtime memory figure, battery percentage saving or extra days of battery
life is claimed until those measurements exist.
