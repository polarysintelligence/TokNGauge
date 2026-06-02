# Packaging & installers

This document describes how to produce native installers for **macOS**, **Windows**
and **Linux** from the ToknGauge source tree.

A helper script — [`scripts/build_installer.py`](../scripts/build_installer.py) —
automates the repetitive steps; the prose below explains what each step does and
the prerequisites you only need to install once per machine.

> **Important architectural note**
> The current tray launchers in [`apps/_tray_app.py`](../apps/_tray_app.py)
> spawn the FastAPI server via `subprocess.Popen([sys.executable, "server.py"])`.
> When the app is frozen with **py2app** / **PyInstaller** / **briefcase**, the
> bundled `sys.executable` is your `.app` / `.exe`, **not** a Python interpreter
> capable of running `server.py` directly. Before producing distributable
> bundles you must refactor `_spawn_server()` to run uvicorn **in a thread**
> inside the same process. See the [In-process server](#in-process-server)
> section below for the 10-line change required.

---

## 0. Prerequisites (one-time, per machine)

| OS | Tooling |
|---|---|
| **macOS** | `xcode-select --install`, [Homebrew](https://brew.sh), `brew install create-dmg`, Python ≥ 3.10 |
| **Windows** | Python ≥ 3.10 (from python.org, **add to PATH**), [Inno Setup 6](https://jrsoftware.org/isdl.php) |
| **Linux** | `sudo apt install python3-venv python3-pip fakeroot dpkg-dev imagemagick libfuse2` (FUSE is needed by AppImageTool at runtime) |

Then in every OS, from the repo root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## In-process server

Replace `_spawn_server` / `_stop_server` in [`apps/_tray_app.py`](../apps/_tray_app.py)
with a uvicorn thread so the frozen app does not need to re-launch Python:

```python
import threading, uvicorn
from server import app as _fastapi_app

def _spawn_server():
    cfg = uvicorn.Config(_fastapi_app, host="127.0.0.1",
                         port=PORT, log_level="warning")
    server = uvicorn.Server(cfg)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return server      # has .should_exit attribute

def _stop_server(server):
    if server is not None:
        server.should_exit = True
```

---

## 1. macOS — `.app` + `.dmg` (py2app)

### Manual

```bash
pip install py2app
python scripts/build_installer.py mac          # → dist/TokNGauge.app + dist/TokNGauge.dmg
```

What the script does:

1. Runs [`scripts/build_icons.py`](../scripts/build_icons.py) to regenerate `static/icons/icon.icns`.
2. Writes a temporary `setup.py` configured for `py2app` (LSUIElement=true so the
   app is menu-bar only, all `static/` and `backend/` files bundled as resources).
3. Invokes `python setup.py py2app -O2 --packages backend,fastapi,uvicorn,starlette,pydantic`.
4. Wraps `dist/TokNGauge.app` in a `.dmg` using `create-dmg` (drag-to-/Applications layout).

### Code signing & notarization (optional but required for distribution)

```bash
codesign --deep --force --options runtime \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  --entitlements packaging/macos/entitlements.plist dist/TokNGauge.app

xcrun notarytool submit dist/TokNGauge.dmg \
  --apple-id you@example.com --team-id TEAMID --password "app-specific-pwd" --wait

xcrun stapler staple dist/TokNGauge.dmg
```

Without these two steps Gatekeeper on other Macs will refuse to launch the app.

---

## 2. Windows — `.exe` installer (PyInstaller + Inno Setup)

### Manual

```powershell
pip install pyinstaller
python scripts\build_installer.py win        # → dist\TokNGauge\TokNGauge.exe + dist\TokNGauge-Setup.exe
```

What the script does:

1. Regenerates `static/icons/icon.ico`.
2. Runs PyInstaller:
   ```
   pyinstaller --noconfirm --windowed --icon static/icons/icon.ico \
     --name TokNGauge \
     --add-data "static;static" \
     --add-data "backend;backend" \
     --add-data "server.py;." \
     apps/menubar-windows/tray.py
   ```
3. Generates a fresh [`packaging/windows/installer.iss`](../packaging/windows/installer.iss)
   Inno Setup script in `dist/` pointing at the folder PyInstaller produced.
4. Invokes `iscc.exe` (Inno Setup compiler) on it, producing `dist/TokNGauge-Setup.exe`.

### Signing (optional)

If you have an EV / OV code-signing certificate:

```powershell
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 dist\TokNGauge-Setup.exe
```

---

## 3. Linux — `.AppImage` and/or `.deb`

### Manual

```bash
pip install pyinstaller
python scripts/build_installer.py linux --format appimage      # → dist/TokNGauge-x86_64.AppImage
python scripts/build_installer.py linux --format deb           # → dist/tokngauge_1.2.0_amd64.deb
python scripts/build_installer.py linux --format both          # both
```

What the script does:

- **AppImage**:
  1. Runs PyInstaller (same flags as Windows but with `:` separators).
  2. Builds a standard `AppDir/` layout: `usr/bin/TokNGauge`, `tokngauge.desktop`
     copied from [`apps/menubar-linux/data/tokngauge.desktop`](../apps/menubar-linux/data/tokngauge.desktop),
     `usr/share/icons/hicolor/256x256/apps/tokngauge.png`.
  3. Downloads `appimagetool-x86_64.AppImage` (cached in `~/.cache/tokngauge/`) and runs it on `AppDir/`.
- **`.deb`**:
  1. Same PyInstaller bundle, copied under `pkgroot/opt/tokngauge/`.
  2. Writes `DEBIAN/control` (Maintainer, Depends: `libgtk-3-0, libwebkit2gtk-4.1-0`),
     `DEBIAN/postinst` (symlinks `/usr/bin/tokngauge`).
  3. Calls `dpkg-deb --build --root-owner-group pkgroot dist/tokngauge_<ver>_amd64.deb`.

### Install / test

```bash
chmod +x dist/TokNGauge-x86_64.AppImage && ./dist/TokNGauge-x86_64.AppImage
sudo dpkg -i dist/tokngauge_1.2.0_amd64.deb && tokngauge
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: backend.providers.claude` inside the bundled app | Add the missing module to PyInstaller `--hidden-import` or to py2app `packages=` list. |
| `Killed: 9` on first launch on macOS (notarized issue) | Make sure all `.dylib`s under `Contents/Frameworks` are signed; rerun `codesign --deep`. |
| `A Python runtime not could be located` on macOS launch | Your Python is not a **framework build**. py2app needs `Python.framework`. Solutions: (a) install Python from python.org (always framework), (b) `PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.11.10` and rebuild from that interpreter, (c) just push a `v*` tag and let the GitHub Actions release workflow build it — `actions/setup-python` always provides a framework build. |
| AppImage refuses to run (`error while loading shared libraries: libfuse.so.2`) | `sudo apt install libfuse2`. |
| Inno Setup compiler not found | The script looks for `iscc.exe` under `%ProgramFiles(x86)%\Inno Setup 6\` — install Inno Setup 6 or add it to PATH. |
| `cairosvg` complains about missing Cairo on Windows | `pip install pycairo` or remove the call to `build_icons.py` and ship pre-rendered icons. |
