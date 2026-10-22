import { defineConfig } from '@playwright/test'
import path from 'node:path'

const python = process.env.ATELIER_TEST_PYTHON || path.resolve('../.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const port = Number(process.env.ATELIER_TEST_PORT || 18765)

export default defineConfig({
  testDir: './tests',
  workers: 1,
  retries: 0,
  timeout: 45000,
  globalTimeout: 300000,
  expect: { timeout: 10000 },
  outputDir: '../runtime/quality/browser-results',
  reporter: [['list'], ['html', { outputFolder: '../runtime/quality/browser-report', open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: 'chromium',
    channel: process.env.ATELIER_BROWSER_CHANNEL || undefined,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: `"${python}" ../scripts/browser_fixture.py --port ${port}`,
    url: `http://127.0.0.1:${port}/qa/state`,
    reuseExistingServer: false,
    timeout: 30000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
