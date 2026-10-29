import { test, expect, type Page, type Locator } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import AxeBuilder from '@axe-core/playwright'

test('model categories retain empty, search, stale and failed-edit states in both layouts', async ({
  page,
  request,
  context,
}) => {
  const paths = [
    '/api/models',
    '/api/loras',
    '/api/controlnets',
    '/api/reference-components',
    '/api/flux/components',
  ]
  const original = await Promise.all(paths.map(async (path) => (await request.get(path)).json()))
  const engine = original[0].engine_url
  const record = {
    name: 'alignment-check.safetensors',
    listed: true,
    architecture: 'sdxl',
    version: 'fixture-v1',
    notes: '',
    source_url: '',
    kind: 'canny',
    sha256: 'a'.repeat(64),
  }
  const held = { ...record, name: 'history-only.safetensors', listed: false }
  let state: 'empty' | 'populated' | 'stale' = 'empty'
  let failedWrites = 0
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const index = paths.findIndex(
      (base) =>
        path === base ||
        path === base + '/sync' ||
        path === base + '/metadata' ||
        path === base + '/selection',
    )
    if (index < 0) return route.continue()
    if (route.request().method() !== 'GET') {
      failedWrites++
      return route.fulfill({
        status: 503,
        json: { detail: 'alignment fixture offline; edits retained' },
      })
    }
    const items = state === 'empty' ? [] : [record, held]
    const common = {
      engine_url: engine,
      synced_at: null,
      sync_error: state === 'stale' ? 'fixture 引擎離線；保留歷史紀錄' : null,
    }
    const result = [
      { ...common, models: items, selected: null },
      { ...common, loras: items },
      { ...common, controlnets: items },
      {
        ...common,
        components: items.map((item) => ({
          ...item,
          role: 'ipadapter',
          family: 'sdxl-plus-vit-h',
        })),
      },
      { ...common, groups: { diffusion_models: items, text_encoders: [], vae: [] } },
    ][index]
    await route.fulfill({ json: result })
  })
  const categories = ['Checkpoint', 'LoRA', '結構控制', '元件', 'FLUX 元件']
  const panel = page.getByRole('tabpanel').filter({ visible: true })
  const ref = await context.newPage()
  await ref.goto(preview + '#models')
  await ref.locator('#scenario').selectOption('empty')
  const emptyStyle = (locator: Locator) =>
    locator.evaluate((element) => {
      const s = getComputedStyle(element)
      return {
        background: s.backgroundColor,
        border: s.borderColor,
        style: s.borderStyle,
        padding: s.padding,
        radius: s.borderRadius,
      }
    })
  await page.goto('/#/models')
  for (const category of categories) {
    await page.getByRole('tab', { name: category, exact: true }).click()
    await ref.locator('[data-modeltype="' + category + '"]').click()
    for (const layout of ['清單', '卡片']) {
      await page.getByRole('button', { name: layout, exact: true }).click()
      await expect(panel.locator('.model-entry')).toHaveCount(0)
      await expect(panel.locator('.placeholder')).toBeVisible()
      expect(await emptyStyle(panel.locator('.placeholder'))).toEqual(
        await emptyStyle(ref.locator('.empty')),
      )
      await expect(panel.locator('.model-grid, .model-collection')).toHaveCount(0)
    }
  }
  await ref.close()
  state = 'populated'
  await page.reload()
  const filters = [
    ['搜尋模型', '清除篩選'],
    ['搜尋 LoRA', '清除 LoRA 篩選'],
    ['搜尋 ControlNet', '清除 ControlNet 篩選'],
    [],
    ['搜尋 FLUX 元件', '清除 FLUX 篩選'],
  ]
  for (let i = 0; i < categories.length; i++) {
    await page.getByRole('tab', { name: categories[i], exact: true }).click()
    await expect(panel.locator('.model-entry')).toHaveCount(2)
    await expect(panel.locator('.model-entry-status').last()).toHaveText('最近清單未列出')
    if (i === 0)
      await expect(
        panel.locator('.model-entry').last().getByRole('button', { name: '套用到創作' }),
      ).toBeDisabled()
    const input = filters[i][0]
    if (input) {
      await panel.locator('.library-management > summary').click()
      await panel.getByLabel(input, { exact: true }).fill('no matching model')
      for (const layout of ['清單', '卡片']) {
        await page.getByRole('button', { name: layout, exact: true }).click()
        await expect(panel.locator('.model-entry')).toHaveCount(0)
        await expect(panel.locator('.model-grid, .model-collection')).toHaveCount(0)
      }
      await panel.getByRole('button', { name: filters[i][1], exact: true }).click()
      await expect(panel.locator('.model-entry')).toHaveCount(2)
    }
    const accessibility = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    expect(accessibility.violations, categories[i]).toEqual([])
  }
  await panel
    .getByRole('button', { name: '編輯 FLUX 元件：alignment-check.safetensors', exact: true })
    .click()
  await panel.getByLabel('元件版本', { exact: true }).fill('keep failed edit')
  await panel.getByRole('button', { name: '保存元件資料', exact: true }).click()
  await expect(panel.getByRole('alert')).toContainText('alignment fixture offline')
  await expect(panel.getByLabel('元件版本', { exact: true })).toHaveValue('keep failed edit')
  await expect(page.getByRole('button', { name: '同步FLUX 元件清單', exact: true })).toBeDisabled()
  await page.getByRole('tab', { name: 'LoRA', exact: true }).click()
  await page.getByRole('tab', { name: 'FLUX 元件', exact: true }).click()
  await expect(panel.getByLabel('元件版本', { exact: true })).toHaveValue('keep failed edit')
  await panel.getByRole('button', { name: '取消元件編輯', exact: true }).click()
  state = 'stale'
  await page.reload()
  for (const category of categories) {
    await page.getByRole('tab', { name: category, exact: true }).click()
    await expect(panel.locator('.model-entry')).toHaveCount(2)
    await expect(
      page.getByRole('alert').filter({ hasText: 'fixture 引擎離線' }).first(),
    ).toBeVisible()
  }
  expect(failedWrites).toBe(1)
  // Browser-only fixture responses must not alter the actual isolated catalogs.
  expect(await Promise.all(paths.map(async (path) => (await request.get(path)).json()))).toEqual(
    original,
  )
})

test('training empty stages keep extra controls and explicit experiment navigation', async ({
  page,
}) => {
  let writes = 0
  let offline = false
  await page.route('**/api/training/**', async (route) => {
    if (route.request().method() !== 'GET') {
      writes++
      return route.fulfill({ status: 500 })
    }
    const path = new URL(route.request().url()).pathname
    if (offline)
      return route.fulfill({ status: 503, json: { detail: 'training verification offline' } })
    if (path.endsWith('/datasets'))
      return route.fulfill({ json: { available: true, datasets: [] } })
    if (path.endsWith('/control'))
      return route.fulfill({ json: { available: true, exports: [], runs: [], requests: [] } })
    await route.continue()
  })
  await page.goto('/#/training')
  await expect(page.getByRole('heading', { name: '尚未選擇審查資料', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
  await expect(page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true })).toHaveCount(
    0,
  )
  await page.getByRole('button', { name: '3 準備訓練 凍結設定', exact: true }).click()
  await expect(page.getByRole('heading', { name: '準備新的訓練', exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: '準備新 run（不開始訓練）', exact: true }),
  ).toBeDisabled()
  await expect(page.locator('.training-prepare-parameters')).not.toHaveAttribute('open', '')
  await page.getByRole('button', { name: '4 執行與產物 追蹤結果', exact: true }).click()
  await expect(
    page.getByText('準備訓練後可在此追蹤原 run；目前沒有可顯示的步數。', { exact: true }),
  ).toBeVisible()
  await expect(page.locator('.training-run-summary progress')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '查看產物與固定比較', exact: true })).toBeDisabled()
  await page.locator('.training-run-management > summary').click()
  await expect(
    page.getByRole('button', { name: '登記既有 run（不啟動）', exact: true }),
  ).toBeVisible()
  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations).toEqual([])
  await page.locator('.training-run-management > summary').click()
  await page.getByRole('button', { name: '查看歷史報告', exact: true }).click()
  await expect(page.locator('#training-run-history')).toBeFocused()
  await expect(page.locator('.training-run-management')).toHaveAttribute('open', '')
  await page.getByRole('button', { name: '前往實驗比較', exact: true }).click()
  await expect(page).toHaveURL(/#\/experiments$/)
  offline = true
  await page.goto('/#/training')
  await expect(page.getByRole('alert')).toContainText('training verification offline')
  expect(writes).toBe(0)
})

const preview = new URL('../../docs/ui-redesign/preview.html', import.meta.url).href
async function box(locator: Locator) {
  const value = await locator.first().boundingBox()
  expect(value).not.toBeNull()
  return value!
}
async function aligned(actual: Locator, reference: Locator, tolerance = 2) {
  const a = await box(actual),
    b = await box(reference)
  for (const field of ['x', 'y', 'width'] as const)
    expect(Math.abs(a[field] - b[field]), field).toBeLessThanOrEqual(tolerance)
}
async function referencePage(page: Page, name: string) {
  await page.goto(preview + '#' + name)
  await page.locator('.sidebar').waitFor()
}

for (const [width, height] of [
  [1280, 800],
  [1440, 900],
  [1920, 1080],
] as const) {
  test(`approved HTML geometry at ${width}px: libraries, workbench, settings and system`, async ({
    page,
    context,
  }, info) => {
    await page.setViewportSize({ width, height })
    const ref = await context.newPage()
    await ref.setViewportSize({ width, height })
    for (const [name, actual, expected] of [
      ['assets', '.asset-grid', '.assets-grid'],
      ['models', '.model-grid', '.model-list'],
      ['gallery', '.artwork-grid', '.gallery'],
      ['settings', '.settings-workspace', '.settings'],
      ['system', '.system-summary-cards', '.system-summary-cards'],
    ]) {
      await referencePage(ref, name!)
      await page.goto('/#/' + name)
      await expect(page.locator(actual!).first()).toBeVisible()
      const expectedSelector = name === 'system' ? '.sys-cards' : expected!
      await aligned(
        page.locator(actual!),
        ref.locator(expectedSelector),
        name === 'gallery' ? 3 : 2,
      )
      const bg = await page.locator('.rail').evaluate((e) => getComputedStyle(e).backgroundColor)
      expect(bg).toBe(
        await ref.locator('.sidebar').evaluate((e) => getComputedStyle(e).backgroundColor),
      )
      const first = page.locator('.rail svg').first(),
        icon = ref.locator('.sidebar svg').first()
      expect((await box(first)).width).toBe((await box(icon)).width)
      if (name === 'assets') {
        await aligned(page.locator('.asset-search input'), ref.locator('.assets-toolbar input'))
        expect(
          await page
            .locator('.asset-grid')
            .evaluate((e) => getComputedStyle(e).gridTemplateColumns.split(' ').length),
        ).toBe(3)
        await expect(page.locator('.asset-management[open]')).toHaveCount(0)
      }
      if (name === 'models') {
        await expect(page.getByRole('button', { name: '清單', exact: true })).toHaveAttribute(
          'aria-pressed',
          'true',
        )
        await page.getByRole('button', { name: '卡片', exact: true }).click()
        await ref.getByRole('button', { name: '卡片', exact: true }).click()
        await aligned(page.locator('.model-grid'), ref.locator('.model-cards'))
        expect((await box(page.locator('.model-card'))).width).toBeCloseTo(
          (await box(ref.locator('.model-entry'))).width,
          0,
        )
        await page.getByRole('button', { name: '清單', exact: true }).click()
      }
      if (name === 'gallery')
        await expect(page.getByRole('button', { name: '固定', exact: true })).toHaveAttribute(
          'aria-pressed',
          'true',
        )
      await page.screenshot({ path: info.outputPath(`${name}-${width}.png`), fullPage: true })
    }
    await referencePage(ref, 'studio')
    // Geometry of the empty stage requires an explicitly empty job collection.
    await page.route('**/api/library/jobs?**', (route) =>
      route.fulfill({ json: { items: [], next_cursor: null } }),
    )
    await page.goto('/#/studio/checkpoint')
    await aligned(page.locator('.studio-settings'), ref.locator('.controls'))
    await aligned(page.locator('#draft-prompt'), ref.locator('#vprompt'))
    await aligned(page.locator('.size-presets'), ref.locator('.size-buttons'), 3)
    await aligned(page.locator('.empty-canvas'), ref.locator('.image-frame'), 3)
    const status = await box(page.locator('.generation-statusbar'))
    expect(status.y + status.height).toBeLessThanOrEqual(height + 1)
    await page.screenshot({ path: info.outputPath(`studio-${width}.png`), fullPage: true })
    await ref.close()
  })
}

test('saved experiment uses the approved three-column result layout, with explicit manual handoff', async ({
  page,
  request,
  context,
}, info) => {
  const state = await (await request.get('/qa/state')).json()
  const creation = await (
    await request.get('/api/artworks/' + state.artwork_id + '/creation-settings')
  ).json()
  const title = 'HTML parity ' + randomUUID()
  const settings = {
    ...creation.settings,
    title,
    prompt: '山巒插畫',
    width: 1024,
    height: 1024,
    seed: '18446744073709551615',
    workflow_mode: 'text2image',
    reference_ids: [],
    image_asset_id: null,
  }
  const response = await request.post('/api/experiments/preview', {
    data: {
      title,
      settings,
      axis: 'steps',
      values: [20, 28, 36],
      case_ids: [],
      suite_id: 'general-illustration',
    },
  })
  expect(response.ok(), await response.text()).toBe(true)
  const saved = await request.post('/api/experiments/plans', {
    headers: { 'Content-Type': 'application/json' },
    data:
      '{"request_id":' + JSON.stringify(randomUUID()) + ',"plan":' + (await response.text()) + '}',
  })
  expect(saved.ok(), await saved.text()).toBe(true)
  const record = await saved.json()
  const ref = await context.newPage()
  await ref.setViewportSize({ width: 1440, height: 900 })
  await referencePage(ref, 'experiments')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/experiments')
  await page.getByLabel('已保存方案', { exact: true }).selectOption(record.id)
  await expect(page.locator('.comparison-summary')).toContainText(title)
  await expect(page.locator('.comparison-card-heading h3')).toHaveText([
    '20 steps',
    '28 steps',
    '36 steps',
  ])
  await aligned(page.locator('.comparison-summary'), ref.locator('.experiment-summary'), 2)
  await aligned(page.locator('.comparison-grid'), ref.locator('.experiment'), 3)
  await expect(page.locator('.experiment-planner')).not.toHaveAttribute('open')
  await expect(page.locator('.generation-submit')).toBeHidden()
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(state.prompts)
  await page.screenshot({ path: info.outputPath('comparison.png'), fullPage: true })
  await page.getByRole('button', { name: '載入比較設定 variant-1', exact: true }).click()
  await expect(page.locator('#draft-prompt')).toHaveValue('山巒插畫')
  await expect(page.locator('#seed')).toHaveValue('18446744073709551615')
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(state.prompts)
  await request.post('/qa/engine/success')
  try {
    const variant = record.plan.variants[0]
    const generated = await request.post('/api/generate', {
      data: {
        ...variant.settings,
        request_id: randomUUID(),
        experiment: {
          plan_id: record.id,
          plan_sha256: record.plan.plan_sha256,
          variant_id: variant.id,
        },
      },
    })
    expect(generated.ok(), await generated.text()).toBe(true)
    const job = await generated.json()
    await expect
      .poll(
        async () => (await (await request.post('/api/jobs/' + job.id + '/refresh')).json()).status,
      )
      .toBe('completed')
    const imported = await request.post('/api/jobs/' + job.id + '/artworks')
    expect(imported.ok(), await imported.text()).toBe(true)
    await page
      .getByRole('navigation')
      .getByRole('button', { name: '實驗比較', exact: true })
      .click()
    await expect(page.locator('.comparison-result-image')).toHaveCount(1)
    await expect(page.locator('.comparison-result-image')).toBeVisible()
    await expect(page.getByRole('button', { name: '記錄評分', exact: true })).toBeVisible()
    await page.screenshot({ path: info.outputPath('comparison-real-result.png'), fullPage: true })
  } finally {
    await request.post('/qa/engine/uncertain')
  }
  await ref.close()
})

test('populated review keeps three columns and protects saved state while using secondary tools', async ({
  page,
  request,
  context,
}, info) => {
  const fixture = await (await request.post('/qa/training-review')).json()
  const manifest = JSON.parse(fixture.manifest_json)
  for (const item of manifest.images) {
    item.split = 'train'
    item.exclusion_reason = ''
  }
  const response = await request.post('/api/training/datasets', {
    data: {
      request_id: randomUUID(),
      source_root: fixture.source_root,
      manifest_json: JSON.stringify(manifest),
      study_json: '',
    },
  })
  expect(response.ok(), await response.text()).toBe(true)
  const record = await response.json()
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/training')
  await page.locator('.training-dataset-management > summary').click()
  await page.locator('[data-dataset-id="' + record.id + '"]').click()
  const ref = await context.newPage()
  await ref.setViewportSize({ width: 1440, height: 900 })
  await referencePage(ref, 'training')
  await expect(page.locator('.training-review-grid')).toBeVisible()
  const columns = await page
    .locator('.training-review-grid')
    .evaluate((e) => getComputedStyle(e).gridTemplateColumns)
  expect(columns).toBe(
    await ref.locator('.training-review').evaluate((e) => getComputedStyle(e).gridTemplateColumns),
  )
  await expect(page.getByLabel('只顯示待補項目')).toBeChecked()
  await expect(page.locator('.review-navigation-details')).not.toHaveAttribute('open')
  await page.getByLabel('內容標註', { exact: true }).fill('keep live review')
  await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
  await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
  await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue('keep live review')
  expect((await (await request.get('/api/training/datasets/' + record.id)).json()).revision).toBe(
    record.revision,
  )
  await page.screenshot({ path: info.outputPath('review.png'), fullPage: true })
  await ref.close()
})

test('comparison creation, save and reload preserve the original v1 document bytes', async ({
  page,
  request,
}) => {
  await page.goto('/#/studio/checkpoint')
  await page.locator('#draft-prompt').fill('real browser comparison')
  await page.locator('.studio-advanced > summary').click()
  await page.locator('#seed').evaluate((e) => {
    for (let p = e.parentElement; p; p = p.parentElement)
      if (p.tagName === 'DETAILS') (p as HTMLDetailsElement).open = true
  })
  await page.locator('#seed').fill('18446744073709551615')
  await page.getByRole('navigation').getByRole('button', { name: '實驗比較', exact: true }).click()
  await page.getByRole('button', { name: '建立比較方案', exact: true }).click()
  await page.locator('#experiment-title').fill('browser v1 ' + randomUUID())
  await page.locator('#experiment-values').fill('[20,28,36]')
  await page.getByRole('button', { name: '預覽比較方案', exact: true }).click()
  await expect(page.locator('.comparison-grid')).toBeVisible()
  await page.locator('.saved-experiments > summary').click()
  const saving = page.waitForResponse(
    (r) => r.url().endsWith('/api/experiments/plans') && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '保存目前預覽方案', exact: true }).click()
  const response = await saving
  expect(response.ok(), await response.text()).toBe(true)
  const record = await response.json()
  expect(record.plan.baseline.seed).toBe('18446744073709551615')
  expect(response.request().postData()).toContain('"cfg":7.0')
  await expect(page.getByLabel('已保存方案', { exact: true })).toBeEnabled()
  await page.getByLabel('已保存方案', { exact: true }).selectOption(record.id)
  await expect(page.locator('.comparison-summary')).toContainText(record.plan.title)
  const doc = await request.get('/api/experiments/plans/' + record.id + '/document')
  expect(doc.ok()).toBe(true)
  expect((await doc.json()).plan_sha256).toBe(record.plan.plan_sha256)
})

test('review save-and-next retains a failed edit and advances only after a saved revision', async ({
  page,
  request,
}) => {
  const fixture = await (await request.post('/qa/training-review')).json()
  const record = await (
    await request.post('/api/training/datasets', {
      data: {
        request_id: randomUUID(),
        source_root: fixture.source_root,
        manifest_json: fixture.manifest_json,
        study_json: '',
      },
    })
  ).json()
  await page.goto('/#/training')
  await page.locator('.training-dataset-management > summary').click()
  await page.locator('[data-dataset-id="' + record.id + '"]').click()
  await expect(page.locator('.training-source-image img')).toHaveAttribute(
    'src',
    new RegExp(record.id),
  )
  await page.getByLabel('內容標註', { exact: true }).fill('saved only after confirmation')
  const url = '**/api/training/datasets/' + record.id
  await page.route(url, async (route) => {
    if (route.request().method() === 'PUT')
      await route.fulfill({ status: 409, json: { detail: '版本已更新' } })
    else await route.continue()
  })
  await page.getByRole('button', { name: '保存並看下一張', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('版本已更新')
  await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue(
    'saved only after confirmation',
  )
  await expect(page.locator('.training-image-form h2')).toHaveText('圖片 1 / 3')
  await page.unroute(url)
  await page.getByRole('button', { name: '保存並看下一張', exact: true }).click()
  await expect(page.locator('.training-image-form h2')).toHaveText('圖片 2 / 3')
  const result = await (await request.get('/api/training/datasets/' + record.id)).json()
  expect(result.revision).toBe(2)
  expect(result.dataset.images[0].caption.content).toBe('saved only after confirmation')
  expect(result.dataset.images[0].caption.status).toBe('pending')
})

test('gallery masonry preserves the real image ratios and the ordered card list', async ({
  page,
  request,
}) => {
  await request.post('/qa/artwork-set')
  await page.goto('/#/gallery')
  const cards = page.locator('.artwork-card')
  await expect(cards.first()).toBeVisible()
  const order = await cards.locator('.card-title h2').allTextContents()
  await page.getByRole('button', { name: '瀑布流', exact: true }).click()
  expect(await cards.locator('.card-title h2').allTextContents()).toEqual(order)
  for (let index = 0; index < 5; index++) {
    const cover = cards.nth(index).locator('.artwork-cover')
    const img = cover.locator('img')
    await expect
      .poll(() => img.evaluate((image: HTMLImageElement) => image.naturalWidth))
      .toBeGreaterThan(0)
    const ratio = await img.evaluate(
      (image: HTMLImageElement) => image.naturalWidth / image.naturalHeight,
    )
    await expect
      .poll(async () => {
        const b = await cover.boundingBox()
        return Math.abs(b!.width / b!.height - ratio)
      })
      .toBeLessThan(0.02)
  }
  await page.getByRole('button', { name: '固定', exact: true }).click()
  const cover = await cards.first().locator('.artwork-cover').boundingBox()
  expect(Math.abs(cover!.width - cover!.height)).toBeLessThan(1)
})
