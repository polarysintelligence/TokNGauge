# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Provider registry — each provider is a small module with
`ID`, `DISPLAY`, `is_available()`, `scan()` → list[SessionSummary].

To add a new provider, drop a module into `backend/providers/` and append it
here.
"""
from __future__ import annotations

from types import ModuleType

from . import claude, codex, copilot_cli, copilot_vscode, cursor, gemini
from ._base import SessionSummary

ALL: list[ModuleType] = [copilot_cli, copilot_vscode, cursor, claude, codex, gemini]


def by_id() -> dict[str, ModuleType]:
    return {m.ID: m for m in ALL}


def info() -> list[dict]:
    return [
        {"id": m.ID, "displayName": m.DISPLAY, "available": m.is_available()}
        for m in ALL
    ]


def scan_all(enabled: list[str] | None = None) -> list[SessionSummary]:
    out: list[SessionSummary] = []
    for m in ALL:
        if enabled is not None and m.ID not in enabled:
            continue
        if not m.is_available():
            continue
        try:
            out.extend(m.scan())
        except Exception:  # noqa: BLE001 — never let one provider break the whole scan
            continue
    return out


__all__ = ["ALL", "by_id", "info", "scan_all", "SessionSummary"]
