# Prismelier

A futuristic-steampunk digital watch face for the **Garmin Forerunner 265**. The default **Foundry** theme combines ebony-inspired wood grain, patinated copper, raised material relief and intricate robotics details.

![Prismelier Foundry design render](docs/preview.png)

*Source-backed design render with illustrative readings, not a Garmin simulator or watch screenshot.*

> **Development project.** The history records a successful FR265 compile in [7b1ac81](https://github.com/bensonlee5/prismelier/commit/7b1ac81b4a5427f47e087c29b294af84496ca59f). The performance revision has been compiled and profiled in the FR265 simulator, but still needs hardware validation. See [performance review](docs/PERFORMANCE.md) and [validation history](docs/QA.md).

## Features

- Prominent **digital time**, following the watch’s 12/24-hour preference
- **Temperature dial** with a 270° band, needle and labeled 0–120°F scale; no separate numeric temperature reading
- **Weekday rim** (`S M T W T F S`) with the current day highlighted, plus a local month/day display such as `Oct 24`
- Monoline **weather icons** and the next **sunrise or sunset time**, with distinct event icons
- **Device battery percentage** at top left and a separate **Body Battery score** at top right
- Recent **heart rate** and daily **steps**
- Sparse, dim, repositioning digital-time-only **always-on display**

The target is the **416 × 416 AMOLED Forerunner 265** (`fr265`). Compatibility with the 265S or other watches is not declared.

## Build and install

Follow the [build and USB installation guide](docs/INSTALL.md) for Linux, Windows or macOS:

1. Install Garmin’s official Connect IQ SDK, the **Forerunner 265 device profile** and the Monkey C tools
2. Configure a private signing key, build for `fr265`, and validate in Garmin’s simulator
3. Copy the resulting `.prg` to `GARMIN/APPS` over USB, disconnect safely and select Prismelier on the watch

Sideloading requires a computer. The iPhone Connect IQ app cannot import a raw development `.prg`, and there is no Garmin Store listing. Keep signing keys outside the repository.

### GitHub Actions

[Compile Forerunner 265](https://github.com/bensonlee5/prismelier/actions/workflows/compile.yml) is a **manually triggered, owner-only** workflow for trusted `main`. It requires a dedicated Linux x64 runner with the official SDK, FR265 profile and local signing key already provisioned. It uploads a PRG and checksums only after a successful compile.

**Runner setup is still required; no successful CI build has been verified.** Read the [CI setup and security guide](docs/CI.md) before registering a runner for this public repository. The workflow does not automatically run pull requests.

## Settings and data

Foundry and **Fahrenheit** are the defaults. Optional settings include Celsius/device units, explicit 12/24-hour time and three procedural color palettes: Reactor, Porcelain and Nocturne. See [settings instructions](docs/INSTALL.md#preferences); phone settings for unpublished sideloaded apps are not guaranteed.

Weather uses Garmin’s existing cache; sunrise/sunset uses the weather observation location, which may differ from your current position. The face cannot force a fresh weather observation. Old data is marked, and unavailable values are not replaced with demo readings. Heart rate is a recent sample; Body Battery is a wellness estimate, not a medical measurement. See [data setup and troubleshooting](docs/INSTALL.md#6-get-weather-solar-heart-rate-and-body-battery-working).

The face has no backend, API key or network permission. It does not activate GPS or transmit health data. Data is cached in RAM, and the textured background is omitted from AOD. Runtime memory use and battery impact still need device validation.

The [performance review](docs/PERFORMANCE.md) removes duplicate startup/wake reads,
caches solar calculations with freshness/invalidation guards, and precomputes
the fixed temperature-band geometry. The design and sparse AOD are preserved;
actual battery savings require watch measurements.

## Development

Run source and asset checks:

```sh
python -m unittest discover -s tests -v
```

With the official SDK and device profile installed:

```sh
python tools/build.py --sdk /path/to/connectiq-sdk --key /private/path/developer.der --release
```

Committed fonts and artwork are included. Optional design-preview generation uses Python, Pillow and locally installed DejaVu fonts:

```sh
python tools/render_preview.py
```

Passing source/parser checks does not establish native compilation or device compatibility. [QA details](docs/QA.md) document the checks performed and remaining validation.

## Credits

The Foundry texture is an AI-generated project asset; live icons and alternate-theme artwork are code-drawn. See [asset provenance and graphics budget](docs/TEXTURE.md). DejaVu font terms are included in the [font license](resources/fonts/LICENSE-DejaVu.txt).

Garmin, Forerunner and Connect IQ are trademarks of Garmin. Prismelier is an independent project and is not endorsed by Garmin.
