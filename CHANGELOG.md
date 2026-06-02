# Changelog

All notable changes to this project will be documented in this file. The
format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [1.2.0] — 2026-05

### Added
- **New provider** keeping the drop-in module pattern:
  - `cursor` — auto-detects the OS-specific Cursor `workspaceStorage`
    (macOS / Linux / Windows; override with `CURSOR_HOME`) and parses
    `anysphere.cursor-chat/transcripts/*.jsonl`. Char-based estimation.
- **Platform-specific tray / taskbar asset folders** mirroring the layout
  of the legacy `ToknGaugeOld` project:
  - `apps/menubar-mac/Resources/` — `AppIcon.icns`, `TrayIcon@1x/@2x.png`,
    `gauge.svg`.
  - `apps/menubar-windows/Resources/` — `AppIcon.ico`, `TrayIcon.png`,
    `gauge.svg`.
  - `apps/menubar-linux/data/` — `tokngauge.svg`, `tokngauge.png`,
    `tokngauge-tray.png`, `tokngauge.desktop`.
- Unit tests for the `cursor` provider (`tests/test_providers.py`).

### Changed
- `start.sh` and `start.ps1` now **free the target port** before launching,
  killing any leftover listener so iterative restarts "just work".
- `start.sh` honours `TOKNGAUGE_PORT` for the banner and the freed port.
- Settings save flow now `await`s the re-render so the "✓ Saved" flash is
  reliably visible (fixes a Playwright flake).
- Playwright timeouts bumped to 60 s to comfortably cover cold scans on
  machines with many local AI sessions.

## [1.1.0] — 2026-05

### Added
- **Multi-provider scanning** via pluggable `backend/providers/` package:
  - `claude` — reads `~/.claude/projects/*/*.jsonl` and uses *real* measured
    tokens from `message.usage` (input / output / cache read / cache write).
  - `codex` — reads `~/.codex/sessions/**/rollout-*.jsonl` and aggregates
    `token_count` events (cumulative input / output / cached input).
  - `gemini` — best-effort scanner for `~/.gemini/{logs.json,chats,sessions}`.
  - Existing Copilot CLI + Copilot VS Code logic extracted into their own
    modules: `copilot_cli`, `copilot_vscode`.
- **Persisted user configuration** at `~/.tokngauge/config.json`
  (`TOKNGAUGE_CONFIG` env var overrides the path). Exposed via
  `GET/POST /api/config`.
- **Settings panel** in the UI: language, currency, formula
  (`charsPerToken` & `inputMultiplier`) and per-provider enable toggles.
- **Internationalisation** (`static/i18n.js`) with **es** and **en** catalogs.
- **Branded multi-resolution icons** (`static/icons/icon.svg` source +
  generated PNG 16→1024, `icon.ico` for Windows, `icon.icns` for macOS,
  `manifest.webmanifest` and full favicon link set in `index.html`).
- `scripts/build_icons.py` to regenerate icons from the SVG.
- `start.ps1` Windows launcher mirror of `start.sh`.
- **Playwright** E2E suite (`tests/playwright/`) + **pytest** unit tests
  (`tests/test_providers.py`).
- `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`.

### Changed
- `/api/cost` now returns `byProvider` aggregations and supports filtering by
  any registered provider id (legacy `cli`/`vscode` values still accepted).
- Billing logic prefers measured tokens (when present) over the char-based
  heuristic, and accounts for cache read/write pricing when reported.
- `TOKNGAUGE_RELOAD=1` opt-in for uvicorn auto-reload (off by default for
  cleaner production runs).

### Backwards compatibility
- `/api/cost` and `/api/cost/projects` query shapes are preserved; new fields
  are additive.
- Existing Copilot CLI / VS Code data continues to work unchanged.

## [1.0.0] — 2025

- Initial release: Copilot CLI + VS Code cost dashboard.
