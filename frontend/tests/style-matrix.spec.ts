import { randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { expect, test } from '@playwright/test'

for (const width of [1440, 390]) {
  test.describe(`${width}px L01`, () => {
    test.use({ viewport: { width, height: 900 } })
    test('new style stack retains ordered conditions and quality failures without dispatch', async ({
      page,
      request,
    }, info) => {
      const response = await request.post('/qa/comparison-context')
      expect(response.ok()).toBe(true)
      const data = await response.json()
      const before = await (await request.get('/qa/state')).json()
      const pixel = JSON.parse(
        await readFile('../models/pixel-art-lora-sdxl-comfy-v1.json', 'utf8'),
      )
      const title = 'L01 ' + randomUUID()
      try {
        const settings = {
          ...data.settings,
          title,
          seed: '18446744073709551615',
          loras: [
            data.settings.loras[0],
            { name: pixel.filename, enabled: true, strength_model: 1, strength_clip: 1 },
          ],
        }
        expect((await request.post('/api/drafts', { data: settings })).ok()).toBe(true)
        await page.goto('/#/studio/checkpoint')
        await page
          .locator('.draft-row')
          .filter({ has: page.getByText(title, { exact: true }) })
          .click()
        if (await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).isVisible())
          await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).click()
        const area = page.getByRole('region', { name: '有序 LoRA 組合實測紀錄' })
        await expect(area.getByRole('status')).toContainText('符合歷史條件')
        await expect(area).toContainText('不是本次生成或品質保證')
        const records = area.locator('details')
        await expect(records).toHaveCount(2)
        await records.first().locator('summary').click()
        await expect(records.first()).toContainText('Pixel Art LoRA')
        await expect(records.first()).toContainText('品質觀察')
        await expect(records.first()).toContainText('9007199254740993')
        await records.nth(1).locator('summary').click()
        await expect(records.nth(1)).toContainText('18446744073709551615')
        await page.getByRole('button', { name: '上移 LoRA 2', exact: true }).click()
        await expect(records).toHaveCount(1)
        await records.first().locator('summary').click()
        await expect(records.first().locator('li').first()).toContainText('Pixel Art LoRA')
        await expect(records.first().locator('li').nth(1)).toContainText('LCM')
        await expect(records.first().getByRole('link')).toHaveAttribute(
          'href',
          /style-matrix-20261023\.md$/,
        )
        await records.first().screenshot({ path: info.outputPath('style-quality.png') })
        await page.getByLabel('LoRA 1 模型強度', { exact: true }).fill('0.5')
        await expect(area.getByRole('status')).toContainText('沒有匹配紀錄')
        await area.scrollIntoViewIfNeeded()
        await page.screenshot({ path: info.outputPath('style-history.png') })
        expect((await (await request.get('/qa/state')).json()).prompts).toBe(before.prompts)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        )
      } finally {
        await request.post('/qa/comparison-context/reset')
      }
    })
  })
}
