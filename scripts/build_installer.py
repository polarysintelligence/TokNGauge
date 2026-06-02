#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Polarys Intelligence

"""Build native installers for ToknGauge.

Usage:
    python scripts/build_installer.py mac
    python scripts/build_installer.py win
    python scripts/build_installer.py linux --format appimage   # or deb / both

Each subcommand is a thin wrapper around the underlying tool (py2app,
PyInstaller, Inno Setup, appimagetool, dpkg-deb) — they must be installed
manually first. See docs/PACKAGING.md for the full prerequisites table.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "TokNGauge"
APP_ID = "com.polarys.tokngauge"
VERSION = "1.2.0"


# ── helpers ─────────────────────────────────────────────────────────


def run(cmd: list[str] | str, *, cwd: Path | None = None, env: dict | None = None) -> None:
    """Run a command, streaming output. Aborts on non-zero exit."""
    print(f"\n$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}\n", flush=True)
    subprocess.run(cmd, cwd=cwd or ROOT, env=env, shell=isinstance(cmd, str), check=True)


def require(tool: str, hint: str = "") -> None:
    """Abort with a friendly message if ``tool`` is not on PATH."""
    if shutil.which(tool) is None:
        sys.exit(f"❌ Required tool '{tool}' not found on PATH. {hint}")


def regen_icons(target: str) -> None:
    """Re-run scripts/build_icons.py only if the target's icon is missing.

    NOTE: this only regenerates the main app icon (static/icons/icon-*.png,
    icon.ico, icon.icns) from static/icons/icon.svg. It does NOT touch the
    provider icons in static/icons/providers/.
    Set TOKNGAUGE_FORCE_ICONS=1 to force a rebuild.
    """
    needed = {
        "mac":   ROOT / "static" / "icons" / "icon.icns",
        "win":   ROOT / "static" / "icons" / "icon.ico",
        "linux": ROOT / "static" / "icons" / "icon-256.png",
    }[target]
    if needed.exists() and os.environ.get("TOKNGAUGE_FORCE_ICONS") != "1":
        print(f"✓ Reusing existing {needed.relative_to(ROOT)} "
              "(set TOKNGAUGE_FORCE_ICONS=1 to regenerate).")
        return
    # Disabled: don't auto-run build_icons.py during installer builds.
    # Re-enable by uncommenting the block below (or run `python scripts/build_icons.py` manually).
    # try:
    #     run([sys.executable, str(ROOT / "scripts" / "build_icons.py")])
    # except subprocess.CalledProcessError:
    #     print("⚠️  build_icons.py failed — continuing with whatever is on disk.")
    print(f"⚠️  {needed.relative_to(ROOT)} missing — run `python scripts/build_icons.py` manually if needed.")


def clean(*paths: Path) -> None:
    for p in paths:
        if p.exists():
            print(f"🧹  rm -rf {p.relative_to(ROOT)}")
            shutil.rmtree(p, ignore_errors=True)


# ── macOS ───────────────────────────────────────────────────────────


MAC_PLIST = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
      "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>CFBundleName</key><string>{name}</string>
        <key>CFBundleDisplayName</key><string>{name}</string>
        <key>CFBundleIdentifier</key><string>{bundle_id}</string>
        <key>CFBundleVersion</key><string>{version}</string>
        <key>CFBundleShortVersionString</key><string>{version}</string>
        <key>CFBundleIconFile</key><string>icon.icns</string>
        <key>LSUIElement</key><true/>
        <key>NSHumanReadableCopyright</key><string>© 2026 Polarys Intelligence</string>
        <key>NSHighResolutionCapable</key><true/>
    </dict>
    </plist>
    """)


def build_mac() -> None:
    if platform.system() != "Darwin":
        sys.exit("❌ The mac target only works on macOS.")
    regen_icons("mac")
    icon = ROOT / "static" / "icons" / "icon.icns"
    if not icon.exists():
        sys.exit("❌ static/icons/icon.icns missing — build_icons.py needs to succeed first.")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("❌ PyInstaller not installed. Run: pip install pyinstaller")

    clean(DIST, BUILD)

    # Write Info.plist for the bundle
    plist_path = BUILD / "Info.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(MAC_PLIST.format(
        name=APP_NAME, bundle_id=APP_ID, version=VERSION,
    ), encoding="utf-8")

    # Collect data files
    add_data = [
        f"static{os.pathsep}static",
        f"backend{os.pathsep}backend",
        f"server.py{os.pathsep}.",
        f"apps/_server_runtime.py{os.pathsep}.",
        f"apps/menubar-mac/Resources{os.pathsep}Resources",
    ]
    pricing = ROOT / "pricing.json"
    if pricing.exists():
        add_data.append(f"pricing.json{os.pathsep}.")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--windowed",
        "--name", APP_NAME,
        "--icon", str(icon),
        "--osx-bundle-identifier", APP_ID,
        "--paths", str(ROOT),
        "--paths", str(ROOT / "apps"),
    ]
    for d in add_data:
        cmd += ["--add-data", d]
    # Hidden imports needed at runtime
    for mod in ("_server_runtime", "server", "backend",
                "cairosvg", "cairocffi", "cffi", "sniffio", "h11",
                "anyio", "click", "pydantic_core"):
        cmd += ["--hidden-import", mod]
    # Exclude unneeded modules
    for exc in ("tkinter", "pytest", "playwright"):
        cmd += ["--exclude-module", exc]
    cmd.append(str(ROOT / "apps" / "menubar-mac" / "tray.py"))

    run(cmd)

    app_path = DIST / f"{APP_NAME}.app"
    if not app_path.exists():
        sys.exit(f"❌ PyInstaller did not produce {app_path}")

    # Inject custom Info.plist into the .app bundle
    shutil.copy(plist_path, app_path / "Contents" / "Info.plist")

    # DMG (optional)
    if shutil.which("create-dmg"):
        dmg = DIST / f"{APP_NAME}-{VERSION}.dmg"
        dmg.unlink(missing_ok=True)
        run([
            "create-dmg",
            "--volname", APP_NAME,
            "--window-size", "600", "400",
            "--icon-size", "100",
            "--icon", f"{APP_NAME}.app", "150", "200",
            "--app-drop-link", "450", "200",
            str(dmg), str(app_path),
        ])
        print(f"\n✅ Built: {app_path.relative_to(ROOT)}")
        print(f"✅ Built: {dmg.relative_to(ROOT)}")
    else:
        print("\n⚠️  create-dmg not installed — skipping .dmg step.")
        print("    Install with: brew install create-dmg")
        print(f"\n✅ Built: {app_path.relative_to(ROOT)}")


# ── Windows ─────────────────────────────────────────────────────────


ISS_TEMPLATE = textwrap.dedent("""\
    ; AUTO-GENERATED by scripts/build_installer.py — do not edit.
    #define MyAppName "{name}"
    #define MyAppVersion "{version}"
    #define MyAppPublisher "Polarys Intelligence"
    #define MyAppExeName "{name}.exe"

    [Setup]
    AppId={{{{B0F1A4E2-7C3D-4E5F-9A6B-2D1E8C7F4A3B}}}}
    AppName={{#MyAppName}}
    AppVersion={{#MyAppVersion}}
    AppPublisher={{#MyAppPublisher}}
    DefaultDirName={{autopf}}\\{{#MyAppName}}
    DefaultGroupName={{#MyAppName}}
    DisableProgramGroupPage=yes
    OutputDir={out_dir}
    OutputBaseFilename={name}-Setup-{version}
    Compression=lzma2/ultra
    SolidCompression=yes
    WizardStyle=modern
    PrivilegesRequired=lowest
    PrivilegesRequiredOverridesAllowed=dialog

    [Languages]
    Name: "english"; MessagesFile: "compiler:Default.isl"

    [Tasks]
    Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
    Name: "startup"; Description: "Launch at Windows startup"; GroupDescription: "Auto-start:"; Flags: unchecked

    [Files]
    Source: "{src_dir}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

    [Icons]
    Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
    Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon
    Name: "{{userstartup}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: startup

    [Run]
    Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "Launch {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
    """)


def _find_iscc() -> str | None:
    if shutil.which("iscc"):
        return "iscc"
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env)
        if not base:
            continue
        candidate = Path(base) / "Inno Setup 6" / "ISCC.exe"
        if candidate.exists():
            return str(candidate)
    return None


def build_win() -> None:
    if platform.system() != "Windows":
        sys.exit("❌ The win target only works on Windows.")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("❌ PyInstaller not installed. Run: pip install pyinstaller")

    regen_icons("win")
    icon = ROOT / "static" / "icons" / "icon.ico"
    if not icon.exists():
        sys.exit("❌ static/icons/icon.ico missing — build_icons.py needs to succeed first.")

    clean(DIST, BUILD)
    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--windowed",
        "--icon", str(icon),
        "--name", APP_NAME,
        "--add-data", f"static{os.pathsep}static",
        "--add-data", f"backend{os.pathsep}backend",
        "--add-data", f"server.py{os.pathsep}.",
        str(ROOT / "apps" / "menubar-windows" / "tray.py"),
    ])

    src_dir = DIST / APP_NAME
    if not src_dir.exists():
        sys.exit(f"❌ PyInstaller did not produce {src_dir}")

    iscc = _find_iscc()
    if not iscc:
        print("\n⚠️  Inno Setup compiler (iscc) not found.")
        print("    Install Inno Setup 6 from https://jrsoftware.org/isdl.php")
        print(f"\n✅ Built (folder bundle only): {src_dir.relative_to(ROOT)}")
        return

    iss_path = DIST / "installer.iss"
    iss_path.write_text(ISS_TEMPLATE.format(
        name=APP_NAME, version=VERSION,
        src_dir=str(src_dir).replace("/", "\\"),
        out_dir=str(DIST).replace("/", "\\"),
    ), encoding="utf-8")
    run([iscc, str(iss_path)])
    installer = DIST / f"{APP_NAME}-Setup-{VERSION}.exe"
    print(f"\n✅ Built: {installer.relative_to(ROOT)}")


# ── Linux ───────────────────────────────────────────────────────────


DESKTOP_FALLBACK = textwrap.dedent("""\
    [Desktop Entry]
    Name=TokNGauge
    Comment=Local cost dashboard for AI coding assistants
    Exec=tokngauge
    Icon=tokngauge
    Terminal=false
    Type=Application
    Categories=Development;Utility;
    """)


def _pyinstaller_linux() -> Path:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("❌ PyInstaller not installed. Run: pip install pyinstaller")
    clean(DIST, BUILD)
    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--windowed",
        "--name", APP_NAME,
        "--add-data", f"static{os.pathsep}static",
        "--add-data", f"backend{os.pathsep}backend",
        "--add-data", f"server.py{os.pathsep}.",
        str(ROOT / "apps" / "menubar-linux" / "tray.py"),
    ])
    src_dir = DIST / APP_NAME
    if not src_dir.exists():
        sys.exit(f"❌ PyInstaller did not produce {src_dir}")
    return src_dir


def _icon_png() -> Path:
    """Find or render a 256x256 PNG for the .desktop file."""
    candidates = [
        ROOT / "static" / "icons" / "icon-256.png",
        ROOT / "static" / "icons" / "icon.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    sys.exit("❌ No PNG icon found in static/icons/ — run scripts/build_icons.py first.")


def build_appimage(src_dir: Path) -> None:
    require("appimagetool", hint="Will auto-download AppImageTool if missing.")
    appdir = BUILD / "AppDir"
    clean(appdir)
    (appdir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)

    # Copy PyInstaller bundle into AppDir
    shutil.copytree(src_dir, appdir / "usr" / "lib" / APP_NAME)
    # Wrapper script in usr/bin
    wrapper = appdir / "usr" / "bin" / "tokngauge"
    wrapper.write_text(
        f'#!/bin/sh\nexec "$(dirname "$0")/../lib/{APP_NAME}/{APP_NAME}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    # AppRun → wrapper
    apprun = appdir / "AppRun"
    apprun.write_text('#!/bin/sh\nexec "$(dirname "$0")/usr/bin/tokngauge" "$@"\n', encoding="utf-8")
    apprun.chmod(0o755)

    # .desktop + icon (root-level copies are mandatory for AppImage)
    desktop_src = ROOT / "apps" / "menubar-linux" / "data" / "tokngauge.desktop"
    desktop_text = desktop_src.read_text(encoding="utf-8") if desktop_src.exists() else DESKTOP_FALLBACK
    (appdir / "tokngauge.desktop").write_text(desktop_text, encoding="utf-8")
    (appdir / "usr" / "share" / "applications" / "tokngauge.desktop").write_text(desktop_text, encoding="utf-8")
    icon = _icon_png()
    shutil.copy(icon, appdir / "tokngauge.png")
    shutil.copy(icon, appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "tokngauge.png")

    # Resolve appimagetool: prefer system, else cached download.
    tool = shutil.which("appimagetool")
    if not tool:
        cache = Path.home() / ".cache" / "tokngauge"
        cache.mkdir(parents=True, exist_ok=True)
        tool_path = cache / "appimagetool-x86_64.AppImage"
        if not tool_path.exists():
            url = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
            print(f"⬇️  Downloading {url} → {tool_path}")
            urllib.request.urlretrieve(url, tool_path)
            tool_path.chmod(0o755)
        tool = str(tool_path)

    out = DIST / f"{APP_NAME}-{VERSION}-x86_64.AppImage"
    out.unlink(missing_ok=True)
    run([tool, str(appdir), str(out)], env={**os.environ, "ARCH": "x86_64"})
    print(f"\n✅ Built: {out.relative_to(ROOT)}")


def build_deb(src_dir: Path) -> None:
    require("dpkg-deb", hint="Install with: sudo apt install dpkg-dev")
    pkgroot = BUILD / "deb"
    clean(pkgroot)
    install_dir = pkgroot / "opt" / "tokngauge"
    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_dir, install_dir, dirs_exist_ok=True)

    # Symlink under /usr/bin
    (pkgroot / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    # Use a postinst symlink because dpkg-deb chokes on absolute symlinks in payload
    (pkgroot / "DEBIAN").mkdir(exist_ok=True)
    (pkgroot / "DEBIAN" / "postinst").write_text(textwrap.dedent("""\
        #!/bin/sh
        set -e
        ln -sf /opt/tokngauge/TokNGauge /usr/bin/tokngauge
        """), encoding="utf-8")
    (pkgroot / "DEBIAN" / "postinst").chmod(0o755)
    (pkgroot / "DEBIAN" / "prerm").write_text(textwrap.dedent("""\
        #!/bin/sh
        set -e
        rm -f /usr/bin/tokngauge
        """), encoding="utf-8")
    (pkgroot / "DEBIAN" / "prerm").chmod(0o755)

    # .desktop entry
    apps_dir = pkgroot / "usr" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop_src = ROOT / "apps" / "menubar-linux" / "data" / "tokngauge.desktop"
    desktop_text = desktop_src.read_text(encoding="utf-8") if desktop_src.exists() else DESKTOP_FALLBACK
    (apps_dir / "tokngauge.desktop").write_text(desktop_text, encoding="utf-8")
    icons_dir = pkgroot / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icons_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(_icon_png(), icons_dir / "tokngauge.png")

    # control file
    size_kb = sum(f.stat().st_size for f in pkgroot.rglob("*") if f.is_file()) // 1024
    control = textwrap.dedent(f"""\
        Package: tokngauge
        Version: {VERSION}
        Section: utils
        Priority: optional
        Architecture: amd64
        Installed-Size: {size_kb}
        Depends: libgtk-3-0, libwebkit2gtk-4.1-0 | libwebkit2gtk-4.0-37
        Maintainer: Polarys Intelligence <hello@polarys.dev>
        Description: Local cost dashboard for AI coding assistants
         TokNGauge aggregates per-session usage data from GitHub Copilot,
         Claude Code, Cursor and others into a single offline dashboard.
        """)
    (pkgroot / "DEBIAN" / "control").write_text(control, encoding="utf-8")

    out = DIST / f"tokngauge_{VERSION}_amd64.deb"
    out.unlink(missing_ok=True)
    run(["dpkg-deb", "--build", "--root-owner-group", str(pkgroot), str(out)])
    print(f"\n✅ Built: {out.relative_to(ROOT)}")


def build_linux(formats: list[str]) -> None:
    if platform.system() != "Linux":
        sys.exit("❌ The linux target only works on Linux.")
    regen_icons("linux")
    src_dir = _pyinstaller_linux()
    if "appimage" in formats:
        build_appimage(src_dir)
    if "deb" in formats:
        build_deb(src_dir)


# ── CLI ─────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="target", required=True)
    sub.add_parser("mac", help="Build .app + .dmg (requires py2app, create-dmg).")
    sub.add_parser("win", help="Build .exe + Inno Setup installer.")
    lp = sub.add_parser("linux", help="Build AppImage and/or .deb.")
    lp.add_argument("--format", choices=["appimage", "deb", "both"], default="both")

    args = p.parse_args()
    DIST.mkdir(exist_ok=True)

    if args.target == "mac":
        build_mac()
    elif args.target == "win":
        build_win()
    elif args.target == "linux":
        formats = ["appimage", "deb"] if args.format == "both" else [args.format]
        build_linux(formats)


if __name__ == "__main__":
    main()
