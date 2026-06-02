# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""User configuration (persisted at ``<project_root>/config.json``)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "language": "es",
    "currency": "USD",
    "charsPerToken": 4,
    "inputMultiplier": 5,
    "enabledProviders": ["copilot-cli", "copilot-vscode", "cursor", "claude", "codex", "gemini"],
    # FX rates relative to 1 USD. Edit in the Settings panel or here directly
    # if the defaults drift too far from reality.
    "fxRates": {"USD": 1.0, "EUR": 0.92, "GBP": 0.79},
}

VALID_LANGUAGES = {"es", "en"}
VALID_CURRENCIES = {"USD", "EUR", "GBP"}


_LEGACY_PATH = Path.home() / ".tokngauge" / "config.json"


def _project_root() -> Path:
    """Repository root (parent of the ``backend/`` package)."""
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    override = os.environ.get("TOKNGAUGE_CONFIG")
    if override:
        return Path(override)
    project_file = _project_root() / "config.json"
    # One-time migration from the legacy ~/.tokngauge/ location so existing
    # users keep their settings without having to re-pick language/currency.
    if not project_file.exists() and _LEGACY_PATH.exists():
        try:
            project_file.write_text(_LEGACY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass
    return project_file


def load() -> dict[str, Any]:
    p = config_path()
    cfg = dict(DEFAULTS)
    cfg["fxRates"] = dict(DEFAULTS["fxRates"])
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if k not in DEFAULTS:
                        continue
                    if k == "fxRates" and isinstance(v, dict):
                        # Merge partial fxRates over defaults so a file
                        # missing one currency keeps the fallback rate.
                        merged = dict(cfg["fxRates"])
                        for ccy, rate in v.items():
                            if ccy in VALID_CURRENCIES:
                                try:
                                    merged[ccy] = float(rate)
                                except (TypeError, ValueError):
                                    pass
                        merged["USD"] = 1.0
                        cfg[k] = merged
                    else:
                        cfg[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save(updates: dict[str, Any]) -> dict[str, Any]:
    cfg = load()
    for k, v in updates.items():
        if k not in DEFAULTS:
            continue
        if k == "language" and v not in VALID_LANGUAGES:
            continue
        if k == "currency" and v not in VALID_CURRENCIES:
            continue
        if k == "charsPerToken":
            try:
                v = max(1, min(20, int(v)))
            except (TypeError, ValueError):
                continue
        if k == "inputMultiplier":
            try:
                v = max(0.0, min(50.0, float(v)))
            except (TypeError, ValueError):
                continue
        if k == "enabledProviders":
            if not isinstance(v, list):
                continue
            v = [str(x) for x in v if isinstance(x, str)]
        if k == "fxRates":
            if not isinstance(v, dict):
                continue
            merged = dict(cfg.get("fxRates") or DEFAULTS["fxRates"])
            for ccy, rate in v.items():
                if ccy not in VALID_CURRENCIES:
                    continue
                try:
                    r = float(rate)
                except (TypeError, ValueError):
                    continue
                if r <= 0 or r > 1000:
                    continue
                merged[ccy] = r
            merged["USD"] = 1.0  # USD is always the base.
            v = merged
        cfg[k] = v

    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        from .cost_estimation import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    return cfg
