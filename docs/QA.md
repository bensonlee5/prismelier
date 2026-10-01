# QA status

Prismelier is a source project with design renders. It has not been built for a
Forerunner 265, run in Garmin's simulator, or installed on physical hardware.

## Recorded result, 1 October 2026, 05:35 UTC

- SDK 9.2.0 and Pillow available: **18 tests passed**, including a fresh parser
  run against all source files, 52 API owner/method pairs and argument
  counts, 61 module constants, and weather symbols checked against Garmin's
  bundled documentation
- Standard-library-only run, with SDK environment variables removed and Python
  site packages disabled: **12 tests passed, 6 optional checks skipped**
- Palette consistency: **4 themes × 67 color entries** match the committed
  `themes.json`; the ambient ink and black background are unchanged in every
  palette. Settings and Data both accept all four theme indexes
- Ambient asset estimate: **2,582 lit pixels maximum**, **1.899%** of the
  135,948-pixel circular screen model, at `08:08`, including the conservative
  one-pixel halo. All 2,880 12/24-hour clock strings and all three bands were
  covered. The three all-times band unions were pairwise disjoint

The latest parser check includes the revised vivid steampunk layout, default
Fahrenheit temperature bar, grouped weather and solar icons, centered AM/PM,
compact large step counts, asymmetric porcelain insert, and explicitly typed
Gregorian weekday/month indexes. The final background uses chamfered ceramic
substrates, fine copper/teal/violet circuit traces, asymmetric junctions,
microbridges, and an engraved lower backplane. The battery readout uses the
current 20px Small font. The new `drawArchitecture`, `trace`, and `junction`
helpers were included in this parser and API check. A static guard confirms
that background architecture is called only after the sleep branch returns;
it is excluded from the time-only ambient display. No source changed during
that parser run. This run also covers timestamped local Body Battery history,
its separate person-and-bolt score, and the Reactor, Foundry, Porcelain, and
Nocturne palettes. Device charge remains a distinct percentage. The new local
`PrismelierPalette.color(value, theme)` call is checked against its definition,
and every generated color mapping is compared with JSON. Renew the fingerprints
after any subsequent source revision.
Source fingerprints for that run:

```text
PrismelierApp.mc   e8696d7cd4acb9ec2ab2971572a5d1ee5a5d80017d23ff7c345fc0eb3dabbb14
PrismelierData.mc  3568805c9c6fc492c46ff3661a01849705f46c7dd394f35c1b7a58cb42def084
PrismelierPalette.mc  80d4f9049b5ef5f31f9f817dc25a5144644a1203f72a46aed3b7a60ede543239
PrismelierView.mc  7d3d267f2dece4ce748ef08a0ad832c31ef5176c11d6ae383da6a70e672fc06a
```

## Automated checks

Run the standard-library test suite from the project root:

```sh
python -m unittest discover -s tests -v
```

The structural checks require neither an SDK nor Pillow. They check the FR265
watch-face manifest, minimum API level, resource references, font page paths and
dimensions, required glyphs (including the old-location `*`), settings options,
permission scope, and specific data/solar/timezone source contracts.

Pillow enables the optional exhaustive ambient-display asset test. It uses the
committed Ambient BMFont atlas and metrics for all 1,440 times in both 12- and
24-hour formats. It counts every nonzero pixel, unions both possible integer
centering positions, and adds a conservative one-pixel halo. Each image must
use less than 10% of the circular 416px screen. It also unions every time in each
of the three display bands and verifies those unions are pairwise disjoint and
inside the screen. Thus no three successive minute bands can share lit pixels
in this asset model. Font PNGs are checked for RGB intensity storage without an
unexpected alpha channel; Pillow also checks that antialiased intensities exist.

These are asset-based estimates, not measurements from Garmin's graphics
renderer, simulator, display-luminance heuristic, or hardware. They cannot prove
device burn-in compliance, battery life, or appearance. The model deliberately
does not claim to execute Monkey C.

## Optional official SDK checks

```sh
CONNECTIQ_SDK=/path/to/official/connectiq-sdk \
  python -m unittest discover -s tests -v
```

`CIQ_SDK` (also used by the build helper) and `CIQ_HOME` are accepted aliases.
The suite checks API calls across all imported modules and reviewed instance
receivers against official SDK method IDs and argument counts. Unknown receivers
fail the check and require review. Module constants and weather-condition
constants are also checked. `AppBase.initialize()` has no API method anchor, so
that constructor is verified against Garmin's official Analog sample instead.
The new `String.find(string)` calls are documented and return an index or null;
the nonexistent `Math.min/max` calls are absent. These name/arity checks do not
perform type inference, app-context validation, or device-specific checking.

The suite additionally runs the official `monkeydoc` parser against all project
`.mc` files. No SDK is included, downloaded, or installed by the project or tests.

The official SDK 9.2.0 parser generated documentation for all four source files
without diagnostics during development. This establishes parser acceptance
only. A deliberately wrong return type was also accepted by `monkeydoc`, so this
is not a type check. A malformed-syntax negative control produced parser errors
despite exit status 0; the test therefore inspects diagnostics as well as exit
status. Re-run against the final sources after every source change.

## Body Battery support and freshness

The public `bodyBattery` field is a nullable 0–100 score, separate from the
device-charge `battery` field. It reads
[`SensorHistory.getBodyBatteryHistory`](https://developer.garmin.com/connect-iq/api-docs/Toybox/SensorHistory.html#getBodyBatteryHistory-instance_function),
which lists the FR265 and API 3.3.0. The existing `SensorHistory` permission and
minimum API 4.2.0 are sufficient. Garmin's SDK App Types matrix explicitly
allows SensorHistory in watch faces; the optional SDK test checks that cell.

The app asks for newest-first local history once per clock minute, or on an
existing forced refresh. It only accepts scores from 0 through 100 with a
non-future timestamp at most **900 seconds (15 minutes)** old. Zero remains a
valid score; missing, expired, invalid, unsupported, or failed reads produce
`null`, never an invented score. Cached timestamps are checked before the
minute throttle, so clock regressions and expiry clear the value promptly.

Fifteen minutes is this app's freshness policy, not a Garmin update guarantee.
The official SDK's *Quantifying the User* chapter says history is recorded
on-device, does not include synced data, and provides no guaranteed interval or
range. This implementation activates no sensors and transmits no health data.
The test suite checks these source contracts and official API support; actual
Body Battery behavior on the watch still needs runtime validation.

## Build and runtime blockers

- **FR265 compilation: not completed.** The official FR265 device profile is
  missing. The compiler cannot validate device-specific symbols, resources,
  memory limits, app restrictions, or generate a usable FR265 binary without it
- **Barrel type-check workaround: blocked.** Official SDK 9.2.0 `barrelbuild -l 3`
  with a minimal temporary library manifest returned `No valid devices could be
  found for building`, then `Barrel build failed`
- **SDK Manager: unavailable in this Linux environment.** Its installed official
  binary requires missing `libwebkit2gtk-4.0.so.37`, `libsoup-2.4.so.1`,
  `libjavascriptcoregtk-4.0.so.18`, and `libjpeg.so.8`; `DISPLAY` is unset
- **Simulator and physical watch: not tested.** PNG previews are explicitly
  design renders with illustrative values, not screenshots from either

Garmin's documented device-profile acquisition flow uses SDK Manager and a
Garmin account login. No login bypass, unofficial device profile, fabricated
compiler profile, or proprietary SDK redistribution was used. See
[Garmin setup](https://developer.garmin.com/connect-iq/connect-iq-basics/getting-started/).

## Required next validation

1. Install the official FR265 profile using Garmin SDK Manager
2. Build with warnings and type checking; resolve all device/resource errors
3. Run Garmin's FR265 simulator, including its always-on screen/heat-map checks
4. Test missing and disconnected weather, observations at 2h and 24h boundaries,
   unknown/future timestamps, no recent HR, Body Battery at 0/100/null and the
   15-minute cutoff, midnight, DST changes, travel,
   unavailable/polar solar events, and settings changes
5. Verify on an actual FR265: fonts, alignment, clipping, wrist activation,
   always-on transitions, freshness behavior, and sustained battery impact

API 5.0+ uses a less-than-10% luminance rule according to Garmin's
[System 7 announcement](https://forums.garmin.com/developer/connect-iq/b/news-announcements/posts/welcome-to-system-7).
The sparse, moving time-only ambient design is deliberately conservative, but
real firmware verification remains necessary.
