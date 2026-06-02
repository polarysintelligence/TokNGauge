# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""TokNGauge — Linux tray launcher. See ../_tray_app.py for details."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# WebKit2GTK's sandboxed NetworkProcess tries to dlopen Snap's old libpthread
# on Ubuntu systems that have Snap installed, causing a symbol-lookup crash.
# Disabling the sandbox avoids that conflict entirely. This flag is harmless
# for a local-only dashboard that never loads untrusted content.
os.environ.setdefault("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS", "1")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _tray_app import main  # noqa: E402

if __name__ == "__main__":
    # Force Qt (PyQt6 + WebEngine) backend: avoids the WebKit2GTK / Snap
    # libpthread conflict present on Ubuntu systems with Snap packages installed.
    main(gui="qt")
