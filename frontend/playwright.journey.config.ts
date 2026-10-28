import { defineConfig } from '@playwright/test'
import path from 'node:path'
import base from './playwright.config'

const python =
  process.env.ATELIER_TEST_PYTHON ||
  path.resolve('../.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const port = Number(process.env.ATELIER_TEST_PORT || 18769)

export default defineConfig(base, {
  testDir: './journey-tests',
  testMatch: '**/isolated-journey.spec.ts',
  timeout: 180000,
  globalTimeout: 240000,
  outputDir: '../runtime/quality/journey-results',
  reporter: [
    ['list'],
    ['html', { outputFolder: '../runtime/quality/journey-report', open: 'never' }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    viewport: { width: 1440, height: 900 },
    actionTimeout: 15000,
    navigationTimeout: 15000,
  },
  webServer: {
    ...base.webServer,
    command: `"${python}" ../scripts/browser_fixture.py --port ${port} --empty`,
    url: `http://127.0.0.1:${port}/qa/state`,
    reuseExistingServer: false,
  },
})
