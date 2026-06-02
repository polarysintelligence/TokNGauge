# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""HTTP integration tests for the FastAPI routes in ``backend.cost_api``."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import pricing as pricing_mod  # noqa: E402
from backend.cost_api import router as cost_router  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with isolated pricing.json + config.json under tmp_path."""
    monkeypatch.setenv("TOKNGAUGE_PRICING", str(tmp_path / "pricing.json"))
    monkeypatch.setenv("TOKNGAUGE_CONFIG", str(tmp_path / "config.json"))
    importlib.reload(pricing_mod)
    app = FastAPI()
    app.include_router(cost_router)
    with TestClient(app) as c:
        yield c
    pricing_mod._cache = None


# ── /api/pricing ───────────────────────────────────────────────────


def test_get_pricing_shape(client):
    r = client.get("/api/pricing")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"path", "exists", "defaults", "overrides", "effective"}
    assert body["exists"] is True  # snapshot bootstraps the file
    assert body["overrides"] == {"models": {}, "premium": {}}
    assert body["effective"]["models"]["claude-opus-4"]["input"] == 15.0


def test_post_pricing_partial_override(client):
    r = client.post(
        "/api/pricing",
        json={"models": {"claude-opus-4": {"input": 99.0}}, "premium": {"claude-opus-4": 5.0}},
    )
    assert r.status_code == 200
    body = r.json()
    # Override diff should contain only the changed fields.
    assert body["overrides"]["models"] == {"claude-opus-4": {"input": 99.0}}
    assert body["overrides"]["premium"] == {"claude-opus-4": 5.0}
    # Effective table reflects the change while keeping untouched fields.
    eff = body["effective"]["models"]["claude-opus-4"]
    assert eff["input"] == 99.0
    assert eff["output"] == 75.0  # untouched fallback
    assert body["effective"]["premium"]["claude-opus-4"] == 5.0


def test_post_pricing_empty_model_removes_it(client):
    # First set an override so there's something to remove.
    client.post("/api/pricing", json={"models": {"claude-opus-4": {"input": 99.0}}})
    # Empty {} for a model wipes its overrides.
    r = client.post("/api/pricing", json={"models": {"claude-opus-4": {}}})
    assert r.status_code == 200
    body = r.json()
    assert "claude-opus-4" not in body["overrides"]["models"]
    # The fallback value comes back through.
    assert body["effective"]["models"]["claude-opus-4"]["input"] == 15.0


def test_delete_pricing_resets_to_defaults(client):
    client.post("/api/pricing", json={"models": {"claude-opus-4": {"input": 1.0}}})
    r = client.delete("/api/pricing")
    assert r.status_code == 200
    body = r.json()
    assert body["overrides"] == {"models": {}, "premium": {}}
    assert body["effective"]["models"]["claude-opus-4"]["input"] == 15.0


def test_post_pricing_reload_picks_up_manual_edit(client, tmp_path):
    # Bootstrap file via a GET.
    client.get("/api/pricing")
    p = Path(tmp_path / "pricing.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    data["models"]["claude-opus-4"]["input"] = 42.0
    p.write_text(json.dumps(data), encoding="utf-8")

    r = client.post("/api/pricing/reload")
    assert r.status_code == 200
    assert r.json()["effective"]["models"]["claude-opus-4"]["input"] == 42.0


# ── /api/config ────────────────────────────────────────────────────


def test_get_config_returns_defaults_including_fx(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] in {"EUR", "USD", "GBP"}
    assert body["fxRates"]["USD"] == 1.0
    assert "EUR" in body["fxRates"]
    assert "GBP" in body["fxRates"]


def test_post_config_fx_partial_merge(client):
    r = client.post("/api/config", json={"fxRates": {"EUR": 0.95}})
    assert r.status_code == 200
    fx = r.json()["fxRates"]
    assert fx["USD"] == 1.0
    assert fx["EUR"] == 0.95
    assert fx["GBP"] == 0.79  # untouched default preserved


def test_post_config_fx_rejects_invalid_entries(client):
    # USD must stay pinned to 1.0; unknown currencies dropped; non-positive rejected.
    r = client.post(
        "/api/config",
        json={"fxRates": {"USD": 42.0, "XXX": 9.0, "EUR": -1.0, "GBP": 0.81}},
    )
    assert r.status_code == 200
    fx = r.json()["fxRates"]
    assert fx["USD"] == 1.0
    assert "XXX" not in fx
    assert fx["EUR"] == 0.92  # invalid → kept previous value (default)
    assert fx["GBP"] == 0.81


# ── /api/providers ─────────────────────────────────────────────────


def test_get_providers_returns_list(client):
    r = client.get("/api/providers")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert any("id" in p for p in body)
