import { test, expect } from '@playwright/test'

for (const width of [390, 768, 1000, 1001]) {
  test(`review image, navigation and editor remain usable at ${width}px`, async ({
    page,
    request,
  }, info) => {
    const fixture = await (await request.post('/qa/training-review?count=6')).json()
    await page.setViewportSize({ width, height: 1000 })
    let finalPreviews = 0
    page.on('request', (request) => {
      if (request.url().includes('/images/img-0006')) finalPreviews++
    })
    await page.goto('/#/training')
    await page.locator('.training-dataset-management > summary').click()
    await page.getByLabel('原圖來源目錄', { exact: true }).fill(fixture.source_root)
    await page.getByLabel('資料清單 JSON', { exact: true }).setInputFiles({
      name: 'dataset.json',
      mimeType: 'application/json',
      buffer: Buffer.from(fixture.manifest_json),
    })
    const imported = page.waitForResponse(
      (response) =>
        response.url().endsWith('/api/training/datasets') && response.request().method() === 'POST',
    )
    const importButton = page.getByRole('button', { name: '匯入待審查清單', exact: true })
    await importButton.click()
    const response = await imported
    expect(response.ok()).toBe(true)
    const dataset = await response.json()
    const image = page.getByRole('img', { name: '審查原圖 img-0001', exact: true })
    // Earlier datasets can have the same image ID; measure this import, not an old preview.
    await expect(image).toHaveAttribute(
      'src',
      `/api/training/datasets/${dataset.id}/images/img-0001?revision=1`,
    )
    await expect(page.getByRole('button', { name: '更新資料集清單', exact: true })).toBeEnabled()
    await expect(image).toBeVisible()
    await expect(image).toHaveJSProperty('complete', true)
    await expect
      .poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth))
      .toBeGreaterThan(0)
    const bounds = {
      navigation: (await page.getByRole('region', { name: '圖片與缺項導覽' }).boundingBox())!,
      image: (await image.boundingBox())!,
      source: (await page.locator('.training-source-image').boundingBox())!,
      editor: (await page.locator('.training-image-form').boundingBox())!,
    }
    expect(bounds.image.width).toBeGreaterThanOrEqual(200)
    expect(bounds.image.height).toBeGreaterThanOrEqual(200)
    if (width <= 1000) {
      expect(bounds.source.y).toBeGreaterThanOrEqual(bounds.navigation.y + bounds.navigation.height)
      expect(bounds.editor.y).toBeGreaterThanOrEqual(bounds.source.y + bounds.source.height)
    } else {
      expect(bounds.source.x).toBeGreaterThanOrEqual(bounds.navigation.x + bounds.navigation.width)
      expect(bounds.editor.x).toBeGreaterThanOrEqual(bounds.source.x + bounds.source.width)
    }
    await info.attach('layout.json', {
      body: JSON.stringify(bounds),
      contentType: 'application/json',
    })
    await image.scrollIntoViewIfNeeded()
    await expect(image).toBeInViewport({ ratio: 0.9 })
    await page.screenshot({ path: info.outputPath('review-image.png') })

    await page.getByLabel('只顯示待補項目', { exact: true }).uncheck()
    await page.getByRole('button', { name: 'img-0006 · test', exact: true }).click()
    await expect(
      page.getByText('最終評估圖保留不預覽，避免在資料審查階段提前曝光。', { exact: true }),
    ).toBeVisible()
    await expect(page.getByLabel('內容標註', { exact: true })).toBeDisabled()
    await expect(page.locator('.training-source-image img')).toHaveCount(0)
    expect(finalPreviews).toBe(0)
    await page.getByRole('button', { name: 'img-0001 · train', exact: true }).click()
    await page.getByLabel('內容標註', { exact: true }).fill('Retain narrow-window edit')
    await page.locator('.review-navigation-details > summary').click()
    await page.getByLabel('搜尋圖片', { exact: true }).fill('no-such-image')
    await expect(
      page.getByText('沒有符合條件的圖片；可清除篩選。已選圖片與未保存編輯仍保留。', {
        exact: true,
      }),
    ).toBeVisible()
    await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue(
      'Retain narrow-window edit',
    )
    await page.locator('.review-extra-fields > summary').click()
    await page.locator('.training-version-management > summary').click()
    await expect(page.getByRole('button', { name: '保存新版本', exact: true })).toBeEnabled()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
    ).toBeDisabled()
    await expect(
      page.getByRole('status').filter({ hasText: '有未保存變更，保存後重新檢查才能匯出' }),
    ).toBeVisible()
  })
}
