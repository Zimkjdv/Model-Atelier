import { test, expect, type APIRequestContext, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.use({ viewport: { width: 1440, height: 900 } })

async function seed(page: Page, request: APIRequestContext) {
  const result = await (await request.post('/qa/artwork-set')).json()
  await page.goto('/#/gallery')
  await page.getByLabel('搜尋作品', { exact: true }).fill(result.group)
  await expect(page.locator('.artwork-card')).toHaveCount(5)
  const listing = await (
    await request.get('/api/library/artworks?limit=12&q=' + result.group)
  ).json()
  return listing.items.map((item: any) => result.items.find((record: any) => record.id === item.id))
}

for (const viewport of [
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
]) {
  test(`${viewport.width}: consistent cards, hover tooltips and bounded detail panes`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize(viewport)
    const records = await seed(page, request)
    const longTitle = 'ModelAtelier_' + 'a-long-original-image-filename_'.repeat(6) + '.png'
    const longModel = 'a-very-long-checkpoint-model-filename-'.repeat(5) + '.safetensors'
    await page.route('**/api/library/artworks?**', async (route) => {
      const body = await (await route.fetch()).json()
      body.items = body.items.map((item: any, index: number) => ({
        ...item,
        title: index === 0 ? longTitle : item.title,
        checkpoint: index === 0 ? longModel : item.checkpoint,
      }))
      await route.fulfill({ json: body })
    })
    await page.route('**/api/artworks/' + records[0].id, async (route) => {
      const body = await (await route.fetch()).json()
      await route.fulfill({ json: { ...body, title: longTitle, checkpoint: longModel } })
    })
    await page.getByRole('button', { name: '重新整理', exact: true }).click()
    const cards = page.locator('.artwork-card')
    const first = cards.first()
    await expect(first.getByRole('heading', { name: longTitle, exact: true })).toBeVisible()
    const heights = await cards.evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().height),
    )
    expect(Math.max(...heights) - Math.min(...heights)).toBeLessThan(1)
    await expect(cards.locator('details')).toHaveCount(0)
    await expect(first.getByRole('button', { name: '查看詳情：' + longTitle })).toBeVisible()
    const name = first.locator('h2 .overflow-text')
    expect(await name.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
    await name.hover()
    const tooltip = page.getByRole('tooltip')
    await expect(tooltip).toHaveText(longTitle)
    await tooltip.hover()
    await expect(tooltip).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(tooltip).not.toBeVisible()
    await first.locator('.gallery-model-name .overflow-text').focus()
    await expect(tooltip).toHaveText(longModel)
    await page.keyboard.press('Escape')
    await name.focus()
    await expect(tooltip).toHaveText(longTitle)
    await page.keyboard.press('Escape')
    await page.screenshot({ path: info.outputPath('cards.png') })

    await first.locator('.artwork-cover').click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('img')).toHaveJSProperty('complete', true)
    const frame = await dialog.boundingBox()
    expect(frame!.x).toBeGreaterThanOrEqual(0)
    expect(frame!.y).toBeGreaterThanOrEqual(0)
    expect(frame!.x + frame!.width).toBeLessThanOrEqual(viewport.width)
    expect(frame!.y + frame!.height).toBeLessThanOrEqual(viewport.height)
    await dialog.locator('h2 .overflow-text').focus()
    await expect(tooltip).toHaveText(longTitle)
    await page.keyboard.press('Escape')
    await expect(dialog).toBeVisible()
    const imageBefore = await dialog.locator('.preview-image').boundingBox()
    const tabs = dialog.getByRole('tablist', { name: '作品詳情分類' })
    await tabs.getByRole('tab', { name: '作品與筆記', exact: true }).focus()
    await page.keyboard.press('ArrowRight')
    await expect(tabs.getByRole('tab', { name: '人工評分', exact: true })).toBeFocused()
    await expect(page.getByLabel('提示服從', { exact: true })).toBeVisible()
    await page.keyboard.press('End')
    await expect(tabs.getByRole('tab', { name: '生成與來源', exact: true })).toBeFocused()
    await expect(dialog.getByRole('link', { name: '下載完整工作流程' })).toBeVisible()
    await expect(dialog.locator('.lora-snapshot > summary')).toContainText('提交時 LoRA 資料')
    await dialog.getByText('作品來源紀錄', { exact: true }).click()
    await dialog.locator('.artwork-detail-scroll').evaluate((element) => {
      element.scrollTop = element.scrollHeight
    })
    expect(
      await dialog.locator('.artwork-detail-scroll').evaluate((e) => e.scrollTop),
    ).toBeGreaterThan(0)
    expect(await dialog.locator('.preview-image').boundingBox()).toEqual(imageBefore)
    await expect(dialog.getByRole('button', { name: '關閉', exact: true })).toBeInViewport()
    await expect(dialog.getByRole('button', { name: '載入創作設定 →' })).toBeInViewport()
    expect(await dialog.evaluate((e) => e.scrollWidth <= e.clientWidth + 1)).toBe(true)
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
    ).toEqual([])
    await page.screenshot({ path: info.outputPath('sources.png') })
    await tabs.getByRole('tab', { name: '作品與筆記', exact: true }).click()
    await page.screenshot({ path: info.outputPath('notes.png') })
    await tabs.getByRole('tab', { name: '人工評分', exact: true }).click()
    await page.screenshot({ path: info.outputPath('ratings.png') })
    await dialog.getByRole('button', { name: '關閉', exact: true }).click()
    await expect(dialog).not.toBeVisible()
    await expect(first.locator('.artwork-cover')).toBeFocused()
  })
}

test('tabs preserve unsaved drafts, failed saves and archive safeguards; saved data and originals survive', async ({
  page,
  request,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  const [item] = await seed(page, request)
  const original = await (await request.get(`/api/artworks/${item.id}/image`)).body()
  const workflow = await (await request.get(`/api/artworks/${item.id}/workflow`)).body()
  await page
    .locator('.artwork-card')
    .first()
    .getByRole('button', { name: /^查看詳情：/ })
    .click()
  const dialog = page.getByRole('dialog')
  const tabs = dialog.getByRole('tablist')
  const note = 'A note preserved while switching detail tabs'
  await page.getByLabel('作品筆記', { exact: true }).fill(note)
  await tabs.getByRole('tab', { name: '人工評分', exact: true }).click()
  await page.getByLabel('提示服從', { exact: true }).selectOption('4')
  await expect(dialog.getByRole('button', { name: '封存作品', exact: true })).toBeDisabled()
  await tabs.getByRole('tab', { name: '生成與來源', exact: true }).click()
  page.once('dialog', (confirmation) => confirmation.dismiss())
  await page.keyboard.press('Escape')
  await expect(dialog).toBeVisible()
  await tabs.getByRole('tab', { name: '作品與筆記', exact: true }).click()
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(note)
  await tabs.getByRole('tab', { name: '人工評分', exact: true }).click()
  const organization = '**/api/artworks/' + item.id + '/organization'
  await page.route(organization, (route) =>
    route.fulfill({ status: 409, json: { detail: '版本已更新' } }),
  )
  await dialog.getByRole('button', { name: '保存評分', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('版本已更新')
  await expect(page.getByLabel('提示服從', { exact: true })).toHaveValue('4')
  await page.unroute(organization)
  await dialog.getByRole('button', { name: '保存評分', exact: true }).click()
  await expect(dialog.getByRole('status')).toHaveText('評分已保存。')
  await tabs.getByRole('tab', { name: '作品與筆記', exact: true }).click()
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(note)
  await dialog.getByRole('button', { name: '保存筆記', exact: true }).click()
  await expect(dialog.getByRole('status')).toHaveText('筆記已保存。')
  await dialog.getByRole('button', { name: '封存作品', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '還原作品', exact: true })).toBeEnabled()
  await dialog.getByRole('button', { name: '還原作品', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '封存作品', exact: true })).toBeEnabled()
  await page.evaluate(() => {
    const dialog = document.querySelector('dialog[open]')!
    const close = Array.from(dialog.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === '關閉',
    )!
    close.click()
    document.querySelector<HTMLButtonElement>('.artwork-card .artwork-cover')!.click()
  })
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(note)
  await tabs.getByRole('tab', { name: '人工評分', exact: true }).click()
  await expect(page.getByLabel('提示服從', { exact: true })).toHaveValue('4')
  const saved = await (await request.get('/api/artworks/' + item.id)).json()
  expect(saved.notes).toBe(note)
  expect(saved.ratings.prompt_adherence).toBe(4)
  expect(saved.archived).toBe(false)
  expect(saved.parameters).toEqual(item.parameters)
  expect(await (await request.get(`/api/artworks/${item.id}/image`)).body()).toEqual(original)
  expect(await (await request.get(`/api/artworks/${item.id}/workflow`)).body()).toEqual(workflow)
  await dialog.getByRole('button', { name: '關閉', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await page.locator('.artwork-card').first().locator('.artwork-cover').click()
  await expect(dialog.getByRole('img')).toBeVisible()
  expect(errors.filter((error) => !error.includes('409 (Conflict)'))).toEqual([])
})

test('missing original keeps parameters and organization available without a broken download', async ({
  page,
  request,
}) => {
  const [item] = await seed(page, request)
  await page.route('**/api/artworks/' + item.id + '/image', (route) =>
    route.fulfill({ status: 404 }),
  )
  await page.locator('.artwork-card').first().locator('.artwork-cover').click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('原圖無法讀取，請重新整理作品庫或從備份還原。')).toBeVisible()
  await expect(dialog.getByRole('link', { name: '下載原圖 ↓', exact: true })).toHaveCount(0)
  await dialog.getByRole('tab', { name: '生成與來源', exact: true }).click()
  await expect(dialog.getByText(item.parameters.prompt, { exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '載入創作設定 →', exact: true })).toBeEnabled()
})
