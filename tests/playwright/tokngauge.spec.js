// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const TMP_CFG = path.resolve(__dirname, '.tng-config.json');

test.beforeEach(async () => {
  try { fs.unlinkSync(TMP_CFG); } catch (_) {}
});

test('home page loads with title and logo', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/TokNGauge/);
  await expect(page.locator('.tng-logo')).toBeVisible();
  await expect(page.locator('h1.tng-title')).toContainText('TokNGauge');
});

test('providers list is populated from API', async ({ page }) => {
  await page.goto('/');
  // Source filter buttons render once /api/providers resolves
  await expect(page.locator('.cost-source-btn').first()).toBeVisible({ timeout: 10_000 });
  const count = await page.locator('.cost-source-btn').count();
  expect(count).toBeGreaterThanOrEqual(2); // at least "All" + 1 provider
});

test('summary cards render with values', async ({ page }) => {
  await page.goto('/');
  // Wait for tabs row to be ready (means data fetched)
  await expect(page.locator('.cost-tabs').first()).toBeVisible({ timeout: 10_000 });
  // Today view: at least one cost card should be present in the DOM
  await expect(page.locator('.cost-card').first()).toBeVisible({ timeout: 10_000 });
});

test('opening settings shows language + formula controls', async ({ page }) => {
  await page.goto('/');
  await page.locator('#tng-settings-btn').click();
  await expect(page.locator('select#tng-lang')).toBeVisible();
  await expect(page.locator('input#tng-cpt')).toBeVisible();
  await expect(page.locator('input#tng-im')).toBeVisible();
});

test('changing language to English updates UI strings', async ({ page }) => {
  await page.goto('/');
  await page.locator('#tng-settings-btn').click();
  await page.locator('select#tng-lang').selectOption('en');
  await page.locator('#tng-save-settings').click();
  await expect(page.locator('.tng-saved-flash')).toHaveText(/saved|guardado/i);
  await expect(page.locator('h1.tng-title')).toBeVisible();
});

test('changing formula persists via API roundtrip', async ({ page, request }) => {
  await page.goto('/');
  await page.locator('#tng-settings-btn').click();
  await page.locator('input#tng-cpt').fill('6');
  await page.locator('input#tng-im').fill('3');
  await page.locator('#tng-save-settings').click();
  await expect(page.locator('.tng-saved-flash')).toHaveText(/saved|guardado/i);

  const r = await request.get('/api/config');
  const cfg = await r.json();
  expect(cfg.charsPerToken).toBe(6);
  expect(cfg.inputMultiplier).toBe(3);
});

test('toggling a provider persists in config', async ({ page, request }) => {
  await page.goto('/');
  await page.locator('#tng-settings-btn').click();
  const firstChk = page.locator('.cost-provider-item input[type=checkbox]').first();
  await firstChk.uncheck();
  await page.locator('#tng-save-settings').click();
  await expect(page.locator('.tng-saved-flash')).toHaveText(/saved|guardado/i);

  const r = await request.get('/api/config');
  const cfg = await r.json();
  expect(cfg.enabledProviders.length).toBeLessThan(7);
});

test('icons are served (svg + png + manifest)', async ({ request }) => {
  const svg = await request.get('/static/icons/icon.svg');
  expect(svg.status()).toBe(200);
  const png = await request.get('/static/icons/icon-256.png');
  expect(png.status()).toBe(200);
  const ico = await request.get('/static/icons/icon.ico');
  expect(ico.status()).toBe(200);
  const mf = await request.get('/static/manifest.webmanifest');
  expect(mf.status()).toBe(200);
});
