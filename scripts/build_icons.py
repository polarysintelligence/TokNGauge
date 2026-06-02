#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Regenerate multi-resolution PNG/ICO/ICNS icons from static/icons/icon.svg.

Requires: pip install Pillow resvg
  (or pip install Pillow cairosvg on Linux/macOS where libcairo is available)
On macOS, also uses /usr/bin/iconutil to build the .icns bundle.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "static" / "icons" / "icon.svg"
OUT = ROOT / "static" / "icons"
SIZES = [16, 24, 32, 48, 64, 128, 256, 512, 1024]


def render_png(size: int, dst: Path) -> None:
    """Render SVG to PNG at the given size. Tries resvg first, falls back to cairosvg."""
    try:
        from resvg._resvg import _script_entrypoint
        _script_entrypoint([str(SVG), str(dst), "-w", str(size), "-h", str(size)])
        return
    except ImportError:
        pass
    import cairosvg
    cairosvg.svg2png(url=str(SVG), output_width=size, output_height=size,
                     write_to=str(dst))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pngs = {}
    for s in SIZES:
        p = OUT / f"icon-{s}.png"
        render_png(s, p)
        pngs[s] = p
        print(f"✓ {p.name}")

    ico = OUT / "icon.ico"
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = [Image.open(pngs[s]).convert("RGBA") for s in ico_sizes]
    imgs[-1].save(ico, format="ICO", append_images=imgs[:-1])
    print(f"  {ico.name}")

    if shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as td:
            iconset = Path(td) / "icon.iconset"
            iconset.mkdir()
            mapping = {16: ("16x16",), 32: ("16x16@2x", "32x32"),
                       64: ("32x32@2x",), 128: ("128x128",),
                       256: ("128x128@2x", "256x256"),
                       512: ("256x256@2x", "512x512"), 1024: ("512x512@2x",)}
            for s, names in mapping.items():
                for n in names:
                    Image.open(pngs[s]).save(iconset / f"icon_{n}.png")
            subprocess.check_call(["iconutil", "-c", "icns", str(iconset),
                                   "-o", str(OUT / "icon.icns")])
            print("✓ icon.icns")
    else:
        print("(skipping .icns: iconutil not on PATH — only available on macOS)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
