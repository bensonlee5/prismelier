# Foundry material asset and graphics budget

The latest Foundry face uses an actual static raster resource, not a texture pasted only into a promotional mockup. All time, temperature, percentages, scores, steps and condition/event icons are overlaid live by Monkey C. The asset itself contains **no display readings or UI icons**.

- Runtime source: `resources/textures/foundry-background-indexed.png`
- Native dimensions: **416 × 416**, opaque 8-bit indexed PNG, at most **256 colors**
- Source PNG file size: **84,734 bytes (82.7 KiB)**
- Resource: `Rez.Drawables.FoundryBackground`, declared in `resources/textures/textures.xml`
- Resource settings: native/default packing, automatic palette, no dithering, compression, transparency disabled
- Only Foundry uses the raster; the three alternate palettes retain the procedural artwork
- Source-backed preview: `docs/preview-416.png`; the renderer loads the very same indexed file
- Icon family: original 2px monoline pictograms at 416px, not platform emoji or baked-in imagery

The artwork combines brushed/aged copper, patinated teal circuitry, satin dark ceramic, a worn ivory ceramic tile and minute laminate/grain details. Hardware contact shadows and bevels are static. Clean readout wells preserve legibility. Meaningful material pixels remain inside a 203px radius (the round display is 208px), avoiding clipped crown corners. Graphics remain motionless rather than animated.

## What the memory numbers mean

Garmin's official SDK 9.2 FR265 device reference lists **416 × 416**, **65,536 screen colors**, and a **131,072-byte watch-face application memory limit**. API 4+ bitmap/font data uses a separate graphics pool; its specific FR265 capacity was not verified. The application-heap number is **not** a maximum PNG file size.

Planning estimates for a single 416px pixel plane, before headers, palette and allocator overhead:

- 8-bit indexed: **173,056 bytes / 169 KiB**
- 16-bit RGB565: **346,112 bytes / 338 KiB**

The 82.7 KiB PNG size is compressed storage, **not a runtime RAM measurement**. The actual compiler encoding, graphics-pool occupancy, app heap, decode cost and battery impact still require the official FR265 profile and simulator/hardware. No native memory-fit or battery-life claim is made.

The implementation keeps one resource reference and loads it outside `onUpdate`. It never calls the reference's `get()` to pin pixel data and never creates another full-screen `BufferedBitmap`. Garmin may still evict/redecode the resource behind that reference. Recoverable resource load/draw errors attempt a procedural fallback; fatal VM memory errors are not claimed to be recoverable.

The sleeping branch returns before any bitmap or ornate artwork is drawn. AOD remains the existing sparse dim digital time. The image is opaque and static; there are no animations, alpha layers, image downloads or timers on the watch.

Sources: [FR265 device reference](https://developer.garmin.com/connect-iq/device-reference/fr265/), [Graphics and graphics pool](https://developer.garmin.com/connect-iq/core-topics/graphics/), [Bitmap resources and packing](https://developer.garmin.com/connect-iq/articles/core-topics/Resources.html).

## Asset provenance and reproduction

The background was generated with OpenAI's built-in image-generation tool from this project's procedural Foundry render as a geometry reference. It was then resized with Lanczos to a 384px interior, centered with 16px black padding inside a 416px canvas, and packed into an opaque 256-color indexed PNG with no dithering. The selected source image was 1254 × 1254. No stock texture, watch-brand image, personal health record or credential is included.

The committed native-resolution asset is sufficient to build. Optional deterministic packing of a newly selected source image:

```sh
python tools/prepare_texture.py /path/to/selected-background.png
```

Generation prompt, condensed without changing the art direction:

> Create a hyperreal static background plate for a 416px digital Garmin watchface, preserving the attached Foundry layout. Straight-on orthographic macro material rendering, no watch case or strap. Remove all numbers, lettering, values and UI icons; leave calm dark readout wells and a pale ceramic solar tile. Keep the top capsules, large time aperture, horizontal temperature track, grouped weather/solar wells, bottom sensor wells and processor in their existing positions. Real aged/brushed copper with fine machining marks; patinated teal PCB solder mask with laminated edges and tiny vias; dark satin ceramic; subtle timber-laminate fused into metal; a worn ivory ceramic insert. Intricate connector pins, flex traces, miniature fasteners and actuator hardware. Raking soft light from upper left, realistic contact shadows and shallow bevels, no perspective tilt. Restrained aged-copper/teal/ivory/charcoal palette. No baked-in data, logos, text, analog clock marks, neon glow, toy plastic or watermark.

The original exact layout constraints additionally specified the quiet-zone coordinates on the 416px reference. Small live-render anchor adjustments were made to fit the resulting material wells; these same coordinates are used by the source and preview compositor. Always inspect a newly generated asset against every data state before replacing the runtime resource.
