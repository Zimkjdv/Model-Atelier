import AxeBuilder from '@axe-core/playwright'
import { writeFile } from 'node:fs/promises'
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test'

const routes = [
  ['system', '系統資訊'],
  ['settings', '設定'],
  ['models', '模型庫'],
  ['gallery', '作品庫'],
  ['assets', '參考素材'],
  ['studio/checkpoint', '創作工作台'],
  ['studio/flux', '創作工作台'],
  ['studio/inpaint', '創作工作台'],
  ['studio/control', '創作工作台'],
  ['studio/reference', '創作工作台'],
] as const

async function keyboardFocus(control: Locator) {
  await control.focus()
  await expect(control).toBeFocused()
  expect(
    await control.evaluate((element) => {
      const style = getComputedStyle(element)
      return { width: style.outlineWidth, style: style.outlineStyle }
    }),
  ).toEqual({ width: '2px', style: 'solid' })
}

async function enter(control: Locator) {
  await keyboardFocus(control)
  await control.press('Enter')
}

async function openDetails(page: Page) {
  // Exercise the native keyboard disclosure rather than setting the DOM's open property.
  const modal = page.getByRole('dialog')
  const root = (await modal.isVisible()) ? modal : page
  const closed = root.locator('details:visible:not([open]) > summary')
  while (await closed.count()) await enter(closed.first())
}

async function capture(page: Page, info: TestInfo, name: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  )
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'])
    .analyze()
  // axe cannot determine all gradient backgrounds. Check the opaque RGB stops used by
  // this theme separately; retain other incomplete findings for visual review.
  const gradientChecks = []
  for (const node of result.incomplete.find((rule) => rule.id === 'color-contrast')?.nodes ?? []) {
    if (node.target.length !== 1 || typeof node.target[0] !== 'string') continue
    const colors = await page.locator(node.target[0]).evaluate((element) => {
      if (element.closest('[aria-hidden="true"]')) return null
      const foreground = getComputedStyle(element)
      for (let parent: Element | null = element; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent)
        if (style.backgroundImage !== 'none')
          return {
            foreground: foreground.color,
            size: Number.parseFloat(foreground.fontSize),
            bold: Number.parseInt(foreground.fontWeight) >= 700,
            background: style.backgroundImage,
          }
        if (style.backgroundColor !== 'rgba(0, 0, 0, 0)') return null
      }
      return null
    })
    if (!colors) continue
    const rgb = (value: string) =>
      value
        .match(/\d+(?:\.\d+)?/g)!
        .slice(0, 3)
        .map(Number)
    const luminance = (channels: number[]) =>
      channels
        .map((value) => {
          const linear = value / 255
          return linear <= 0.04045 ? linear / 12.92 : ((linear + 0.055) / 1.055) ** 2.4
        })
        .reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index]!, 0)
    const light = luminance(rgb(colors.foreground))
    const stops = colors.background.match(/rgb\([^)]+\)/g)
    expect(stops, 'Theme gradient must have opaque RGB stops').not.toBeNull()
    const ratios = stops!.map((stop) => {
      const dark = luminance(rgb(stop))
      return (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05)
    })
    const minimum = colors.size >= 24 || (colors.bold && colors.size >= 18.667) ? 3 : 4.5
    gradientChecks.push({ target: node.target, ...colors, ratios, minimum })
    expect(Math.min(...ratios), JSON.stringify(gradientChecks.at(-1))).toBeGreaterThanOrEqual(
      minimum,
    )
  }
  const report = info.outputPath(name + '.json')
  await writeFile(
    report,
    JSON.stringify(
      {
        viewport: page.viewportSize(),
        url: page.url(),
        tool: result.testEngine,
        violations: result.violations,
        incomplete: result.incomplete,
        passedRules: result.passes.map((rule) => rule.id),
        gradientChecks,
      },
      null,
      2,
    ),
  )
  await info.attach(name + '.json', { path: report, contentType: 'application/json' })
  const screenshot = info.outputPath(name + '.png')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: screenshot, fullPage: true })
  await info.attach(name + '.png', { path: screenshot, contentType: 'image/png' })
  expect(result.violations, JSON.stringify(result.violations, null, 2)).toEqual([])
  expect(result.incomplete.filter((rule) => rule.id !== 'color-contrast')).toEqual([])
}

for (const [route, title] of routes)
  test(`all-page accessibility: ${route}`, async ({ page, request }, info) => {
    const before = (await (await request.get('/qa/state')).json()).prompts
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 })
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const navigation = await page.goto('/#/' + route)
      if (!navigation) await page.reload()
      await page.waitForLoadState('networkidle')
      await expect(page.getByRole('heading', { level: 1, name: title, exact: true })).toBeVisible()
      await expect(page.locator('main')).toBeFocused()
      await expect(page).toHaveTitle(title + ' · Model Atelier')
      await expect(
        page
          .getByRole('navigation', { name: '主要導覽' })
          .getByRole('button', { name: title, exact: true }),
      ).toHaveAttribute('aria-current', 'page')
      const brand = page.locator('a.brand')
      await expect(brand).toBeVisible()
      await expect(brand).toHaveAccessibleName(
        width === 1440 ? /Model Atelier.*個人 AI 創作工作台/ : '系統資訊',
      )
      await enter(page.getByRole('link', { name: '跳至主要內容' }))
      await expect(page.locator('main')).toBeFocused()
      await expect(page).toHaveURL(new RegExp('#/' + route + '$'))
      // Follow the actual Tab order from main, including focus-driven scrolling.
      for (let index = 0; index < 8; index++) {
        await page.keyboard.press('Tab')
        const focused = page.locator(':focus')
        // Tabbing beyond the last control may move into browser chrome.
        if (!(await focused.count())) break
        await expect(focused).toBeVisible()
        expect(
          await focused.evaluate((element) => {
            const rect = element.getBoundingClientRect(),
              style = getComputedStyle(element)
            return (
              rect.bottom > 0 &&
              rect.top < innerHeight &&
              style.outlineWidth === '2px' &&
              style.outlineStyle === 'solid'
            )
          }),
        ).toBe(true)
      }
      await openDetails(page)
      expect(
        await page.locator('main').evaluate((element) => getComputedStyle(element).scrollBehavior),
      ).toBe('auto')
      await capture(page, info, `expanded-${width}`)
    }
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  })

for (const width of [1440, 390]) {
  test(`${width}px: hardware cards, device status and stale/offline warnings`, async ({
    page,
    request,
  }, info) => {
    const engine = await (await request.get('/api/engine')).json()
    const memory = { total: 16 * 1024 ** 3, used: 4 * 1024 ** 3, free: 12 * 1024 ** 3 }
    const device = {
      name: 'V06 synthetic GPU',
      type: 'cuda',
      index: 0,
      vram: memory,
      torch_vram: memory,
    }
    const platform = {
      host: 'V06 fixture host',
      os: 'Fixture OS',
      python: '3.12 fixture',
      updated_at: '2026-10-23T00:00:00Z',
      gpus: [
        {
          ...memory,
          index: '0',
          name: 'NVIDIA GeForce V06 synthetic GPU',
          driver: 'fixture driver',
        },
      ],
      gpu_error: null,
      ram: memory,
      disk: { ...memory, path: 'C:/V06/isolated-data' },
    }
    const local = await (await request.get('/api/local-environment')).json()
    let unavailable = false
    await page.route('**/api/system', (route) =>
      unavailable
        ? route.fulfill({ status: 503, json: { detail: 'V06 platform unavailable' } })
        : route.fulfill({ json: platform }),
    )
    await page.route('**/api/engine', (route) =>
      route.fulfill({
        json: {
          ...engine,
          connected: !unavailable,
          error: unavailable ? 'V06：引擎離線，請檢查連線。' : '',
          diagnostics: {
            ...engine.diagnostics,
            status: unavailable ? 'offline' : 'available',
            devices: unavailable ? [] : [device],
          },
          execution_device: {
            ...engine.execution_device,
            status: unavailable ? 'unavailable' : 'available',
            device: { type: 'cuda', index: 0 },
          },
        },
      }),
    )
    await page.route('**/api/local-environment', (route) =>
      route.fulfill({
        json: {
          ...local,
          status: 'available',
          devices: [device],
          system: { ...local.system, cuda_available: false },
          warnings: ['V06：本機 CUDA 不可用；與遠端執行裝置分開顯示。'],
        },
      }),
    )
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/system')
    await page.waitForLoadState('networkidle')
    await expect(
      page.getByRole('heading', { name: 'V06 synthetic GPU', exact: true }),
    ).toBeVisible()
    await expect(page.getByRole('status').filter({ hasText: '已取得設定的執行裝置' })).toBeVisible()
    await expect(
      page.getByRole('status').filter({ hasText: '此 Python 環境回報 CUDA 不可用' }),
    ).toBeVisible()
    await openDetails(page)
    await capture(page, info, 'hardware-devices')
    unavailable = true
    await enter(page.getByRole('button', { name: '↻ 重新整理', exact: true }))
    await expect(page.getByRole('alert')).toContainText('平台硬體資訊更新失敗')
    await expect(page.getByRole('status').filter({ hasText: '目前執行裝置不可用' })).toBeVisible()
    await expect(page.getByText('V06 fixture host', { exact: true })).toBeVisible()
    await expect(page.getByRole('status').filter({ hasText: 'V06：引擎離線' })).toBeVisible()
    await capture(page, info, 'hardware-stale-offline')
  })

  test(`${width}px: catalog editors, validation and horizontal table keyboard`, async ({
    page,
    request,
  }, info) => {
    const prepared = await request.post('/qa/comparison-context')
    expect(prepared.ok()).toBe(true)
    const engine = (await (await request.get('/api/settings')).json()).comfy_url
    const item = {
      name: 'v06-fixture.safetensors',
      listed: true,
      version: '',
      notes: '',
      source_url: '',
      architecture: 'sdxl',
      kind: 'canny',
    }
    // UI-only catalogs: these responses cannot affect another browser context or the database.
    await page.route('**/api/controlnets', (r) =>
      r.fulfill({
        json: { engine_url: engine, controlnets: [item], synced_at: null, sync_error: null },
      }),
    )
    await page.route('**/api/flux/components', (r) =>
      r.fulfill({
        json: {
          engine_url: engine,
          groups: { diffusion_models: [item], text_encoders: [], vae: [] },
          synced_at: null,
          sync_error: null,
        },
      }),
    )
    try {
      await page.setViewportSize({ width, height: 900 })
      await page.goto('/#/models')
      await page.waitForLoadState('networkidle')
      await enter(
        page
          .locator('.model-card')
          .first()
          .getByRole('button', { name: '查看流程驗證紀錄', exact: true }),
      )
      await expect(page.getByRole('region', { name: '模型與流程驗證紀錄' })).toBeVisible()
      await enter(
        page.locator('.model-card').first().getByRole('button', { name: '編輯資料', exact: true }),
      )
      await enter(
        page
          .locator('.lora-card')
          .first()
          .getByRole('button', { name: '編輯 LoRA 資料', exact: true }),
      )
      await enter(
        page
          .locator('.control-card')
          .first()
          .getByRole('button', { name: '編輯 ControlNet 資料', exact: true }),
      )
      await enter(
        page.getByRole('button', { name: '編輯 FLUX 元件：v06-fixture.safetensors', exact: true }),
      )
      await openDetails(page)
      await capture(page, info, 'catalog-editors')
      const table = page.getByRole('region', { name: 'FLUX 元件與來源版本表格' })
      await keyboardFocus(table)
      const start = await table.evaluate((element) => element.scrollLeft)
      for (let step = 0; step < 8; step++) await table.press('ArrowRight')
      if (width === 390)
        await expect
          .poll(() => table.evaluate((element) => element.scrollLeft))
          .toBeGreaterThan(start)
      await table.screenshot({ path: info.outputPath('flux-table-keyboard.png') })
    } finally {
      const reset = await request.post('/qa/comparison-context/reset')
      expect(reset.ok()).toBe(true)
    }
  })

  test(`${width}px: artwork toggle, modal keyboard trap and focus return`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width, height: 900 })
    await request.post('/qa/populate')
    const state = await (await request.get('/qa/state')).json()
    const original = await (await request.get('/api/artworks/' + state.artwork_id)).json()
    await page.goto('/#/gallery')
    await expect(page.getByRole('group', { name: '作品分頁', exact: true })).toBeVisible()
    await page.getByLabel('搜尋作品', { exact: true }).fill('qa-artwork.png')
    const card = page
      .locator('.artwork-card')
      .filter({ has: page.getByRole('button', { name: '查看作品 qa-artwork.png', exact: true }) })
    const favorite = card.getByRole('button', { name: /收藏.*：qa-artwork.png/ })
    await expect(favorite).toHaveAttribute('aria-pressed', String(!!original.favorite))
    await enter(favorite)
    await expect(card.getByRole('button', { name: /收藏.*：qa-artwork.png/ })).toHaveAttribute(
      'aria-pressed',
      String(!original.favorite),
    )
    await expect(
      page.getByRole('status').filter({ hasText: original.favorite ? '已取消收藏' : '已加入收藏' }),
    ).toBeVisible()
    await enter(card.getByRole('button', { name: /收藏.*：qa-artwork.png/ }))
    await expect(card.getByRole('button', { name: /收藏.*：qa-artwork.png/ })).toHaveAttribute(
      'aria-pressed',
      String(!!original.favorite),
    )
    await enter(card.getByRole('button', { name: '選取作品：qa-artwork.png', exact: true }))
    await expect(page.getByRole('region', { name: '已選作品', exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: '作品並排比較', exact: true })).toHaveCount(0)
    await capture(page, info, 'artwork-selection')
    const cover = page.getByRole('button', { name: '查看作品 qa-artwork.png', exact: true })
    await enter(cover)
    const dialog = page.getByRole('dialog', { name: 'qa-artwork.png', exact: true })
    const close = dialog.getByRole('button', { name: '關閉', exact: true })
    await expect(close).toBeFocused()
    await close.press('Shift+Tab')
    expect(await page.locator(':focus').evaluate((element) => !!element.closest('dialog'))).toBe(
      true,
    )
    await openDetails(page)
    await capture(page, info, 'artwork-dialog')
    await keyboardFocus(close)
    await capture(page, info, 'artwork-dialog-top')
    await page.keyboard.press('Escape')
    await expect(dialog).not.toBeVisible()
    await expect(cover).toBeFocused()
  })

  test(`${width}px: asset editor, no results, loading and error announcements`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/assets')
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('group', { name: '素材分頁' })).toBeVisible()
    const card = page.locator('.asset-card').first()
    await enter(card.getByRole('button', { name: /編輯素材/ }))
    await expect(card.getByLabel('素材名稱')).toBeVisible()
    await capture(page, info, 'asset-editor')
    await enter(card.getByRole('button', { name: '取消', exact: true }))
    await page.getByRole('searchbox', { name: '搜尋素材' }).fill('v06-no-matching-asset')
    await expect(page.getByRole('heading', { name: '目前沒有符合條件的素材' })).toBeVisible()
    await capture(page, info, 'asset-empty')
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route('**/api/library/assets?**', async (route) => {
      await gate
      await route.fulfill({
        status: 503,
        json: { detail: 'V06：素材服務暫時無法讀取，請稍後重新整理。' },
      })
    })
    try {
      await enter(page.getByRole('button', { name: '重新整理', exact: true }))
      await expect(page.getByRole('status').filter({ hasText: '正在處理素材' })).toBeVisible()
      await capture(page, info, 'asset-loading')
    } finally {
      release()
    }
    await expect(page.getByRole('alert')).toContainText('V06：素材服務暫時無法讀取')
    await capture(page, info, 'asset-error')
  })

  test(`${width}px: settings, diagnostic JSON keyboard and connection failure`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/settings')
    await page.waitForLoadState('networkidle')
    await enter(page.getByRole('button', { name: '預覽診斷 JSON', exact: true }))
    const preview = page.getByLabel('診斷 JSON 預覽', { exact: true })
    await expect(preview).toBeVisible()
    await keyboardFocus(preview)
    await preview.press('End')
    await openDetails(page)
    await capture(page, info, 'settings-preview')
    await page.route('**/api/settings', (route) =>
      route.request().method() === 'PUT'
        ? route.fulfill({ status: 503, json: { detail: 'V06：設定保存失敗，請稍後再試。' } })
        : route.continue(),
    )
    await enter(page.getByRole('button', { name: '保存並檢查連線', exact: true }))
    await expect(page.getByRole('status').filter({ hasText: 'V06：設定保存失敗' })).toBeVisible()
    await expect(page.getByLabel('服務位址', { exact: true })).toHaveValue(
      'http://mock-engine.invalid:8188',
    )
    await capture(page, info, 'settings-error')
  })

  test(`${width}px: image input, import error, mask keyboard and control source`, async ({
    page,
    request,
  }, info) => {
    const state = await (await request.get('/qa/state')).json()
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/studio/checkpoint')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Checkpoint 工作流程', { exact: true }).selectOption('image2image')
    await page.getByLabel('輸入圖片', { exact: true }).selectOption(state.asset_id)
    await openDetails(page)
    await capture(page, info, 'checkpoint-image-input')
    const transfer = page.locator('.settings-transfer:visible')
    await transfer.getByRole('textbox').fill('{ invalid JSON')
    await enter(transfer.getByRole('button', { name: '驗證並預覽設定', exact: true }))
    await expect(transfer.getByRole('alert')).toBeVisible()
    await capture(page, info, 'checkpoint-import-error')
    await page.goto('/#/studio/inpaint')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('原圖', { exact: true }).selectOption(state.asset_id)
    await expect(page.locator('canvas')).toBeVisible()
    const brush = page.getByRole('slider', { name: /大小/ })
    await keyboardFocus(brush)
    const before = Number(await brush.inputValue())
    await brush.press('ArrowRight')
    await expect(brush).toHaveValue(String(before + 1))
    await enter(page.getByRole('button', { name: '反相', exact: true }))
    await expect(
      page.getByRole('status').filter({ hasText: '已標記 4,096 個原圖像素' }),
    ).toBeVisible()
    await capture(page, info, 'inpaint-mask')
    await page.goto('/#/studio/control')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('原圖', { exact: true }).selectOption(state.asset_id)
    await expect(page.getByRole('img', { name: '結構參考素材：qa-source.png' })).toBeVisible()
    await expect(page.getByLabel('提交能力狀態')).toContainText('尚缺必要條件')
    await capture(page, info, 'control-source')
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(state.prompts)
  })
}
