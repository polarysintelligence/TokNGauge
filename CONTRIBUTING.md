# Contributing to TokNGauge

Thanks for your interest! TokNGauge stays intentionally **simple**: Python + FastAPI on the
backend, vanilla JS on the frontend, zero build step. Please respect that scope when
proposing changes.

## Quick start

```bash
git clone <repo>
cd ToknGauge
./start.sh          # or .\start.ps1 on Windows
# open http://localhost:8770
```

## Project layout

```
backend/
  config.py             persisted user config (~/.tokngauge/config.json)
  cost_estimation.py    aggregation + billing
  cost_api.py           FastAPI routes
  providers/
    _base.py            shared dataclass + helpers
    copilot_cli.py      GitHub Copilot CLI sessions
    copilot_vscode.py   Copilot VS Code transcripts
    cursor.py           Cursor IDE workspaceStorage transcripts
    claude.py           Claude CLI sessions (real measured tokens)
    codex.py            Codex CLI rollouts (real measured tokens)
    gemini.py           Gemini CLI (best-effort)
static/                 index.html, app.js, style.css, i18n.js, icons/
apps/
  menubar-mac/          macOS tray assets (AppIcon.icns + TrayIcon PNGs)
  menubar-windows/      Windows tray assets (AppIcon.ico + TrayIcon PNG)
  menubar-linux/        Linux desktop + indicator assets + .desktop file
tests/
  test_providers.py     pytest unit tests
  playwright/           Playwright E2E
scripts/build_icons.py  regenerate icons from SVG
```

## Adding a new provider

1. Create `backend/providers/<name>.py` exporting:
   - `ID = "<name>"`, `DISPLAY = "Human Name"`
   - `is_available() -> bool`
   - `scan() -> list[SessionSummary]`
2. Register it in `backend/providers/__init__.py` `ALL`.
3. Add an entry to `PROVIDER_LABEL` and `SOURCE_ICON` in `static/app.js`.
4. Add fixture-based tests under `tests/test_providers.py`.

Use the existing providers as templates. Prefer **real measured tokens** when the provider
emits them; fall back to the char-based heuristic only when there's no signal.

## Tests

Backend:
```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/test_providers.py -v
```

End-to-end (Playwright):
```bash
cd tests/playwright
npm install
npx playwright install chromium
npx playwright test
```

The Playwright config boots its own server on port 8766 with a temp config file.

## Code style

- Backend: type hints + dataclasses where possible. Keep modules small and pure.
- Frontend: no framework, no bundler. Keep `app.js` readable.
- i18n: every user-visible string goes through `t('key')` and exists in both
  `es` and `en` catalogs in `static/i18n.js`.

## Pull requests

- One topic per PR.
- Run `pytest` and `playwright test` before submitting.
- Update `CHANGELOG.md`.
- New providers must include unit tests.

## License

By contributing you agree your contributions are licensed under the MIT License
and that the copyright is held by Polarys Intelligence.
