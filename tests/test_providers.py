# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Unit tests for backend providers and config — uses temp dirs only."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make backend importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import config as cfg_mod
from backend.cost_estimation import summary_to_billing
from backend.providers import claude, codex, copilot_cli, cursor, gemini
from backend.providers._base import SessionSummary, project_name_from_path


# ── Helpers ────────────────────────────────────────────────────────


def write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")


# ── _base helpers ──────────────────────────────────────────────────


def test_project_name_from_path():
    assert project_name_from_path("/foo/bar/baz") == "baz"
    assert project_name_from_path("file:///foo/bar/baz%20qux") == "baz qux"
    assert project_name_from_path("") == "unknown"
    assert project_name_from_path("/") == "unknown"


# ── Config ─────────────────────────────────────────────────────────


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKNGAUGE_CONFIG", str(tmp_path / "config.json"))
    cfg = cfg_mod.load()
    assert cfg["language"] == "es"
    cfg2 = cfg_mod.save({"language": "en", "charsPerToken": 5, "inputMultiplier": 7})
    assert cfg2["language"] == "en"
    assert cfg2["charsPerToken"] == 5
    assert cfg2["inputMultiplier"] == 7
    # Invalid values are silently ignored
    cfg3 = cfg_mod.save({"language": "fr", "charsPerToken": 9999})
    assert cfg3["language"] == "en"
    assert cfg3["charsPerToken"] == 20  # clamped


# ── Copilot CLI provider ───────────────────────────────────────────


def test_copilot_cli_parses_session(tmp_path, monkeypatch):
    sid = tmp_path / "abc"
    sid.mkdir()
    write_jsonl(sid / "events.jsonl", [
        {"type": "session.start", "data": {"sessionId": "s1", "startTime": "2026-05-01T10:00:00Z"}},
        {"type": "session.model_change", "data": {"newModel": "claude-sonnet-4"}},
        {"type": "user.message", "data": {"content": "hello"}},
        {"type": "assistant.message", "data": {"content": "world response", "toolRequests": [{"arguments": "x"}]}},
    ])
    (sid / "workspace.yaml").write_text("cwd: /tmp/myproject\n", encoding="utf-8")

    monkeypatch.setattr(copilot_cli, "base_dir", lambda: tmp_path)
    sessions = copilot_cli.scan()
    assert len(sessions) == 1
    s = sessions[0]
    assert s.sessionId == "s1"
    assert s.project == "myproject"
    assert s.turns == 1
    assert s.userMessages == 1
    assert s.toolCalls == 1
    assert s.outputChars > 0


# ── Claude provider ────────────────────────────────────────────────


def test_claude_uses_measured_tokens(tmp_path, monkeypatch):
    base = tmp_path / "claude_home"
    proj = base / "projects" / "-Users-foo-myrepo"
    proj.mkdir(parents=True)
    write_jsonl(proj / "sess.jsonl", [
        {"type": "user", "timestamp": "2026-05-01T10:00:00Z",
         "message": {"content": "hi"}},
        {"type": "assistant", "timestamp": "2026-05-01T10:00:05Z",
         "message": {"model": "claude-sonnet-4-5",
                     "usage": {"input_tokens": 100, "output_tokens": 50,
                               "cache_creation_input_tokens": 10,
                               "cache_read_input_tokens": 5}}},
    ])

    monkeypatch.setattr(claude, "base_dirs", lambda: [base])
    sessions = claude.scan()
    assert len(sessions) == 1
    s = sessions[0]
    assert s.project == "myrepo"
    assert s.measuredInputTokens == 100
    assert s.measuredOutputTokens == 50
    assert s.measuredCacheReadTokens == 5
    assert s.measuredCacheWriteTokens == 10
    assert "claude-sonnet-4" in s.modelTokens

    billing = summary_to_billing(s, chars_per_token=4, input_multiplier=5)
    assert billing["measured"] is True
    assert billing["inputTokens"] == 100
    assert billing["outputTokens"] == 50
    assert billing["estimatedCostUSD"] > 0


# ── Codex provider ─────────────────────────────────────────────────


def test_codex_aggregates_token_counts(tmp_path, monkeypatch):
    sess = tmp_path / "rollout.jsonl"
    write_jsonl(sess, [
        {"type": "session_meta", "timestamp": "2026-05-01T10:00:00Z",
         "payload": {"id": "c1", "timestamp": "2026-05-01T10:00:00Z",
                     "cwd": "/tmp/codexproj"}},
        {"type": "turn_context", "payload": {"model": "gpt-5-codex"}},
        {"type": "event_msg", "payload": {"type": "token_count",
            "info": {"total_token_usage": {"input_tokens": 200, "output_tokens": 80, "cached_input_tokens": 50}}}},
        {"type": "event_msg", "payload": {"type": "token_count",
            "info": {"total_token_usage": {"input_tokens": 500, "output_tokens": 150, "cached_input_tokens": 90}}}},
    ])

    monkeypatch.setattr(codex, "sessions_dir", lambda: tmp_path)
    sessions = codex.scan()
    assert len(sessions) == 1
    s = sessions[0]
    assert s.project == "codexproj"
    # Last cumulative wins
    assert s.measuredInputTokens == 500
    assert s.measuredOutputTokens == 150
    assert s.measuredCacheReadTokens == 90


# ── Gemini provider ────────────────────────────────────────────────


def test_gemini_parses_chat(tmp_path, monkeypatch):
    base = tmp_path / "gemini"
    chats = base / "chats"
    chats.mkdir(parents=True)
    (chats / "c1.json").write_text(json.dumps({
        "messages": [
            {"role": "user", "content": "hi", "timestamp": "2026-05-01T10:00:00Z"},
            {"role": "model", "model": "gemini-2.5-pro", "content": "hello back",
             "tokens": {"input_tokens": 3, "output_tokens": 5}},
        ]
    }), encoding="utf-8")

    monkeypatch.setattr(gemini, "base_dir", lambda: base)
    sessions = gemini.scan()
    assert len(sessions) == 1
    s = sessions[0]
    assert s.turns == 1
    assert s.measuredInputTokens == 3
    assert s.measuredOutputTokens == 5


# ── Cursor provider ────────────────────────────────────────────────


def test_cursor_parses_transcript(tmp_path, monkeypatch):
    base = tmp_path / "cursor_ws"
    ws = base / "ws-abc"
    tdir = ws / "anysphere.cursor-chat" / "transcripts"
    tdir.mkdir(parents=True)
    (ws / "workspace.json").write_text(json.dumps({"folder": "file:///Users/foo/myrepo"}), encoding="utf-8")
    write_jsonl(tdir / "t1.jsonl", [
        {"type": "user", "data": {"content": "hi", "timestamp": "2026-05-01T10:00:00Z"}},
        {"type": "assistant", "data": {"content": "hey there", "model": "claude-sonnet-4"}},
    ])

    monkeypatch.setattr(cursor, "workspace_storage", lambda: base)
    sessions = cursor.scan()
    assert len(sessions) == 1
    s = sessions[0]
    assert s.project == "myrepo"
    assert s.userMessages == 1
    assert s.turns == 1
    assert s.outputChars > 0


# ── Billing: heuristic path ────────────────────────────────────────


def test_heuristic_billing():
    s = SessionSummary(source="copilot-cli", outputChars=400, inputChars=100, turns=2,
                       modelChars={"claude-sonnet-4": 400})
    b = summary_to_billing(s, chars_per_token=4, input_multiplier=5)
    assert b["measured"] is False
    assert b["outputTokens"] == 100
    assert b["inputTokens"] == 500  # 100 * 5
    assert b["estimatedCostUSD"] > 0


# ── Billing: changing formula impacts cost ─────────────────────────


def test_formula_tuning_changes_cost():
    s = SessionSummary(source="copilot-cli", outputChars=4000, inputChars=200, turns=1,
                       modelChars={"claude-sonnet-4": 4000})
    a = summary_to_billing(s, chars_per_token=4, input_multiplier=5)
    b = summary_to_billing(s, chars_per_token=8, input_multiplier=2)
    assert a["estimatedCostUSD"] > b["estimatedCostUSD"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
