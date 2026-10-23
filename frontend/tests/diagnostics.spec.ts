import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'

for (const width of [1440, 390]) test(`${width}px: diagnostic preview, ID filter and exact download stay private and read-only`, async ({ page, request }, info) => {
  await page.setViewportSize({ width, height: 900 })
  await request.post('/qa/engine/uncertain')
  const jobId = randomUUID()
  const submitted = await request.post('/api/generate', { data: {
    request_id: jobId, title: 'PRIVATE_TITLE', prompt: 'PRIVATE_PROMPT C:\\Users\\PERSON', negative_prompt: 'PRIVATE_NEGATIVE',
    engine_url: 'http://mock-engine.invalid:8188', checkpoint: 'demo.safetensors', width: 512, height: 512, seed: '18446744073709551615',
  } })
  expect(submitted.ok()).toBe(true)
  const requestId = submitted.headers()['x-request-id']
  const before = await (await request.get('/api/jobs/' + jobId)).json()
  const prompts = (await (await request.get('/qa/state')).json()).prompts
  await request.post('/qa/engine/offline')
  try {
    await page.goto('/#/settings')
    const panel = page.getByRole('region', { name: '故障診斷', exact: true })
    await panel.getByRole('button', { name: '唯讀檢查狀態', exact: true }).click()
    await expect(panel.getByLabel('服務與資料狀態')).toContainText('離線')
    await expect(panel.getByLabel('服務與資料狀態')).toContainText('可讀')
    await panel.locator('#diagnostic-job').fill(jobId)
    await panel.locator('#diagnostic-request').fill(requestId)
    await panel.getByRole('button', { name: '預覽診斷 JSON', exact: true }).click()
    const preview = await panel.getByLabel('診斷 JSON 預覽').innerText()
    const value = JSON.parse(preview)
    expect(value.events.length).toBeGreaterThan(0)
    expect(value.events.every(event => event.job_id === jobId && event.request_id === requestId)).toBe(true)
    expect(value.events.some(event => event.stage === 'engine_submit' && event.classification === 'submission_uncertain')).toBe(true)
    expect(preview).not.toContain('PRIVATE')
    expect(preview).not.toContain('mock-engine.invalid')
    expect(preview).not.toContain('demo.safetensors')
    expect(value.readiness.data.status).toBe('readable')
    expect(value.readiness.engine.status).toBe('offline')
    const downloaded = page.waitForEvent('download')
    await panel.getByRole('button', { name: '下載此預覽 JSON', exact: true }).click()
    const file = await downloaded
    expect(await readFile((await file.path())!, 'utf8')).toBe(preview)
    expect(file.suggestedFilename()).toBe('model-atelier-diagnostics.json')
    await page.screenshot({ path: info.outputPath('diagnostic-preview.png') })
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(prompts)
    // The independent sampler may advance while diagnostics are open. Generation
    // ownership, revision and all submission-time measurements must remain unchanged.
    const withoutLiveSamples = (job: any) => {
      const copy = structuredClone(job)
      delete copy.measurements.continuous_resources
      return copy
    }
    expect(withoutLiveSamples(await (await request.get('/api/jobs/' + jobId)).json())).toEqual(withoutLiveSamples(before))
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await panel.locator('#diagnostic-request').fill('invalid')
    await expect(panel.getByRole('button', { name: '下載此預覽 JSON', exact: true })).not.toBeVisible()
    await panel.getByRole('button', { name: '預覽診斷 JSON', exact: true }).click()
    await expect(panel.getByRole('alert')).toBeVisible()
  } finally { await request.post('/qa/engine/uncertain').catch(() => {}) }
})
