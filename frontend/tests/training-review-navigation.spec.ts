import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

for (const width of [1440, 1280]) {
  test(`saved review issues navigate past 200 without altering annotations at ${width}px`, async ({
    page,
    request,
  }) => {
    const fixture = await (await request.post('/qa/training-review?count=125')).json()
    let writes = 0,
      finalPreviews = 0
    page.on('request', (req) => {
      const path = new URL(req.url()).pathname
      if (path.startsWith('/api/training/') && ['PUT', 'PATCH'].includes(req.method())) writes++
      if (path.includes('/images/img-0125')) finalPreviews++
    })
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
    await expect(
      page.getByRole('status').filter({ hasText: '已匯入待審查資料；原圖與原清單未修改。' }),
    ).toBeVisible()
    await page.getByLabel('只顯示待補項目', { exact: true }).uncheck()
    await page.locator('.review-navigation-details > summary').click()
    await page.getByText(/^符合篩選的圖片缺項（/).click()
    await expect(
      page.getByRole('status').filter({ hasText: '篩選結果 125 / 125 張' }),
    ).toBeVisible()
    await page.getByLabel('內容標註', { exact: true }).fill('unsaved first image')
    await page.getByLabel('搜尋圖片', { exact: true }).fill('img-0121')
    await page.getByLabel('篩選圖片用途', { exact: true }).selectOption('train')
    await page.getByLabel('缺項篩選', { exact: true }).selectOption('caption_review_required')
    await expect(page.getByRole('status').filter({ hasText: '篩選結果 1 / 125 張' })).toBeVisible()
    await page
      .getByRole('button', { name: '定位 img-0121：內容標註尚未完成審查', exact: true })
      .click()
    await expect(page.getByText('第 7 / 7 頁圖片', { exact: true })).toBeVisible()
    await expect(page.locator('#training-image-editor')).toBeFocused()
    await expect(page.getByRole('img', { name: '審查原圖 img-0121', exact: true })).toBeVisible()
    await page.getByLabel('內容標註', { exact: true }).fill('unsaved later image')
    await expect(
      page.getByRole('button', { name: '定位 img-0121：內容標註尚未完成審查', exact: true }),
    ).toHaveCount(0) // later issue page, never truncated away
    await page.getByRole('button', { name: '下一張有阻擋缺項', exact: true }).click()
    await expect(page.getByRole('img', { name: '審查原圖 img-0122', exact: true })).toBeVisible()
    await page.getByLabel('搜尋圖片', { exact: true }).fill('does-not-exist')
    await expect(
      page.getByText('沒有符合條件的圖片；可清除篩選。已選圖片與未保存編輯仍保留。', {
        exact: true,
      }),
    ).toBeVisible()
    await page.getByRole('button', { name: '清除圖片篩選', exact: true }).click()
    for (let i = 0; i < 4; i++)
      await page.getByRole('button', { name: '下一頁缺項', exact: true }).click()
    await expect(page.getByText('第 5 / 5 頁缺項', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '定位 img-0124：來源用途尚未記錄', exact: true }).click()
    await expect(page.getByRole('img', { name: '審查原圖 img-0124', exact: true })).toBeVisible()
    await page.getByLabel('搜尋圖片', { exact: true }).fill('img-0125')
    await page.getByRole('button', { name: 'img-0125 · test', exact: true }).click()
    await expect(
      page.getByText('最終評估圖保留不預覽，避免在資料審查階段提前曝光。', { exact: true }),
    ).toBeVisible()
    await expect(page.getByLabel('內容標註', { exact: true })).toBeDisabled()
    expect(finalPreviews).toBe(0)
    await page.getByLabel('搜尋圖片', { exact: true }).fill('img-0121')
    await page.getByRole('button', { name: 'img-0121 · train', exact: true }).click()
    await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue('unsaved later image')
    await page.getByLabel('搜尋圖片', { exact: true }).fill('img-0001')
    await page.getByRole('button', { name: 'img-0001 · train', exact: true }).click()
    await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue('unsaved first image')
    expect(writes).toBe(0)
    await page.getByRole('button', { name: '2 匯出資料包', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
    ).toBeDisabled()
    const accessibility = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze()
    expect(accessibility.violations).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
