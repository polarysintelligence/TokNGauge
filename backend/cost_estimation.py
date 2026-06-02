# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Multi-provider cost estimation.

Aggregates `SessionSummary`s from every available provider and computes
costs using the user-configurable formula. Sessions that report REAL token
usage (Claude, Codex, Gemini when available) use those values directly;
character-based sessions (Copilot) fall back to the heuristic
`tokens = chars / charsPerToken` plus `input ≈ output × inputMultiplier`.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from . import config as cfg_mod
from . import pricing as pricing_mod
from . import providers as providers_pkg
from .providers._base import SessionSummary

# ── Pricing (USD per 1M tokens) ───────────────────────────────────
# Defaults + user overrides live in `backend/pricing.py`. These names are
# kept as thin proxies for backwards compatibility with tests/imports.

def _pricing_table() -> dict[str, dict[str, float]]:
    return pricing_mod.get_model_pricing()


def _premium_table() -> dict[str, float]:
    return pricing_mod.get_premium_multipliers()


class _LazyDict:
    """Read-only view that always reflects current pricing."""

    def __init__(self, getter):
        self._getter = getter

    def __getitem__(self, k):
        return self._getter()[k]

    def get(self, k, default=None):
        return self._getter().get(k, default)

    def __iter__(self):
        return iter(self._getter())

    def items(self):
        return self._getter().items()

    def keys(self):
        return self._getter().keys()

    def values(self):
        return self._getter().values()


MODEL_PRICING = _LazyDict(_pricing_table)
PREMIUM_MULTIPLIERS = _LazyDict(_premium_table)


def _model_cost(model: str, t_in: int, t_out: int, t_cr: int = 0, t_cw: int = 0) -> float:
    p = pricing_mod.get_model_price(model)
    return (
        t_in * p.get("input", 0.0) / 1_000_000
        + t_out * p.get("output", 0.0) / 1_000_000
        + t_cr * p.get("cacheRead", 0.0) / 1_000_000
        + t_cw * p.get("cacheWrite", 0.0) / 1_000_000
    )


def summary_to_billing(s: SessionSummary, chars_per_token: int, input_multiplier: float) -> dict[str, Any]:
    """Convert a SessionSummary to a billing dict, using measured tokens when present."""
    measured = (s.measuredInputTokens + s.measuredOutputTokens) > 0
    models_breakdown: list[dict[str, Any]] = []

    if measured:
        input_tokens = s.measuredInputTokens
        output_tokens = s.measuredOutputTokens
        cache_read = s.measuredCacheReadTokens
        cache_write = s.measuredCacheWriteTokens
        total_cost = 0.0
        if s.modelTokens:
            for model, tk in s.modelTokens.items():
                c = _model_cost(model, tk.get("input", 0), tk.get("output", 0),
                                tk.get("cacheRead", 0), tk.get("cacheWrite", 0))
                total_cost += c
                premium = PREMIUM_MULTIPLIERS.get(model, 1.0)
                models_breakdown.append({
                    "model": model,
                    "inputTokens": tk.get("input", 0),
                    "outputTokens": tk.get("output", 0),
                    "cacheReadTokens": tk.get("cacheRead", 0),
                    "cacheWriteTokens": tk.get("cacheWrite", 0),
                    "cost": round(c, 6),
                    "premiumRequests": round(s.turns * premium, 1),
                })
        else:
            total_cost = _model_cost("unknown", input_tokens, output_tokens, cache_read, cache_write)
    else:
        output_tokens = max(0, s.outputChars // chars_per_token) if s.outputChars else 0
        approx_input = s.inputChars // chars_per_token if s.inputChars else 0
        input_tokens = max(approx_input, int(output_tokens * input_multiplier))
        cache_read = cache_write = 0
        total_cost = 0.0
        if s.modelChars:
            for model, chars in s.modelChars.items():
                m_out = max(0, chars // chars_per_token)
                m_in = int(m_out * input_multiplier)
                c = _model_cost(model, m_in, m_out)
                total_cost += c
                premium = PREMIUM_MULTIPLIERS.get(model, 1.0)
                models_breakdown.append({
                    "model": model,
                    "inputTokens": m_in,
                    "outputTokens": m_out,
                    "cacheReadTokens": 0,
                    "cacheWriteTokens": 0,
                    "cost": round(c, 6),
                    "premiumRequests": round(s.turns * premium, 1),
                })
        else:
            total_cost = _model_cost("unknown", input_tokens, output_tokens)

    return {
        "sessionId": s.sessionId,
        "source": s.source,
        "file": s.file,
        "startTime": s.startTime,
        "project": s.project,
        "cwd": s.cwd,
        "turns": s.turns,
        "userMessages": s.userMessages,
        "toolCalls": s.toolCalls,
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "cacheReadTokens": cache_read,
        "cacheWriteTokens": cache_write,
        "totalTokens": input_tokens + output_tokens + cache_read + cache_write,
        "estimatedCostUSD": round(total_cost, 6),
        "measured": measured,
        "models": models_breakdown,
    }


def _parse_date(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _aggregate_period(sessions: list[dict], period: str) -> dict[str, dict]:
    buckets: dict[str, dict] = defaultdict(lambda: {
        "cost": 0.0, "sessions": 0, "turns": 0, "toolCalls": 0,
        "inputTokens": 0, "outputTokens": 0, "premiumRequests": 0.0,
        "byProvider": defaultdict(float),
    })
    for s in sessions:
        dt = _parse_date(s.get("startTime", ""))
        if not dt:
            continue
        fmt = {"daily": "%Y-%m-%d", "monthly": "%Y-%m", "yearly": "%Y"}.get(period, "%Y-%m-%d")
        key = dt.strftime(fmt)
        b = buckets[key]
        cost = s.get("estimatedCostUSD", 0)
        b["cost"] += cost
        b["sessions"] += 1
        b["turns"] += s.get("turns", 0)
        b["toolCalls"] += s.get("toolCalls", 0)
        b["inputTokens"] += s.get("inputTokens", 0)
        b["outputTokens"] += s.get("outputTokens", 0)
        src = s.get("source", "unknown")
        b["byProvider"][src] += cost
        for m in s.get("models", []):
            b["premiumRequests"] += m.get("premiumRequests", 0)
    out: dict[str, dict] = {}
    for k, b in sorted(buckets.items()):
        entry: dict = {}
        for kk, vv in b.items():
            if kk == "byProvider":
                entry["byProvider"] = {pk: round(pv, 4) for pk, pv in vv.items()}
            elif isinstance(vv, float):
                entry[kk] = round(vv, 4)
            else:
                entry[kk] = vv
        out[k] = entry
    return out


def _aggregate_by(sessions: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {
        "cost": 0.0, "sessions": 0, "turns": 0, "toolCalls": 0,
        "inputTokens": 0, "outputTokens": 0, "premiumRequests": 0.0,
    })
    for s in sessions:
        k = s.get(key, "unknown") or "unknown"
        b = out[k]
        b["cost"] += s.get("estimatedCostUSD", 0)
        b["sessions"] += 1
        b["turns"] += s.get("turns", 0)
        b["toolCalls"] += s.get("toolCalls", 0)
        b["inputTokens"] += s.get("inputTokens", 0)
        b["outputTokens"] += s.get("outputTokens", 0)
        for m in s.get("models", []):
            b["premiumRequests"] += m.get("premiumRequests", 0)
    return {k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}
            for k, v in sorted(out.items(), key=lambda x: -x[1]["cost"])}


def _aggregate_by_model(sessions: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {
        "cost": 0.0, "inputTokens": 0, "outputTokens": 0,
        "cacheReadTokens": 0, "cacheWriteTokens": 0,
        "premiumRequests": 0.0, "turns": 0,
    })
    for s in sessions:
        for m in s.get("models", []):
            r = out[m["model"]]
            r["cost"] += m.get("cost", 0)
            r["inputTokens"] += m.get("inputTokens", 0)
            r["outputTokens"] += m.get("outputTokens", 0)
            r["cacheReadTokens"] += m.get("cacheReadTokens", 0)
            r["cacheWriteTokens"] += m.get("cacheWriteTokens", 0)
            r["premiumRequests"] += m.get("premiumRequests", 0)
            r["turns"] += 1
    return {k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}
            for k, v in sorted(out.items(), key=lambda x: -x[1]["cost"])}


# ── In-memory cache (TTL) ──────────────────────────────────────
CACHE_TTL_SECONDS = 30
_billing_cache: dict[tuple, tuple[float, list[dict]]] = {}
_response_cache: dict[str, tuple[float, dict]] = {}


def invalidate_cache() -> None:
    """Clear all cached billing and response data."""
    _billing_cache.clear()
    _response_cache.clear()


def _get_billing_sessions(cfg: dict) -> list[dict]:
    """Return cached billing sessions for the given config, scanning at most every TTL."""
    enabled = tuple(sorted(cfg["enabledProviders"]))
    key = (enabled, cfg["charsPerToken"], cfg["inputMultiplier"])
    now = time.time()
    hit = _billing_cache.get(key)
    if hit and (now - hit[0]) < CACHE_TTL_SECONDS:
        return hit[1]
    summaries = providers_pkg.scan_all(enabled=list(enabled))
    sessions = [summary_to_billing(s, cfg["charsPerToken"], cfg["inputMultiplier"])
                for s in summaries]
    _billing_cache[key] = (now, sessions)
    return sessions


def get_cost_data(
    source: str = "all",
    project: str | None = None,
    period: str = "daily",
    days: int | None = None,
) -> dict[str, Any]:
    cfg = cfg_mod.load()
    cache_key = json.dumps({
        "s": source, "p": project, "pe": period, "d": days,
        "cfg": [cfg["charsPerToken"], cfg["inputMultiplier"],
                sorted(cfg["enabledProviders"]), cfg.get("currency"), cfg.get("language")],
    }, sort_keys=True)
    now = time.time()
    cached = _response_cache.get(cache_key)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    sessions = list(_get_billing_sessions(cfg))

    if source and source != "all":
        sessions = [s for s in sessions if s["source"] == source]

    if project:
        sessions = [s for s in sessions if s.get("project") == project]

    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        sessions = [s for s in sessions
                    if (dt := _parse_date(s.get("startTime", ""))) and dt >= cutoff]

    sessions.sort(key=lambda s: s.get("startTime", ""), reverse=True)

    total_cost = sum(s["estimatedCostUSD"] for s in sessions)
    total_in = sum(s["inputTokens"] for s in sessions)
    total_out = sum(s["outputTokens"] for s in sessions)
    total_turns = sum(s["turns"] for s in sessions)
    total_tools = sum(s["toolCalls"] for s in sessions)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_sessions = [s for s in sessions if s.get("startTime", "").startswith(today)]

    by_provider_count: dict[str, int] = defaultdict(int)
    for s in sessions:
        by_provider_count[s["source"]] += 1

    result = {
        "summary": {
            "totalCostUSD": round(total_cost, 6),
            "todayCostUSD": round(sum(s["estimatedCostUSD"] for s in today_sessions), 6),
            "totalInputTokens": total_in,
            "totalOutputTokens": total_out,
            "totalTokens": total_in + total_out,
            "totalTurns": total_turns,
            "totalToolCalls": total_tools,
            "sessionCount": len(sessions),
            "todaySessionCount": len(today_sessions),
            "byProvider": dict(by_provider_count),
        },
        "timeSeries": _aggregate_period(sessions, period),
        "byProject": _aggregate_by(sessions, "project"),
        "byProvider": _aggregate_by(sessions, "source"),
        "byModel": _aggregate_by_model(sessions),
        "sessions": [{k: v for k, v in s.items() if k != "models"} for s in sessions[:100]],
        "config": cfg,
    }
    _response_cache[cache_key] = (now, result)
    return result


def get_projects_list() -> list[dict]:
    cfg = cfg_mod.load()
    summaries = providers_pkg.scan_all(enabled=cfg["enabledProviders"])
    counts: dict[str, dict] = defaultdict(lambda: {"sessions": 0, "sources": set()})
    for s in summaries:
        p = s.project or "unknown"
        counts[p]["sessions"] += 1
        counts[p]["sources"].add(s.source)
    return sorted(
        [{"name": k, "sessions": v["sessions"], "sources": sorted(v["sources"])}
         for k, v in counts.items()],
        key=lambda x: -x["sessions"],
    )
