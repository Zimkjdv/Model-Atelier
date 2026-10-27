import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const routes = [
  'system',
  'settings',
  'models',
  'gallery',
  'assets',
  'experiments',
  'training',
  'studio/checkpoint',
  'studio/flux',
  'studio/inpaint',
  'studio/control',
  'studio/reference',
]

for (const [width, height] of [
  [1280, 800],
  [1440, 900],
  [1920, 1080],
] as const)
  test(`desktop redesign ${width}px: every route, real state and no automatic submissions`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    const before = (await (await request.get('/qa/state')).json()).prompts
    for (const route of routes) {
      await page.goto('/#/' + route)
      await expect(page.locator('.app-topbar h1')).toBeVisible()
      if (route.startsWith('studio/'))
        await expect(
          page.locator('.generation-submit .primary').filter({ visible: true }),
        ).toBeVisible()
      await expect(page.locator('h1')).toHaveCount(1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      expect(await page.locator('.rail').evaluate((el) => el.getBoundingClientRect().width)).toBe(
        72,
      )
      if (route.startsWith('studio/')) {
        expect(
          await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1),
        ).toBe(true)
        const button = await page
          .locator('.generation-submit .primary')
          .filter({ visible: true })
          .boundingBox()
        expect(button!.y + button!.height).toBeLessThanOrEqual(height)
      }
    }
    expect(errors).toEqual([])
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  })

test('workbench purposes, exact seed, cached forms and experiments navigation preserve state', async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/#/studio/checkpoint')
  await page.locator('#draft-prompt').fill('retain my live workbench prompt')
  await page.getByRole('button', { name: '圖片重繪', exact: true }).click()
  await expect(page.locator('#checkpoint-workflow')).toHaveValue('image2image')
  await page.getByRole('button', { name: '文字創作', exact: true }).click()
  await expect(page.locator('#checkpoint-workflow')).toHaveValue('text2image')
  await page.locator('.studio-advanced>summary').first().click()
  await page.locator('#seed').evaluate((el) => {
    let p = el.parentElement
    while (p) {
      if (p.tagName === 'DETAILS') (p as HTMLDetailsElement).open = true
      p = p.parentElement
    }
  })
  await page.locator('#seed').fill('18446744073709551615')
  await page.getByRole('button', { name: 'FLUX.1 [schnell]', exact: true }).click()
  await page.locator('#flux-prompt').fill('separate flux settings')
  await page.getByRole('navigation').getByRole('button', { name: '作品庫', exact: true }).click()
  await page.goBack()
  await expect(page.locator('#flux-prompt')).toHaveValue('separate flux settings')
  await page.getByRole('button', { name: 'Checkpoint／SDXL', exact: true }).click()
  await expect(page.locator('#draft-prompt')).toHaveValue('retain my live workbench prompt')
  await expect(page.locator('#seed')).toHaveValue('18446744073709551615')
  await page.getByRole('navigation').getByRole('button', { name: '實驗比較', exact: true }).click()
  await expect(page.locator('.experiments-workspace')).toBeVisible()
  await expect(page.locator('.generation-submit')).toBeHidden()
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '創作工作台', exact: true })
    .click()
  await expect(page.locator('#draft-prompt')).toHaveValue('retain my live workbench prompt')
  expect(errors).toEqual([])
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('system tabs, real capacity, keyboard focus and retained storage actions', async ({
  page,
}) => {
  await page.goto('/#/system')
  await expect(page.getByRole('status').filter({ hasText: '整體正常' })).toBeVisible()
  await page.getByRole('tab', { name: '主機與引擎', exact: true }).click()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: '儲存與目錄', exact: true })).toBeFocused()
  await expect(page.getByRole('region', { name: '目錄與磁碟容量', exact: true })).toBeVisible()
  await page.getByText(/查看 [0-9]+ 個目錄/).click()
  await expect(page.locator('.storage-directory code').first()).toBeVisible()
  expect(await page.locator('.storage-directory').first().innerText()).not.toMatch(
    /C: · 可讀|D: · 可讀/,
  )
  await expect(page.getByRole('button', { name: '管理額外模型目錄', exact: true })).toBeVisible()
  expect(await page.evaluate(() => location.hash)).toBe('#/system')
  await page.getByRole('button', { name: '管理額外模型目錄', exact: true }).click()
  await expect(page.getByRole('tab', { name: '模型路徑', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

test('connection test does not save; settings tabs keep pending input', async ({
  page,
  request,
}) => {
  const before = await (await request.get('/api/settings')).json()
  await page.goto('/#/settings')
  await page.locator('#url').fill('http://mock-engine.invalid:8189')
  await page.getByRole('button', { name: '測試（不保存）', exact: true }).click()
  await expect(page.locator('form.settings [role=status]')).not.toHaveText('')
  expect(await (await request.get('/api/settings')).json()).toEqual(before)
  await page.getByRole('tab', { name: '資料與隱私', exact: true }).click()
  await page.getByRole('tab', { name: '引擎連線', exact: true }).click()
  await expect(page.locator('#url')).toHaveValue('http://mock-engine.invalid:8189')
})

test('gallery layouts, selection, top-right archive and close, notes and read-only source', async ({
  page,
  request,
}) => {
  await request.post('/qa/artwork-set')
  await page.goto('/#/gallery')
  const first = page.locator('.artwork-card').first()
  await first.locator('.gallery-overlay.select').click()
  await expect(first.locator('.gallery-overlay.select')).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: '瀑布流', exact: true }).click()
  await expect(page.locator('.artwork-grid')).toHaveClass(/masonry/)
  await expect(first.locator('.gallery-overlay.select')).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: '固定', exact: true }).click()
  await first.locator('.artwork-cover').click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(
    dialog.locator('.preview-top-actions').getByRole('button', { name: '關閉', exact: true }),
  ).toBeVisible()
  await expect(
    dialog.locator('.preview-top-actions').getByRole('button', { name: /封存作品|還原作品/ }),
  ).toBeVisible()
  await dialog.locator('#artwork-notes').fill('new layout keeps the real note')
  await dialog.getByRole('button', { name: '保存筆記', exact: true }).click()
  await expect(dialog.getByText('筆記已保存。', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '關閉', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await page.getByRole('combobox', { name: '排序', exact: true }).selectOption('model')
  await expect(page.getByRole('combobox', { name: '排序', exact: true })).toHaveValue('model')
})

test('mask undo and redo preserve full-resolution pixels and saved PNG contract', async ({
  page,
  request,
}) => {
  await page.goto('/qa/state')
  const bytes = await page.evaluate(() => {
    const c = document.createElement('canvas')
    c.width = 640
    c.height = 800
    c.getContext('2d')!.fillRect(0, 0, 640, 800)
    return c.toDataURL('image/png').split(',')[1]!
  })
  const source = await (
    await request.post('/api/assets?filename=redesign-mask-source.png', {
      headers: { 'Content-Type': 'application/octet-stream' },
      data: Buffer.from(bytes, 'base64'),
    })
  ).json()
  await page.goto('/#/studio/inpaint')
  await page.locator('#inpaint-source').selectOption(source.id)
  const editor = page.getByRole('region', { name: '遮罩繪製', exact: true })
  await expect(editor.getByRole('button', { name: '筆刷', exact: true })).toBeEnabled()
  await editor.locator('summary').click()
  await editor.getByRole('button', { name: '中央區塊', exact: true }).click()
  const mask = editor.locator('canvas')
  const snapshot = () => mask.evaluate((c: HTMLCanvasElement) => c.toDataURL())
  const painted = await snapshot()
  await editor.getByRole('button', { name: '復原', exact: true }).click()
  await expect(editor.getByRole('button', { name: '重做', exact: true })).toBeEnabled()
  expect(await snapshot()).not.toBe(painted)
  await editor.getByRole('button', { name: '重做', exact: true }).click()
  await expect.poll(snapshot).toBe(painted)
  await editor.getByRole('button', { name: '保存遮罩', exact: true }).click()
  await expect(editor.getByRole('status')).toContainText('使用已保存遮罩')
  expect(await mask.evaluate((c: HTMLCanvasElement) => [c.width, c.height])).toEqual([640, 800])
})

test('training export step preserves live annotations and test images remain protected', async ({
  page,
  request,
}) => {
  const fixture = await (await request.post('/qa/training-review?count=125')).json()
  await page.goto('/#/training')
  await page.getByLabel('原圖來源目錄', { exact: true }).fill(fixture.source_root)
  await page.getByLabel('資料清單 JSON', { exact: true }).setInputFiles({
    name: 'dataset.json',
    mimeType: 'application/json',
    buffer: Buffer.from(fixture.manifest_json),
  })
  await page.getByRole('button', { name: '匯入待審查清單', exact: true }).click()
  await page.getByLabel('內容標註', { exact: true }).fill('preserved across export sub-step')
  await expect(page.getByRole('heading', { name: '資料出口檢查', exact: true })).toBeHidden()
  await page.getByRole('button', { name: '2 匯出資料包', exact: true }).click()
  await expect(page.getByRole('heading', { name: '資料出口檢查', exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
  ).toBeDisabled()
  await page.getByRole('button', { name: '1 審查資料', exact: true }).click()
  await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue(
    'preserved across export sub-step',
  )
  await expect(page.getByLabel('只顯示待補項目')).toBeChecked()
})

test('desktop automatic accessibility checks for all management panels', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  for (const route of routes) {
    await page.goto('/#/' + route)
    await expect(page.locator('.app-topbar h1')).toBeVisible()
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    expect(result.violations, route).toEqual([])
  }
})

test('model and asset handoff preserve live settings and never submit implicitly', async ({
  page,
  request,
}) => {
  await request.post('/qa/extended-models')
  const beforeCatalog = await (await request.get('/api/models')).json()
  const before = (await (await request.get('/qa/state')).json()).prompts
  try {
    await page.goto('/#/studio/checkpoint')
    await page.locator('#draft-prompt').fill('keep this when choosing a model')
    await page.getByRole('navigation').getByRole('button', { name: '模型庫', exact: true }).click()
    page.once('dialog', (d) => d.accept())
    await page
      .locator('.model-card')
      .filter({ has: page.getByRole('heading', { name: 'alternate.safetensors', exact: true }) })
      .getByRole('button', { name: '套用到創作', exact: true })
      .click()
    await expect(page.locator('#draft-model')).toHaveValue('alternate.safetensors')
    await expect(page.locator('#draft-prompt')).toHaveValue('keep this when choosing a model')
    expect((await (await request.get('/api/models')).json()).selected).toBe(beforeCatalog.selected)
    const source = (await (await request.get('/api/assets')).json()).find((a: any) => !a.archived)
    expect(source).toBeTruthy()
    const result = await request.put('/api/assets/' + source.id, {
      data: {
        title: source.title,
        purpose: 'composition',
        archived: false,
        revision: source.revision,
      },
    })
    expect(result.ok()).toBe(true)
    await page
      .getByRole('navigation')
      .getByRole('button', { name: '參考素材', exact: true })
      .click()
    await page
      .locator('.asset-card')
      .filter({ has: page.locator('a[href="/api/assets/' + source.id + '/image"]') })
      .getByRole('button', { name: '用於創作', exact: true })
      .click()
    await expect(page).toHaveURL(/#\/studio\/control$/)
    await expect(page.locator('#control-source')).toHaveValue(source.id)
    await page
      .getByRole('navigation')
      .getByRole('button', { name: '創作工作台', exact: true })
      .click()
    await page.getByRole('button', { name: '文字創作', exact: true }).click()
    await expect(page.locator('#draft-prompt')).toHaveValue('keep this when choosing a model')
    await expect(page.locator('#draft-model')).toHaveValue('alternate.safetensors')
    const currentSource = await (await request.get('/api/assets/' + source.id)).json()
    expect(
      (
        await request.put('/api/assets/' + source.id, {
          data: {
            title: currentSource.title,
            purpose: 'character',
            archived: false,
            revision: currentSource.revision,
          },
        })
      ).ok(),
    ).toBe(true)
    await page
      .getByRole('navigation')
      .getByRole('button', { name: '參考素材', exact: true })
      .click()
    await page
      .locator('.asset-card')
      .filter({ has: page.locator('a[href="/api/assets/' + source.id + '/image"]') })
      .getByRole('button', { name: '用於創作', exact: true })
      .click()
    await expect(page).toHaveURL(/#\/studio\/reference$/)
    await expect(page.locator('#reference-source')).toHaveValue(source.id)
    await page.locator('.studio-advanced > summary').click()
    await expect(page.locator('#reference-mode')).toHaveValue('character')

    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  } finally {
    await request.post('/qa/extended-models/reset')
  }
})

test('reference component metadata refreshes after an explicit save in the model library', async ({
  page,
}) => {
  await page.goto('/#/models')
  await page.getByRole('tab', { name: '元件', exact: true }).click()
  await page.getByRole('button', { name: '同步參考元件', exact: true }).click()
  await page.getByText('同步與登記參考元件', { exact: true }).click()
  const selector = page.locator('#reference-metadata-component')
  await expect(selector.locator('option')).not.toHaveCount(1)
  const key = (await selector.locator('option').nth(1).getAttribute('value'))!
  await selector.selectOption(key)
  await page.locator('#reference-metadata-version').fill('redesign metadata refresh')
  const refreshed = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === '/api/reference-components' && r.request().method() === 'GET',
  )
  await page.getByRole('button', { name: '保存參考元件登記', exact: true }).click()
  expect((await refreshed).ok()).toBe(true)
  await selector.selectOption('')
  await selector.selectOption(key)
  await expect(page.locator('#reference-metadata-version')).toHaveValue('redesign metadata refresh')
})
