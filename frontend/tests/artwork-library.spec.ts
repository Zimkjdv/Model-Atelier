import { createHash } from 'node:crypto'
import { writeFile } from 'node:fs/promises'
import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
  type TestInfo,
} from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })
const dialog = (page: Page) => page.getByRole('dialog')
const comparison = (page: Page) => page.getByRole('region', { name: '作品並排比較', exact: true })
const card = (page: Page, item: any) =>
  page
    .locator('.artwork-card')
    .filter({ has: page.getByRole('heading', { name: item.title, exact: true }) })
const detail = async (request: APIRequestContext, id: string) =>
  (await request.get('/api/artworks/' + id)).json()
const digest = (value: Buffer) => createHash('sha256').update(value).digest('hex')

async function evidence(
  info: TestInfo,
  name: string,
  value: string | Buffer,
  contentType = 'application/json',
) {
  const path = info.outputPath(name)
  await writeFile(path, value)
  await info.attach(name, { path, contentType })
}

async function seed(page: Page, request: APIRequestContext) {
  const response = await request.post('/qa/artwork-set')
  expect(response.ok()).toBe(true)
  const data = await response.json()
  await page.goto('/#/system')
  expect(await page.evaluate(() => innerWidth)).toBe(390)
  await page.getByRole('button', { name: '作品庫', exact: true }).click()
  await page.getByLabel('搜尋作品', { exact: true }).fill(data.group)
  await expect(page.locator('.artwork-card')).toHaveCount(5)
  return data
}

async function open(page: Page, item: any) {
  await card(page, item)
    .getByRole('button', { name: '查看作品 ' + item.title, exact: true })
    .click()
  await expect(dialog(page)).toBeVisible()
  await expect(dialog(page).getByRole('img', { name: item.title, exact: true })).toHaveJSProperty(
    'naturalWidth',
    item.width,
  )
}

async function decision(
  page: Page,
  action: () => Promise<unknown>,
  accept = false,
  type = 'confirm',
) {
  const warning = page.waitForEvent('dialog')
  const doing = action()
  const value = await warning
  expect(value.type()).toBe(type)
  if (accept) await value.accept()
  else await value.dismiss()
  await doing
}

async function cancelReload(page: Page) {
  await decision(
    page,
    () => page.reload({ timeout: 2500 }).catch(() => null),
    false,
    'beforeunload',
  )
}

async function save(page: Page, id: string, button: Locator) {
  const result = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === `/api/artworks/${id}/organization` &&
      response.request().method() === 'PATCH',
  )
  await button.click()
  const response = await result
  return {
    status: response.status(),
    body: response.request().postDataJSON(),
    value: await response.json(),
  }
}

async function close(page: Page) {
  await dialog(page).getByRole('button', { name: '關閉', exact: true }).click()
  await expect(dialog(page)).not.toBeVisible()
}

async function scores(page: Page, values: (number | null)[]) {
  if (!(await page.locator('#rating-prompt_adherence').isVisible()))
    await dialog(page).getByText('生成設定、人工評分與完整來源', { exact: true }).click()
  for (const [index, key] of [
    'prompt_adherence',
    'character_consistency',
    'visual_style',
    'composition',
  ].entries()) {
    await page
      .locator('#rating-' + key)
      .selectOption(values[index] === null ? { label: '未評分／不適用' } : String(values[index]))
  }
}

test('390px organize: filters, favorite, notes, archive, restore and immutable originals', async ({
  page,
  request,
}, info) => {
  const { group, items } = await seed(page, request)
  const item = items[0]
  const original = await (await request.get(`/api/artworks/${item.id}/image`)).body()
  const workflow = await (await request.get(`/api/artworks/${item.id}/workflow`)).body()
  const favorite = await save(
    page,
    item.id,
    card(page, item).getByRole('button', { name: '收藏作品：' + item.title, exact: true }),
  )
  expect(favorite.status).toBe(200)
  await expect(
    card(page, item).getByRole('button', { name: '取消收藏：' + item.title, exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await page.getByLabel('只看收藏', { exact: true }).check()
  await expect(page.locator('.artwork-card')).toHaveCount(1)
  await open(page, item)
  const note = group + ' saved observation'
  await page.getByLabel('作品筆記', { exact: true }).fill(note)
  const notes = await save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存筆記', exact: true }),
  )
  expect(notes.body).toEqual({ revision: favorite.value.revision, notes: note })
  await expect(dialog(page).getByRole('status').filter({ hasText: '筆記已保存' })).toBeVisible()
  await close(page)
  await page.getByLabel('搜尋作品', { exact: true }).fill(note)
  await page.getByLabel('模型篩選', { exact: true }).fill(item.checkpoint)
  await expect(page.locator('.artwork-card')).toHaveCount(1)
  await page.getByLabel('模型篩選', { exact: true }).fill(items[1].checkpoint)
  await expect(page.locator('.artwork-card')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('empty-filter.png'), fullPage: true })
  await expect(
    page.getByText('調整搜尋、模型或收藏篩選；封存作品可在「已封存」中還原。', { exact: true }),
  ).toBeVisible()
  await page.getByLabel('模型篩選', { exact: true }).fill('')
  await expect(page.locator('.artwork-card')).toHaveCount(1)
  const archived = await save(
    page,
    item.id,
    card(page, item).getByRole('button', { name: '封存作品：' + item.title, exact: true }),
  )
  expect(archived.value.archived).toBe(true)
  await page.getByRole('button', { name: '重新整理', exact: true }).click()
  await expect(page.locator('.artwork-card')).toHaveCount(0)
  await page.locator('#artwork-scope').selectOption('archived')
  await expect(page.locator('.artwork-card')).toHaveCount(1)
  const restored = await save(
    page,
    item.id,
    card(page, item).getByRole('button', { name: '還原作品：' + item.title, exact: true }),
  )
  expect(restored.value.archived).toBe(false)
  await page.locator('#artwork-scope').selectOption('active')
  await expect(page.locator('.artwork-card')).toHaveCount(1)
  await page.reload()
  await page.getByLabel('搜尋作品', { exact: true }).fill(note)
  await expect(card(page, item)).toBeVisible()
  await open(page, item)
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(note)
  await expect(dialog(page).getByText('作品清單讀取中，完成後即可保存。')).not.toBeVisible()
  await page.screenshot({ path: info.outputPath('organization.png') })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  )
  const final = await detail(request, item.id)
  expect([final.favorite, final.archived, final.notes]).toEqual([true, false, note])
  expect(final.parameters).toEqual(item.parameters)
  expect(await (await request.get(`/api/artworks/${item.id}/workflow`)).body()).toEqual(workflow)
  expect(await (await request.get(`/api/artworks/${item.id}/image`)).body()).toEqual(original)
  expect(digest(original)).toBe(final.sha256)
  await evidence(
    info,
    'organization.json',
    JSON.stringify({ before: item, favorite, notes, archived, restored, final }, null, 2),
  )
  await evidence(info, 'original.png', original, 'image/png')
  await evidence(info, 'workflow.json', workflow)
})

test('390px unsaved notes and ratings protect close, Escape, reload, window and history', async ({
  page,
  request,
}, info) => {
  const { items } = await seed(page, request)
  const item = items[0]
  await open(page, item)
  await page.getByLabel('作品筆記', { exact: true }).fill('keep this unsaved note')
  await scores(page, [4, null, 2, 5])
  await decision(page, () =>
    dialog(page).getByRole('button', { name: '關閉', exact: true }).click(),
  )
  await decision(page, () => page.keyboard.press('Escape'))
  await decision(page, () =>
    dialog(page).getByRole('button', { name: '載入創作設定 →', exact: true }).click(),
  )
  await cancelReload(page)
  await decision(page, () => page.close({ runBeforeUnload: true }), false, 'beforeunload')
  expect(page.isClosed()).toBe(false)
  await decision(page, () => page.goBack())
  await expect(page).toHaveURL(/#\/gallery$/)
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue('keep this unsaved note')
  await expect(page.locator('#rating-prompt_adherence')).toHaveValue('4')
  await page.screenshot({ path: info.outputPath('unsaved.png') })
  await decision(
    page,
    () => dialog(page).getByRole('button', { name: '關閉', exact: true }).click(),
    true,
  )
  await expect(dialog(page)).not.toBeVisible()
  await open(page, item)
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue('')
  await expect(page.locator('#rating-prompt_adherence')).toHaveJSProperty('selectedIndex', 0)
  await page.getByLabel('作品筆記', { exact: true }).fill('discard on accepted history navigation')
  await decision(page, () => page.goBack(), true)
  await expect(page).toHaveURL(/#\/system$/)
  await page.goForward()
  await expect(page).toHaveURL(/#\/gallery$/)
  const final = await detail(request, item.id)
  expect(final.notes).toBe('')
  expect(Object.values(final.ratings)).toEqual([null, null, null, null])
  expect(final.revision).toBe(0)
  await evidence(info, 'unsaved.json', JSON.stringify(final, null, 2))
})

test('390px original images: parameter differences, keyboard scroll and four-item selection', async ({
  page,
  request,
}, info) => {
  const { group, items } = await seed(page, request)
  for (const item of items.slice(0, 2))
    await card(page, item)
      .getByRole('button', { name: '選取作品：' + item.title, exact: true })
      .click()
  await page.getByRole('button', { name: '並排比較（2–4 張）', exact: true }).click()
  const compare = comparison(page)
  await expect(compare).toContainText('作品比較 · 2 / 4')
  const images = compare.locator('.comparison-images img')
  await expect(images).toHaveCount(2)
  for (const [index, item] of items.slice(0, 2).entries()) {
    await expect(images.nth(index)).toHaveAttribute('src', `/api/artworks/${item.id}/image`)
    await expect(images.nth(index)).toHaveJSProperty('naturalWidth', item.width)
    await expect(images.nth(index)).toHaveJSProperty('naturalHeight', item.height)
    expect(await images.nth(index).evaluate((image) => getComputedStyle(image).objectFit)).toBe(
      'contain',
    )
    const bytes = await (await request.get(`/api/artworks/${item.id}/image`)).body()
    expect(digest(bytes)).toBe(item.sha256)
    await evidence(info, 'compared-' + index + '.png', bytes, 'image/png')
  }
  const row = (label: string) =>
    compare
      .locator('tbody tr')
      .filter({ has: page.locator('th').filter({ hasText: new RegExp('^' + label + '$') }) })
  await expect(row('Seed（不同）').getByRole('cell')).toHaveText([
    '18446744073709551615',
    '18446744073709551614',
  ])
  await expect(row('Steps（不同）').getByRole('cell')).toHaveText(['12', '16'])
  await expect(row('輸出尺寸（不同）').getByRole('cell')).toHaveText(['128 × 64', '64 × 128'])
  await expect(row('Sampler').getByRole('cell')).toHaveText(['euler', 'euler'])
  const loras = await row('有序 LoRA／強度（不同）').getByRole('cell').allTextContents()
  expect(loras[0]!.indexOf('fixture-alpha')).toBeLessThan(loras[0]!.indexOf('fixture-beta'))
  expect(loras[1]!.indexOf('fixture-beta')).toBeLessThan(loras[1]!.indexOf('fixture-alpha'))
  expect(loras[0]).toContain('model 0.5 / CLIP 1')
  await row('Seed（不同）').scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('comparison-parameters.png') })
  const scroller = compare.locator('.comparison-scroll')
  await expect(scroller).toHaveAttribute('tabindex', '0')
  await compare.getByRole('button', { name: '清空比較選擇', exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(scroller).toBeFocused()
  await scroller.press('ArrowRight')
  await expect.poll(() => scroller.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
  await page.getByRole('button', { name: '返回作品庫', exact: true }).click()
  await page.getByLabel('搜尋作品', { exact: true }).fill(group + '-no-match')
  await expect(page.locator('.artwork-card')).toHaveCount(0)
  await expect(page.getByRole('region', { name: '已選作品', exact: true })).toContainText(
    '已選 2 件',
  )
  await page.getByLabel('搜尋作品', { exact: true }).fill(group)
  await expect(page.locator('.artwork-card')).toHaveCount(5)
  for (const item of items.slice(2, 4))
    await card(page, item)
      .getByRole('button', { name: '選取作品：' + item.title, exact: true })
      .click()
  await page.getByRole('button', { name: '並排比較（2–4 張）', exact: true }).click()
  await expect(compare).toContainText('作品比較 · 4 / 4')
  await scroller.hover({ position: { x: 30, y: 30 } })
  await page.mouse.wheel(1800, 0)
  await expect.poll(() => scroller.evaluate((element) => element.scrollLeft)).toBeGreaterThan(400)
  await page.screenshot({ path: info.outputPath('comparison-scrolled.png') })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  )
  await compare.getByRole('button', { name: '移出比較：' + items[1].title, exact: true }).click()
  await expect(compare).toContainText('作品比較 · 3 / 4')
  await page.getByRole('button', { name: '返回作品庫', exact: true }).click()
  await expect(
    card(page, items[4]).getByRole('button', { name: '選取作品：' + items[4].title, exact: true }),
  ).toBeEnabled()
  await page.getByRole('button', { name: '清除選取', exact: true }).click()
  await expect(compare).not.toBeVisible()
  await expect(
    page.locator('.artwork-card button[aria-label^="選取作品："][aria-pressed="true"]'),
  ).toHaveCount(0)
  await evidence(info, 'comparison.json', JSON.stringify({ items, loras }, null, 2))
})

test('390px two tabs: notes and ratings conflict, explicit reload and save keep both drafts safe', async ({
  page,
  request,
}, info) => {
  const { group, items } = await seed(page, request)
  const item = items[0]
  for (const entry of items.slice(0, 2))
    await card(page, entry)
      .getByRole('button', { name: '選取作品：' + entry.title, exact: true })
      .click()
  await page.getByRole('button', { name: '並排比較（2–4 張）', exact: true }).click()
  await comparison(page)
    .getByRole('button', { name: '預覽及評分：' + item.title, exact: true })
    .click()
  await expect(dialog(page)).toBeVisible()
  await page.getByLabel('作品筆記', { exact: true }).fill('local notes retained with ratings')
  await scores(page, [5, null, 2, 4])
  const other = await page.context().newPage()
  await other.goto('/#/gallery')
  await expect(other.getByRole('button', { name: '重新整理', exact: true })).toBeEnabled()
  let releaseRead!: () => void
  const reading = new Promise<void>((resolve) => {
    releaseRead = resolve
  })
  const filteredRead = other.waitForRequest(
    (request) =>
      new URL(request.url()).pathname === '/api/library/artworks' &&
      new URL(request.url()).searchParams.get('q') === group,
  )
  await other.route('**/api/library/artworks?**', async (route) => {
    await reading
    await route.continue()
  })
  await other.getByLabel('搜尋作品', { exact: true }).fill(group)
  await filteredRead
  await open(other, item)
  await other.getByLabel('作品筆記', { exact: true }).fill('saved by another tab')
  await scores(other, [1, 3, null, 2])
  await expect(dialog(other).getByRole('button', { name: '保存筆記', exact: true })).toBeDisabled()
  await expect(dialog(other).getByRole('button', { name: '保存評分', exact: true })).toBeDisabled()
  await expect(dialog(other).getByRole('status')).toHaveText('作品清單讀取中，完成後即可保存。')
  releaseRead()
  await expect(dialog(other).getByRole('button', { name: '保存筆記', exact: true })).toBeEnabled()
  await other.unroute('**/api/library/artworks?**')
  await save(other, item.id, dialog(other).getByRole('button', { name: '保存筆記', exact: true }))
  const remote = await save(
    other,
    item.id,
    dialog(other).getByRole('button', { name: '保存評分', exact: true }),
  )
  await expect(dialog(other).getByRole('status').filter({ hasText: '評分已保存' })).toBeVisible()
  await page.bringToFront()
  const conflict = await save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存評分', exact: true }),
  )
  expect(conflict.status).toBe(409)
  const notesConflict = await save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存筆記', exact: true }),
  )
  expect(notesConflict.status).toBe(409)
  await expect(dialog(page).getByRole('alert')).toContainText('另一個視窗')
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(
    'local notes retained with ratings',
  )
  await expect(page.locator('#rating-visual_style')).toHaveValue('2')
  await page.screenshot({ path: info.outputPath('rating-conflict.png') })
  await decision(page, () =>
    dialog(page).getByRole('button', { name: '重新讀取筆記', exact: true }).click(),
  )
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(
    'local notes retained with ratings',
  )
  expect((await detail(request, item.id)).ratings).toEqual(remote.value.ratings)
  await decision(
    page,
    () => dialog(page).getByRole('button', { name: '重新讀取筆記', exact: true }).click(),
    true,
  )
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue('saved by another tab')
  await expect(page.locator('#rating-character_consistency')).toHaveValue('3')
  await page.getByLabel('作品筆記', { exact: true }).fill('confirmed local rationale')
  await scores(page, [5, null, 2, 4])
  const ratings = await save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存評分', exact: true }),
  )
  expect(ratings.status).toBe(200)
  expect(ratings.body.revision).toBe(remote.value.revision)
  expect(ratings.value.notes).toBe('saved by another tab')
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(
    'confirmed local rationale',
  )
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(`**/api/artworks/${item.id}/organization`, async (route) => {
    await gate
    await route.continue()
  })
  const saving = save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存筆記', exact: true }),
  )
  await expect(dialog(page).getByRole('button', { name: '關閉', exact: true })).toBeDisabled()
  await expect(dialog(page).getByRole('button', { name: '保存評分', exact: true })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog(page)).toBeVisible()
  await cancelReload(page)
  release()
  const notes = await saving
  expect(notes.body).toEqual({
    revision: ratings.value.revision,
    notes: 'confirmed local rationale',
  })
  await expect(dialog(page).getByRole('status').filter({ hasText: '筆記已保存' })).toBeVisible()
  await close(page)
  const compared = comparison(page)
    .locator('article')
    .filter({ has: page.getByRole('heading', { name: item.title, exact: true }) })
  await expect(compared.locator('dd')).toHaveText(['5 / 5', '未評分／不適用', '2 / 5', '4 / 5'])
  await page.reload()
  await page.getByRole('button', { name: '返回作品庫', exact: true }).click()
  await page.getByLabel('搜尋作品', { exact: true }).fill(group)
  await open(page, item)
  await page.getByText('生成設定、人工評分與完整來源', { exact: true }).click()
  await expect(page.locator('#rating-composition')).toHaveValue('4')
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(
    'confirmed local rationale',
  )
  await expect(dialog(page).getByText('作品清單讀取中，完成後即可保存。')).not.toBeVisible()
  await page.locator('#rating-composition').scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('saved-ratings.png') })
  const final = await detail(request, item.id)
  expect(final.parameters).toEqual(item.parameters)
  expect(final.sha256).toBe(item.sha256)
  await evidence(
    info,
    'rating-revisions.json',
    JSON.stringify(
      { before: item, remote, conflict, notesConflict, ratings, notes, final },
      null,
      2,
    ),
  )
  await other.close()
})

test('390px failed saves retain notes and scores without retries', async ({
  page,
  request,
}, info) => {
  await page.clock.install()
  const { items } = await seed(page, request)
  const item = items[0]
  await open(page, item)
  await page.getByLabel('作品筆記', { exact: true }).fill('retained after failure')
  await scores(page, [3, null, 4, 1])
  let attempts = 0
  await page.route(`**/api/artworks/${item.id}/organization`, async (route) => {
    attempts++
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'fixture organization failure' }),
    })
  })
  const failed = await save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存評分', exact: true }),
  )
  expect(failed.status).toBe(503)
  await expect(dialog(page).getByRole('alert')).toContainText('fixture organization failure')
  await page.clock.fastForward(16000)
  expect(attempts).toBe(1)
  expect((await detail(request, item.id)).revision).toBe(0)
  await expect(page.locator('#rating-visual_style')).toHaveValue('4')
  await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue('retained after failure')
  await page.screenshot({ path: info.outputPath('save-failure.png') })
  await cancelReload(page)
  await page.unroute(`**/api/artworks/${item.id}/organization`)
  const ratings = await save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存評分', exact: true }),
  )
  expect(ratings.status).toBe(200)
  const notes = await save(
    page,
    item.id,
    dialog(page).getByRole('button', { name: '保存筆記', exact: true }),
  )
  expect(notes.status).toBe(200)
  await expect(dialog(page).getByRole('status').filter({ hasText: '筆記已保存' })).toBeVisible()
  const final = await detail(request, item.id)
  expect(final.notes).toBe('retained after failure')
  expect(final.ratings).toEqual({
    prompt_adherence: 3,
    character_consistency: null,
    visual_style: 4,
    composition: 1,
  })
  await evidence(
    info,
    'failed-save.json',
    JSON.stringify({ failed, ratings, notes, final }, null, 2),
  )
})

test.beforeEach(async ({ request }, info) => {
  const before = await (await request.get('/qa/state')).json()
  info.annotations.push({ type: 'engine-prompts-before', description: String(before.prompts) })
})
test.afterEach(async ({ request }, info) => {
  const before = info.annotations.find(
    (entry) => entry.type === 'engine-prompts-before',
  )!.description
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(Number(before))
})
