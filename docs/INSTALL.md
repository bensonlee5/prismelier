# Build and load Prismelier on a Forerunner 265

## Current release status

A prebuilt **Forerunner 265-only** `.prg` is available from the [README download link](../README.md#build-and-install). Download it and skip to [USB installation](#4-copy-the-prg-over-usb), or build your own using the steps below. See the [README status](../README.md#status) for validation limits. There is no Connect IQ Store listing.

## 1. Set up Garmin's official tools

Use a Windows PC, Mac, or Ubuntu Linux computer. Garmin documents **Ubuntu** for its Linux SDK; other Linux distributions may need additional library work. An iPhone alone cannot do this raw-file sideload.

1. Download **SDK Manager** from [Garmin's official SDK page](https://developer.garmin.com/connect-iq/sdk/). Review the developer agreement before accepting it
2. Start SDK Manager and sign in to your Garmin account through its own login interface. Do not put your password in this repository or a terminal command
3. Install the latest stable Connect IQ SDK and set it active. **Also install/update the Forerunner 265 device definition** in the Devices section. Downloading the SDK ZIP alone does not install the device profiles
4. Install [Visual Studio Code](https://code.visualstudio.com/) and the **Monkey C** extension published by **Garmin** from its Extensions view
5. Install the Java runtime required by the extension (Garmin documents Java 11 or newer). In VS Code, open the command palette and run **Monkey C: Verify Installation**
6. Create a private developer signing key using **Monkey C: Generate a Developer Key**. Save it outside the repository. Keep a private backup for future updates; do not upload or commit it. The key file needs no particular extension: the extension saves it as `developer_key` by default, and the examples below use that name

Official references: [Getting Started](https://developer.garmin.com/connect-iq/connect-iq-basics/getting-started/) and [VS Code extension](https://developer.garmin.com/connect-iq/reference-guides/visual-studio-code-extension/).

## 2. Open and build the project

1. Download this repository with **Code → Download ZIP**, then extract it, or clone it with Git
2. In VS Code choose **File → Open Folder** and select the folder containing `manifest.xml` and `monkey.jungle`
3. Open `source/PrismelierView.mc`
4. Run **Monkey C: Verify Installation** again if the SDK/key configuration has changed
5. Run **Monkey C: Build for Device** from the command palette. Choose **Forerunner 265**, then an output folder
6. The output is a `.prg` file. Copy **that file**, not the source ZIP or an `.iq` store-export package

For CLI builds, with the official device profile already installed:

```sh
python tools/build.py --sdk /path/to/connectiq-sdk --key /private/path/developer_key --release
```

The output is `build/Prismelier.prg`. On Windows quote paths with spaces; the helper selects `monkeyc.bat`. It never downloads proprietary SDK files, generates credentials, or tries another watch target behind your back.

For a direct compiler invocation:

```sh
monkeyc -f monkey.jungle -d fr265 -o build/Prismelier.prg -y /private/path/developer_key -r -w -l 1
```

Create `build` first. Use the full path to `monkeyc`/`monkeyc.bat` if it is not on your PATH. **Do not change the device to 265S** to get around a profile error.

## 3. Test in the real Garmin simulator first

With a source file selected, use **Run → Run Without Debugging** and choose Forerunner 265. Work through the simulator items in [QA](QA.md#open-validation), especially no-weather startup and low-power mode. Simulator values are test fixtures, not your personal data. A successful simulator run still does not prove hardware battery life or weather sync.

## 4. Copy the `.prg` over USB

Use a **data-capable Garmin USB charging cable**. Wait for any sync/file operations to finish first. If the watch asks for USB/file-transfer mode, accept the file-transfer mode. If necessary, check **System → USB Mode**; the exact label can vary by firmware. Never format the device or overwrite its system files.

Garmin's required destination is **`GARMIN/APPS`**. Folder capitalization may be presented as `Garmin/Apps` by a file manager. Use the existing folders.

### Linux (your computer)

1. Connect the watch and open Files/Nautilus, Dolphin, or your normal desktop file manager
2. Look under **Devices** for the Forerunner/Garmin, then open its internal/primary storage if shown
3. Open **GARMIN → APPS**, and copy in the built `.prg`
4. Wait for the copy to finish. Eject/unmount using the file manager if that option is shown, then unplug

The FR265 uses MTP. Many Linux desktops provide MTP through their existing file manager backend; availability depends on the distribution. It may **not** appear as an ordinary `/media/...` drive. If it is not listed, install your distribution's normal MTP/file-manager support, reconnect and try again. Do not run a guessed `cp` command against a nonexistent mount point. Garmin Express is not required for copying the file, and Garmin does not provide a Linux version of Express.

### Windows

1. Connect the watch, then open **File Explorer → This PC → Forerunner 265**
2. Open **Primary/Internal Storage** if shown, then **GARMIN → APPS**
3. Copy the `.prg`, wait for completion, safely disconnect where offered, and unplug

Close Garmin Express or other Garmin programs if another application already has exclusive access to the MTP device.

### macOS

You can build and run the simulator on a Mac. However, the FR265's MTP storage generally **does not appear as a normal Finder drive**. Garmin's current support guidance recommends Windows to access these devices' folders.

Garmin's supported folder-access route is to move the `.prg` to a Windows computer, then follow the Windows steps above. Do not expect Garmin Express to import an arbitrary development `.prg`.

**Mac alternative tested on 1 October 2026:** Homebrew's `libmtp` 1.1.23 successfully copied this build to an FR265, and reading the file back produced an identical SHA-256 checksum. This validates transfer, not the watch's installation or rendering. Close competing MTP applications first:

```sh
brew install libmtp
mtp-detect
mtp-folders
# Confirm Forerunner 265 and the existing GARMIN/Apps folder in the output.
mtp-sendfile Prismelier-fr265.prg /GARMIN/Apps
```

Run the last command from the folder containing your downloaded `.prg`, or substitute its local path. The second argument is the **existing destination folder**, not a filename. Confirm the output reaches 100% and reports a new file ID; a zero exit code alone does not guarantee a copy. After the command finishes and releases the device, unplug and select the face below.

Sources: [Garmin sideload instructions](https://developer.garmin.com/connect-iq/connect-iq-basics/your-first-app/), [Garmin MTP guidance](https://support.garmin.com/en-US/?faq=CZqibgTHMb0dAYEaj2UiU7), [Mac folder-access guidance](https://support.garmin.com/en-IN/?faq=4NnyLlu0o5ASH4BVZ6QWPA).

## 5. Select the face

After unplugging, give the watch a moment to install the file. From the current watch face:

1. Hold **UP**
2. Select **Watch Face**
3. Scroll to **Prismelier**
4. Press **START**, then choose **Apply** if prompted

If absent, restart the watch once and recheck. If it still does not appear, use the troubleshooting checklist; do not copy random files into other system folders.

## 6. Get weather, solar, heart rate and Body Battery working

- Pair the watch with **Garmin Connect on your iPhone**, and let it sync
- Keep Bluetooth connected and allow Garmin Connect the background/location access it needs for Garmin's own weather feature. Choose the permissions yourself in iOS
- First check the watch's **native Weather glance**. If Garmin itself has no current weather, this face cannot manufacture it
- The gauge is **outdoor weather temperature**, not the wrist/ambient sensor, which can be distorted by body heat
- Solar calculations use the weather observation's location; no GPS session is started by this face. A stale station/location can be wrong after travel
- Wear the watch with wrist HR enabled. HR appears only when a valid, timestamped sample is at most two minutes old
- Body Battery uses recent local watch history; keep wearing the watch for Garmin to establish a score. The top-right person/bolt value is a 0–100 score, not battery-charge percentage. It becomes `--` when no valid sample is available within 15 minutes
- Allow the face to read the listed Sensor History/Positioning permissions during installation if prompted

The watch, firmware and Garmin Connect decide weather refresh timing. Polling the API more often does not force an update.

## Preferences

The reliable options for a **sideloaded, unpublished** development build are:

- Change the watch's **time format**; it is followed by default. Temperature defaults explicitly to **Fahrenheit**, independent of system units
- Or edit `resources/settings/properties.xml` before rebuilding:
  - `Palette`: `0` Reactor (lime/violet/cyan), `1` Foundry (copper/teal, default), `2` Porcelain (ivory/charcoal), `3` Nocturne (midnight/amber)
  - `TimeFormat`: `0` watch setting, `1` 12-hour, `2` 24-hour
  - `TemperatureUnits`: `2` Fahrenheit (default), `1` Celsius, `0` watch setting
- In the simulator, use its app-settings editor to exercise the provided settings schema

Sideloaded apps may not appear with editable settings in Garmin Connect/Connect IQ on the phone. This repository does not promise that phone flow. If an existing sideload retains old property values, test the new configuration in the simulator and use the watch's normal uninstall/reinstall flow if you deliberately want to reset its settings.

## Troubleshooting

| Symptom | Check |
|---|---|
| `Invalid device id: fr265` / empty build target list | Install the **Forerunner 265 device profile**, not only the SDK. Keep the manifest target as `fr265` |
| Linux SDK Manager missing WebKit/JPEG libraries | Follow Garmin's supported Ubuntu setup. Do not download random replacement `.so` binaries or make incompatible library symlinks |
| No watch storage visible | Data cable, USB mode, working MTP support, and no competing MTP application |
| Face does not appear | Correct 265 build, `.prg` copied to `GARMIN/APPS`, completed transfer, disconnect and restart |
| IQ error symbol | Return to a built-in face; inspect Garmin's developer error logs privately. Do not publish logs containing personal data |
| Empty temperature band / no needle / crossed weather icon | Check native Weather glance, Garmin Connect sync, phone location permissions and watch time |
| Muted gauge, crossed weather icon and small crossed-ring warning | Cache is at least 2h old; readings disappear at 24h or when age cannot be verified |
| Solar insert `--:--` | No usable weather location or no sunrise/sunset in the queried window; can occur in polar regions |
| HR `--` | Watch not worn, wrist HR disabled, or no recent valid sample |
| Person/bolt Body Battery `--` | No valid score in the last 15 minutes, or its timestamp cannot be verified; check Garmin's native Body Battery glance |
| Screen becomes mostly empty | Normal low-power/AOD design; raise wrist to restore the full face |
| AOD is off entirely | Watch display setting, sleep mode, firmware protection, or an AOD issue. This requires simulator/device validation |

To remove it, first select a built-in watch face. Use the watch/app's normal uninstall option if exposed, or remove only this sideloaded `.prg` from `GARMIN/APPS`. Do not remove other apps or system data.
