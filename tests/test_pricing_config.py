# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Tests for the pricing.json source-of-truth and config fxRates merge."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import config as cfg_mod
from backend import pricing as pricing_mod
from backend.cost_estimation import _model_cost


@pytest.fixture
def isolated_pricing(tmp_path, monkeypatch):
    """Point pricing + config at a throwaway dir and reset module caches."""
    monkeypatch.setenv("TOKNGAUGE_PRICING", str(tmp_path / "pricing.json"))
    monkeypatch.setenv("TOKNGAUGE_CONFIG", str(tmp_path / "config.json"))
    importlib.reload(pricing_mod)
    yield tmp_path
    pricing_mod._cache = None


# ── pricing.json bootstrap ─────────────────────────────────────────


def test_pricing_bootstrap_writes_full_table(isolated_pricing):
    p = pricing_mod.pricing_path()
    assert p.exists(), "first access must materialize the file"
    data = json.loads(p.read_text(encoding="utf-8"))
    # Every fallback model must be present in the on-disk file.
    for name in pricing_mod._FALLBACK_MODEL_PRICING:
        assert name in data["models"]
        for field in ("input", "output", "cacheRead", "cacheWrite"):
            assert data["models"][name][field] == pricing_mod._FALLBACK_MODEL_PRICING[name][field]
    for name, val in pricing_mod._FALLBACK_PREMIUM_MULTIPLIERS.items():
        assert data["premium"][name] == val


def test_snapshot_after_bootstrap_has_empty_overrides(isolated_pricing):
    snap = pricing_mod.snapshot()
    assert snap["overrides"] == {"models": {}, "premium": {}}
    # And the effective table equals the fallbacks.
    assert snap["effective"]["models"]["claude-opus-4"]["input"] == 15.0


# ── pricing.save ───────────────────────────────────────────────────


def test_save_partial_persists_full_table_and_diff(isolated_pricing):
    pricing_mod.snapshot()  # bootstrap
    pricing_mod.save({"models": {"claude-opus-4": {"input": 99.0}}})
    snap = pricing_mod.snapshot()
    # File still has every model
    on_disk = json.loads(pricing_mod.pricing_path().read_text(encoding="utf-8"))
    assert set(on_disk["models"]) >= set(pricing_mod._FALLBACK_MODEL_PRICING)
    # Only the edited field shows up as override
    assert snap["overrides"]["models"] == {"claude-opus-4": {"input": 99.0}}
    assert snap["effective"]["models"]["claude-opus-4"]["input"] == 99.0
    # Untouched field stays
    assert snap["effective"]["models"]["claude-opus-4"]["output"] == 75.0


def test_save_empty_dict_removes_model(isolated_pricing):
    pricing_mod.snapshot()
    pricing_mod.save({"models": {"claude-opus-4": {}}})
    on_disk = json.loads(pricing_mod.pricing_path().read_text(encoding="utf-8"))
    assert "claude-opus-4" not in on_disk["models"]
    # Effective table still resolves via the embedded fallback.
    eff = pricing_mod.snapshot()["effective"]
    assert eff["models"]["claude-opus-4"]["input"] == 15.0


def test_reset_regenerates_file(isolated_pricing):
    pricing_mod.snapshot()
    pricing_mod.save({"models": {"claude-opus-4": {"input": 1.0}}})
    pricing_mod.reset()
    snap = pricing_mod.snapshot()
    assert snap["overrides"] == {"models": {}, "premium": {}}
    assert snap["effective"]["models"]["claude-opus-4"]["input"] == 15.0


# ── cost formula — README worked example ───────────────────────────


def test_readme_worked_example_claude_opus_4(isolated_pricing):
    """50K in + 8K out + 12K cacheR + 2K cacheW on claude-opus-4 → 1.4055 USD."""
    pricing_mod.snapshot()  # bootstrap defaults
    cost = _model_cost("claude-opus-4", 50_000, 8_000, 12_000, 2_000)
    assert round(cost, 4) == 1.4055


# ── config.fxRates ─────────────────────────────────────────────────


def test_fx_rates_default(isolated_pricing):
    cfg = cfg_mod.load()
    assert cfg["fxRates"] == {"USD": 1.0, "EUR": 0.92, "GBP": 0.79}


def test_fx_rates_partial_merge_preserves_others(isolated_pricing):
    cfg_mod.save({"fxRates": {"EUR": 0.95}})
    cfg = cfg_mod.load()
    assert cfg["fxRates"]["EUR"] == 0.95
    assert cfg["fxRates"]["GBP"] == 0.79  # untouched
    assert cfg["fxRates"]["USD"] == 1.0   # always pinned


def test_fx_rates_rejects_invalid_entries(isolated_pricing):
    cfg_mod.save({"fxRates": {"XXX": 9.9, "EUR": -1, "GBP": "nope"}})
    cfg = cfg_mod.load()
    assert "XXX" not in cfg["fxRates"]
    assert cfg["fxRates"]["EUR"] == 0.92  # negative ignored
    assert cfg["fxRates"]["GBP"] == 0.79  # non-numeric ignored
    assert cfg["fxRates"]["USD"] == 1.0


def test_fx_rates_usd_cannot_be_overridden(isolated_pricing):
    cfg_mod.save({"fxRates": {"USD": 42.0}})
    cfg = cfg_mod.load()
    assert cfg["fxRates"]["USD"] == 1.0
