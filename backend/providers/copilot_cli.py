# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""GitHub Copilot CLI scanner — `~/.copilot/session-state/{uuid}/events.jsonl`."""
from __future__ import annotations

from pathlib import Path

from ._base import (
    SessionSummary,
    home,
    normalize_model,
    project_name_from_path,
    safe_iter_lines,
    safe_load_json,
)

ID = "copilot-cli"
DISPLAY = "Copilot CLI"


def base_dir() -> Path:
    return home() / ".copilot" / "session-state"


def is_available() -> bool:
    return base_dir().is_dir()


def _read_workspace_yaml(yaml_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line and not line.startswith((" ", "\t")):
                    k, _, v = line.partition(":")
                    out[k.strip()] = v.strip()
    except (OSError, PermissionError):
        pass
    return out


def _parse_events(filepath: Path) -> SessionSummary:
    s = SessionSummary(source=ID, file=filepath.name)
    current_model = ""
    for line in safe_iter_lines(filepath):
        event = safe_load_json(line)
        if not event:
            continue
        etype = event.get("type", "")
        data = event.get("data", {})

        if etype == "session.start":
            s.sessionId = data.get("sessionId", "")
            s.startTime = data.get("startTime", event.get("timestamp", ""))
        elif etype == "session.model_change":
            nm = data.get("newModel", "")
            if nm:
                current_model = normalize_model(nm)
        elif etype == "user.message":
            s.userMessages += 1
            s.inputChars += len(data.get("content", ""))
            for att in data.get("attachments", []) or []:
                if isinstance(att, str):
                    s.inputChars += len(att)
                else:
                    s.inputChars += len(str(att))
        elif etype == "assistant.message":
            s.turns += 1
            chars = len(data.get("content", "")) + len(data.get("reasoningText", ""))
            for tr in data.get("toolRequests", []) or []:
                s.toolCalls += 1
                chars += len(str(tr.get("arguments", "")))
            s.outputChars += chars
            model = current_model or "unknown"
            s.modelChars[model] = s.modelChars.get(model, 0) + chars
        elif etype in ("tool.execution_start", "hook.start"):
            s.toolCalls += 1
    return s


def scan() -> list[SessionSummary]:
    base = base_dir()
    if not base.is_dir():
        return []
    out: list[SessionSummary] = []
    for sid_dir in base.iterdir():
        if not sid_dir.is_dir():
            continue
        events = sid_dir / "events.jsonl"
        if not events.exists():
            continue
        ws = _read_workspace_yaml(sid_dir / "workspace.yaml")
        cwd = ws.get("cwd", "")
        summary = _parse_events(events)
        summary.cwd = cwd
        summary.project = project_name_from_path(cwd)
        out.append(summary)
    return out
