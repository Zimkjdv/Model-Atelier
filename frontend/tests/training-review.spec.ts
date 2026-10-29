import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

for (const width of [1440, 390]) {
  test(`human review, version conflicts and train-only export at ${width}px`, async ({
    page,
    request,
  }) => {
    const fixture = await (await request.post('/qa/training-review')).json()
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/training')
    await page.locator('.training-dataset-management > summary').click()
    await page.getByLabel('原圖來源目錄', { exact: true }).fill(fixture.source_root)
    await page.getByLabel('資料清單 JSON', { exact: true }).setInputFiles({
      name: 'dataset.json',
      mimeType: 'application/json',
      buffer: Buffer.from(fixture.manifest_json),
    })
    await page.getByRole('button', { name: '匯入待審查清單', exact: true }).click()
    await expect(page.getByRole('img', { name: '審查原圖 img-0001' })).toBeVisible()
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await expect(page.getByText('仍有待審查項目', { exact: true })).toBeVisible()
    await expect(
      page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
    ).toBeDisabled()
    await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
    await page.locator('.review-extra-fields > summary').click()
    await page.getByLabel('內容標註', { exact: true }).fill('flat red geometric illustration')
    await page.getByLabel('標註狀態', { exact: true }).selectOption('approved')
    await page.getByLabel('標註審查人', { exact: true }).fill('synthetic reviewer')
    await page.getByLabel('訓練用途紀錄', { exact: true }).selectOption('recorded')
    await page
      .getByLabel('來源用途依據', { exact: true })
      .fill('Self-authored fixture; no artist image.')
    await page.getByLabel('來源審查人', { exact: true }).fill('synthetic reviewer')
    page.once('dialog', (dialog) => dialog.dismiss())
    await page.getByRole('button', { name: '設定', exact: true }).click()
    await expect(page).toHaveURL(/#\/training$/)
    await page.locator('.training-version-management > summary').click()
    await page.getByRole('button', { name: '保存新版本', exact: true }).click()
    await expect(page.getByText('已保存 · 修訂 2', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await expect(page.getByText('資料出口檢查通過', { exact: true })).toBeVisible()
    await page.locator('.training-export-details > summary').click()
    await expect(
      page.locator('.training-export-details').getByText(/缺少獨立最終評估圖/),
    ).toBeVisible()
    let exports = 0
    await page.route('**/api/training/datasets/*/exports', async (route) => {
      exports++
      await route.fetch()
      await route.abort('failed')
    })
    await page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await page.getByRole('button', { name: '查回原匯出結果', exact: true }).click()
    await expect(page.getByText(/匯出狀態：completed/)).toBeVisible()
    expect(exports).toBe(1)
    const list = (await (await request.get('/api/training/datasets')).json()).datasets
    const item = list.find((v: { id: string }) => page.url().includes(v.id)) || list[0]
    const old = await (await request.get(`/api/training/datasets/${item.id}?revision=1`)).json()
    expect(old.dataset.images[0].caption.status).toBe('pending')
    await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
    await page.getByLabel('內容標註', { exact: true }).fill('keep local edit')
    await page.route('**/api/training/datasets/*', async (route) => {
      if (route.request().method() === 'PUT')
        await route.fulfill({ status: 409, json: { detail: '資料已在其他視窗更新' } })
      else await route.continue()
    })
    await page.getByRole('button', { name: '保存新版本', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('資料已在其他視窗更新')
    await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue('keep local edit')
    const accessibility = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze()
    expect(accessibility.violations).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
