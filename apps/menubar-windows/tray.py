# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""TokNGauge — Windows tray launcher. See ../_tray_app.py for details."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _tray_app import main  # noqa: E402

if __name__ == "__main__":
    main()
