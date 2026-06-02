# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""
Cross-platform (Linux / Windows) TokNGauge tray app.

- Renders a minimalist gauge glyph as the tray icon (no background).
- Launches the FastAPI server as a child process.
- Clicking the tray icon opens / focuses a small embedded WebView window
  (via pywebview) pointing at http://localhost:<PORT>.
- Right-click menu: Show, Reload, Open in browser, Restart server, Quit.

Linux deps:
    pip install pystray pywebview[gtk] Pillow
    (or pywebview[qt] if you prefer QtWebEngine)

Windows deps:
    pip install pystray pywebview Pillow
    (pywebview on Windows uses the bundled Edge WebView2 runtime)

Run:
    python apps/menubar-linux/tray.py     # Linux
    python apps/menubar-windows/tray.py   # Windows
"""
from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _server_runtime import start_server, stop_server  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("TOKNGAUGE_PORT", "8770"))
URL = f"http://localhost:{PORT}"
WINDOW_SIZE = (940, 760)

# Minimalist gauge glyph — thin strokes, transparent background.
# Matches the macOS template icon so all platforms feel the same.
_TRAY_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
  <g fill='none' stroke='black' stroke-width='4'
     stroke-linecap='round' stroke-linejoin='round'>
    <path d='M 10 44 A 22 22 0 0 1 54 44'/>
    <path d='M 12 36 L 16 38'/>
    <path d='M 20 24 L 23 27'/>
    <path d='M 32 20 L 32 24'/>
    <path d='M 44 24 L 41 27'/>
    <path d='M 52 36 L 48 38'/>
    <path d='M 32 44 L 44 28'/>
  </g>
  <circle cx='32' cy='44' r='3.2' fill='black'/>
</svg>"""

_GAUGE_STROKE_WIDTH = 4
_GAUGE_ARC_BBOX = (10, 22, 54, 66)
_GAUGE_STROKES = (
    (12, 36, 16, 38),
    (20, 24, 23, 27),
    (32, 20, 32, 24),
    (44, 24, 41, 27),
    (52, 36, 48, 38),
    (32, 44, 44, 28),  # needle
)
_GAUGE_CENTER = (32, 44)
_GAUGE_DOT_RADIUS = 3.2

def _panel_is_dark() -> bool:
    """Return True when the system panel/taskbar is dark (icon needs white strokes).

    Detection order:
      1. Windows: registry SystemUsesLightTheme key.
      2. Linux/GNOME: gsettings org.gnome.desktop.interface color-scheme.
      3. Linux fallback: GTK_THEME env var.
      4. Hard default: True (dark) — most modern Linux panels & Windows taskbars are dark.
    """
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            return val == 0  # 0 = dark, 1 = light
        except Exception:
            return True  # Windows taskbar defaults to dark

    # Linux — try GNOME gsettings first
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            return "dark" in result.stdout.lower()
    except Exception:
        pass

    # Fallback: GTK_THEME env var (e.g. "Adwaita:dark")
    if "dark" in os.environ.get("GTK_THEME", "").lower():
        return True

    return True  # safe default — most Linux panels are dark


def _render_icon(size: int = 64, color: tuple[int, int, int] = (0, 0, 0)):
    """Render the gauge glyph to a Pillow Image with transparent background.

    On Windows the tray is usually rendered on a dark taskbar, so we recolor
    the strokes to white. On Linux we keep black, which works on most modern
    panels (and AppIndicator scales it).
    """
    from PIL import Image, ImageDraw

    scale = size / 64.0
    stroke = max(1, round(_GAUGE_STROKE_WIDTH * scale))
    rgba = (color[0], color[1], color[2], 255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    def s(v: float) -> float:
        return v * scale
    arc_bbox = (s(_GAUGE_ARC_BBOX[0]), s(_GAUGE_ARC_BBOX[1]),
                s(_GAUGE_ARC_BBOX[2]), s(_GAUGE_ARC_BBOX[3]))
    draw.arc(arc_bbox, start=180, end=360, fill=rgba, width=stroke)
    for x1, y1, x2, y2 in _GAUGE_STROKES:
        draw.line((s(x1), s(y1), s(x2), s(y2)), fill=rgba, width=stroke)
    cx, cy = s(_GAUGE_CENTER[0]), s(_GAUGE_CENTER[1])
    r = s(_GAUGE_DOT_RADIUS)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba)

    return img


def _spawn_server() -> subprocess.Popen:
    env = os.environ.copy()
    env["TOKNGAUGE_PORT"] = str(PORT)
    python = sys.executable
    venv_python = REPO_ROOT / (".venv/Scripts/python.exe" if os.name == "nt"
                               else ".venv/bin/python")
    if venv_python.exists():
        python = str(venv_python)
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x08000000
    return subprocess.Popen(
        [python, str(REPO_ROOT / "server.py")],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _stop_server(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class TrayApp:
    def __init__(self, gui: str | None = None) -> None:
        import pystray
        import webview

        self._pystray = pystray
        self._webview = webview
        self._gui = gui  # pywebview backend override ('qt', 'gtk', None=auto)
        self.proc: subprocess.Popen | None = _spawn_server()
        self.window = None
        self.icon = None

    # ---- actions ----
    def show(self, _icon=None, _item=None) -> None:
        if self.window is None:
            return
        try:
            self.window.show()
        except Exception:
            pass

    def hide(self, _icon=None, _item=None) -> None:
        if self.window is None:
            return
        try:
            self.window.hide()
        except Exception:
            pass

    def reload(self, _icon=None, _item=None) -> None:
        if self.window is None:
            return
        try:
            self.window.load_url(URL)
        except Exception:
            pass

    def open_browser(self, _icon=None, _item=None) -> None:
        webbrowser.open(URL)

    def restart_server(self, _icon=None, _item=None) -> None:
        _stop_server(self.proc)
        self.proc = _spawn_server()
        threading.Timer(1.5, self.reload).start()

    def quit(self, _icon=None, _item=None) -> None:
        _stop_server(self.proc)
        try:
            if self.icon is not None:
                self.icon.stop()
        finally:
            try:
                if self.window is not None:
                    self.window.destroy()
            except Exception:
                pass

    # ---- run ----
    def run(self) -> None:
        pystray = self._pystray
        webview = self._webview

        # Pick icon color based on platform/theme panel contrast.
        color = (255, 255, 255) if _panel_is_dark() else (0, 0, 0)
        image = _render_icon(64, color=color)

        menu = pystray.Menu(
            pystray.MenuItem("Show TokNGauge", self.show, default=True),
            pystray.MenuItem("Hide", self.hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Reload web view", self.reload),
            pystray.MenuItem(f"Open {URL} in browser", self.open_browser),
            pystray.MenuItem("Restart server", self.restart_server),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit),
        )
        self.icon = pystray.Icon("tokngauge", image, "TokNGauge", menu)

        # run_detached() registers the AppIndicator with the existing GTK/GLib
        # main loop instead of starting its own — avoids the "main context
        # already acquired by another thread" conflict with pywebview.
        self.icon.run_detached()

        self.window = webview.create_window(
            "TokNGauge",
            URL,
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            hidden=True,
            resizable=True,
        )
        kwargs: dict = {}
        if self._gui:
            kwargs["gui"] = self._gui
        try:
            webview.start(**kwargs)
        finally:
            self.quit()


def main(gui: str | None = None) -> None:
    TrayApp(gui=gui).run()


if __name__ == "__main__":
    main()
