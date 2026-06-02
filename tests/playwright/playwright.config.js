// @ts-check
const { defineConfig } = require('@playwright/test');
const path = require('path');

const repoRoot = path.resolve(__dirname, '..', '..');
const tmpConfig = path.resolve(__dirname, '.tng-config.json');

module.exports = defineConfig({
  testDir: '.',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8766',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `${repoRoot}/.venv/bin/python ${repoRoot}/server.py`,
    cwd: repoRoot,
    env: {
      TOKNGAUGE_PORT: '8766',
      TOKNGAUGE_CONFIG: tmpConfig,
    },
    url: 'http://127.0.0.1:8766/api/providers',
    reuseExistingServer: false,
    timeout: 60_000,
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
