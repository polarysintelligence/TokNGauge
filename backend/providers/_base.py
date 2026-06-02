# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Shared helpers and types for provider scanners."""
from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote


@dataclass
class SessionSummary:
    """A normalized representation of one local agent/IDE session."""

    sessionId: str = ""
    source: str = ""              # provider id (copilot-cli, claude, ...)
    file: str = ""
    startTime: str = ""           # ISO 8601
    project: str = "unknown"
    cwd: str = ""
    turns: int = 0
    userMessages: int = 0
    toolCalls: int = 0
    inputChars: int = 0
    outputChars: int = 0
    # When the source reports REAL token usage, populate these:
    measuredInputTokens: int = 0
    measuredOutputTokens: int = 0
    measuredCacheReadTokens: int = 0
    measuredCacheWriteTokens: int = 0
    modelChars: dict[str, int] = field(default_factory=dict)
    modelTokens: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def project_name_from_path(path: str) -> str:
    if not path:
        return "unknown"
    if path.startswith("file://"):
        path = unquote(path[7:])
    parts = path.rstrip("/").rstrip("\\").replace("\\", "/").split("/")
    return parts[-1] if parts and parts[-1] else "unknown"


def safe_iter_lines(filepath: Path) -> Iterable[str]:
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line
    except (OSError, PermissionError):
        return


def safe_load_json(line: str) -> dict | None:
    try:
        return json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None


def home() -> Path:
    return Path.home()


def vscode_workspace_storage() -> Path:
    system = platform.system()
    if system == "Darwin":
        return home() / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage"
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "workspaceStorage"
    return home() / ".config" / "Code" / "User" / "workspaceStorage"


def normalize_model(model_str: str) -> str:
    if not model_str:
        return "unknown"
    m = model_str.lower()
    if "opus" in m:
        return "claude-opus-4"
    if "sonnet" in m:
        return "claude-sonnet-4"
    if "haiku" in m:
        return "claude-haiku"
    if "gpt-5" in m and "mini" in m:
        return "gpt-4o-mini"
    if "gpt-4.1" in m:
        return "gpt-4.1"
    if "gpt-4o-mini" in m:
        return "gpt-4o-mini"
    if "gpt-4o" in m or "gpt-5" in m or "codex" in m:
        return "gpt-4o"
    if "gemini" in m:
        return "gemini-2.5-pro"
    return "unknown"
