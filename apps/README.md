# TokNGauge — Tray / menu-bar apps

Each platform has a tiny tray application that:

- Launches `server.py` as a child process (kills it on quit).
- Shows a minimalist gauge glyph in the system tray / menu bar (thin
  strokes, no background — matches the favicon style).
- On click, opens a small **embedded** web view (760×720) pointing at
  `http://localhost:8770` so you don't need to alt-tab to a browser.
- Provides a context menu: *Reload*, *Open in browser*, *Restart server*,
  *Quit*.

| OS       | Launcher                                                                  | UI toolkit                       |
|----------|---------------------------------------------------------------------------|----------------------------------|
| macOS    | [`apps/menubar-mac/tray.py`](menubar-mac/tray.py)                         | PyObjC + WKWebView (NSPopover)   |
| Linux    | [`apps/menubar-linux/tray.py`](menubar-linux/tray.py)                     | `pystray` + `pywebview` (GTK/Qt) |
| Windows  | [`apps/menubar-windows/tray.py`](menubar-windows/tray.py)                 | `pystray` + `pywebview` (WebView2) |

The cross-platform implementation (Linux + Windows) lives in
[`apps/_tray_app.py`](_tray_app.py); macOS has its own native file because
it uses PyObjC directly.

---

## Prerequisites (all platforms)

1. Clone the repo and create a venv at the repo root:
   ```bash
   python3 -m venv .venv
   ```
2. Activate it and install the base server deps:
   ```bash
   # macOS / Linux
   source .venv/bin/activate
   pip install -r requirements.txt

   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

The tray launchers will automatically prefer `.venv/bin/python`
(`.venv\Scripts\python.exe` on Windows) when spawning the server, so the
server inherits the same environment.

---

## macOS

### Install tray-only deps

```bash
source .venv/bin/activate
pip install pyobjc-framework-Cocoa pyobjc-framework-WebKit
```

### Run

```bash
python apps/menubar-mac/tray.py
```

You should see a small gauge glyph appear in the menu bar (top right of
the screen). The icon is a **template image**, so macOS automatically
tints it black in light mode and white in dark mode — the same way
system icons behave.

- **Left-click** the icon → toggles an `NSPopover` with the TokNGauge UI
  embedded via `WKWebView`.
- **Right-click** (or Ctrl-click) → menu with *Open in browser*,
  *Restart server*, *Reload web view*, *Quit TokNGauge*.

No Dock icon is added (`NSApplicationActivationPolicyAccessory`), so it
behaves like a true menu-bar utility.

### Run at login (optional)

Create a LaunchAgent at `~/Library/LaunchAgents/com.tokngauge.tray.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.tokngauge.tray</string>
  <key>ProgramArguments</key>
  <array>
    <string>/ABSOLUTE/PATH/TO/ToknGauge/.venv/bin/python</string>
    <string>/ABSOLUTE/PATH/TO/ToknGauge/apps/menubar-mac/tray.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
</dict>
</plist>
```

Then load it: `launchctl load ~/Library/LaunchAgents/com.tokngauge.tray.plist`.

---

## Linux

### System packages

`pywebview` needs a WebKit backend. Choose **one**:

- **GTK / WebKit2GTK** (recommended on GNOME / XFCE):
  ```bash
  # Debian / Ubuntu (dev headers required to build PyGObject/pycairo in a venv)
  sudo apt install gir1.2-webkit2-4.1 python3-gi gir1.2-gtk-3.0 libcairo2-dev \
                   python3-dev libgirepository1.0-dev \
                   gir1.2-ayatanaappindicator3-0.1
  # Fedora
  sudo dnf install webkit2gtk4.1 python3-gobject gtk3
  ```
- **Qt / QtWebEngine** (alternative):
  ```bash
  sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine
  ```

`pystray` works best with an **AppIndicator**-compatible panel:

- GNOME users: install the [AppIndicator and KStatusNotifierItem
  Support](https://extensions.gnome.org/extension/615/appindicator-support/)
  extension, otherwise the icon won't appear.
- KDE / XFCE / Cinnamon / MATE / Budgie: works out of the box.
- Wayland-only sessions can be flaky — XWayland is the safest path.

### Python deps

```bash
source .venv/bin/activate
# GTK backend
pip install pystray "pywebview[gtk]" Pillow cairosvg
# OR: Qt backend
pip install pystray "pywebview[qt]" Pillow cairosvg
```

### Run

```bash
python apps/menubar-linux/tray.py
```

- Default-click on the indicator opens / focuses the embedded window.
- The full menu is always available via right-click.
- If your panel has a light background, the black glyph is correct. For a
  dark panel, edit `apps/_tray_app.py` and switch the Linux branch in
  `color = (255, 255, 255) if os.name == "nt" else (0, 0, 0)` to white.

### Run at login (optional)

The repo already ships a desktop entry at
[`apps/menubar-linux/data/tokngauge.desktop`](menubar-linux/data/tokngauge.desktop).
For the **tray** instead of the bare server, create your own:

```ini
# ~/.config/autostart/tokngauge-tray.desktop
[Desktop Entry]
Type=Application
Name=TokNGauge Tray
Exec=/absolute/path/to/ToknGauge/.venv/bin/python /absolute/path/to/ToknGauge/apps/menubar-linux/tray.py
Icon=tokngauge
Terminal=false
X-GNOME-Autostart-enabled=true
```

---

## Windows

### Prerequisites

- **Python 3.11+** (from python.org or the Microsoft Store).
- **Edge WebView2 Runtime** — preinstalled on Windows 11 and recent
  Windows 10 updates. If missing, install the Evergreen Standalone
  installer from <https://developer.microsoft.com/microsoft-edge/webview2/>.

### Python deps (PowerShell)

```powershell
.venv\Scripts\Activate.ps1
pip install pystray pywebview Pillow cairosvg
```

> `cairosvg` on Windows needs the Cairo native library. The easiest fix
> if you get `OSError: no library called "cairo-2" was found` is:
> ```powershell
> pip install cairocffi pycairo
> ```
> or install GTK for Windows (which bundles `libcairo-2.dll`) from
> <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer>.

### Run

```powershell
python apps\menubar-windows\tray.py
```

- Icon appears in the system tray (bottom-right notification area; you
  may have to drag it out of the hidden overflow popover the first time).
- Left-click → embedded WebView window. Closing the window only hides
  it; use *Quit* in the menu to fully exit.
- The icon is rendered in white to contrast with the default dark
  taskbar. If you use a light theme, edit the same `color = …` line in
  `apps/_tray_app.py` and set it to black.
- The server is launched with `CREATE_NO_WINDOW` so no console pops up.

### Run at login (optional)

Press <kbd>Win</kbd>+<kbd>R</kbd>, type `shell:startup`, then drop a
shortcut whose target is:

```
C:\absolute\path\to\ToknGauge\.venv\Scripts\pythonw.exe C:\absolute\path\to\ToknGauge\apps\menubar-windows\tray.py
```

Using `pythonw.exe` (note the trailing `w`) keeps the launcher silent.

---

## Troubleshooting

| Symptom                                                  | Fix                                                                                  |
|----------------------------------------------------------|--------------------------------------------------------------------------------------|
| Icon doesn't appear on Linux (GNOME)                     | Install the AppIndicator GNOME extension.                                            |
| `OSError: no library called "cairo-2"` (Windows)         | `pip install cairocffi pycairo` or install GTK for Windows.                          |
| Embedded window is blank on Windows                      | Install Edge WebView2 Runtime.                                                       |
| Port 8770 already in use                                 | `export TOKNGAUGE_PORT=8771` (PowerShell: `$env:TOKNGAUGE_PORT=8771`) before launch. |
| Server doesn't die when quitting the tray                | The tray sends `SIGTERM` then `kill`; if a stale process remains, check `lsof -i :8770` (macOS/Linux) or `netstat -ano \| findstr 8770` (Windows). |
| macOS popover too small / cropped                        | Adjust `POPOVER_SIZE` in [`apps/menubar-mac/tray.py`](menubar-mac/tray.py).         |
| Linux/Windows window too small / cropped                 | Adjust `WINDOW_SIZE` in [`apps/_tray_app.py`](_tray_app.py).                        |

---

## Customising the icon

The glyph is defined as an inline SVG in two places (kept identical):

- macOS: `_TRAY_SVG` in [`apps/menubar-mac/tray.py`](menubar-mac/tray.py).
- Linux + Windows: `_TRAY_SVG` in [`apps/_tray_app.py`](_tray_app.py).

It is rendered to PNG at runtime via `cairosvg`. To change the look,
edit the SVG strokes / paths and relaunch. No build step required.
