# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from . import config as cfg_mod
from . import pricing as pricing_mod
from . import providers as providers_pkg
from .cost_estimation import get_cost_data, get_projects_list, invalidate_cache

router = APIRouter()


@router.get("/api/cost")
async def api_cost(
    source: str = Query("all", description="Provider id or 'all'"),
    project: str | None = Query(None),
    period: str = Query("daily"),
    days: int | None = Query(None),
    refresh: int = Query(0, description="Set to 1 to bypass cache"),
):
    if refresh:
        invalidate_cache()
    return JSONResponse(get_cost_data(source=source, project=project, period=period, days=days))


@router.get("/api/cost/projects")
async def api_projects():
    return JSONResponse(get_projects_list())


@router.get("/api/providers")
async def api_providers():
    return JSONResponse(providers_pkg.info())


@router.get("/api/config")
async def api_get_config():
    return JSONResponse(cfg_mod.load())


@router.post("/api/config")
async def api_save_config(payload: dict[str, Any] = Body(...)):
    return JSONResponse(cfg_mod.save(payload))


@router.get("/api/pricing")
async def api_get_pricing():
    """Return defaults, user overrides, effective merged pricing and file path."""
    return JSONResponse(pricing_mod.snapshot())


@router.post("/api/pricing")
async def api_save_pricing(payload: dict[str, Any] = Body(...)):
    """Merge ``payload`` into the user pricing overrides file and reload."""
    return JSONResponse(pricing_mod.save(payload))


@router.post("/api/pricing/reload")
async def api_reload_pricing():
    """Re-read overrides from disk and bust cost caches."""
    pricing_mod.reload()
    return JSONResponse(pricing_mod.snapshot())


@router.delete("/api/pricing")
async def api_reset_pricing():
    """Remove user overrides and restore defaults."""
    return JSONResponse(pricing_mod.reset())
