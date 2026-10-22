import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import { writeFile } from 'node:fs/promises'
import path from 'node:path'

const mode = process.argv[2]
if (!['legacy', 'paged'].includes(mode)) throw new Error('Usage: node benchmark-listing.mjs legacy|paged')
const python = process.env.ATELIER_TEST_PYTHON || path.resolve('../.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const browser = await chromium.launch()
const results = []
try {
  for (const count of [100, 1000, 10000]) {
    const server = spawn(python, ['../scripts/browser_fixture.py', '--port', '18766', '--count', String(count), ...(mode === 'legacy' ? ['--legacy-ui'] : [])], { windowsHide: true, stdio: 'ignore' })
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
    try {
      let ready = false
      for (let i = 0; i < 300; i++) {
        if (server.exitCode !== null) throw new Error('Fixture server exited')
        try { if ((await fetch('http://127.0.0.1:18766/qa/state')).ok) { ready = true; break } } catch {}
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      if (!ready) throw new Error('Fixture did not start')
      const page = await context.newPage()
      page.setDefaultTimeout(30000)
      let bytes = 0
      const bodies = []
      page.on('response', response => {
        if (/\/api\/(library\/)?(artworks|jobs)(\?|$)/.test(response.url())) bodies.push(response.body().then(body => { bytes += body.length }).catch(() => {}))
      })
      await page.goto('http://127.0.0.1:18766')
      const start = performance.now()
      await page.getByRole('button', { name: '作品庫', exact: true }).click()
      await page.locator('.artwork-card').first().waitFor()
      await page.locator('#artwork-search').fill('fixture-00001')
      await page.waitForTimeout(400)
      await page.waitForFunction(() => !document.body.innerText.includes('正在讀取或匯入作品'))
      await Promise.all(bodies)
      const result = { count, interactive_search_ms: Math.round(performance.now() - start), list_response_bytes: bytes,
        rendered_cards: await page.locator('.artwork-card').count(), js_heap_bytes: await page.evaluate(() => performance.memory?.usedJSHeapSize ?? null) }
      results.push(result)
      console.log(JSON.stringify(result))
      await writeFile(`../runtime/q04-ui-${mode}.json`, JSON.stringify({ mode, browser: browser.version(), repeats: 1, results }, null, 2))
    } catch (e) {
      results.push({count, error:String(e), interactive_search_ms:null})
      console.error(String(e))
    } finally {
      await context.close()
      server.kill()
      await new Promise(resolve => server.once('exit', resolve))
    }
  }
} finally { await browser.close() }
await writeFile(`../runtime/q04-ui-${mode}.json`, JSON.stringify({ mode, browser: browser.version(), repeats: 1, results }, null, 2))
if (mode === 'paged' && results.some(result => result.error || result.interactive_search_ms > 2500)) throw new Error('Paged UI exceeded the 2500ms budget')
