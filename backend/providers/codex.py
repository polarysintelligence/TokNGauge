# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""OpenAI Codex CLI scanner — `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`.

Codex logs include `event_msg` events of type `token_count` with cumulative
`total_token_usage` and per-turn `last_token_usage`. We aggregate per session.
"""
from __future__ import annotations

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

ID = "codex"
DISPLAY = "Codex CLI"


def base_dir() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else home() / ".codex"


def sessions_dir() -> Path:
    d = base_dir() / "sessions"
    if d.is_dir():
        return d
    return base_dir()


def is_available() -> bool:
    return base_dir().is_dir()


def _parse_session(filepath: Path) -> SessionSummary:
    s = SessionSummary(source=ID, file=filepath.name)
    current_model = "unknown"
    total_in = total_out = total_cached = 0
    for line in safe_iter_lines(filepath):
        e = safe_load_json(line)
        if not e:
            continue
        et = e.get("type", "")
        payload = e.get("payload", {}) or {}
        if et == "session_meta":
            s.sessionId = payload.get("id", "")
            s.startTime = payload.get("timestamp", e.get("timestamp", ""))
            cwd = payload.get("cwd", "")
            s.cwd = cwd
            s.project = project_name_from_path(cwd)
        elif et == "turn_context":
            model = payload.get("model", "") or (payload.get("collaboration_mode", {}) or {}).get("settings", {}).get("model", "")
            if model:
                current_model = normalize_model(model)
        elif et == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info", {}) or {}
            total = info.get("total_token_usage") or {}
            # Use cumulative totals (last one wins)
            total_in = int(total.get("input_tokens", total_in) or total_in)
            total_out = int(total.get("output_tokens", total_out) or total_out)
            total_cached = int(total.get("cached_input_tokens", total_cached) or total_cached)
            s.turns += 1  # rough turn count from token_count events
        elif et == "response_item":
            role = (payload.get("role") or "")
            if role == "user":
                s.userMessages += 1
                content = payload.get("content")
                s.inputChars += len(str(content)) if content else 0
            elif role == "assistant":
                content = payload.get("content")
                s.outputChars += len(str(content)) if content else 0
            if payload.get("type") == "function_call":
                s.toolCalls += 1
    s.measuredInputTokens = total_in
    s.measuredOutputTokens = total_out
    s.measuredCacheReadTokens = total_cached
    if total_in or total_out:
        s.modelTokens[current_model] = {
            "input": total_in, "output": total_out,
            "cacheRead": total_cached, "cacheWrite": 0,
        }
    return s


def scan() -> list[SessionSummary]:
    out: list[SessionSummary] = []
    root = sessions_dir()
    if not root.is_dir():
        return out
    for jsonl in root.rglob("*.jsonl"):
        out.append(_parse_session(jsonl))
    return out
