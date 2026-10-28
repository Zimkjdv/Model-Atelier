import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import AxeBuilder from '@axe-core/playwright'

test.use({ viewport: { width: 1440, height: 900 } })
const selection = (page: Page) => page.getByRole('region', { name: '已選作品', exact: true })
const comparison = (page: Page) => page.getByRole('region', { name: '作品並排比較', exact: true })
const choose = (page: Page, title: string) =>
  page.getByRole('button', { name: '選取作品：' + title, exact: true }).click()
const compare = (page: Page) =>
  selection(page).getByRole('button', { name: '並排比較（2–4 張）', exact: true })
async function seed(page: Page, request: APIRequestContext) {
  const response = await request.post('/qa/artwork-set')
  expect(response.ok()).toBe(true)
  const data = await response.json()
  await page.goto('/#/gallery')
  await page.getByLabel('搜尋作品', { exact: true }).fill(data.group)
  await expect(page.locator('.artwork-card')).toHaveCount(5)
  return data.items as { id: string; title: string; revision: number; sha256: string }[]
}
test.beforeEach(async ({ request }, info) => {
  info.annotations.push({
    type: 'prompts',
    description: String((await (await request.get('/qa/state')).json()).prompts),
  })
})
test.afterEach(async ({ request }, info) => {
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(
    Number(info.annotations.find((a) => a.type === 'prompts')!.description),
  )
})

test('selection strip precedes explicit comparison; history, filters and unsaved scores remain safe', async ({
  page,
  request,
}, info) => {
  const items = await seed(page, request)
  await choose(page, items[0].title)
  await expect(selection(page)).toContainText('已選 1 件')
  await expect(compare(page)).toBeDisabled()
  await expect(comparison(page)).toHaveCount(0)
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
  ).toEqual([])
  await choose(page, items[1].title)
  await expect(compare(page)).toBeEnabled()
  await expect(page).toHaveURL(/#\/gallery$/)
  await expect(comparison(page)).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('selection-strip.png'), fullPage: true })
  await compare(page).click()
  await expect(page).toHaveURL(/#\/gallery\/compare$/)
  await expect(page.locator('.app-topbar h1')).toHaveText('作品比較')
  await expect(comparison(page)).toContainText('作品比較 · 2 / 4')
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
  ).toEqual([])
  await expect(page.locator('.artwork-grid')).not.toBeVisible()
  await comparison(page)
    .getByRole('button', { name: '預覽及評分：' + items[0].title, exact: true })
    .click()
  await page.getByLabel('作品筆記', { exact: true }).fill('keep pending comparison note')
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.goBack()
  await expect(page).toHaveURL(/#\/gallery\/compare$/)
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(
    'keep pending comparison note',
  )
  page.once('dialog', (dialog) => dialog.accept())
  await page.goBack()
  await expect(page).toHaveURL(/#\/gallery$/)
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(selection(page)).toContainText('已選 2 件')
  await expect(page.locator('.artwork-card')).toHaveCount(5)
  await page.goForward()
  await expect(comparison(page)).toBeVisible()
  await page.screenshot({ path: info.outputPath('comparison-page.png'), fullPage: true })
  await page.getByRole('button', { name: '返回作品庫', exact: true }).click()
  await expect(selection(page)).toBeVisible()
  await selection(page).getByRole('button', { name: '清除選取', exact: true }).click()
  await expect(selection(page)).toHaveCount(0)
  await page.goBack()
  await expect(page.getByRole('status').filter({ hasText: '尚未選取作品' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('status').filter({ hasText: '尚未選取作品' })).toBeVisible()
  await expect(comparison(page)).toHaveCount(0)
})

test('five items are available for batch management; comparison keeps the 2–4 limit', async ({
  page,
  request,
}) => {
  const items = await seed(page, request)
  for (const item of items) await choose(page, item.title)
  await expect(selection(page)).toContainText('已選 5 件')
  await expect(compare(page)).toBeDisabled()
  await expect(selection(page).getByRole('button', { name: '批次封存', exact: true })).toBeEnabled()
  await choose(page, items[4].title)
  await compare(page).click()
  await expect(comparison(page)).toContainText('作品比較 · 4 / 4')
  await comparison(page)
    .getByRole('button', { name: '移出比較：' + items[1].title, exact: true })
    .click()
  await expect(comparison(page)).toContainText('作品比較 · 3 / 4')
  await page.getByRole('button', { name: '返回作品庫', exact: true }).click()
  await expect(selection(page)).toContainText('已選 3 件')
  await expect(
    page.getByRole('button', { name: '選取作品：' + items[1].title, exact: true }),
  ).toHaveAttribute('aria-pressed', 'false')
})

test('batch original ZIP is downloadable, then archive and restore preserve originals and settings', async ({
  page,
  request,
}, info) => {
  const items = (await seed(page, request)).slice(0, 2)
  const originals = await Promise.all(
    items.map(async (item) => (await request.get('/api/artworks/' + item.id)).json()),
  )
  for (const item of items) await choose(page, item.title)
  const download = page.waitForEvent('download')
  await selection(page).getByRole('button', { name: '批次下載原圖（2 張）', exact: true }).click()
  const file = await download
  expect(file.suggestedFilename()).toBe('model-atelier-artworks.zip')
  const path = info.outputPath(file.suggestedFilename())
  await file.saveAs(path)
  expect((await readFile(path)).subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 3, 4]))
  await expect(selection(page)).toContainText('已選 2 件')
  await selection(page).getByRole('button', { name: '批次封存', exact: true }).click()
  await expect(selection(page)).toHaveCount(0)
  await expect(page.locator('.artwork-card')).toHaveCount(3)
  await page.getByRole('button', { name: '已封存', exact: true }).click()
  await expect(page.locator('.artwork-card')).toHaveCount(2)
  for (const item of items) await choose(page, item.title)
  await selection(page).getByRole('button', { name: '批次還原', exact: true }).click()
  await expect(selection(page)).toHaveCount(0)
  await expect(page.locator('.artwork-card')).toHaveCount(0)
  for (const [index, item] of items.entries()) {
    const updated = await (await request.get('/api/artworks/' + item.id)).json()
    expect(updated.archived).toBe(false)
    expect(updated.revision).toBe(originals[index].revision + 2)
    expect(updated.sha256).toBe(originals[index].sha256)
    expect(updated.parameters).toEqual(originals[index].parameters)
  }
})

test('partial conflict keeps failed selection and remote notes; explicit reload permits a deliberate retry', async ({
  page,
  request,
}) => {
  const items = (await seed(page, request)).slice(0, 2)
  for (const item of items) await choose(page, item.title)
  const remote = await request.patch(`/api/artworks/${items[1].id}/organization`, {
    data: { revision: 0, notes: 'another window' },
  })
  expect(remote.ok()).toBe(true)
  await selection(page).getByRole('button', { name: '批次封存', exact: true }).click()
  await expect(selection(page)).toContainText('已選 1 件')
  await expect(page.getByRole('alert')).toContainText(items[1].title)
  const updated = await (await request.get('/api/artworks/' + items[1].id)).json()
  expect(updated.archived).toBe(false)
  expect(updated.notes).toBe('another window')
  await page.getByRole('button', { name: '重新讀取選取狀態', exact: true }).click()
  await expect(page.getByRole('button', { name: '重新讀取選取狀態', exact: true })).toHaveCount(0)
  await selection(page).getByRole('button', { name: '批次封存', exact: true }).click()
  await expect(selection(page)).toHaveCount(0)
  expect((await (await request.get('/api/artworks/' + items[1].id)).json()).notes).toBe(
    'another window',
  )
})

test('uncertain save stops the batch without retry; cancel only stops subsequent writes', async ({
  page,
  request,
}) => {
  const items = (await seed(page, request)).slice(0, 3)
  for (const item of items) await choose(page, item.title)
  const attempts: string[] = []
  await page.route('**/api/artworks/*/organization', async (route) => {
    attempts.push(route.request().url())
    await route.abort('failed')
  })
  await selection(page).getByRole('button', { name: '批次封存', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('結果尚未確認')
  expect(attempts).toHaveLength(1)
  await expect(selection(page)).toContainText('已選 3 件')
  await page.unroute('**/api/artworks/*/organization')
  await page.getByRole('button', { name: '重新讀取選取狀態', exact: true }).click()
  await expect(selection(page).getByRole('button', { name: '批次封存', exact: true })).toBeEnabled()
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(`**/api/artworks/${items[0].id}/organization`, async (route) => {
    await gate
    await route.continue()
  })
  await selection(page).getByRole('button', { name: '批次封存', exact: true }).click()
  await selection(page).getByRole('button', { name: '停止後續操作', exact: true }).click()
  release()
  await expect(selection(page)).toContainText('已選 2 件')
  for (const [index, item] of items.entries())
    expect((await (await request.get('/api/artworks/' + item.id)).json()).archived).toBe(
      index === 0,
    )
})

test('failed ZIP retains selection and reports a readable error without automatic retry', async ({
  page,
  request,
}) => {
  const items = (await seed(page, request)).slice(0, 2)
  for (const item of items) await choose(page, item.title)
  let attempts = 0
  await page.route('**/api/artwork-downloads', async (route) => {
    attempts++
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '原圖遺失，未產生 ZIP' }),
    })
  })
  await selection(page).getByRole('button', { name: '批次下載原圖（2 張）', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('原圖遺失，未產生 ZIP')
  await expect(selection(page)).toContainText('已選 2 件')
  expect(attempts).toBe(1)
})
