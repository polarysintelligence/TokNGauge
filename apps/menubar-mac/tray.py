# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""
TokNGauge — macOS menu-bar app with embedded WebView popover.

- Shows the same colorful gauge icon as the web favicon in the status bar.
- Left-click opens a small popover with the TokNGauge UI embedded via WKWebView.
- Right-click (or Ctrl-click) shows a menu: Open in browser / Restart / Quit.
- Manages the FastAPI server as a child process.

Run:
    python apps/menubar-mac/tray.py

Requires:
    pip install pyobjc-framework-Cocoa pyobjc-framework-WebKit
"""
from __future__ import annotations

import os
import sys
import tempfile
import webbrowser
from pathlib import Path

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSPopover,
    NSPopoverBehaviorTransient,
    NSStatusBar,
    NSVariableStatusItemLength,
    NSViewController,
)
from Foundation import NSURL, NSURLRequest, NSTimer
from WebKit import WKWebView, WKWebViewConfiguration

# In a PyInstaller frozen bundle, data files live under sys._MEIPASS.
if getattr(sys, "frozen", False):
    _BASE = Path(sys._MEIPASS)
else:
    _BASE = Path(__file__).resolve().parent
    REPO_ROOT = _BASE.parents[1]
    sys.path.insert(0, str(REPO_ROOT / "apps"))

from _server_runtime import start_server, stop_server  # noqa: E402
RESOURCES = _BASE / "Resources"
ICON_PATH = RESOURCES / "TrayIcon@2x.png"
PORT = int(os.environ.get("TOKNGAUGE_PORT", "8770"))
URL = f"http://localhost:{PORT}"

POPOVER_SIZE = (940, 760)
ICON_BAR_HEIGHT = 18  # macOS menu bar icon size (points)

# Minimalist gauge glyph designed for the menu bar:
# thin strokes, transparent background, just the dial + needle + tick marks.
# Rendered at runtime so it always matches and stays crisp on Retina.
_TRAY_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
  <g fill='none' stroke='black' stroke-width='4'
     stroke-linecap='round' stroke-linejoin='round'>
    <!-- gauge arc (semicircle) -->
    <path d='M 10 44 A 22 22 0 0 1 54 44'/>
    <!-- tick marks -->
    <path d='M 12 36 L 16 38'/>
    <path d='M 20 24 L 23 27'/>
    <path d='M 32 20 L 32 24'/>
    <path d='M 44 24 L 41 27'/>
    <path d='M 52 36 L 48 38'/>
    <!-- needle -->
    <path d='M 32 44 L 44 28'/>
  </g>
  <circle cx='32' cy='44' r='3.2' fill='black'/>
</svg>"""


def _build_template_icon() -> Path:
    """Render the minimalist gauge SVG to a PNG suitable for an NSImage template.

    macOS template images use only the alpha channel — color is ignored and
    replaced with the menu-bar tint (black in light mode, white in dark mode).
    """
    import cairosvg

    tmp = Path(tempfile.gettempdir()) / "tokngauge-tray-template.png"
    cairosvg.svg2png(
        bytestring=_TRAY_SVG.encode("utf-8"),
        output_width=64,
        output_height=64,
        write_to=str(tmp),
    )
    return tmp


class AppDelegate(NSObject):
    def initWithServerProc_(self, proc):
        self = objc.super(AppDelegate, self).init()
        if self is None:
            return None
        self.proc = proc
        self.status_item = None
        self.popover = None
        self.webview = None
        return self

    # --- lifecycle ---
    def applicationDidFinishLaunching_(self, _notification):
        self._build_status_item()
        self._build_popover()

    def applicationWillTerminate_(self, _notification):
        self._stop_server()

    # --- UI setup ---
    def _build_status_item(self):
        bar = NSStatusBar.systemStatusBar()
        item = bar.statusItemWithLength_(NSVariableStatusItemLength)

        if ICON_PATH.exists():
            try:
                template_path = _build_template_icon()
            except Exception:
                template_path = ICON_PATH
            image = NSImage.alloc().initByReferencingFile_(str(template_path))
            image.setSize_((ICON_BAR_HEIGHT, ICON_BAR_HEIGHT))
            # template=True -> macOS tints it black/white to match the menu bar
            image.setTemplate_(True)
            item.button().setImage_(image)
        else:
            item.button().setTitle_("TG")

        item.button().setToolTip_("TokNGauge")
        item.button().setTarget_(self)
        item.button().setAction_("statusItemClicked:")
        # Accept left and right clicks
        try:
            from AppKit import NSEventMaskLeftMouseUp, NSEventMaskRightMouseUp
            item.button().sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)
        except Exception:
            pass

        self.status_item = item

    def _build_popover(self):
        config = WKWebViewConfiguration.alloc().init()
        frame = NSMakeRect(0, 0, POPOVER_SIZE[0], POPOVER_SIZE[1])
        webview = WKWebView.alloc().initWithFrame_configuration_(frame, config)

        vc = NSViewController.alloc().init()
        vc.setView_(webview)

        popover = NSPopover.alloc().init()
        popover.setContentViewController_(vc)
        popover.setContentSize_(POPOVER_SIZE)
        popover.setBehavior_(NSPopoverBehaviorTransient)
        popover.setAnimates_(True)

        self.popover = popover
        self.webview = webview
        self._load_url()

    def _load_url(self):
        # Cache-bust on every load so JS/CSS edits show up without restarting
        # the tray app. WKWebView otherwise serves a stale copy.
        import time as _time
        bust = int(_time.time())
        url = NSURL.URLWithString_(f"{URL}/?v={bust}")
        req = NSURLRequest.requestWithURL_cachePolicy_timeoutInterval_(url, 1, 30.0)
        # cachePolicy=1 → NSURLRequestReloadIgnoringLocalCacheData
        self.webview.loadRequest_(req)

    # --- actions ---
    def statusItemClicked_(self, sender):
        from AppKit import NSApp
        try:
            from AppKit import NSEventTypeRightMouseUp
        except ImportError:
            NSEventTypeRightMouseUp = 2  # legacy fallback
        event = NSApplication.sharedApplication().currentEvent()
        if event is not None and event.type() == NSEventTypeRightMouseUp:
            self._show_menu(sender)
            return
        self._toggle_popover(sender)

    def _toggle_popover(self, sender):
        if self.popover.isShown():
            self.popover.performClose_(sender)
            return
        button = self.status_item.button()
        self._load_url()
        from AppKit import NSRectEdgeMinY
        self.popover.showRelativeToRect_ofView_preferredEdge_(
            button.bounds(), button, NSRectEdgeMinY
        )
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def _show_menu(self, sender):
        menu = NSMenu.alloc().init()
        items = [
            (f"Open {URL} in browser", "openInBrowser:"),
            (None, None),
            ("Restart server", "restartServer:"),
            ("Reload web view", "reloadWebView:"),
            (None, None),
            ("Quit TokNGauge", "quitApp:"),
        ]
        for title, action in items:
            if title is None:
                menu.addItem_(NSMenuItem.separatorItem())
                continue
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
            mi.setTarget_(self)
            menu.addItem_(mi)

        self.status_item.setMenu_(menu)
        self.status_item.button().performClick_(None)
        # Remove menu so the next left-click toggles the popover again
        self.status_item.setMenu_(None)

    def openInBrowser_(self, _sender):
        webbrowser.open(URL)

    def reloadWebView_(self, _sender):
        self._load_url()

    def restartServer_(self, _sender):
        self._stop_server()
        self.proc = _spawn_server()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.5, self, "reloadWebView:", None, False
        )

    def quitApp_(self, _sender):
        self._stop_server()
        NSApplication.sharedApplication().terminate_(None)

    # --- server mgmt ---
    def _stop_server(self):
        stop_server(self.proc)
        self.proc = None


def _spawn_server():
    """Run uvicorn in-process so frozen bundles don't need a 2nd interpreter."""
    os.environ["TOKNGAUGE_PORT"] = str(PORT)
    return start_server(port=PORT)


def main() -> None:
    proc = _spawn_server()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon
    delegate = AppDelegate.alloc().initWithServerProc_(proc)
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
