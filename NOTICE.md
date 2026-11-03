# Source notices

Game Shelf is an independent Omarchy plugin, not an official Omarchy or HyDE release.

Own native UI/controller integration: GPL-3.0-only. Installed Omarchy `qs.Ui` and `qs.Commons` are imported, not bundled.

`runtime/0.4.1/BoundedProcess.qml` adapts Battlelamb/omarchy-native-overview@759521b73df88fb437f21586517c97214c638ffc, original path `runtime/0.2.0/BoundedProcess.qml` (GPL-3.0-only), adding an explicit request deadline property. Native host admission patterns are adapted from that release's `runtime/0.2.0/Overview.qml`; `tests/native-io.cjs` adapts its `tests/native-io.test.cjs` (GPL-3.0-only), adding the configurable-deadline case/control. Full licence in LICENSE.

HyDE reference snapshot: HyDE-Project/HyDE@fa2fd57afc7203b1b5653d3271f3a57ea3873f97. Exact backend/dataset adaptation and separate third-party rights: see NOTICE.backend.md. No wallpaper, font or screenshot asset is bundled merely because it appeared in a donor preview.

## Preview assets

`preview.png` is an actual native Qt capture with explicitly illustrative catalogue data, not an installed-app inventory or proof of external actions. The original geometric artwork and monograms are GPL-3.0-only; corresponding SVG sources are in `docs/preview-source/` where applicable. Native UI source is in the versioned runtime. No Mosaic branding, code or artwork is copied. Installed font/component rights remain with their original licensors; no font binary is bundled. See `docs/PREVIEW.md`.
