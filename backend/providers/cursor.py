# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Cursor IDE scanner.

Cursor is a VS Code fork that stores chat transcripts under the OS-specific
"User/workspaceStorage" tree, similar to VS Code, but inside its own
`Cursor` application support folder:

* macOS   — `~/Library/Application Support/Cursor/User/workspaceStorage`
* Linux   — `~/.config/Cursor/User/workspaceStorage`
* Windows — `%APPDATA%/Cursor/User/workspaceStorage`

Each workspace dir contains a `workspace.json` (folder URI) and either
`anysphere.cursor-chat/transcripts/*.jsonl` or `state.vscdb` files. We only
scan the JSONL transcripts (best-effort) and fall back to char-based
token estimation.

Token counts are heuristic — Cursor does not expose them in transcripts.
"""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from ._base import (
    SessionSummary,
    home,
    normalize_model,
    project_name_from_path,
    safe_iter_lines,
    safe_load_json,
)

ID = "cursor"
DISPLAY = "Cursor"


def workspace_storage() -> Path:
    """Locate the OS-specific Cursor workspaceStorage directory."""
    env = os.environ.get("CURSOR_HOME")
    if env:
        return Path(env)
    system = platform.system()
    if system == "Darwin":
        return home() / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Cursor" / "User" / "workspaceStorage"
    return home() / ".config" / "Cursor" / "User" / "workspaceStorage"


def is_available() -> bool:
    return workspace_storage().is_dir()


def _parse_transcript(filepath: Path) -> SessionSummary:
    s = SessionSummary(source=ID, file=filepath.name, sessionId=filepath.stem)
    current_model = ""
    for line in safe_iter_lines(filepath):
        event = safe_load_json(line)
        if not event:
            continue
        etype = event.get("type", "") or event.get("role", "")
        data = event.get("data", event)
        if not s.startTime:
            s.startTime = data.get("timestamp", "") or event.get("timestamp", "")
        nm = data.get("model", "") or event.get("model", "")
        if nm:
            current_model = normalize_model(nm)
        content = data.get("content", "") or data.get("text", "")
        if isinstance(content, list):
            content = " ".join(str(p) for p in content)
        if etype in ("user", "user.message", "human"):
            s.userMessages += 1
            s.inputChars += len(str(content))
        elif etype in ("assistant", "assistant.message", "model"):
            s.turns += 1
            chars = len(str(content))
            for tr in data.get("toolRequests", []) or data.get("tools", []) or []:
                s.toolCalls += 1
                chars += len(str(tr))
            s.outputChars += chars
            key = current_model or "unknown"
            s.modelChars[key] = s.modelChars.get(key, 0) + chars
    return s


def scan() -> list[SessionSummary]:
    base = workspace_storage()
    if not base.is_dir():
        return []
    out: list[SessionSummary] = []
    for ws_dir in base.iterdir():
        if not ws_dir.is_dir():
            continue
        project = "unknown"
        ws_json = ws_dir / "workspace.json"
        if ws_json.exists():
            try:
                ws_data = json.loads(ws_json.read_text(encoding="utf-8"))
                project = project_name_from_path(ws_data.get("folder", ""))
            except (json.JSONDecodeError, OSError):
                pass
        # Possible transcript locations seen in the wild
        candidates = [
            ws_dir / "anysphere.cursor-chat" / "transcripts",
            ws_dir / "cursor.cursor" / "transcripts",
            ws_dir / "transcripts",
        ]
        for tdir in candidates:
            if not tdir.is_dir():
                continue
            for jsonl in tdir.glob("*.jsonl"):
                summary = _parse_transcript(jsonl)
                summary.project = project
                summary.cwd = ws_dir.name
                out.append(summary)
    return out
