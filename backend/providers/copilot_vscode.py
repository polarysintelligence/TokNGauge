# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""VS Code Copilot Chat transcript scanner."""
from __future__ import annotations

import json
from pathlib import Path

from ._base import (
    SessionSummary,
    normalize_model,
    project_name_from_path,
    safe_iter_lines,
    safe_load_json,
    vscode_workspace_storage,
)

ID = "copilot-vscode"
DISPLAY = "Copilot VS Code"


def is_available() -> bool:
    return vscode_workspace_storage().is_dir()


def _parse_transcript(filepath: Path) -> SessionSummary:
    s = SessionSummary(source=ID, file=filepath.name)
    current_model = ""
    for line in safe_iter_lines(filepath):
        event = safe_load_json(line)
        if not event:
            continue
        etype = event.get("type", "")
        data = event.get("data", event)
        if etype == "session.start":
            s.sessionId = data.get("sessionId", "")
            s.startTime = data.get("startTime", event.get("timestamp", ""))
        elif etype == "session.model_change":
            nm = data.get("newModel", "") or data.get("model", "")
            if nm:
                current_model = normalize_model(nm)
        elif etype == "user.message":
            s.userMessages += 1
            s.inputChars += len(str(data.get("content", "")))
        elif etype == "assistant.message":
            s.turns += 1
            chars = len(str(data.get("content", "")))
            for tr in data.get("toolRequests", []) or []:
                s.toolCalls += 1
                chars += len(str(tr.get("arguments", "")))
            s.outputChars += chars
            s.modelChars[current_model or "unknown"] = (
                s.modelChars.get(current_model or "unknown", 0) + chars
            )
    return s


def scan() -> list[SessionSummary]:
    base = vscode_workspace_storage()
    if not base.is_dir():
        return []
    out: list[SessionSummary] = []
    for ws_dir in base.iterdir():
        if not ws_dir.is_dir():
            continue
        tdir = ws_dir / "GitHub.copilot-chat" / "transcripts"
        if not tdir.is_dir():
            continue
        project = "unknown"
        ws_json = ws_dir / "workspace.json"
        if ws_json.exists():
            try:
                ws_data = json.loads(ws_json.read_text(encoding="utf-8"))
                project = project_name_from_path(ws_data.get("folder", ""))
            except (json.JSONDecodeError, OSError):
                pass
        for jsonl in tdir.glob("*.jsonl"):
            summary = _parse_transcript(jsonl)
            summary.project = project
            summary.cwd = ws_dir.name
            out.append(summary)
    return out
