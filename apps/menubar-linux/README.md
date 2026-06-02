# TokNGauge — Linux tray / desktop assets

These are the assets a packager (`.deb`, `.rpm`, Flatpak, AppImage) or a
native tray wrapper (e.g. `libappindicator`, `pystray`) would consume.

## Files

| File                   | Install location (FHS)                              |
|------------------------|-----------------------------------------------------|
| `tokngauge.svg`        | `/usr/share/icons/hicolor/scalable/apps/`           |
| `tokngauge.png`        | `/usr/share/icons/hicolor/256x256/apps/`            |
| `tokngauge-tray.png`   | indicator / panel applet                            |
| `tokngauge.desktop`    | `/usr/share/applications/`                          |

## Quick local install

```bash
install -Dm644 apps/menubar-linux/data/tokngauge.svg \
  ~/.local/share/icons/hicolor/scalable/apps/tokngauge.svg
install -Dm644 apps/menubar-linux/data/tokngauge.png \
  ~/.local/share/icons/hicolor/256x256/apps/tokngauge.png
install -Dm644 apps/menubar-linux/data/tokngauge.desktop \
  ~/.local/share/applications/tokngauge.desktop
update-desktop-database ~/.local/share/applications || true
gtk-update-icon-cache ~/.local/share/icons/hicolor || true
```
