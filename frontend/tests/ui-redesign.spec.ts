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
  await page.locator('.architecture-switch > summary').click()
  await page.getByRole('button', { name: 'FLUX.1 [schnell]', exact: true }).click()
  await page.locator('#flux-prompt').fill('separate flux settings')
  await page.getByRole('navigation').getByRole('button', { name: '作品庫', exact: true }).click()
  await page.goBack()
  await expect(page.locator('#flux-prompt')).toHaveValue('separate flux settings')
  await page.locator('.architecture-switch > summary').click()
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

test('engine testing and saving show distinct progress and protect the selected address', async ({
  page,
  request,
}) => {
  const before = await (await request.get('/api/settings')).json()
  const candidate = 'http://mock-engine.invalid:8189'
  const operations: string[] = []
  page.on('request', (value) => {
    const path = new URL(value.url()).pathname
    if (value.method() === 'POST' && path === '/api/engine/test') operations.push('test')
    if (value.method() === 'PUT' && path === '/api/settings') operations.push('save')
  })
  let releaseTest!: () => void
  let releaseSave!: () => void
  const testGate = new Promise<void>((resolve) => (releaseTest = resolve))
  const saveGate = new Promise<void>((resolve) => (releaseSave = resolve))
  await page.route(
    '**/api/engine/test',
    async (route) => {
      await testGate
      await route.fulfill({ json: { connected: true, url: candidate } })
    },
    { times: 1 },
  )
  await page.route('**/api/settings', async (route) => {
    if (route.request().method() === 'PUT') await saveGate
    await route.continue()
  })
  await page.goto('/#/settings')
  const form = page.locator('form.settings')
  const address = form.getByLabel('引擎位址', { exact: true })
  const status = form.getByRole('status')
  const testButton = form.getByRole('button', { name: '測試（不保存）', exact: true })
  const saveButton = form.getByRole('button', { name: '保存並套用', exact: true })
  await expect(address).toHaveValue(before.comfy_url)
  await address.fill(candidate)
  try {
    const tested = page.waitForRequest('**/api/engine/test')
    await testButton.click()
    expect((await tested).postDataJSON()).toEqual({ comfy_url: candidate })
    const testing = form.getByRole('button', { name: '測試中…', exact: true })
    await expect(testing).toBeDisabled()
    await expect(saveButton).toBeDisabled()
    await expect(address).toBeDisabled()
    await expect(status).toHaveText(`正在測試 ${candidate} 的連線…`)
    await testing.dispatchEvent('click')
    await form.dispatchEvent('submit')
    expect(await (await request.get('/api/settings')).json()).toEqual(before)
    expect(operations).toEqual(['test'])
    releaseTest()
    await expect(status).toHaveText(`測試連線成功，${candidate} 可連線（尚未保存）。`)

    await page.route('**/api/engine/test', (route) =>
      route.fulfill({ json: { connected: false, url: candidate, error: '模擬引擎離線。' } }),
    )
    await testButton.click()
    await expect(status).toHaveText(`測試 ${candidate} 的連線失敗。模擬引擎離線。`)
    expect(operations).toEqual(['test', 'test'])
    expect(await (await request.get('/api/settings')).json()).toEqual(before)
    await page.getByRole('tab', { name: '資料與隱私', exact: true }).click()
    await page.getByRole('tab', { name: '引擎連線', exact: true }).click()
    await expect(address).toHaveValue(candidate)

    await address.fill(candidate + '/')
    const saved = page.waitForRequest(
      (value) => value.url().endsWith('/api/settings') && value.method() === 'PUT',
    )
    await saveButton.click()
    expect((await saved).postDataJSON()).toEqual({ comfy_url: candidate + '/' })
    await expect(form.getByRole('button', { name: '保存中…', exact: true })).toBeDisabled()
    await expect(testButton).toBeDisabled()
    await expect(address).toBeDisabled()
    await expect(status).toHaveText(`正在保存並套用 ${candidate}/…`)
    await testButton.dispatchEvent('click')
    await form.dispatchEvent('submit')
    expect(await (await request.get('/api/settings')).json()).toEqual(before)
    expect(operations).toEqual(['test', 'test', 'save'])
    releaseSave()
    await expect(status).toHaveText(`設定已保存，已套用 ${candidate}。`)
    await expect(address).toHaveValue(candidate)
    await expect(saveButton).toBeEnabled()
    expect(await (await request.get('/api/settings')).json()).toEqual({ comfy_url: candidate })
    expect(operations).toEqual(['test', 'test', 'save'])
  } finally {
    await page.close()
    releaseTest()
    releaseSave()
    expect((await request.put('/api/settings', { data: before })).ok()).toBeTruthy()
  }
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
  await page.getByRole('button', { name: '生成結果', exact: true }).click()
  await expect(mask).toBeHidden()
  await page.getByRole('button', { name: '遮罩編輯', exact: true }).click()
  await expect.poll(snapshot).toBe(painted)
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
  await page.locator('.training-dataset-management > summary').click()
  await page.getByLabel('原圖來源目錄', { exact: true }).fill(fixture.source_root)
  await page.getByLabel('資料清單 JSON', { exact: true }).setInputFiles({
    name: 'dataset.json',
    mimeType: 'application/json',
    buffer: Buffer.from(fixture.manifest_json),
  })
  await page.getByRole('button', { name: '匯入待審查清單', exact: true }).click()
  await page.getByLabel('內容標註', { exact: true }).fill('preserved across export sub-step')
  await expect(page.getByRole('heading', { name: '匯出資料包', exact: true })).toBeHidden()
  await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
  await expect(page.getByRole('heading', { name: '匯出資料包', exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
  ).toBeDisabled()
  await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
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
      .filter({ has: page.locator('[data-asset-cover="' + source.id + '"]') })
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
    await page.locator('[data-asset-cover="' + source.id + '"]').click()
    await page.getByRole('dialog').getByRole('button', { name: '用於創作', exact: true }).click()
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
  await page.getByRole('button', { name: '同步元件清單', exact: true }).click()
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

test('display preferences survive reload and reset without touching drafts or pending requests', async ({
  page,
}) => {
  const legacyKey = 'atelier-studio-display-v1'
  const pendingKey = 'atelier-pending-submission'
  const pending =
    '{"request_id":"00000000-0000-4000-8000-000000000001","seed":"18446744073709551615"}'
  await page.goto('/#/system')
  await page.evaluate(
    ({ legacyKey, pendingKey, pending }) => {
      localStorage.setItem(legacyKey, JSON.stringify({ advanced: true, references: false }))
      localStorage.setItem(pendingKey, pending)
    },
    { legacyKey, pendingKey, pending },
  )
  await page.goto('/#/studio/checkpoint')
  await page.reload()
  await expect(page.locator('#seed').locator('xpath=ancestor::details[1]')).toHaveAttribute(
    'open',
    '',
  )
  const nav = page.getByRole('navigation', { name: '主要導覽' })
  await nav.getByRole('button', { name: '模型庫' }).click()
  const models = page.getByRole('group', { name: '模型排版' })
  await models.getByRole('button', { name: '卡片' }).click()
  await nav.getByRole('button', { name: '作品庫' }).click()
  const artworks = page.getByRole('group', { name: '作品排版' })
  await artworks.getByRole('button', { name: '瀑布流' }).click()
  await page.reload()
  await expect(artworks.getByRole('button', { name: '瀑布流' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await nav.getByRole('button', { name: '模型庫' }).click()
  await expect(models.getByRole('button', { name: '卡片' })).toHaveAttribute('aria-pressed', 'true')
  await nav.getByRole('button', { name: '設定' }).click()
  await page.getByRole('tab', { name: '外觀與語言' }).click()
  await page.getByRole('button', { name: '重設顯示偏好' }).click()
  await expect(page.getByText('已恢復預設排版與區塊展開狀態。')).toBeVisible()
  await nav.getByRole('button', { name: '模型庫' }).click()
  await expect(models.getByRole('button', { name: '清單' })).toHaveAttribute('aria-pressed', 'true')
  await nav.getByRole('button', { name: '作品庫' }).click()
  await expect(artworks.getByRole('button', { name: '固定' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(await page.evaluate((key) => localStorage.getItem(key), pendingKey)).toBe(pending)
})

test('unknown display preference version falls back without overwriting storage', async ({
  page,
}) => {
  const key = 'atelier-display-preferences-v2'
  const invalid = '{"version":999,"models":"cards"}'
  await page.goto('/#/system')
  await page.evaluate(({ key, invalid }) => localStorage.setItem(key, invalid), { key, invalid })
  await page.goto('/#/models')
  await page.reload()
  await expect(
    page.getByRole('group', { name: '模型排版' }).getByRole('button', { name: '清單' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('無法讀取顯示偏好，已使用預設排版。')).toBeVisible()
  expect(await page.evaluate((key) => localStorage.getItem(key), key)).toBe(invalid)
})

for (const width of [1440, 390]) {
  test(`${width}px: global tasks show progress across pages and locate the original job`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    const before = (await (await request.get('/qa/state')).json()).prompts
    await request.post('/qa/engine/uncertain')
    await page.goto('/#/studio/checkpoint')
    await page.locator('#draft-model').selectOption('demo.safetensors')
    await page.locator('#draft-prompt').fill('A test landscape')
    const response = page.waitForResponse(
      (value) => value.url().endsWith('/api/generate') && value.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '生成圖片', exact: true }).click()
    const submitted = await response
    expect(submitted.ok()).toBeTruthy()
    const job = await submitted.json()
    const id = job.id
    const liveRequests: string[] = []
    await page.route('**/api/jobs/*/events', async (route) => {
      if (
        !route
          .request()
          .url()
          .endsWith('/' + id + '/events')
      )
        return route.continue()
      liveRequests.push(id)
      const update = {
        ...job,
        status: 'running',
        revision: 100000,
        progress: { node: 'KSampler', percent: 40, updated_at: '2099-01-01T00:00:00Z' },
      }
      await route.fulfill({
        contentType: 'text/event-stream',
        body: 'event: job\ndata: ' + JSON.stringify({ job: update }) + '\n\n',
      })
    })
    await page.getByRole('navigation').getByRole('button', { name: '作品庫' }).click()
    const trigger = page.getByRole('button', { name: /任務抽屜/ })
    await trigger.click()
    const drawer = page.getByRole('dialog', { name: '生成任務' })
    const entry = drawer.locator('[data-task-id="' + id + '"]')
    await expect(entry).toContainText('http://mock-engine.invalid:8188')
    await expect(entry.getByRole('progressbar')).toHaveAttribute('value', '40')
    expect(liveRequests.length).toBeGreaterThan(0)
    expect(
      await drawer.evaluate((element) => {
        const bounds = element.getBoundingClientRect()
        return (
          bounds.left >= 0 &&
          bounds.right <= innerWidth &&
          element.scrollWidth <= element.clientWidth
        )
      }),
    ).toBe(true)
    await page.keyboard.press('Escape')
    await expect(drawer).toBeHidden()
    await expect(trigger).toBeFocused()
    await trigger.click()
    await entry.getByRole('button', { name: '前往原任務' }).click()
    await expect(drawer).toBeHidden()
    await expect(page).toHaveURL(/#\/studio\/checkpoint$/)
    await expect(page.locator('.job').filter({ hasText: id })).toBeFocused()
    await expect(page.locator('#draft-prompt')).toHaveValue('A test landscape')
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 1)
  })
}
