# TokNGauge — macOS tray assets

These resources are intended for a future native menu-bar wrapper
(Swift / SwiftUI). They are kept here, alongside `menubar-windows` and
`menubar-linux`, so contributors can pick them up without regenerating
artwork.

## Files

| File                  | Purpose                                            |
|-----------------------|----------------------------------------------------|
| `gauge.svg`           | Master vector logo (matches `static/icons/icon.svg`) |
| `AppIcon.icns`        | macOS app icon bundle (Dock / Finder / Cmd-Tab)    |
| `TrayIcon@1x.png`     | Template image for the menu bar at 1× (32×32)      |
| `TrayIcon@2x.png`     | Retina variant (64×64)                             |

For a true "template" rendering on macOS dark/light menu bars, re-export
`TrayIcon*.png` as monochrome black + alpha and load the image with
`isTemplate = true`.

## Regenerating

```bash
python scripts/build_icons.py
cp static/icons/icon.icns apps/menubar-mac/Resources/AppIcon.icns
cp static/icons/icon-32.png apps/menubar-mac/Resources/TrayIcon@1x.png
cp static/icons/icon-64.png apps/menubar-mac/Resources/TrayIcon@2x.png
```
