# Battery and performance review

Reviewed 1 October 2026 against `7b1ac81`, including its FR265 compile fixes.
These are source-level improvements, not a measured battery-life guarantee.

## Changes

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
- Fix the optional SDK texture-schema test to accept the already-corrected
  automatic-palette XML on main, without assuming a removed palette child

The ebony bitmap, digital time, temperature band/needle, palettes, text and icon
placement are unchanged. No full-screen backing buffer or new raster is added.
All 72 cached band segments have the same endpoint formula as before.

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

## Verification and limits

- **56 tests passed** with official SDK 9.2.0 and Pillow, including the official
  parser, API name/arity audit, existing assets/AOD checks and seven new
  performance source/model tests
- Standard-library-only: **47 passed, 9 optional tests skipped**
- New tests guard cache invalidation/retry, wake/startup read paths, fixed dial
  geometry and absence of new timers/sensor activation. Python models are
  independent fixtures, not execution of Monkey C or a Garmin emulator
- The remote base commit reports a successful FR265 build. This review's cloud
  environment still lacks the official FR265 compiler profile, so **this new
  revision has not been natively compiled, simulator-tested or watch-tested**
- The compile workflow is owner/manual/main-only. No PR-triggered native build
  is expected; a draft PR is not a green native CI result

## Acceptance checks before release

1. Compile this exact revision for FR265 with the official profile, then inspect
   heap/graphics-pool usage and active `onUpdate` timing in Garmin's profiler
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
