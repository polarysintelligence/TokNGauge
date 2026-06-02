# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Gemini CLI scanner — `~/.gemini/tmp/{hash}/logs.json` + `chats/*.json`.

The Gemini CLI persists sessions and a logs file. Token counts are not always
present; we fall back to character-based estimation when missing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ._base import (
    SessionSummary,
    home,
    normalize_model,
    project_name_from_path,
    safe_iter_lines,
    safe_load_json,
)

ID = "gemini"
DISPLAY = "Gemini CLI"


def base_dir() -> Path:
    env = os.environ.get("GEMINI_HOME")
    return Path(env) if env else home() / ".gemini"


def is_available() -> bool:
    return base_dir().is_dir()


def _parse_logs(filepath: Path) -> list[SessionSummary]:
    """Parse Gemini's logs.json — array of {sessionId, type, message, ...}."""
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    sessions: dict[str, SessionSummary] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        sid = str(entry.get("sessionId") or entry.get("session_id") or "default")
        s = sessions.setdefault(sid, SessionSummary(source=ID, sessionId=sid, file=filepath.name))
        ts = entry.get("timestamp") or entry.get("time") or ""
        if ts and not s.startTime:
            s.startTime = ts
        etype = entry.get("type", "")
        msg = entry.get("message", "") or entry.get("content", "")
        if etype in ("user", "user_prompt", "userMessage"):
            s.userMessages += 1
            s.inputChars += len(str(msg))
        elif etype in ("model", "assistant", "modelResponse"):
            s.turns += 1
            s.outputChars += len(str(msg))
            model = normalize_model(entry.get("model", ""))
            s.modelChars[model] = s.modelChars.get(model, 0) + len(str(msg))
    return list(sessions.values())


def _parse_chat(filepath: Path) -> SessionSummary | None:
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    s = SessionSummary(source=ID, file=filepath.name, sessionId=filepath.stem)
    messages = data.get("messages") if isinstance(data, dict) else None
    if not isinstance(messages, list):
        return None
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or m.get("type", "")
        content = m.get("content") or m.get("parts") or m.get("text") or ""
        if isinstance(content, list):
            content = " ".join(str(p) for p in content)
        content = str(content)
        if not s.startTime:
            s.startTime = m.get("timestamp", "")
        if role in ("user", "human"):
            s.userMessages += 1
            s.inputChars += len(content)
        elif role in ("model", "assistant"):
            s.turns += 1
            s.outputChars += len(content)
            mname = normalize_model(m.get("model", "gemini"))
            s.modelChars[mname] = s.modelChars.get(mname, 0) + len(content)
            tok = m.get("tokens") or m.get("usage") or {}
            if isinstance(tok, dict):
                s.measuredInputTokens += int(tok.get("input", tok.get("input_tokens", 0)) or 0)
                s.measuredOutputTokens += int(tok.get("output", tok.get("output_tokens", 0)) or 0)
    return s


def scan() -> list[SessionSummary]:
    out: list[SessionSummary] = []
    base = base_dir()
    if not base.is_dir():
        return out

    # logs.json in tmp/ subdirs
    tmp = base / "tmp"
    if tmp.is_dir():
        for sub in tmp.iterdir():
            if sub.is_dir():
                logs = sub / "logs.json"
                if logs.exists():
                    out.extend(_parse_logs(logs))

    # Per-session JSON files in chats/ or sessions/
    for sub in ("chats", "sessions"):
        d = base / sub
        if d.is_dir():
            for jf in d.glob("*.json"):
                s = _parse_chat(jf)
                if s:
                    out.append(s)

    # Default project from cwd? unknown — keep as such
    for s in out:
        if not s.project or s.project == "unknown":
            s.project = "gemini"
    return out
