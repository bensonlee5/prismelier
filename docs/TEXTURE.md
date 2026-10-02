# Foundry material asset and graphics budget

The latest Foundry face uses an actual static raster resource, not a texture pasted only into a promotional mockup. All time, temperature, weekdays, date, percentages, scores, steps and condition/event icons are overlaid live by Monkey C. The asset itself contains **no display readings or UI icons**.

- Runtime source: `resources/textures/foundry-background-indexed.png`
- Native dimensions: **416 × 416**, opaque 8-bit indexed PNG, at most **256 colors**
- Source PNG file size: **109,779 bytes (107.2 KiB)**
- Resource: `Rez.Drawables.FoundryBackground`, declared in `resources/textures/textures.xml`
- Resource settings: native/default packing, automatic palette, no dithering, compression, transparency disabled
- Only Foundry uses the raster; the three alternate palettes retain the procedural artwork
- Selected-A source fixture: [`docs/screenshots/selected-a-source-preview.png`](screenshots/selected-a-source-preview.png); native simulator validation is pending
- Icon family: original 2px monoline pictograms at 416px, not platform emoji or baked-in imagery

The artwork combines convex lacquered ebony-inspired hardwood with fine, directional dark-brown and graphite grain, raised machined copper/brass, deep teal patina, satin dark ceramic and an ivory ceramic solar tile. Raised inlays and rims use upper-left highlights and lower-right contact shadows/occlusion; recessed wells keep the live graphics clear. Hardware contact shadows and bevels are static. Clean readout wells preserve legibility. Meaningful material pixels remain inside a 204px radius (the round display is 208px), avoiding clipped crown corners. Graphics remain motionless rather than animated.

## What the memory numbers mean

Garmin's official SDK 9.2 FR265 device reference lists **416 × 416**, **65,536 screen colors**, and a **131,072-byte watch-face application memory limit**. API 4+ bitmap/font data uses a separate graphics pool; its specific FR265 capacity was not verified. The application-heap number is **not** a maximum PNG file size.

Planning estimates for a single 416px pixel plane, before headers, palette and allocator overhead:

- 8-bit indexed: **173,056 bytes / 169 KiB**
- 16-bit RGB565: **346,112 bytes / 338 KiB**

The 107.2 KiB PNG size is compressed storage, **not a runtime RAM measurement**. The bitmap lives in the graphics pool, not the app heap; in the previous release’s simulator measurements, drawing its earlier texture cost no more than the vector themes' artwork (see [PERFORMANCE](PERFORMANCE.md#simulator-profile-1-october-2026)). Graphics-pool occupancy and on-watch decode cost remain unmeasured.

The implementation keeps one resource reference and loads it outside `onUpdate`. It never calls the reference's `get()` to pin pixel data and never creates another full-screen `BufferedBitmap`. Garmin may still evict/redecode the resource behind that reference. Recoverable resource load/draw errors attempt a procedural fallback; fatal VM memory errors are not claimed to be recoverable.

The sleeping branch returns before any bitmap or ornate artwork is drawn. AOD remains the existing sparse dim digital time. The image is opaque and static; there are no animations, alpha layers, image downloads or timers on the watch.

Sources: [FR265 device reference](https://developer.garmin.com/connect-iq/device-reference/fr265/), [Graphics and graphics pool](https://developer.garmin.com/connect-iq/core-topics/graphics/), [Bitmap resources and packing](https://developer.garmin.com/connect-iq/articles/core-topics/Resources.html).

## Asset provenance and reproduction

The user selected the latest A paired-rails composition on 2 October 2026. Its new blank material artwork was generated with OpenAI image generation; interface overlays were rendered deterministically in the reference SVG. The exact Library source (`libfile_316658af04f081918d97ab53596e9315`) is 1254 × 1254, SHA-256 `64db7ec171b512ba44f4832793ff6aed64f2ee54c09a30a3e6ed0d7545ab3eeb`. It was inspected, resized without cropping with Lanczos to 416 × 416, and packed as an opaque 256-color PNG without dithering. The selected reference and immutable geometry spec are committed under `docs/screenshots/selected-a-reference.png` and `docs/design/selected-a.json`. No live values are baked into the runtime texture.

The committed native-resolution asset is sufficient to build. Optional deterministic packing of a newly selected source image:

```sh
python tools/prepare_texture.py /path/to/selected-background.png
```

The chosen packed PNG has SHA256 `90429faa8bc80e696195bea68618378f2f37997a3903b0e2bb00c3c48ea105ee`.

Live overlays are positioned in `source/PrismelierView.mc`: time at y=77 (with the AM/PM mark inside the visor), month/day at y=176, temperature dial centered at (133,263) with its unit below the hub, weather icon and condition word to its right, and sensor values at y=329. `tests/test_layout_revision.py` checks text against each well using the committed font metrics. Inspect new artwork in the simulator against every state before replacing the runtime resource.
