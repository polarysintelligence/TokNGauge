// ── TokNGauge — Standalone Cost Estimation App ───────────────────
(function () {
  'use strict';

  const t = (k, p) => window.tngI18n.t(k, p);

  // ── State ────────────────────────────────────────────────────────
  let _costCache = {};
  let _currentView = 'today';
  let _currentSource = 'all';
  let _currentProject = null;
  let _config = {
    language: 'es', currency: 'USD', charsPerToken: 4, inputMultiplier: 5,
    enabledProviders: ['copilot-cli', 'copilot-vscode', 'cursor', 'claude', 'codex', 'gemini'],
    fxRates: { USD: 1.0, EUR: 0.92, GBP: 0.79 },
  };
  let _providers = [];

  const PROVIDER_LABEL = {
    'copilot-cli': 'Copilot CLI',
    'copilot-vscode': 'Copilot VS Code',
    'cursor': 'Cursor',
    'claude': 'Claude',
    'codex': 'Codex',
    'gemini': 'Gemini',
  };
  const SOURCE_ICON = {
    'copilot-cli': '🖥️', 'copilot-vscode': '💬', 'cursor': '🟪',
    'claude': '🟧', 'codex': '🟦', 'gemini': '🟣',
  };
  const PROVIDER_SHORT = {
    'copilot-cli': 'Copilot CLI', 'copilot-vscode': 'Copilot VSCode',
    'cursor': 'Cursor', 'claude': 'Claude', 'codex': 'Codex', 'gemini': 'Gemini',
  };
  const _GITHUB_SVG = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>`;
  const _VSCODE_SVG = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M11.6 1.2 14.5 2.6c.3.1.5.4.5.7v9.4c0 .3-.2.6-.5.7l-2.9 1.4c-.3.1-.7.1-.9-.2L4.6 9 2.3 10.7c-.2.2-.5.1-.7 0L.4 9.7c-.3-.3-.3-.7 0-1L2.6 8 .4 6.3c-.3-.3-.3-.7 0-1l1.2-1c.2-.2.5-.2.7 0L4.6 7l6.1-5.6c.2-.3.6-.4.9-.2zm-.4 3.3L6.7 8l4.5 3.5V4.5z"/></svg>`;
  const PROVIDER_ICONS = {
    'all':            `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 4h12M2 8h12M2 12h12"/></svg>`,
    'copilot-cli':    _GITHUB_SVG,
    'copilot-vscode': _VSCODE_SVG,
    'cursor':         `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M2 1.6v12.8L8 8z"/><path d="M2 1.6 13.2 8 2 14.4z" fill="currentColor" opacity=".55"/></svg>`,
    'claude':         `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M4.3 11.2 6.8 4.8h1.5l2.5 6.4h-1.4l-.55-1.5H6.25l-.55 1.5H4.3zm2.35-2.7h1.8L7.55 5.95 6.65 8.5zm5.6 2.7V4.8h1.35v6.4h-1.35z"/></svg>`,
    'codex':          `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5.5 6.5 4 8l1.5 1.5M10.5 6.5 12 8l-1.5 1.5M9.2 5.5l-2.4 5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`,
    'gemini':         `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0c0 4.4-3.6 8-8 8 4.4 0 8 3.6 8 8 0-4.4 3.6-8 8-8-4.4 0-8-3.6-8-8z"/></svg>`,
  };

  // ── Theme ────────────────────────────────────────────────────────
  window.toggleTheme = function () {
    const html = document.documentElement;
    const cur = html.getAttribute('data-ui-theme');
    const next = cur === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-ui-theme', next);
    localStorage.setItem('tokngauge-theme', next);
  };
  const savedTheme = localStorage.getItem('tokngauge-theme');
  if (savedTheme) document.documentElement.setAttribute('data-ui-theme', savedTheme);

  // ── Provider icon helper ─────────────────────────────────────────
  const provIcon = (id) => PROVIDER_ICONS[id]
    ? `<span class="tng-prov-icon" data-provider="${id}" title="${id}">${PROVIDER_ICONS[id]}</span>`
    : (SOURCE_ICON[id] || '');

  // ── Fetch helpers ────────────────────────────────────────────────
  async function fetchCost(params = {}) {
    const qs = new URLSearchParams();
    for (const k of ['source', 'project', 'period', 'days']) {
      if (params[k] != null && params[k] !== '') qs.set(k, String(params[k]));
    }
    const key = qs.toString();
    if (_costCache[key]) return _costCache[key];
    try {
      const res = await fetch('/api/cost?' + key);
      if (!res.ok) return null;
      const data = await res.json();
      _costCache[key] = data;
      return data;
    } catch (e) {
      console.warn('[tokngauge]', e);
      return null;
    }
  }
  async function fetchConfig() {
    try {
      const r = await fetch('/api/config');
      if (r.ok) _config = Object.assign(_config, await r.json());
    } catch (e) { /* keep defaults */ }
    window.tngI18n.set(_config.language);
    document.documentElement.setAttribute('lang', _config.language);
  }
  async function saveConfig(updates) {
    const r = await fetch('/api/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (r.ok) _config = await r.json();
    window.tngI18n.set(_config.language);
    document.documentElement.setAttribute('lang', _config.language);
    _costCache = {};
  }
  async function fetchProviders() {
    try {
      const r = await fetch('/api/providers');
      if (r.ok) _providers = await r.json();
    } catch (e) { _providers = []; }
  }

  let _pricing = null;
  async function fetchPricing() {
    try {
      const r = await fetch('/api/pricing');
      if (r.ok) _pricing = await r.json();
    } catch (e) { /* keep last */ }
    return _pricing;
  }
  async function savePricing(payload) {
    const r = await fetch('/api/pricing', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (r.ok) _pricing = await r.json();
    _costCache = {};
    return _pricing;
  }
  async function reloadPricing() {
    const r = await fetch('/api/pricing/reload', { method: 'POST' });
    if (r.ok) _pricing = await r.json();
    _costCache = {};
    return _pricing;
  }
  async function resetPricing() {
    const r = await fetch('/api/pricing', { method: 'DELETE' });
    if (r.ok) _pricing = await r.json();
    _costCache = {};
    return _pricing;
  }

  // ── Format helpers ───────────────────────────────────────────────
  const CURRENCY_SYMBOLS = { USD: '$', EUR: '€', GBP: '£' };
  const FALLBACK_RATES = { USD: 1.0, EUR: 0.92, GBP: 0.79 };
  const rate = (ccy) => {
    const r = (_config.fxRates || {})[ccy];
    return (typeof r === 'number' && r > 0) ? r : (FALLBACK_RATES[ccy] || 1.0);
  };
  const conv = (usd) => usd * rate(_config.currency);
  const sym = () => CURRENCY_SYMBOLS[_config.currency] || '$';
  const fmtTokens = (n) => n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
                       : n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n);
  const fmtCost = (n) => `${sym()}${conv(n).toFixed(4)}`;
  const fmtCostShort = (n) => {
    const v = conv(n), s = sym();
    return v >= 100 ? `${s}${v.toFixed(0)}` : v >= 1 ? `${s}${v.toFixed(2)}` : `${s}${v.toFixed(4)}`;
  };

  // ── Spinner ──────────────────────────────────────────────────────
  const SPINNER = '<span class="neon-spinner"><svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><circle cx="32" cy="32" r="30" fill="none" stroke="url(#cost-sp-g)" stroke-width="2"/><defs><linearGradient id="cost-sp-g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#22d3ee"/><stop offset="100%" stop-color="#a855f7"/></linearGradient></defs></svg></span>';

  // ── Badge ────────────────────────────────────────────────────────
  async function loadCostBadge() {
    const data = await fetchCost({ source: 'all', days: 1 });
    const badge = document.getElementById('cost-badge');
    if (!badge || !data) return;
    const today = data.summary.todayCostUSD || 0;
    badge.textContent = `${t('header.today')}: ${sym()}${conv(today).toFixed(2)}`;
    badge.title = `${data.summary.todaySessionCount} ${t('card.sessions')}`;
    badge.classList.toggle('cost-badge-warn', today > 1.0);
    badge.classList.toggle('cost-badge-danger', today > 5.0);
  }

  // ── i18n DOM helper ──────────────────────────────────────────────
  function applyI18nAttrs(root) {
    (root || document).querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.dataset.i18n);
    });
  }

  // ── View renderer ────────────────────────────────────────────────
  async function renderView() {
    const body = document.getElementById('cost-panel-body');
    if (!body) return;
    body.innerHTML = '<div class="cost-loading">' + SPINNER + ' ' + t('loading') + '</div>';
    let html = renderTabs();
    if (_currentView === 'today') {
      html += await renderToday();
    } else if (_currentView === 'daily') {
      html += await renderTimeSeries('daily', 30);
    } else if (_currentView === 'monthly') {
      html += await renderTimeSeries('monthly', null);
    } else if (_currentView === 'yearly') {
      html += await renderTimeSeries('yearly', null);
    } else if (_currentView === 'projects') {
      html += await renderProjects();
    }
    body.innerHTML = html;
    attachHandlers(body);
  }

  // ── Settings modal ───────────────────────────────────────────────
  function openSettingsModal() {
    closeSettingsModal();
    const overlay = document.createElement('div');
    overlay.className = 'tng-modal-overlay';
    overlay.id = 'tng-settings-modal';
    overlay.innerHTML = `<div class="tng-modal" role="dialog" aria-modal="true">${renderSettings()}</div>`;
    document.body.appendChild(overlay);
    document.body.classList.add('tng-modal-open');
    attachSettingsHandlers(overlay);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeSettingsModal();
    });
    document.addEventListener('keydown', _escClose);
    fetchPricing().then(() => {
      const host = overlay.querySelector('#tng-pricing-host');
      if (!host) return;
      host.innerHTML = renderPricingSection();
      attachPricingHandlers(overlay);
    });
  }
  function closeSettingsModal() {
    const m = document.getElementById('tng-settings-modal');
    if (m) m.remove();
    document.body.classList.remove('tng-modal-open');
    document.removeEventListener('keydown', _escClose);
  }
  function _escClose(e) { if (e.key === 'Escape') closeSettingsModal(); }

  function attachSettingsHandlers(root) {
    const cancelBtn = root.querySelector('#tng-cancel-settings');
    if (cancelBtn) cancelBtn.addEventListener('click', closeSettingsModal);
    const saveBtn = root.querySelector('#tng-save-settings');
    if (saveBtn) saveBtn.addEventListener('click', async () => {
      const lang = root.querySelector('#tng-lang').value;
      const currency = root.querySelector('#tng-currency').value;
      const cpt = parseInt(root.querySelector('#tng-cpt').value, 10);
      const im = parseFloat(root.querySelector('#tng-im').value);
      const enabled = Array.from(root.querySelectorAll('input[name="tng-provider"]:checked')).map(c => c.value);
      const fxRates = { USD: 1.0 };
      ['EUR', 'GBP'].forEach(c => {
        const el = root.querySelector(`#tng-fx-${c}`);
        const v = el ? parseFloat(el.value) : NaN;
        if (!isNaN(v) && v > 0) fxRates[c] = v;
      });
      await saveConfig({
        language: lang, currency, charsPerToken: cpt,
        inputMultiplier: im, enabledProviders: enabled, fxRates,
      });
      const pricingPayload = _collectPricingPayload(root);
      if (Object.keys(pricingPayload.models).length || Object.keys(pricingPayload.premium).length) {
        await savePricing(pricingPayload);
      }
      _costCache = {};
      closeSettingsModal();
      applyI18nAttrs(document);
      loadCostBadge();
      renderView();
    });
  }

  function attachHandlers(body) {
    body.querySelectorAll('.cost-tab').forEach(tab => tab.addEventListener('click', () => {
      _currentView = tab.dataset.view; renderView();
    }));
    const dd = body.querySelector('#tng-source-dd');
    const ddBtn = body.querySelector('#tng-source-dd-btn');
    const ddMenu = body.querySelector('#tng-source-dd-menu');
    if (dd && ddBtn && ddMenu) {
      ddBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = dd.classList.toggle('open');
        ddMenu.classList.toggle('open', open);
      });
      ddMenu.querySelectorAll('.tng-source-dd-option').forEach(opt => {
        opt.addEventListener('click', () => {
          _currentSource = opt.dataset.source;
          _costCache = {};
          dd.classList.remove('open');
          ddMenu.classList.remove('open');
          renderView();
        });
      });
      document.addEventListener('click', function closeDD(e) {
        if (!dd.contains(e.target)) {
          dd.classList.remove('open');
          ddMenu.classList.remove('open');
          document.removeEventListener('click', closeDD);
        }
      });
    }
    body.querySelectorAll('.cost-project-link').forEach(link => link.addEventListener('click', (e) => {
      e.preventDefault();
      _currentProject = link.dataset.project; _currentView = 'daily'; _costCache = {}; renderView();
    }));
    const clear = body.querySelector('.cost-clear-project');
    if (clear) clear.addEventListener('click', (e) => {
      e.preventDefault(); _currentProject = null; _costCache = {}; renderView();
    });
  }

  function renderTabs() {
    const views = [
      { id: 'today', key: 'tab.today' },
      { id: 'daily', key: 'tab.daily' },
      { id: 'monthly', key: 'tab.monthly' },
      { id: 'yearly', key: 'tab.yearly' },
      { id: 'projects', key: 'tab.projects' },
    ];
    let html = '<div class="cost-tabs-row">';
    html += '<div class="cost-tabs">';
    for (const v of views) {
      html += `<button class="cost-tab ${_currentView === v.id ? 'active' : ''}" data-view="${v.id}">${t(v.key)}</button>`;
    }
    html += '</div>';
    if (_currentView !== 'settings') {
      const provList = _providers.length
        ? _providers
        : Object.keys(PROVIDER_ICONS).filter(id => id !== 'all').map(id => ({ id, displayName: PROVIDER_SHORT[id] || id, available: true }));
      const sources = [{ id: 'all', label: t('source.all'), icon: PROVIDER_ICONS['all'] }].concat(
        provList.map(p => ({ id: p.id, label: PROVIDER_SHORT[p.id] || p.displayName || p.id, icon: PROVIDER_ICONS[p.id] || '' }))
      );
      const cur = sources.find(s => s.id === _currentSource) || sources[0];
      const chevron = `<svg class="tng-source-dd-arrow" width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 1l4 4 4-4"/></svg>`;
      const check = `<svg class="tng-source-dd-check" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 6l3 3 5-5"/></svg>`;
      html += `<div class="tng-source-dropdown" id="tng-source-dd">`;
      html += `<button class="tng-source-dd-btn" id="tng-source-dd-btn" type="button"><span class="tng-source-dd-icon" data-provider="${cur.id}">${cur.icon}</span><span class="tng-source-dd-label">${cur.label}</span>${chevron}</button>`;
      html += `<div class="tng-source-dd-menu" id="tng-source-dd-menu">`;
      for (const s of sources) {
        const active = s.id === _currentSource;
        html += `<button class="tng-source-dd-option${active ? ' active' : ''}" data-source="${s.id}" type="button"><span class="tng-source-dd-icon" data-provider="${s.id}">${s.icon}</span><span>${s.label}</span>${active ? check : ''}</button>`;
      }
      html += `</div></div>`;
    }
    html += '</div>';
    if (_currentProject && _currentView !== 'settings') {
      html += `<div class="cost-project-filter">${t('project.filter')}: <strong>${_currentProject}</strong> <a href="#" class="cost-clear-project">${t('project.clear')}</a></div>`;
    }
    return html;
  }

  async function renderToday() {
    const data = await fetchCost({ source: _currentSource, days: 1, period: 'daily', project: _currentProject });
    if (!data) return `<p class="cost-loading">${t('error')}</p>`;
    const s = data.summary;
    let html = `
      <div class="cost-summary">
        <div class="cost-card cost-card-today">
          <div class="cost-card-label">${t('card.today')}</div>
          <div class="cost-card-value">${fmtCost(s.todayCostUSD)}</div>
          <div class="cost-card-sub">${s.todaySessionCount} ${t('card.sessions')} · ${s.totalTurns} ${t('card.turns')}</div>
        </div>
        <div class="cost-card">
          <div class="cost-card-label">${t('card.tokens')}</div>
          <div class="cost-card-value">${fmtTokens(s.totalTokens)}</div>
          <div class="cost-card-sub">↑${fmtTokens(s.totalInputTokens)} ↓${fmtTokens(s.totalOutputTokens)}</div>
        </div>
        <div class="cost-card">
          <div class="cost-card-label">${t('card.toolCalls')}</div>
          <div class="cost-card-value">${s.totalToolCalls}</div>
          <div class="cost-card-sub">${Object.entries(s.byProvider || {}).map(([k, v]) => `${provIcon(k)}${v}`).join(' · ')}</div>
        </div>
      </div>`;
    const models = data.byModel || {};
    if (Object.keys(models).length) html += renderModelTable(models);
    const provs = data.byProvider || {};
    if (Object.keys(provs).length) html += renderProviderTable(provs);
    const sessions = (data.sessions || []).slice(0, 10);
    if (sessions.length) html += renderSessionsTable(sessions);
    html += `<p class="cost-note">${t('note.heuristic')}</p>`;
    return html;
  }

  async function renderTimeSeries(period, days) {
    const data = await fetchCost({ source: _currentSource, period, days, project: _currentProject });
    if (!data) return `<p class="cost-loading">${t('error')}</p>`;
    const s = data.summary, ts = data.timeSeries || {};
    let html = `
      <div class="cost-summary">
        <div class="cost-card cost-card-total">
          <div class="cost-card-label">${t('card.total')}</div>
          <div class="cost-card-value">${fmtCost(s.totalCostUSD)}</div>
          <div class="cost-card-sub">${s.sessionCount} ${t('card.sessions')}</div>
        </div>
        <div class="cost-card">
          <div class="cost-card-label">${t('card.tokens')}</div>
          <div class="cost-card-value">${fmtTokens(s.totalTokens)}</div>
          <div class="cost-card-sub">↑${fmtTokens(s.totalInputTokens)} ↓${fmtTokens(s.totalOutputTokens)}</div>
        </div>
        <div class="cost-card">
          <div class="cost-card-label">${t('card.avg')}</div>
          <div class="cost-card-value">${s.sessionCount ? fmtCostShort(s.totalCostUSD / s.sessionCount) : sym() + '0'}</div>
          <div class="cost-card-sub">${s.sessionCount ? Math.round(s.totalTurns / s.sessionCount) : 0} ${t('card.turns')}/${t('card.sessions').replace(/s$/, '')}</div>
        </div>
      </div>`;
    const entries = Object.entries(ts);
    if (entries.length) {
      const maxCost = Math.max(...entries.map(([, v]) => v.cost));
      const sectionKey = period === 'daily' ? 'section.costByDay' : period === 'monthly' ? 'section.costByMonth' : 'section.costByYear';
      const stacked = _currentSource === 'all';
      // collect providers actually present (for legend ordering)
      const provSet = new Set();
      if (stacked) entries.forEach(([, v]) => Object.keys(v.byProvider || {}).forEach(p => provSet.add(p)));
      const provList = Array.from(provSet);
      html += `<div class="cost-chart"><h4 class="cost-section-title">${t(sectionKey)}</h4>`;
      if (stacked && provList.length > 1) {
        html += `<div class="cost-stack-legend">`;
        for (const p of provList) {
          html += `<span class="cost-stack-legend-item">${provIcon(p)}<span class="cost-stack-swatch" data-provider="${p}"></span>${p}</span>`;
        }
        html += `</div>`;
      }
      html += `<div class="cost-bars">`;
      const shown = period === 'daily' ? entries.slice(-30) : entries;
      for (const [key, val] of shown) {
        const pct = maxCost > 0 ? (val.cost / maxCost) * 100 : 0;
        const label = period === 'daily' ? key.slice(5) : key;
        let fillHtml;
        if (stacked && val.byProvider && Object.keys(val.byProvider).length) {
          fillHtml = '<div class="cost-bar-stack" style="width:' + pct + '%">';
          for (const p of provList) {
            const c = val.byProvider[p] || 0;
            if (c <= 0) continue;
            const segPct = (c / val.cost) * 100;
            fillHtml += `<div class="cost-bar-seg" data-provider="${p}" style="width:${segPct}%" title="${p}: ${fmtCostShort(c)}"></div>`;
          }
          fillHtml += '</div>';
        } else {
          fillHtml = `<div class="cost-bar-fill" style="width:${pct}%"></div>`;
        }
        html += `<div class="cost-bar-row">
          <span class="cost-bar-label">${label}</span>
          <div class="cost-bar-track">${fillHtml}</div>
          <span class="cost-bar-value">${fmtCostShort(val.cost)}</span>
          <span class="cost-bar-sessions">${val.sessions}s</span>
        </div>`;
      }
      html += '</div></div>';
    }
    const models = data.byModel || {};
    if (Object.keys(models).length) html += renderModelTable(models);
    const provs = data.byProvider || {};
    if (_currentSource === 'all' && Object.keys(provs).length) html += renderProviderTable(provs);
    return html;
  }

  async function renderProjects() {
    const data = await fetchCost({ source: _currentSource, period: 'monthly' });
    if (!data) return `<p class="cost-loading">${t('error')}</p>`;
    const projects = data.byProject || {};
    let html = `
      <div class="cost-summary">
        <div class="cost-card cost-card-total">
          <div class="cost-card-label">${t('card.total')}</div>
          <div class="cost-card-value">${fmtCost(data.summary.totalCostUSD)}</div>
          <div class="cost-card-sub">${data.summary.sessionCount} ${t('card.sessions')}</div>
        </div>
        <div class="cost-card">
          <div class="cost-card-label">${t('card.projects')}</div>
          <div class="cost-card-value">${Object.keys(projects).length}</div>
          <div class="cost-card-sub">${Object.entries(data.summary.byProvider || {}).map(([k, v]) => `${provIcon(k)}${v}`).join(' · ')}</div>
        </div>
      </div>`;
    if (Object.keys(projects).length) {
      const maxCost = Math.max(...Object.values(projects).map(p => p.cost));
      html += `<h4 class="cost-section-title">${t('section.costByProject')}</h4><div class="cost-bars">`;
      for (const [name, val] of Object.entries(projects)) {
        const pct = maxCost > 0 ? (val.cost / maxCost) * 100 : 0;
        html += `<div class="cost-bar-row">
          <a href="#" class="cost-bar-label cost-project-link" data-project="${name}" title="${name}">${name.length > 28 ? name.slice(0, 26) + '…' : name}</a>
          <div class="cost-bar-track"><div class="cost-bar-fill cost-bar-fill-project" style="width:${pct}%"></div></div>
          <span class="cost-bar-value">${fmtCostShort(val.cost)}</span>
          <span class="cost-bar-sessions">${val.sessions}s</span>
        </div>`;
      }
      html += '</div>';
    }
    const provs = data.byProvider || {};
    if (_currentSource === 'all' && Object.keys(provs).length > 1) html += renderProviderTable(provs);
    return html;
  }

  function renderSettings() {
    const langs = window.tngI18n.available;
    const currencies = ['USD', 'EUR', 'GBP'];
    const provs = _providers.length ? _providers : Object.keys(PROVIDER_LABEL).map(id => ({ id, displayName: PROVIDER_LABEL[id], available: true }));
    let html = `<div class="cost-settings"><h3>${t('settings.title')}</h3>`;
    html += `<div class="cost-setting-row"><label for="tng-lang">${t('settings.language')}</label>
      <select id="tng-lang">${langs.map(l => `<option value="${l}" ${l === _config.language ? 'selected' : ''}>${l.toUpperCase()}</option>`).join('')}</select></div>`;
    html += `<div class="cost-setting-row"><label for="tng-currency">${t('settings.currency')}</label>
      <select id="tng-currency">${currencies.map(c => `<option value="${c}" ${c === _config.currency ? 'selected' : ''}>${c}</option>`).join('')}</select></div>`;
    const fx = _config.fxRates || { USD: 1.0, EUR: 0.92, GBP: 0.79 };
    html += `<div class="cost-setting-row cost-fx-row">
      <label>${t('settings.fxRates')} <span class="cost-setting-unit">${t('settings.fxRates.unit')}</span></label>
      <div class="cost-fx-inputs">
        ${['EUR', 'GBP'].map(c => `<span class="cost-fx-item"><span class="cost-fx-ccy">${CURRENCY_SYMBOLS[c]} ${c}</span><input id="tng-fx-${c}" class="cost-fx-input" type="number" min="0.0001" step="0.0001" value="${fx[c] != null ? fx[c] : FALLBACK_RATES[c]}"></span>`).join('')}
      </div>
    </div>
    <p class="cost-setting-help">${t('settings.fxRates.help')}</p>`;
    html += `<h4>${t('settings.formula')}</h4>`;
    html += `<div class="cost-setting-row"><label for="tng-cpt">${t('settings.charsPerToken')} <span class="cost-setting-unit">${t('settings.charsPerToken.unit')}</span></label>
      <input id="tng-cpt" type="number" min="1" max="20" step="1" value="${_config.charsPerToken}"></div>`;
    html += `<p class="cost-setting-help">${t('settings.charsPerToken.help')}</p>`;
    html += `<div class="cost-setting-row"><label for="tng-im">${t('settings.inputMultiplier')} <span class="cost-setting-unit">${t('settings.inputMultiplier.unit')}</span></label>
      <input id="tng-im" type="number" min="0" max="50" step="0.1" value="${_config.inputMultiplier}"></div>`;
    html += `<p class="cost-setting-help">${t('settings.inputMultiplier.help')}</p>`;
    html += `<div class="cost-formula-box">
      <p class="cost-formula-intro">${t('settings.formula.intro')}</p>
      <ul class="cost-formula-list">
        <li><code>${t('settings.formula.output')}</code></li>
        <li><code>${t('settings.formula.input')}</code></li>
        <li><code>${t('settings.formula.cost')}</code> <span class="cost-formula-unit">${t('settings.formula.costUnit')}</span></li>
      </ul>
      <div class="cost-formula-legend">
        <span><b>N</b> · ${t('settings.formula.legendN').replace(/^N\s*=\s*/, '')}</span>
        <span><b>M</b> · ${t('settings.formula.legendM').replace(/^M\s*=\s*/, '')}</span>
      </div>
    </div>`;
    html += `<h4>${t('settings.providers')}</h4><div class="cost-providers-list">`;
    for (const p of provs) {
      const checked = _config.enabledProviders.includes(p.id) ? 'checked' : '';
      const availCls = p.available ? '' : ' cost-provider-item-off';
      const availTip = p.available ? t('settings.providerAvailable') : t('settings.providerUnavailable');
      html += `<label class="cost-provider-item${availCls}" title="${availTip}"><input type="checkbox" name="tng-provider" value="${p.id}" ${checked}>${provIcon(p.id)}<span class="cost-provider-name">${PROVIDER_LABEL[p.id] || p.displayName}</span><span class="cost-provider-status">${p.available ? '●' : '○'}</span></label>`;
    }
    html += `</div>`;
    html += `<div id="tng-pricing-host">${renderPricingSection()}</div>`;
    html += `<div class="cost-setting-actions"><button id="tng-cancel-settings" class="tng-btn-secondary" type="button">${t('settings.cancel')}</button><button id="tng-save-settings" class="tng-btn-primary" type="button">${t('settings.save')}</button></div>`;
    html += `</div>`;
    return html;
  }

  function _priceInput(model, field, val) {
    const safeVal = (val == null || isNaN(val)) ? '' : Number(val);
    return `<input class="tng-price-input" type="number" min="0" step="0.0001" data-model="${model}" data-field="${field}" value="${safeVal}">`;
  }

  function renderPricingSection() {
    const title = t('settings.pricing');
    if (!_pricing) {
      return `<h4>${title}</h4><p class="cost-setting-help">${t('loading')}</p>`;
    }
    const eff = _pricing.effective || { models: {}, premium: {} };
    const overrides = _pricing.overrides || { models: {}, premium: {} };
    const modelNames = Array.from(new Set([
      ...Object.keys(eff.models || {}),
      ...Object.keys(overrides.models || {}),
    ])).sort((a, b) => a === 'unknown' ? 1 : b === 'unknown' ? -1 : a.localeCompare(b));

    let html = `<h4>${title} <span class="cost-setting-unit">${t('settings.pricing.unit')}</span></h4>`;
    html += `<p class="cost-setting-help">${t('settings.pricing.help')}</p>`;
    html += `<div class="cost-pricing-toolbar">
      <code class="cost-pricing-path" title="${_pricing.path || ''}">${(_pricing.path || '').replace(/.*\/(?=[^/]+\/[^/]+$)/, '…/')}</code>
      <button id="tng-pricing-about" class="tng-btn-icon" type="button" title="${t('settings.pricing.aboutBtn')}" aria-label="${t('settings.pricing.aboutBtn')}">ⓘ</button>
      <span class="cost-pricing-flag">${_pricing.exists ? t('settings.pricing.fileExists') : t('settings.pricing.fileMissing')}</span>
      <span class="tng-spacer"></span>
      <button id="tng-pricing-reload" class="tng-btn-secondary" type="button">↻ ${t('settings.pricing.reload')}</button>
      <button id="tng-pricing-reset" class="tng-btn-secondary" type="button">⟲ ${t('settings.pricing.reset')}</button>
    </div>`;
    const safePath = (_pricing.path || '').replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
    html += `<div id="tng-pricing-about-box" class="cost-pricing-about" hidden>
      <h5>${t('settings.pricing.aboutTitle')}</h5>
      <p>${t('settings.pricing.aboutP1', { path: safePath })}</p>
      <p>${t('settings.pricing.aboutP2')}</p>
      <p><b>${t('settings.pricing.aboutSources')}</b></p>
      <ul class="cost-pricing-about-links">
        <li><a href="https://www.anthropic.com/pricing#api" target="_blank" rel="noopener">Anthropic Claude</a></li>
        <li><a href="https://openai.com/api/pricing/" target="_blank" rel="noopener">OpenAI / Codex</a></li>
        <li><a href="https://ai.google.dev/pricing" target="_blank" rel="noopener">Google Gemini</a></li>
        <li><a href="https://docs.github.com/en/copilot/managing-copilot/understanding-and-managing-copilot-usage/understanding-and-managing-requests-in-copilot" target="_blank" rel="noopener">GitHub Copilot (premium requests)</a></li>
        <li><a href="https://www.cursor.com/pricing" target="_blank" rel="noopener">Cursor</a></li>
      </ul>
      <p class="cost-pricing-about-tip">${t('settings.pricing.aboutTip')}</p>
    </div>`;
    html += `<div class="cost-pricing-tablewrap"><table class="cost-pricing-table">
      <thead><tr>
        <th title="${t('tip.model')}">${t('table.model')}<span class="tng-th-info">ⓘ</span></th>
        <th title="${t('tip.input')}">${t('settings.pricing.colInput')}<span class="tng-th-info">ⓘ</span></th>
        <th title="${t('tip.output')}">${t('settings.pricing.colOutput')}<span class="tng-th-info">ⓘ</span></th>
        <th title="${t('tip.cacheR')}">${t('settings.pricing.colCacheR')}<span class="tng-th-info">ⓘ</span></th>
        <th title="${t('tip.cacheW')}">${t('settings.pricing.colCacheW')}<span class="tng-th-info">ⓘ</span></th>
        <th title="${t('tip.premium')}">${t('settings.pricing.colPremium')}<span class="tng-th-info">ⓘ</span></th>
      </tr></thead><tbody>`;
    for (const name of modelNames) {
      const m = (eff.models && eff.models[name]) || {};
      const prem = (eff.premium && eff.premium[name] != null) ? eff.premium[name] : 1;
      const isOverridden = (overrides.models && overrides.models[name])
        || (overrides.premium && overrides.premium[name] != null);
      html += `<tr${isOverridden ? ' class="tng-price-row-mod"' : ''}>
        <td><code>${name}</code></td>
        <td>${_priceInput(name, 'input', m.input)}</td>
        <td>${_priceInput(name, 'output', m.output)}</td>
        <td>${_priceInput(name, 'cacheRead', m.cacheRead)}</td>
        <td>${_priceInput(name, 'cacheWrite', m.cacheWrite)}</td>
        <td><input class="tng-price-input" type="number" min="0" step="0.01" data-premium="${name}" value="${prem}"></td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
    html += `<div class="cost-pricing-add">
      <input id="tng-pricing-newmodel" type="text" placeholder="${t('settings.pricing.addPlaceholder')}" maxlength="80">
      <button id="tng-pricing-add" class="tng-btn-secondary" type="button">+ ${t('settings.pricing.addBtn')}</button>
    </div>`;
    html += `<p id="tng-pricing-status" class="cost-setting-help" aria-live="polite"></p>`;
    return html;
  }

  function _collectPricingPayload(root) {
    const models = {};
    root.querySelectorAll('.tng-price-input[data-model]').forEach(inp => {
      const m = inp.dataset.model, f = inp.dataset.field;
      if (!models[m]) models[m] = {};
      const v = inp.value === '' ? null : parseFloat(inp.value);
      if (v != null && !isNaN(v)) models[m][f] = v;
    });
    const premium = {};
    root.querySelectorAll('.tng-price-input[data-premium]').forEach(inp => {
      const v = inp.value === '' ? null : parseFloat(inp.value);
      if (v != null && !isNaN(v)) premium[inp.dataset.premium] = v;
    });
    return { models, premium };
  }

  function attachPricingHandlers(root) {
    const status = (msg) => {
      const el = root.querySelector('#tng-pricing-status');
      if (el) { el.textContent = msg || ''; }
    };
    const refreshSection = () => {
      const host = root.querySelector('#tng-pricing-host');
      if (host) { host.innerHTML = renderPricingSection(); attachPricingHandlers(root); }
    };

    const reloadBtn = root.querySelector('#tng-pricing-reload');
    if (reloadBtn) reloadBtn.addEventListener('click', async () => {
      reloadBtn.disabled = true;
      await reloadPricing();
      refreshSection();
      status(t('settings.pricing.reloaded'));
    });

    const aboutBtn = root.querySelector('#tng-pricing-about');
    const aboutBox = root.querySelector('#tng-pricing-about-box');
    if (aboutBtn && aboutBox) {
      aboutBtn.addEventListener('click', () => {
        const open = !aboutBox.hidden;
        aboutBox.hidden = open;
        aboutBtn.classList.toggle('is-active', !open);
      });
    }

    const resetBtn = root.querySelector('#tng-pricing-reset');
    if (resetBtn) resetBtn.addEventListener('click', async () => {
      if (!confirm(t('settings.pricing.resetConfirm'))) return;
      resetBtn.disabled = true;
      await resetPricing();
      refreshSection();
      status(t('settings.pricing.resetDone'));
    });

    const addBtn = root.querySelector('#tng-pricing-add');
    const newInp = root.querySelector('#tng-pricing-newmodel');
    if (addBtn && newInp) {
      const doAdd = async () => {
        const name = (newInp.value || '').trim();
        if (!name) return;
        await savePricing({ models: { [name]: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } } });
        await fetchPricing();
        refreshSection();
        status(`+ ${name}`);
      };
      addBtn.addEventListener('click', doAdd);
      newInp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); doAdd(); } });
    }
  }

  function renderModelTable(models) {
    let html = `<h4 class="cost-section-title">${t('section.modelBreakdown')}</h4>`;
    html += `<table class="cost-table"><thead><tr><th title="${t('tip.model')}">${t('table.model')}<span class="tng-th-info">ⓘ</span></th><th title="${t('tip.input')}">${t('table.input')}<span class="tng-th-info">ⓘ</span></th><th title="${t('tip.output')}">${t('table.output')}<span class="tng-th-info">ⓘ</span></th><th>${t('table.cost')}</th><th title="${t('tip.premium')}">${t('table.premium')}<span class="tng-th-info">ⓘ</span></th></tr></thead><tbody>`;
    for (const [model, info] of Object.entries(models)) {
      html += `<tr><td><code>${model}</code></td><td>${fmtTokens(info.inputTokens)}</td><td>${fmtTokens(info.outputTokens)}</td><td>${fmtCost(info.cost)}</td><td>${(info.premiumRequests || 0).toFixed(0)}</td></tr>`;
    }
    html += '</tbody></table>';
    return html;
  }

  function renderProviderTable(provs) {
    let html = `<h4 class="cost-section-title">${t('section.providerBreakdown')}</h4>`;
    html += `<table class="cost-table"><thead><tr><th>${t('table.source')}</th><th>${t('card.sessions')}</th><th>${t('table.turns')}</th><th>${t('table.cost')}</th></tr></thead><tbody>`;
    for (const [name, info] of Object.entries(provs)) {
      html += `<tr><td>${provIcon(name)} <code>${name}</code></td><td>${info.sessions}</td><td>${info.turns}</td><td>${fmtCost(info.cost)}</td></tr>`;
    }
    html += '</tbody></table>';
    return html;
  }

  function renderSessionsTable(sessions) {
    let html = `<h4 class="cost-section-title">${t('section.lastSessions')}</h4>`;
    html += `<table class="cost-table cost-table-sessions"><thead><tr><th>${t('table.time')}</th><th>${t('table.source')}</th><th>${t('table.project')}</th><th>${t('table.turns')}</th><th>${t('table.tools')}</th><th>${t('table.cost')}</th></tr></thead><tbody>`;
    for (const s of sessions) {
      const time = s.startTime ? new Date(s.startTime).toLocaleString(_config.language, { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '—';
      const icon = provIcon(s.source) || '·';
      const proj = (s.project || '?').length > 18 ? (s.project || '?').slice(0, 16) + '…' : (s.project || '?');
      html += `<tr><td>${time}</td><td title="${s.source}">${icon}</td><td title="${s.project || ''}">${proj}</td><td>${s.turns}</td><td>${s.toolCalls}</td><td>${fmtCost(s.estimatedCostUSD)}</td></tr>`;
    }
    html += '</tbody></table>';
    return html;
  }

  // ── Init ─────────────────────────────────────────────────────────
  async function init() {
    await Promise.all([fetchConfig(), fetchProviders()]);
    applyI18nAttrs(document);
    const setBtn = document.getElementById('tng-settings-btn');
    if (setBtn) setBtn.addEventListener('click', () => openSettingsModal());
    loadCostBadge();
    renderView();
    setInterval(() => { _costCache = {}; loadCostBadge(); }, 60000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
