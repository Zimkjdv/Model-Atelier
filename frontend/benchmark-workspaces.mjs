import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { cpus, platform, release } from 'node:os'
import path from 'node:path'

const mode = process.argv[2]
if (!['before', 'after'].includes(mode))
  throw new Error('Usage: node benchmark-workspaces.mjs before|after')
const port = Number(process.env.ATELIER_TEST_PORT || 18861)
const base = 'http://127.0.0.1:' + port
const python =
  process.env.ATELIER_TEST_PYTHON ||
  path.resolve('../.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const channel = process.env.ATELIER_BROWSER_CHANNEL || undefined
const server = spawn(
  python,
  ['../scripts/browser_fixture.py', '--port', String(port), '--count', '100'],
  { windowsHide: true, stdio: 'ignore' },
)
let startupError
server.once('error', (error) => {
  startupError = error
})
let browser
try {
  for (let attempt = 0; ; attempt++) {
    if (startupError) throw startupError
    if (server.exitCode !== null) throw new Error('Fixture exited: ' + server.exitCode)
    const response = await fetch(base + '/qa/state').catch(() => null)
    if (response?.ok) break
    if (attempt === 199) throw new Error('Fixture did not start')
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  browser = await chromium.launch({ channel })
  const results = []
  const repeats = 11
  const measure = async (page, action, ready) => {
    const start = await page.evaluate(() => performance.now())
    await action()
    await ready()
    return page.evaluate((since) => {
      const now = performance.now()
      const entries = performance
        .getEntriesByType('resource')
        .filter((entry) => entry.startTime >= since)
      const js = entries.filter((entry) => /\.m?js$/.test(new URL(entry.name).pathname))
      return {
        ms: Math.round(now - since),
        js_requests: js.length,
        js_decoded_bytes: js.reduce((total, entry) => total + entry.decodedBodySize, 0),
        js_transfer_bytes: js.reduce((total, entry) => total + entry.transferSize, 0),
      }
    }, start)
  }
  for (let i = 0; i < repeats; i++) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    try {
      const page = await context.newPage()
      const main = page.getByRole('main')
      const nav = page.getByRole('navigation', { name: '主要導覽' })
      const visit = (name) => nav.getByRole('button', { name, exact: true }).click()
      await page.goto(base + '/', { waitUntil: 'commit' })
      await main.getByRole('tab', { name: '總覽' }).waitFor()
      const first = await page.evaluate(() => {
        const js = performance
          .getEntriesByType('resource')
          .filter((entry) => /\.m?js$/.test(new URL(entry.name).pathname))
        return {
          ms: Math.round(performance.now()),
          js_requests: js.length,
          js_decoded_bytes: js.reduce((total, entry) => total + entry.decodedBodySize, 0),
          js_transfer_bytes: js.reduce((total, entry) => total + entry.transferSize, 0),
        }
      })
      const gallery = await measure(
        page,
        () => visit('作品庫'),
        () => page.locator('.artwork-card').first().waitFor(),
      )
      const models = await measure(
        page,
        () => visit('模型庫'),
        () => page.getByRole('group', { name: '模型排版' }).waitFor(),
      )
      const studio = await measure(
        page,
        () => visit('創作工作台'),
        () =>
          page
            .getByRole('group', { name: '起始配方' })
            .getByRole('button')
            .first()
            .and(page.locator('button:enabled'))
            .waitFor(),
      )
      const gallery_again = await measure(
        page,
        () => visit('作品庫'),
        () => page.locator('.artwork-card').first().waitFor(),
      )
      results.push({ first, gallery, models, studio, gallery_again })
    } finally {
      await context.close()
    }
  }
  const median = Object.fromEntries(
    Object.keys(results[0]).map((key) => [
      key,
      Object.fromEntries(
        Object.keys(results[0][key]).map((field) => [
          field,
          results.map((result) => result[key][field]).sort((a, b) => a - b)[
            Math.floor(repeats / 2)
          ],
        ]),
      ),
    ]),
  )
  const report = {
    mode,
    browser: browser.version(),
    channel,
    os: platform() + ' ' + release(),
    cpu: cpus()[0]?.model,
    viewport: '1440x900',
    fixture_count: 100,
    repeats,
    results,
    median,
  }
  await mkdir('../runtime/quality', { recursive: true })
  await writeFile(
    '../runtime/quality/o02-' + mode + '.json',
    JSON.stringify(report, null, 2) + '\n',
  )
  console.log(JSON.stringify({ browser: report.browser, cpu: report.cpu, median }))
} finally {
  try {
    await browser?.close()
  } finally {
    server.kill()
  }
}
