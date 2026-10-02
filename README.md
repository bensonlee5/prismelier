# Prismelier

A copper-and-wood watch face with time, weather, sunrise/sunset, Body Battery, heart rate, and steps.

![Prismelier on Forerunner 265](docs/screenshots/full-redraw-final-fr265.png)

## Features

| Feature | What you see |
|---|---|
| Time & date | 12/24-hour time, weekday, month and day |
| Temperature | Current-temperature needle and today's low–high range; °F or °C |
| Weather | Condition icon and label, humidity, and today's rain chance |
| Sun | Next sunrise or sunset time |
| Battery | Watch charge percentage and separate Body Battery score |
| Activity | Heart rate and daily steps |
| Always-on | Dim, time-only display while resting |
| Themes | Foundry, Reactor, Porcelain, and Nocturne |

## Download

Choose your **exact watch model**. The 265 and 265S use different files.

| Watch | Download |
|---|---|
| Forerunner 265 | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fr265/Prismelier-fr265.prg) |
| Forerunner 265S | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fr265s/Prismelier-fr265s.prg) |
| Forerunner 165 | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fr165/Prismelier-fr165.prg) |
| Forerunner 165 Music | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fr165m/Prismelier-fr165m.prg) |
| Forerunner 965 | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fr965/Prismelier-fr965.prg) |
| Forerunner 970 | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fr970/Prismelier-fr970.prg) |
| Venu 2 | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/venu2/Prismelier-venu2.prg) |
| Venu 2 Plus | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/venu2plus/Prismelier-venu2plus.prg) |
| Venu 3 | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/venu3/Prismelier-venu3.prg) |
| Venu 3S | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/venu3s/Prismelier-venu3s.prg) |
| epix (Gen 2) | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/epix2/Prismelier-epix2.prg) |
| epix Pro (Gen 2) 47mm | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/epix2pro47mm/Prismelier-epix2pro47mm.prg) |
| fēnix 8 43mm | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fenix843mm/Prismelier-fenix843mm.prg) |
| fēnix 8 47mm / 51mm | [Download .prg](https://github.com/bensonlee5/prismelier/raw/refs/heads/main/dist/models/fenix847mm/Prismelier-fenix847mm.prg) |

Forerunner 265 has been checked in Garmin’s simulator. Other models are experimental and have not been visually tested on their watches.

## Install

1. Download your model’s `.prg` file above.
2. Connect the watch to your computer by USB and copy the file into its existing `GARMIN/APPS` folder. On macOS, use an MTP file-transfer app if the watch does not appear in Finder.
3. Disconnect the watch. Hold **UP/MENU → Watch Face**, choose **Prismelier**, and apply it (menus vary by model).

No SDK is needed. The phone’s Connect IQ app cannot install these files. [Detailed USB instructions](docs/INSTALL.md#4-copy-the-prg-over-usb).

The default is Foundry with Fahrenheit and your watch’s time format. [Change preferences](docs/INSTALL.md#preferences). Weather requires a recent Garmin Connect sync; missing readings appear as `--`.
