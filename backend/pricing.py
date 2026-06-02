# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Model pricing (USD per 1M tokens).

The full price table lives in ``<project_root>/pricing.json``. On first run
(or if you delete the file) it is recreated from the embedded ``_FALLBACK_*``
tables in this module — those exist purely as a safety net so the app still
boots if the JSON is missing or unreadable.

The file shape is::

    {
      "models": {
        "claude-opus-4": {"input": 15.0, "output": 75.0, "cacheRead": 1.5, "cacheWrite": 18.75},
        ...
      },
      "premium": {
        "claude-opus-4": 3.0,
        ...
      }
    }

Edit the file directly (then call :func:`reload`) or use the Settings UI /
``POST /api/pricing`` to change values.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

# ── Embedded fallback (only used if the JSON file is missing/unreadable) ──
_FALLBACK_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4": {"input": 15.0, "output": 75.0, "cacheRead": 1.5, "cacheWrite": 18.75},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cacheRead": 0.3, "cacheWrite": 3.75},
    "claude-haiku": {"input": 0.25, "output": 1.25, "cacheRead": 0.03, "cacheWrite": 0.30},
    "gpt-4.1": {"input": 2.0, "output": 8.0, "cacheRead": 0.5, "cacheWrite": 0.0},
    "gpt-4o": {"input": 2.5, "output": 10.0, "cacheRead": 1.25, "cacheWrite": 0.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cacheRead": 0.075, "cacheWrite": 0.0},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0, "cacheRead": 0.3125, "cacheWrite": 0.0},
    "unknown": {"input": 3.0, "output": 15.0, "cacheRead": 0.0, "cacheWrite": 0.0},
}

_FALLBACK_PREMIUM_MULTIPLIERS: dict[str, float] = {
    "claude-opus-4": 3.0,
    "claude-sonnet-4": 1.0,
    "claude-haiku": 0.33,
    "gpt-4.1": 0.0,
    "gpt-4o": 0.0,
    "gpt-4o-mini": 0.0,
    "gemini-2.5-pro": 1.0,
    "unknown": 1.0,
}

# Backwards-compatible aliases (older callers used these names).
DEFAULT_MODEL_PRICING = _FALLBACK_MODEL_PRICING
DEFAULT_PREMIUM_MULTIPLIERS = _FALLBACK_PREMIUM_MULTIPLIERS

_PRICE_FIELDS = ("input", "output", "cacheRead", "cacheWrite")

# ── State ─────────────────────────────────────────────────────────
_cache: dict[str, Any] | None = None


def _project_root() -> Path:
    """Repository root (parent of the ``backend/`` package)."""
    return Path(__file__).resolve().parent.parent


_LEGACY_PATH = Path.home() / ".tokngauge" / "pricing.json"


def _write_json(p: Path, data: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")


def _bootstrap_file(p: Path) -> None:
    """Create ``pricing.json`` from embedded fallbacks (or migrate legacy)."""
    if p.exists():
        return
    # Prefer migrating the user's previous overrides (if any), merged on top
    # of the embedded defaults — so we end up with a full, self-describing
    # file regardless of how partial the legacy one was.
    legacy_data: dict[str, Any] = {}
    if _LEGACY_PATH.exists():
        try:
            raw = json.loads(_LEGACY_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                legacy_data = raw
        except (OSError, json.JSONDecodeError):
            legacy_data = {}
    merged = _merge(_FALLBACK_MODEL_PRICING, _FALLBACK_PREMIUM_MULTIPLIERS, legacy_data)
    try:
        _write_json(p, merged)
    except OSError:
        pass


def pricing_path() -> Path:
    override = os.environ.get("TOKNGAUGE_PRICING")
    if override:
        p = Path(override)
    else:
        p = _project_root() / "pricing.json"
    _bootstrap_file(p)
    return p


def _read_file() -> dict[str, Any]:
    """Return the raw contents of pricing.json (full table or partial)."""
    p = pricing_path()
    if not p.exists():
        return {"models": {}, "premium": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"models": {}, "premium": {}}
    if not isinstance(data, dict):
        return {"models": {}, "premium": {}}
    models = data.get("models") if isinstance(data.get("models"), dict) else {}
    premium = data.get("premium") if isinstance(data.get("premium"), dict) else {}
    return {"models": models, "premium": premium}


# Backwards-compat alias used elsewhere in the module.
_read_overrides = _read_file


def _diff_vs_fallback(file_data: dict[str, Any]) -> dict[str, Any]:
    """Return the subset of ``file_data`` that differs from the embedded
    fallback tables. Used by the UI to mark "customized" rows."""
    out_models: dict[str, dict[str, float]] = {}
    for name, fields in (file_data.get("models") or {}).items():
        if not isinstance(fields, dict):
            continue
        base = _FALLBACK_MODEL_PRICING.get(name)
        if base is None:
            # Model that isn't in fallbacks at all → fully user-defined.
            out_models[name] = dict(fields)
            continue
        diff = {k: v for k, v in fields.items()
                if k in _PRICE_FIELDS and base.get(k) != v}
        if diff:
            out_models[name] = diff
    out_premium: dict[str, float] = {}
    for name, val in (file_data.get("premium") or {}).items():
        base = _FALLBACK_PREMIUM_MULTIPLIERS.get(name)
        if base is None or base != val:
            out_premium[name] = val
    return {"models": out_models, "premium": out_premium}


def _merge(defaults_models: dict, defaults_premium: dict, overrides: dict) -> dict[str, Any]:
    models = copy.deepcopy(defaults_models)
    for name, fields in (overrides.get("models") or {}).items():
        if not isinstance(name, str) or not isinstance(fields, dict):
            continue
        base = models.get(name, {"input": 0.0, "output": 0.0, "cacheRead": 0.0, "cacheWrite": 0.0})
        merged = dict(base)
        for k in _PRICE_FIELDS:
            if k in fields:
                try:
                    merged[k] = max(0.0, float(fields[k]))
                except (TypeError, ValueError):
                    continue
        models[name] = merged

    premium = dict(defaults_premium)
    for name, val in (overrides.get("premium") or {}).items():
        if not isinstance(name, str):
            continue
        try:
            premium[name] = max(0.0, float(val))
        except (TypeError, ValueError):
            continue
    return {"models": models, "premium": premium}


def _effective() -> dict[str, Any]:
    global _cache
    if _cache is None:
        # File is the source of truth; embedded fallbacks fill any gaps so the
        # app keeps working even if pricing.json was partially edited by hand.
        _cache = _merge(_FALLBACK_MODEL_PRICING, _FALLBACK_PREMIUM_MULTIPLIERS, _read_file())
    return _cache


def reload() -> dict[str, Any]:
    """Drop the in-memory cache and re-read overrides from disk."""
    global _cache
    _cache = None
    # Also bust the cost cache so prices apply on next request.
    try:
        from .cost_estimation import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    return _effective()


def get_model_pricing() -> dict[str, dict[str, float]]:
    return _effective()["models"]


def get_premium_multipliers() -> dict[str, float] :
    return _effective()["premium"]


def get_model_price(model: str) -> dict[str, float]:
    table = get_model_pricing()
    return table.get(model, table["unknown"])


def get_premium(model: str) -> float:
    return get_premium_multipliers().get(model, 1.0)


# ── Public API used by routes ─────────────────────────────────────
def snapshot() -> dict[str, Any]:
    """Return file contents, embedded fallbacks, the diff vs fallback (used by
    the UI to highlight customized rows) and the effective resolved table."""
    file_data = _read_file()
    effective = _effective()
    return {
        "path": str(pricing_path()),
        "exists": pricing_path().exists(),
        "defaults": {
            "models": _FALLBACK_MODEL_PRICING,
            "premium": _FALLBACK_PREMIUM_MULTIPLIERS,
        },
        "overrides": _diff_vs_fallback(file_data),
        "effective": effective,
    }


def save(payload: dict[str, Any]) -> dict[str, Any]:
    """Patch the on-disk pricing file with ``payload`` and persist the full
    resulting table.

    ``payload`` accepts the same shape as the file: ``{"models": {...},
    "premium": {...}}``. Unknown fields are ignored. Pass an empty dict for
    a model to delete it from the file (it will then fall back to the
    embedded default, if any).
    """
    current = _read_file()
    models = dict(current.get("models") or {})
    premium = dict(current.get("premium") or {})

    in_models = payload.get("models") if isinstance(payload, dict) else None
    if isinstance(in_models, dict):
        for name, fields in in_models.items():
            if not isinstance(name, str):
                continue
            if fields is None or fields == {}:
                models.pop(name, None)
                continue
            if not isinstance(fields, dict):
                continue
            entry = dict(models.get(name) or _FALLBACK_MODEL_PRICING.get(name) or {})
            for k in _PRICE_FIELDS:
                if k in fields:
                    try:
                        entry[k] = max(0.0, float(fields[k]))
                    except (TypeError, ValueError):
                        continue
            if entry:
                models[name] = entry

    in_premium = payload.get("premium") if isinstance(payload, dict) else None
    if isinstance(in_premium, dict):
        for name, val in in_premium.items():
            if not isinstance(name, str):
                continue
            if val is None:
                premium.pop(name, None)
                continue
            try:
                premium[name] = max(0.0, float(val))
            except (TypeError, ValueError):
                continue

    out = {"models": models, "premium": premium}
    _write_json(pricing_path(), out)
    reload()
    return snapshot()


def reset() -> dict[str, Any]:
    """Delete user overrides file and reload defaults."""
    p = pricing_path()
    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass
    reload()
    return snapshot()
