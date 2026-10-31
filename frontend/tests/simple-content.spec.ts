import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import AxeBuilder from '@axe-core/playwright'

const animagine = JSON.parse(await readFile('../models/animagine-xl-4.0-opt.json', 'utf8'))
const pony = JSON.parse(await readFile('../models/pony-v6-xl.json', 'utf8'))
let original: Record<string, unknown>
let engine: string
test.beforeEach(async ({ request }) => {
  const catalog = await (await request.get('/api/models')).json()
  engine = catalog.engine_url
  original = catalog.models.find((item: { name: string }) => item.name === 'demo.safetensors')
  await request.post('/qa/simple-creation')
  await request.post('/qa/engine/success')
})
test.afterEach(async ({ request }) => {
  await request.put('/api/models/metadata', {
    data: {
      engine_url: engine,
      name: 'demo.safetensors',
      architecture: original.architecture,
      sha256: original.sha256,
      version: original.version,
    },
  })

  await request.post('/qa/simple-creation?enabled=false')
  await request.post('/api/engine/capabilities/sync')
})

for (const unavailable of [true, false])
  test(`simple preview contains ${unavailable ? 'offline error' : 'saved image'} above save controls and task history`, async ({
    page,
    request,
  }, info) => {
    const before = (await (await request.get('/qa/state')).json()).prompts
    await request.post('/qa/engine/offline')
    await page.route('**/api/library/jobs?*', async (route) => {
      const response = await route.fetch()
      const body = await response.json()
      body.items = body.items.map((job: Record<string, unknown>) => ({
        ...job,
        checkpoint: 'animagine-xl-4.0-opt.safetensors',
      }))
      await route.fulfill({ json: body })
    })
    if (unavailable) {
      await page.route('**/api/jobs/*/results', (route) =>
        route.fulfill({
          json: {
            items: [
              {
                index: 0,
                filename: 'offline.png',
                saved: false,
                local_available: false,
                width: null,
                height: null,
              },
            ],
          },
        }),
      )
      await page.route('**/api/jobs/*/results/*/image', (route) =>
        route.fulfill({
          status: 503,
          json: { detail: '原引擎離線或無法讀取結果；尚未匯入作品庫的圖片需要原引擎。' },
        }),
      )
    }
    await page.goto('/#/studio/simple')
    const preview = page.getByRole('region', { name: '創作畫布', exact: true })
    const canvas = preview.locator(unavailable ? '.empty-canvas' : '.result-canvas')
    if (unavailable) await expect(preview.getByRole('alert')).toContainText('原引擎離線')
    else await expect(canvas.locator('img')).toHaveJSProperty('naturalWidth', 64)
    const actions = page.locator('.simple-result-actions')
    await expect(actions.getByRole('button', { name: '存入作品庫', exact: true })).toBeVisible()
    for (const [width, height] of [
      [1280, 800],
      [1440, 900],
      [1920, 1080],
      [2732, 1806],
      [390, 844],
    ]) {
      await page.setViewportSize({ width: width!, height: height! })
      await preview.scrollIntoViewIfNeeded()
      await page.screenshot({
        path: info.outputPath(`${unavailable ? 'offline' : 'saved'}-${width}.png`),
      })
      const frame = (await preview.boundingBox())!
      const surface = (await canvas.boundingBox())!
      const caption = (await preview.locator('.stage-caption').boundingBox())!
      const buttons = (await actions.boundingBox())!
      const status = (await page.locator('.simple-stage .generation-statusbar').boundingBox())!
      expect(
        surface.y + surface.height,
        `${width}px canvas must stay inside preview`,
      ).toBeLessThanOrEqual(frame.y + frame.height + 1)
      expect(caption.y, `${width}px caption must follow canvas`).toBeGreaterThanOrEqual(
        surface.y + surface.height - 1,
      )
      expect(buttons.y, `${width}px save buttons must follow preview`).toBeGreaterThanOrEqual(
        frame.y + frame.height - 1,
      )
      expect(
        buttons.y,
        `${width}px save buttons must be inside the bottom action row`,
      ).toBeGreaterThanOrEqual(status.y - 1)
      expect(buttons.y + buttons.height).toBeLessThanOrEqual(status.y + status.height + 1)
      expect(surface.height).toBeGreaterThanOrEqual(160)
      expect(surface.height).toBeLessThanOrEqual(Math.max(240, Math.min(680, height! * 0.6)) + 1)
      expect(surface.x).toBeGreaterThanOrEqual(frame.x - 1)
      expect(surface.x + surface.width).toBeLessThanOrEqual(frame.x + frame.width + 1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
    }
    if (unavailable) {
      await page.getByRole('button', { name: '重新讀取結果', exact: true }).click()
      await expect(preview.getByRole('alert')).toContainText('原引擎離線')
    }
    expect(
      (
        await new AxeBuilder({ page })
          .include('.atelier-shell')
          .withTags(['wcag2a', 'wcag2aa'])
          .analyze()
      ).violations,
    ).toEqual([])
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  })
for (const [name, architecture, sha256] of [
  ['Animagine', 'sdxl', animagine.sha256],
  ['Pony', 'sdxl', pony.sha256],
  ['generic SDXL', 'sdxl', 'a'.repeat(64)],
  ['unknown', 'unknown', ''],
])
  test(`${name}: summary and details share evidence, edits and LoRA keep its scope`, async ({
    page,
    request,
  }) => {
    const before = (await (await request.get('/qa/state')).json()).prompts
    await request.put('/api/models/metadata', {
      data: { engine_url: engine, name: 'demo.safetensors', architecture, sha256 },
    })
    const profile = await (
      await request.get(
        '/api/models/profile?' +
          new URLSearchParams({ engine_url: engine, name: 'demo.safetensors' }),
      )
    ).json()
    await page.route('**/api/loras', (route) =>
      route.fulfill({
        json: {
          engine_url: engine,
          synced_at: '2026-10-30T00:00:00Z',
          sync_error: null,
          loras: [
            {
              name: 'evidence-demo.safetensors',
              listed: true,
              architecture: 'sdxl',
              version: 'test-only',
            },
          ],
        },
      }),
    )
    await page.goto('/#/studio/checkpoint')
    await page.locator('#draft-model').selectOption('demo.safetensors')
    await page.locator('.studio-advanced > summary').click()
    await page.getByText('模型能力、預設與差異確認', { exact: true }).click()
    if (architecture === 'unknown') {
      await expect(page.locator('.model-profile')).toContainText('此模型尚無可套用的參數預設')
      await expect(page.locator('.preset-evidence-summary')).toHaveCount(0)
    } else {
      await expect(page.locator('.preset-evidence-summary')).toHaveText(profile.preset.validation)
      await page.getByText('預設來源與提示詞參考', { exact: true }).click()
      await expect(page.locator('.preset-evidence-detail')).toHaveText(profile.preset.validation)
      await page.locator('#steps').fill('31')
      await expect(page.locator('.preset-evidence-changes')).toContainText('取樣參數已修改')
      await page.getByText('LoRA 與有序組合', { exact: true }).click()
      await page.locator('#creation-lora').selectOption('evidence-demo.safetensors')
      await page.getByRole('button', { name: '加入 LoRA', exact: true }).click()
      await expect(page.locator('.preset-evidence-changes')).toContainText('實測不包含此組合')
      await expect(page.locator('.preset-evidence-summary')).toHaveText(profile.preset.validation)
      await expect(page.locator('.preset-evidence-detail')).toHaveText(profile.preset.validation)
      await expect(page.locator('.preset-evidence-changes')).toContainText(
        '未判定目前描述、角色或畫風',
      )
    }
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  })

for (const width of [1440, 390])
  test(`${width}px: real examples, exact recipe download and tutorial screenshots`, async ({
    page,
    request,
  }, info) => {
    const before = (await (await request.get('/qa/state')).json()).prompts
    await request.put('/api/models/metadata', {
      data: {
        engine_url: engine,
        name: 'demo.safetensors',
        architecture: 'sdxl',
        sha256: animagine.sha256,
      },
    })
    await page.route('**/api/library/jobs?*', (route) =>
      route.fulfill({ json: { items: [], next_cursor: null } }),
    )
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/studio/simple')
    await expect(page.locator('.simple-card-image')).toHaveCount(3)
    expect(
      await page
        .locator('.simple-card-image')
        .evaluateAll((nodes: HTMLImageElement[]) =>
          nodes.every((node) => node.complete && node.naturalWidth >= 512),
        ),
    ).toBe(true)
    await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
    await page.locator('.simple-intro').scrollIntoViewIfNeeded()
    await page.screenshot({ path: info.outputPath('simple-creation-guide.png'), fullPage: false })
    await page.getByText('真實範例、完整配方與觀察', { exact: true }).click()
    await expect(page.locator('.simple-example')).toContainText('手部')
    const downloaded = page.waitForEvent('download')
    await page.getByRole('link', { name: '下載完整配方與實測紀錄（JSON）' }).click()
    const download = await downloaded
    const recipe = JSON.parse(await readFile((await download.path())!, 'utf8'))
    expect(recipe.template_context.selection).toEqual({
      template_id: 'animagine',
      template_version: 1,
    })
    expect(recipe.settings.seed).toBe('9007199254740993')
    expect(recipe.image.sha256).toMatch(/^[a-f0-9]{64}$/)
    await expect(page.locator('.simple-example')).not.toContainText('目前設定已修改')
    await page.getByRole('button', { name: '編輯描述', exact: true }).click()
    await page.locator('#simple-prompt').fill('changed English scene')
    await expect(page.locator('.simple-example')).toContainText('目前設定已修改')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
    if (width === 1440) {
      await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
      await expect(page.locator('#draft-prompt')).toBeVisible()
      await expect(
        page.getByText('正在確認模型工作流程資料，請稍候。', { exact: true }),
      ).toHaveCount(0)
      await page.evaluate(() => scrollTo(0, 0))
      await page.screenshot({ path: info.outputPath('studio-guide.png'), fullPage: false })
      await page.getByRole('button', { name: '局部修補', exact: true }).click()
      const state = await (await request.get('/qa/state')).json()
      await page.locator('#inpaint-source').selectOption(state.asset_id)
      await page.locator('#inpaint-checkpoint').selectOption('demo.safetensors')
      await page.getByText('鍵盤區塊選取與快捷鍵', { exact: true }).click()
      await page.getByRole('button', { name: '中央區塊', exact: true }).click()
      await expect(page.getByRole('button', { name: '保存遮罩', exact: true })).toBeEnabled()
      await page.getByText('鍵盤區塊選取與快捷鍵', { exact: true }).click()
      await page.evaluate(() => scrollTo(0, 0))
      await page.screenshot({ path: info.outputPath('inpaint-guide.png'), fullPage: false })
      expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
    }
  })
