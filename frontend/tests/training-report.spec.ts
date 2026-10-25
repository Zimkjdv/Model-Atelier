import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFile } from 'node:fs/promises'

for (const width of [1440, 390]) {
  test(`training report previews exact downloads, scopes and stale reads at ${width}px`, async ({
    page,
  }) => {
    const first = 'c6000000-0000-4000-8000-000000000001',
      second = 'c6000000-0000-4000-8000-000000000002'
    let reports = 0,
      writes = 0,
      delayed = false,
      release = () => {}
    let expected = ''
    await page.addInitScript(() => {
      const original = window.fetch
      window.fetch = (input, options) =>
        original(
          input,
          String(input).includes('/report?') ? { ...options, signal: undefined } : options,
        )
    })
    await page.route('**/api/training/**', async (route) => {
      const url = new URL(route.request().url()),
        path = url.pathname.replace('/api/training/', '')
      if (route.request().method() !== 'GET') writes++
      if (path === 'control')
        return route.fulfill({
          json: {
            available: true,
            requests: [],
            exports: [],
            runs: [first, second].map((run_id) => ({
              run_id,
              status: 'unavailable',
              configuration: { label: 'Synthetic unavailable run' },
            })),
          },
        })
      if (path.endsWith('/report')) {
        reports++
        if (delayed)
          await new Promise<void>((resolve) => {
            release = resolve
          })
        const logs = url.searchParams.get('include_logs') === 'true'
        const body = {
          schema_version: 1,
          kind: 'model-atelier-training-report',
          run_id: path.split('/')[1],
          capture_finished_at: '2026-10-25T04:00:00+00:00',
          scope: { logs_included: logs, read_only: true, payload_files_verified: false },
          issues: [{ record: 'state.json', code: 'unreadable_record' }],
          observation: { status: 'unknown', resources_released: null },
          ...(logs ? { log: { text: '合成日誌尾段，非作者資料' } } : {}),
        }
        expected = JSON.stringify(body, null, 2)
        return route.fulfill({ contentType: 'application/json', body: expected })
      }
      return route.fulfill({ status: 404, json: { detail: 'Fixture metadata unavailable' } })
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/training')
    await page.getByRole('button', { name: '訓練執行', exact: true }).click()
    await expect(page.getByLabel('報告 run', { exact: true })).toHaveValue(first)
    expect(reports).toBe(0)
    await page.getByRole('button', { name: '預覽訓練報告', exact: true }).click()
    const preview = page.getByRole('region', { name: '訓練報告 JSON 預覽', exact: true })
    await expect(preview).toBeVisible()
    await expect(preview).toHaveText(expected)
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: '下載此訓練報告 JSON', exact: true }).click()
    const file = await download
    expect(file.suggestedFilename()).toBe(`training-report-${first}.json`)
    expect(await readFile((await file.path())!, 'utf8')).toBe(expected)
    expect(reports).toBe(1)
    await page
      .getByRole('checkbox', { name: '附上 worker 日誌尾段與狀態訊息', exact: true })
      .check()
    await expect(preview).toHaveCount(0)
    await page.getByRole('button', { name: '預覽訓練報告', exact: true }).click()
    await expect(preview).toContainText('合成日誌尾段')
    expect(reports).toBe(2)
    delayed = true
    await page.getByRole('button', { name: '預覽訓練報告', exact: true }).click()
    await expect.poll(() => reports).toBe(3)
    await page.getByLabel('報告 run', { exact: true }).selectOption(second)
    release()
    await expect(preview).toHaveCount(0)
    delayed = false
    await page.getByRole('button', { name: '預覽訓練報告', exact: true }).click()
    await expect(preview).toContainText(second)
    expect(writes).toBe(0)
    await page.route(`**/api/training/runs/${second}/report?*`, (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: 1,
          kind: 'model-atelier-training-report',
          run_id: first,
          scope: { logs_included: true },
          issues: [],
        }),
      }),
    )
    await page.getByRole('button', { name: '預覽訓練報告', exact: true }).click()
    await expect(
      page.getByRole('alert').filter({ hasText: '報告識別或資料範圍不符' }),
    ).toBeVisible()
    await expect(preview).toHaveCount(0)
    await page.route(`**/api/training/runs/${second}/report?*`, (route) =>
      route.fulfill({ contentType: 'application/json', body: ' '.repeat(1024 * 1024 + 1) }),
    )
    await page.getByRole('button', { name: '預覽訓練報告', exact: true }).click()
    await expect(page.getByRole('alert').filter({ hasText: '訓練報告超過 1 MiB' })).toBeVisible()
    await expect(
      page.getByRole('button', { name: '下載此訓練報告 JSON', exact: true }),
    ).toHaveCount(0)
    const accessibility = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze()
    expect(accessibility.violations).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
