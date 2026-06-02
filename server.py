# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""
TokNGauge — Standalone Copilot session cost estimation server.

Run:
    python server.py

Opens on http://localhost:8770
"""
from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.cost_api import router as cost_router

app = FastAPI(title="TokNGauge", version="1.2.0")

# API routes
app.include_router(cost_router)

# Serve static frontend
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    host = os.environ.get("TOKNGAUGE_HOST", "0.0.0.0")
    port = int(os.environ.get("TOKNGAUGE_PORT", "8770"))
    reload = os.environ.get("TOKNGAUGE_RELOAD", "0") == "1"
    uvicorn.run("server:app", host=host, port=port, reload=reload)
