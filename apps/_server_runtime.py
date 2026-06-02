# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Shared FastAPI server runtime for the tray apps.

Runs uvicorn in a daemon thread inside the same process as the tray, so that
frozen bundles (py2app, PyInstaller) don't need to re-launch a second Python
interpreter — `sys.executable` inside a bundle is the .app/.exe itself.

API:
    handle = start_server(port=8770)
    ...
    stop_server(handle)
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

# Make sure the repo root is importable so `import server` resolves to the
# top-level server.py regardless of where the tray script lives.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def start_server(port: int = 8770, host: str = "127.0.0.1") -> Any:
    """Start uvicorn in a background daemon thread and return its Server handle.

    Blocks briefly (up to 5 s) until the server reports it is ready, so that
    the tray can open the WebView pointing at an already-listening port.
    """
    import uvicorn
    from server import app as fastapi_app

    config = uvicorn.Config(
        fastapi_app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="tokngauge-uvicorn", daemon=True)
    thread.start()

    deadline = time.time() + 5.0
    while time.time() < deadline and not getattr(server, "started", False):
        time.sleep(0.05)

    server._tokngauge_thread = thread  # type: ignore[attr-defined]
    return server


def stop_server(handle: Any) -> None:
    """Ask the uvicorn server thread to shut down cleanly."""
    if handle is None:
        return
    try:
        handle.should_exit = True
    except Exception:
        pass
    thread: threading.Thread | None = getattr(handle, "_tokngauge_thread", None)
    if thread is not None and thread.is_alive():
        thread.join(timeout=5)
