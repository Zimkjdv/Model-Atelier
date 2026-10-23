import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

for (const width of [1440, 390]) {
  test.describe(`${width}px R05`, () => {
    test.use({ viewport: { width, height: 900 } })
    test('anime suite selection and prompt comparison save without generation', async ({
      page,
      request,
    }, info) => {
      expect((await request.post('/qa/extended-models')).ok()).toBe(true)
      const before = await (await request.get('/qa/state')).json()
      const title = 'R05 ' + randomUUID()
      try {
        const creation = await (
          await request.get('/api/artworks/' + before.artwork_id + '/creation-settings')
        ).json()
        const settings = { ...creation.settings, title, width: 64, height: 64 }
        expect((await request.post('/api/drafts', { data: settings })).ok()).toBe(true)
        await page.goto('/#/studio/checkpoint')
        await page
          .locator('.draft-row')
          .filter({ has: page.getByText(title, { exact: true }) })
          .click()
        if (await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).isVisible())
          await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).click()
        const area = page.locator('.experiment-planner')
        await area.locator(':scope > summary').click()
        await page.locator('#experiment-title').fill(title)
        await page.locator('#experiment-suite').selectOption('anime-illustration')
        await area.getByRole('checkbox', { name: '成年旅人半身像', exact: true }).check()
        await page.locator('#experiment-axis').selectOption('seed')
        await page
          .locator('#experiment-values')
          .fill('["9007199254740993", "18446744073709551615"]')
        await area.getByRole('button', { name: '預覽比較方案', exact: true }).click()
        await expect(area.getByRole('region', { name: '參數比較預覽' })).toContainText(
          'anime-portrait',
        )
        // Switching suites clears selected cases and the obsolete preview.
        await page.locator('#experiment-suite').selectOption('general-illustration')
        await expect(area.getByRole('region', { name: '參數比較預覽' })).toHaveCount(0)
        await expect(area.getByRole('checkbox', { checked: true })).toHaveCount(0)
        await expect(area.getByRole('checkbox', { name: '椅子說明書', exact: true })).toBeVisible()
        await page.locator('#experiment-axis').selectOption('prompt')
        const prompts = ['adult traveler, red scarf', 'score_9, adult traveler, red scarf']
        await page.locator('#experiment-values').fill(JSON.stringify(prompts))
        await area.getByRole('button', { name: '預覽比較方案', exact: true }).click()
        await expect(area.getByRole('region', { name: '參數比較預覽' })).toContainText(
          '預計 2 次生成',
        )
        await area.locator('.saved-experiments > summary').click()
        const saving = page.waitForResponse(
          (r) => r.url().endsWith('/api/experiments/plans') && r.request().method() === 'POST',
        )
        await area.getByRole('button', { name: '保存目前預覽方案', exact: true }).click()
        const response = await saving
        expect(response.ok(), await response.text()).toBe(true)
        const saved = await response.json()
        expect(saved.plan.axis).toBe('prompt')
        expect(saved.plan.schema_version).toBe(2)
        expect(
          saved.plan.variants.map((v: { settings: { prompt: string } }) => v.settings.prompt),
        ).toEqual(prompts)
        await area.getByRole('button', { name: '載入比較設定 variant-2', exact: true }).click()
        await expect(page.locator('#draft-prompt')).toHaveValue(prompts[1])
        expect((await (await request.get('/qa/state')).json()).prompts).toBe(before.prompts)
        await area.scrollIntoViewIfNeeded()
        await page.screenshot({ path: info.outputPath('anime-prompt-comparison.png') })
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        )
      } finally {
        await request.post('/qa/extended-models/reset')
      }
    })
  })
}
