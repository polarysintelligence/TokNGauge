<p align="center">
  <img src="docs/images/logo.png" width="360" alt="TokNGauge logo">
</p>

<h1 align="center">TokNGauge</h1>

<p align="center">
  <b>Local-first cost dashboard for your AI coding assistants.</b><br>
  GitHub Copilot CLI · Copilot in VS Code · Claude CLI · Codex CLI · Gemini CLI
</p>

<p align="center">
  <a href="LICENSE"><img alt="MIT" src="https://img.shields.io/badge/license-MIT-22c55e"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%2B-3776ab">
  <img alt="Frontend" src="https://img.shields.io/badge/frontend-vanilla%20JS-f7df1e">
  <img alt="Tests" src="https://img.shields.io/badge/tests-pytest%20%2B%20playwright-2563eb">
</p>

---

TokNGauge scans local session logs from your AI coding assistants and tells
you, in plain numbers, **how much your sessions are costing today, this week,
and this month** — all **without uploading anything anywhere**. Everything
runs on your machine: a tiny FastAPI server, vanilla JS, no build step.

## ✨ Features

- 🔌 **Six providers out of the box** — Copilot CLI, Copilot VS Code,
  Cursor, Claude CLI, Codex CLI, Gemini CLI. New providers are a
  drop-in module.
- 🎯 **Real measured tokens** when the provider emits them (Claude `usage`,
  Codex `token_count`). Char-based heuristic only as a fallback.
- 💱 **Cost in USD / EUR / GBP** with per-model pricing (incl. cache
  read/write tiers for Claude).
- 🌍 **i18n**: Spanish and English UI, switchable from settings.
- ⚙️ **User-tunable formula**: change `charsPerToken` and `inputMultiplier`
  on the fly. Settings persist at `<project_root>/config.json` (per-model
  prices in `<project_root>/pricing.json`).
- 🖥️ **Native-feeling taskbar icons** for Windows (`.ico`), macOS (`.icns`)
  and Linux/web (multi-size PNG + SVG).
- 🧪 **Tested** with `pytest` (unit) and **Playwright** (E2E).
- 🪶 **Simple to hack on**: ~7 files of backend, ~3 of frontend, zero
  bundlers.

## 🚀 Quick start

### macOS / Linux

```bash
git clone <your-fork>
cd ToknGauge
./start.sh
```

### Windows

```powershell
.\start.ps1
```

Then open <http://localhost:8770>. Set `TOKNGAUGE_PORT=8081` to change it.

> First run creates `.venv/` and installs `fastapi` + `uvicorn`. Nothing else
> is required at runtime.

## 📦 Providers

| Provider              | Source path                                | Tokens               |
|-----------------------|--------------------------------------------|----------------------|
| `copilot-cli`         | `~/.copilot/session-state/*/events.jsonl`  | char-based heuristic |
| `copilot-vscode`      | VS Code `workspaceStorage` chat sessions   | char-based heuristic |
| `cursor`              | Cursor `workspaceStorage` transcripts      | char-based heuristic |
| `claude`              | `~/.claude/projects/*/*.jsonl`             | **measured**         |
| `codex`               | `~/.codex/sessions/**/rollout-*.jsonl`     | **measured**         |
| `gemini`              | `~/.gemini/{logs.json,chats,sessions}`     | measured if present  |

Each provider is a self-contained module under
[`backend/providers/`](backend/providers/) exposing `is_available()` and
`scan()`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the recipe to add your
own (e.g. Continue, Sourcegraph Cody).

> The Cursor provider auto-detects the OS-specific
> `User/workspaceStorage` folder (override with `CURSOR_HOME`).

## ⚙️ Configuration

Open the **⚙️ Settings** panel from the header, or edit
`config.json` in the project root directly. Schema:

```json
{
  "language": "es",                  // "es" | "en"
  "currency": "USD",                 // "USD" | "EUR" | "GBP"
  "charsPerToken": 4,                // heuristic divisor for char→token
  "inputMultiplier": 5,              // input/output char ratio assumption
  "enabledProviders": ["copilot-cli", "copilot-vscode", "cursor", "claude", "codex", "gemini"],
  "fxRates": { "USD": 1.0, "EUR": 0.92, "GBP": 0.79 }  // see "Currency conversion"
}
```

Override the config path with `TOKNGAUGE_CONFIG=/path/to/file.json` (used by
the test suite).

### Currency conversion (`fxRates`)

The backend **always computes costs in USD** (because pricing tables are
published in USD). Conversion to EUR / GBP happens in the browser using
`fxRates`, which expresses **how many units of each currency equal 1 USD**:

```json
"fxRates": { "USD": 1.0, "EUR": 0.92, "GBP": 0.79 }
```

So `$1.40 USD × 0.92 = €1.29`. Edit these from **Settings → FX rates** (or
the file directly) whenever the market drifts too far from the defaults.
USD is always pinned at `1.0`; invalid values are ignored on save.

### Per-model pricing (`pricing.json`)

The price table lives in **`<project_root>/pricing.json`** and is the single
source of truth for cost calculations. On first run it is auto-generated
from an embedded fallback copy (in [`backend/pricing.py`](backend/pricing.py))
so the app works out of the box; from then on the file wins. Edit it from
the **⚙️ Settings → Pricing** panel or directly with your editor, then click
**Reload** (or restart).

Schema:

```json
{
  "models": {
    "claude-opus-4":   { "input": 15.0, "output": 75.0, "cacheRead": 1.5,    "cacheWrite": 18.75 },
    "claude-sonnet-4": { "input":  3.0, "output": 15.0, "cacheRead": 0.3,    "cacheWrite":  3.75 },
    "gpt-4.1":         { "input":  2.0, "output":  8.0, "cacheRead": 0.5,    "cacheWrite":  0.0  },
    "gemini-2.5-pro":  { "input": 1.25, "output": 10.0, "cacheRead": 0.3125, "cacheWrite":  0.0  },
    "my-custom-model": { "input":  1.0, "output":  2.0 }
  },
  "premium": {
    "claude-opus-4":   3.0,
    "claude-sonnet-4": 1.0,
    "gpt-4.1":         0.0,
    "gemini-2.5-pro":  1.0
  }
}
```

- All prices are **USD per 1M tokens**.
- `models[name]` accepts `input`, `output`, `cacheRead`, `cacheWrite`.
  Missing fields fall back to `0.0`. Removing a model from the file
  restores its embedded fallback price (if it has one).
- `premium[name]` is the "premium requests" multiplier used by quota-based
  plans (e.g. GitHub Copilot). `0.0` means no extra cost.
- Unknown models fall through to the `"unknown"` row.

**Where to get the real numbers** (providers refresh them often — always
double-check on the official pages):

- Anthropic Claude — <https://www.anthropic.com/pricing#api>
- OpenAI / Codex   — <https://openai.com/api/pricing/>
- Google Gemini    — <https://ai.google.dev/gemini-api/docs/pricing>
- GitHub Copilot   — <https://docs.github.com/en/copilot/managing-copilot/managing-copilot-as-an-individual-subscriber/about-billing-for-github-copilot/about-billing-for-copilot-premium-requests>
- Cursor           — <https://cursor.com/pricing>

Override the file path with `TOKNGAUGE_PRICING=/abs/path/to/pricing.json`.

### How costs are estimated

Prices in `pricing.json` are quoted in **USD per 1,000,000 tokens** (the
industry-standard unit). For every session and model, the formula in
[`backend/cost_estimation.py`](backend/cost_estimation.py) is:

```
cost_USD = (input_tokens      × price.input      / 1_000_000)
         + (output_tokens     × price.output     / 1_000_000)
         + (cacheRead_tokens  × price.cacheRead  / 1_000_000)
         + (cacheWrite_tokens × price.cacheWrite / 1_000_000)
```

For providers that report real token counts (Claude `usage`, Codex
`token_count`, Gemini when available), those numbers feed the formula
directly. For char-based providers (Copilot CLI/VS Code, Cursor), tokens
are estimated first:

```
output_tokens ≈ output_chars / charsPerToken
input_tokens  ≈ output_tokens × inputMultiplier
```

Both knobs are exposed in the Settings panel.

#### Worked example

A Claude Opus 4 session reports:

| Bucket      | Tokens  | Price (USD / 1M) | USD             |
|-------------|--------:|-----------------:|----------------:|
| input       |  50,000 |           15.00  | 0.7500          |
| output      |   8,000 |           75.00  | 0.6000          |
| cache read  |  12,000 |            1.50  | 0.0180          |
| cache write |   2,000 |           18.75  | 0.0375          |
| **Total**   |         |                  | **1.4055 USD**  |

That is the `estimatedCostUSD` the API returns. If your `currency` is
`EUR` and `fxRates.EUR = 0.92`, the UI displays:

```
1.4055 × 0.92 = 1.2931 €  →  shown as “1.29 €”
```

#### Premium requests (Copilot-style plans)

Quota-based plans (e.g. GitHub Copilot) bill **per request**, not per
token. For each turn, TokNGauge multiplies by `pricing.json → premium[model]`:

```
premium_requests_for_turn = premium[model]
```

So 10 turns on `claude-opus-4` (multiplier `3.0`) burn **30 premium
requests**. This figure is informational only — it does **not** influence
the USD/EUR cost above.

## 🌐 API

| Method | Path                            | Description                          |
|--------|---------------------------------|--------------------------------------|
| GET    | `/api/providers`                | List registered providers + status   |
| GET    | `/api/config`                   | Current persisted config             |
| POST   | `/api/config`                   | Update config (JSON body, partial)   |
| GET    | `/api/cost?days=N&source=…`     | Aggregated cost data                 |
| GET    | `/api/cost/projects?days=N`     | List of project names                |

## 🧪 Testing

```bash
# All unit + HTTP tests (28 tests, ~12 s)
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/ -q --ignore=tests/playwright

# Just one file
pytest tests/test_providers.py -v       # provider parsers
pytest tests/test_pricing_config.py -v  # pricing.json + fxRates
pytest tests/test_cost_api.py -v        # FastAPI endpoints

# End-to-end (Playwright spins up its own server on :8766)
cd tests/playwright
npm install
npx playwright install chromium
npx playwright test
```

CI runs the same suite on Python 3.10/3.11/3.12 via [`.github/workflows/tests.yml`](.github/workflows/tests.yml) on every push and PR to `main`.

## 🖥️ Menu-bar / tray app

TokNGauge ships a tiny tray app for each OS that **launches the server
automatically** and shows a minimalist gauge glyph next to the clock.
Clicking it opens a small **embedded** mini-window with the full UI —
no browser tab needed.

Full setup, autostart and troubleshooting per OS:
**[`apps/README.md`](apps/README.md)**.

Quick launch (after `pip install -r requirements.txt` in a venv):

```bash
# macOS
pip install pyobjc-framework-Cocoa pyobjc-framework-WebKit
python apps/menubar-mac/tray.py

# Linux (Debian/Ubuntu, GTK backend)
# System libs (incl. dev headers needed to build PyGObject/pycairo from source)
sudo apt install gir1.2-webkit2-4.1 python3-gi gir1.2-gtk-3.0 libcairo2-dev \
                 python3-dev libgirepository1.0-dev \
                 gir1.2-ayatanaappindicator3-0.1
pip install pystray "pywebview[gtk]" Pillow cairosvg
python apps/menubar-linux/tray.py
```

```powershell
# Windows (PowerShell) — requires Edge WebView2 Runtime
pip install pystray pywebview Pillow cairosvg
python apps\menubar-windows\tray.py
```

### Platform assets

The raw artwork each app / installer consumes:

- **macOS** — [`apps/menubar-mac/Resources/`](apps/menubar-mac/) with
  `AppIcon.icns` and template-friendly `TrayIcon@1x.png` / `TrayIcon@2x.png`.
- **Windows** — [`apps/menubar-windows/Resources/`](apps/menubar-windows/)
  with a multi-resolution `AppIcon.ico` plus a 32×32 `TrayIcon.png`.
- **Linux** — [`apps/menubar-linux/data/`](apps/menubar-linux/) with
  `tokngauge.svg`, `tokngauge.png`, an indicator-friendly
  `tokngauge-tray.png`, and a ready-to-install
  [`tokngauge.desktop`](apps/menubar-linux/data/tokngauge.desktop).

Regenerate everything from the SVG master with `python scripts/build_icons.py`.

## 🎨 Regenerating the icons

The icons under [`static/icons/`](static/icons/) are committed, but you can
rebuild them from the SVG source:

```bash
pip install -r requirements-dev.txt   # adds Pillow + cairosvg
python scripts/build_icons.py
```

## 🗂️ Project layout

```
backend/
  config.py                persisted user config + validation
  cost_estimation.py       provider orchestrator + billing
  cost_api.py              FastAPI routes
  providers/               pluggable scanners (one file per provider)
static/
  index.html  app.js  style.css  i18n.js  manifest.webmanifest
  icons/      icon.svg, icon.ico, icon.icns, icon-{16…1024}.png
tests/
  test_providers.py        pytest unit tests
  playwright/              E2E suite + config
apps/
  menubar-mac/Resources/   AppIcon.icns + TrayIcon@1x/@2x.png + gauge.svg
  menubar-windows/Resources/  AppIcon.ico + TrayIcon.png + gauge.svg
  menubar-linux/data/      tokngauge.svg/.png + tokngauge.desktop
scripts/
  build_icons.py           regenerate icons from SVG
server.py                  uvicorn entry point
start.sh / start.ps1       launchers (auto-free the chosen port)
```

## 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). The guiding principle is **keep it
simple**: no build step, no framework, small files, real tests.

## 📜 License

[MIT](LICENSE) © 2026 Polarys Intelligence.

## 🙏 Acknowledgements

- Provider-scanning ideas adapted from an earlier TypeScript prototype
  ("ToknGaugeOld") — distilled here into the simplest possible Python form.
- Claude · Codex · Gemini · Copilot trademarks belong to their respective
  owners; TokNGauge is an independent local tool and is not affiliated with
  any of them.
