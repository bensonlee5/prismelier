# Foundry material asset and graphics budget

The latest Foundry face uses an actual static raster resource, not a texture pasted only into a promotional mockup. All time, temperature, weekdays, date, percentages, scores, steps and condition/event icons are overlaid live by Monkey C. The asset itself contains **no display readings or UI icons**.

- Runtime source: `resources/textures/foundry-background-indexed.png`
- Native dimensions: **416 × 416**, opaque 8-bit indexed PNG, at most **256 colors**
- Source PNG file size: **119,661 bytes (116.9 KiB)**
- Resource: `Rez.Drawables.FoundryBackground`, declared in `resources/textures/textures.xml`
- Resource settings: native/default packing, automatic palette, no dithering, compression, transparency disabled
- Only Foundry uses the raster; the three alternate palettes retain the procedural artwork
- Simulator screenshot: [`docs/screenshots/foundry.png`](screenshots/foundry.png)
- Icon family: original 2px monoline pictograms at 416px, not platform emoji or baked-in imagery

The artwork combines convex lacquered ebony-inspired hardwood with fine, directional dark-brown and graphite grain, raised machined copper/brass, deep teal patina, satin dark ceramic and an ivory ceramic solar tile. Raised inlays and rims use upper-left highlights and lower-right contact shadows/occlusion; recessed wells keep the live graphics clear. Hardware contact shadows and bevels are static. Clean readout wells preserve legibility. Meaningful material pixels remain inside a 204px radius (the round display is 208px), avoiding clipped crown corners. Graphics remain motionless rather than animated.

## What the memory numbers mean

Garmin's official SDK 9.2 FR265 device reference lists **416 × 416**, **65,536 screen colors**, and a **131,072-byte watch-face application memory limit**. API 4+ bitmap/font data uses a separate graphics pool; its specific FR265 capacity was not verified. The application-heap number is **not** a maximum PNG file size.

Planning estimates for a single 416px pixel plane, before headers, palette and allocator overhead:

- 8-bit indexed: **173,056 bytes / 169 KiB**
- 16-bit RGB565: **346,112 bytes / 338 KiB**

The 116.9 KiB PNG size is compressed storage, **not a runtime RAM measurement**. The bitmap lives in the graphics pool, not the app heap; in the simulator, drawing it costs no more than the vector themes' artwork (see [PERFORMANCE](PERFORMANCE.md#simulator-profile-1-october-2026)). Graphics-pool occupancy and on-watch decode cost remain unmeasured.

The implementation keeps one resource reference and loads it outside `onUpdate`. It never calls the reference's `get()` to pin pixel data and never creates another full-screen `BufferedBitmap`. Garmin may still evict/redecode the resource behind that reference. Recoverable resource load/draw errors attempt a procedural fallback; fatal VM memory errors are not claimed to be recoverable.

The sleeping branch returns before any bitmap or ornate artwork is drawn. AOD remains the existing sparse dim digital time. The image is opaque and static; there are no animations, alpha layers, image downloads or timers on the watch.

Sources: [FR265 device reference](https://developer.garmin.com/connect-iq/device-reference/fr265/), [Graphics and graphics pool](https://developer.garmin.com/connect-iq/core-topics/graphics/), [Bitmap resources and packing](https://developer.garmin.com/connect-iq/articles/core-topics/Resources.html).

## Asset provenance and reproduction

The background was generated with OpenAI’s built-in image-generation tool from this project's updated procedural geometry guide and its earlier Foundry texture as references. A second focused pass strengthened raised relief, bevel depth and directional contact shadows without moving the readout wells. The user selected the ebony-inspired wood study: a focused material-only edit replaced the earlier figured wood with clear directional grain while preserving the same panels, metalwork, relief and readout wells. The selected candidate is used unchanged as the actual Foundry resource. It was downsampled directly to 416 × 416 with Lanczos, then packed into an opaque 256-color indexed PNG with no dithering. The geometry guide already includes the black circular safe margin. The selected source image was 1254 × 1254. A user-supplied instrument reference informed the graduated band and calendar layout; that personal reference photo is **not** distributed with this project. No personal readings, credentials, third-party watch artwork or logos are baked into the asset.

The committed native-resolution asset is sufficient to build. Optional deterministic packing of a newly selected source image:

```sh
python tools/prepare_texture.py /path/to/selected-background.png
```

Generation direction, condensed:

> Preserve the exact geometry guide: two top metric capsules, large upper digital-time visor, small date plate, lower-left circular temperature well, right-side weather bay and pale solar tile, lower health readout and seven outer weekday pockets. The original relief pass used polished figured walnut/cocobolo wood, copper/brass with gleaming rubbed edges and deep patina, petrol enamel and intricate robotics circuitry. Orthographic front view, no watch body or wrist. Leave all readout wells empty. No text, values, icons, clock indices, hands, temperature needle or band; these are live overlays.

Relief refinement direction:

> Keep all panel positions and the silhouette unchanged. Give proud wood inlays and metal ribs substantial edge thickness, recessed display/gauge wells, undercut lips, raised fastener heads, upper-left specular bevel highlights and soft lower-right contact shadows. Preserve quiet, dark text wells and readable light ceramic. Static material relief, not animated 3D rendering.

Selected ebony material direction:

> Change only the wood to ebony-inspired hardwood: nearly black chocolate/graphite with subtle warm-brown long straight fibers and clear directional grain. No burl, floral figures, rosettes or swirls. Retain the polished sheen, readable grain, raised profiles, bevel thickness, existing lighting, copper/brass, teal patina, electronics, silhouette and exact readout-well geometry.

The chosen packed PNG has SHA256 `f9da729f8e2a1c66d35960f19ae08a2609bbae42428d4e2b6c44a4051b808ff4`.

Live overlays are positioned in `source/PrismelierView.mc`: time at y=77 (with the AM/PM mark inside the visor), month/day at y=175, temperature dial centered at (137,267) with its unit below the hub, weather icon and condition word to its right, and sensor values at y=338. `tests/test_layout_revision.py` checks text against each well using the committed font metrics. Inspect new artwork in the simulator against every state before replacing the runtime resource.
