# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Claude CLI / Desktop scanner — `~/.claude/projects/{slug}/*.jsonl`.

Claude logs include REAL token counts in `message.usage`, so we use them
directly instead of estimating from character counts.
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

ID = "claude"
DISPLAY = "Claude CLI"


def base_dirs() -> list[Path]:
    dirs: list[Path] = []
    env_many = os.environ.get("CLAUDE_CONFIG_DIRS")
    if env_many:
        dirs.extend(Path(p) for p in env_many.split(":") if p)
    env_one = os.environ.get("CLAUDE_CONFIG_DIR")
    if env_one:
        dirs.append(Path(env_one))
    if not dirs:
        dirs.append(home() / ".claude")
    return dirs


def is_available() -> bool:
    return any(d.is_dir() for d in base_dirs())


def _unslug(name: str) -> str:
    # Claude encodes the project path as e.g. "-Users-foo-projects-bar"
    if name.startswith("-"):
        return "/" + name[1:].replace("-", "/")
    return name


def _parse_jsonl(filepath: Path, project_slug: str) -> SessionSummary:
    s = SessionSummary(source=ID, file=filepath.name, sessionId=filepath.stem)
    s.cwd = _unslug(project_slug)
    s.project = project_name_from_path(s.cwd)
    for line in safe_iter_lines(filepath):
        entry = safe_load_json(line)
        if not entry:
            continue
        etype = entry.get("type", "")
        if etype == "user":
            s.userMessages += 1
            msg = entry.get("message", {})
            content = msg.get("content", "")
            s.inputChars += len(content if isinstance(content, str) else str(content))
            if not s.startTime:
                s.startTime = entry.get("timestamp", "")
        elif etype == "assistant":
            s.turns += 1
            if not s.startTime:
                s.startTime = entry.get("timestamp", "")
            msg = entry.get("message", {})
            usage = msg.get("usage") or {}
            model = normalize_model(msg.get("model", ""))
            inp = int(usage.get("input_tokens", 0) or 0)
            out = int(usage.get("output_tokens", 0) or 0)
            cw = int(usage.get("cache_creation_input_tokens", 0) or 0)
            cr = int(usage.get("cache_read_input_tokens", 0) or 0)
            s.measuredInputTokens += inp
            s.measuredOutputTokens += out
            s.measuredCacheWriteTokens += cw
            s.measuredCacheReadTokens += cr
            mt = s.modelTokens.setdefault(model, {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0})
            mt["input"] += inp
            mt["output"] += out
            mt["cacheRead"] += cr
            mt["cacheWrite"] += cw
        elif etype == "tool_use" or etype == "tool_result":
            s.toolCalls += 1
    return s


def scan() -> list[SessionSummary]:
    out: list[SessionSummary] = []
    for base in base_dirs():
        projects = base / "projects"
        if not projects.is_dir():
            continue
        for proj in projects.iterdir():
            if not proj.is_dir():
                continue
            for jsonl in proj.glob("*.jsonl"):
                out.append(_parse_jsonl(jsonl, proj.name))
    return out
