import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
test.use({ viewport: { width: 1440, height: 900 } })

async function openAncestors(page: any, selector: string) {
  await page.locator(selector).evaluate((element: HTMLElement) => {
    let parent = element.parentElement
    while (parent) {
      if (parent instanceof HTMLDetailsElement) parent.open = true
      parent = parent.parentElement
    }
  })
}

test('gallery metadata, average ratings, page size, selection and clear filters', async ({
  page,
  request,
}) => {
  await request.post('/qa/populate')
  const all = await (await request.get('/api/library/artworks?limit=4&scope=all')).json()
  const first = (await (await request.get('/api/library/artworks?limit=4')).json()).items[0]
  const rated = await request.patch('/api/artworks/' + first.id + '/organization', {
    data: {
      revision: first.revision,
      ratings: {
        prompt_adherence: 3,
        character_consistency: null,
        visual_style: 5,
        composition: null,
      },
    },
  })
  expect(rated.ok(), await rated.text()).toBe(true)
  await page.goto('/#/gallery')
  await expect(page.locator('.artwork-card')).toHaveCount(12)
  await expect(page.locator('.gallery-list-meta')).toContainText(
    '全部 ' + all.all_total + ' 張（含封存）',
  )
  const card = page
    .locator('.artwork-card')
    .filter({ has: page.getByRole('heading', { name: first.title, exact: true }) })
  await expect(card.locator('.gallery-rating')).toContainText('平均 4.0 / 5 · 已評 2 / 4 項')
  await expect(card.locator('.gallery-date')).not.toBeEmpty()
  await card.getByRole('button', { name: '選取作品：' + first.title, exact: true }).click()
  await page.getByLabel('每頁作品筆數').selectOption('4')
  await expect(page.locator('.artwork-card')).toHaveCount(4)
  await page.getByRole('button', { name: '下一頁', exact: true }).click()
  await expect(page.locator('.gallery-list-meta')).toContainText('第 2 /')
  await page.getByLabel('每頁作品筆數').selectOption('24')
  await expect(page.locator('.artwork-card')).toHaveCount(24)
  await expect(page.locator('.gallery-list-meta')).toContainText('第 1 /')
  await expect(page.locator('.gallery-selectionbar')).toContainText('已選 1 件')
  await page.getByRole('button', { name: '已封存', exact: true }).click()
  await page
    .getByRole('searchbox', { name: '搜尋作品', exact: true })
    .fill('no-such-artwork-qwerty')
  await expect(page.getByRole('button', { name: '清除搜尋與篩選', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '清除搜尋與篩選', exact: true }).click()
  await expect(page.getByRole('button', { name: '已封存', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByRole('searchbox', { name: '搜尋作品', exact: true })).toHaveValue('')
  await expect(page.locator('.artwork-card').first()).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: '../docs/ui-redesign/platform-gallery-information-fixture.png' })
})

test('asset clear filters preserves archive scope and empty library guides upload', async ({
  page,
}) => {
  await page.goto('/#/assets')
  await page.getByText('素材篩選、整理與流程能力', { exact: true }).click()
  await page.getByRole('button', { name: '查看已封存', exact: true }).click()
  await page.getByRole('button', { name: '角色', exact: true }).click()
  await page.getByRole('searchbox', { name: '搜尋素材', exact: true }).fill('no-such-asset-qwerty')
  await expect(page.getByRole('button', { name: '清除搜尋與用途篩選', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '清除搜尋與用途篩選', exact: true }).click()
  await expect(page.getByRole('searchbox', { name: '搜尋素材', exact: true })).toHaveValue('')
  await expect(page.getByRole('button', { name: '全部', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByRole('button', { name: '查看使用中素材', exact: true })).toBeVisible()
  await page.route('**/api/library/assets?**', (route) =>
    route.fulfill({
      json: { items: [], total: 0, all_total: 0, next_cursor: null, previous_cursor: null },
    }),
  )
  await page.reload()
  await expect(
    page.getByRole('heading', { name: '收集你的第一張參考圖', exact: true }),
  ).toBeVisible()
  await page.locator('.placeholder').getByRole('button', { name: '上傳素材', exact: true }).click()
  await expect(page.locator('input[type=file]')).toBeVisible()
})

test('preflight reports independent field errors beside controls and focuses collapsed fields', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.route('**/api/engine/capabilities', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    await route.fulfill({ json: { ...body, stale: true } })
  })
  await page.goto('/#/studio/checkpoint')
  await openAncestors(page, '#width')
  await page.locator('#width').fill('899')
  await page.locator('#height').fill('0')
  await openAncestors(page, '#seed')
  await page.locator('#seed').fill('18446744073709551616')
  await expect(page.locator('#width')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('#width-preflight-error')).toBeVisible()
  await expect(page.locator('#seed')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('.preflight-blockers')).toContainText('過期')
  await expect(
    page.locator('.preflight-blockers').getByRole('link', { name: '檢查引擎連線', exact: true }),
  ).toBeVisible()
  await page.locator('#seed').evaluate((element: HTMLElement) => {
    const details = element.closest('details')
    if (details) details.open = false
  })
  await page
    .locator('.preflight-fields')
    .getByRole('button', { name: /^Seed：/ })
    .click()
  await expect(page.locator('#seed')).toBeFocused()
  const inputBox = await page.locator('#seed').boundingBox()
  const dockBox = await page.locator('.studio-submit').boundingBox()
  expect(inputBox!.y + inputBox!.height).toBeLessThanOrEqual(dockBox!.y)
  await page.locator('#seed').fill('18446744073709551615')
  await expect(page.locator('#seed')).not.toHaveAttribute('aria-invalid')
  await expect(page.locator('#width')).toHaveValue('899')
  await expect(page.locator('.generation-submit > button.primary')).toBeDisabled()
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  const a11y = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  expect(a11y.violations).toEqual([])
  await page.screenshot({ path: '../docs/ui-redesign/platform-preflight-fields-fixture.png' })
})

test('settings export guide returns to cached parameters and reveals the actual exchange controls', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/#/studio/checkpoint')
  await page.locator('#draft-prompt').fill('preserve these parameters for export')
  await openAncestors(page, '#seed')
  await page.locator('#seed').fill('18446744073709551615')
  await page.getByRole('navigation').getByRole('button', { name: '設定', exact: true }).click()
  await page.getByRole('tab', { name: '資料與隱私', exact: true }).click()
  await page.getByRole('button', { name: 'Checkpoint 設定匯出／匯入', exact: true }).click()
  await expect(page).toHaveURL(/#\/studio\/checkpoint$/)
  await expect(page.locator('.settings-transfer')).toHaveAttribute('open')
  await expect(page.getByRole('button', { name: '匯出目前創作設定', exact: true })).toBeVisible()
  await expect(page.locator('#draft-prompt')).toHaveValue('preserve these parameters for export')
  await expect(page.locator('#seed')).toHaveValue('18446744073709551615')
  await page.getByRole('button', { name: '匯出目前創作設定', exact: true }).click()
  await expect(page.getByRole('link', { name: '下載上次匯出的設定', exact: true })).toBeVisible()
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('training summary uses reported progress, unknowns and failed-read snapshot without starting a run', async ({
  page,
}) => {
  const id = 'b5000000-0000-4000-8000-000000000001'
  const run: any = {
    run_id: id,
    status: 'prepared',
    resources_released: true,
    manifest_sha256: 'a'.repeat(64),
    configuration: { label: 'UI progress fixture', max_steps: 100 },
    state: { steps_completed: 43 },
    checkpoints: [],
    log_tail: 'fixture log',
    start_requested: false,
    dataset: {},
    base: {},
    environment: {},
    resume: null,
    resources: null,
    artifacts: null,
  }
  let fail = false,
    writes = 0
  await page.route('**/api/training/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') {
      writes++
      return route.fulfill({ status: 500 })
    }
    if (path.endsWith('/control'))
      return route.fulfill({ json: { available: true, requests: [], runs: [run], exports: [] } })
    if (path === '/api/training/runs/' + id)
      return route.fulfill(
        fail ? { status: 503, json: { detail: 'fixture unavailable' } } : { json: run },
      )
    await route.continue()
  })
  await page.goto('/#/training')
  await page.getByRole('button', { name: '4 執行與產物 追蹤結果', exact: true }).click()
  const summary = page.getByRole('region', { name: '訓練執行摘要', exact: true })
  await expect(summary.locator('.training-kpi strong')).toHaveText('43')
  await expect(summary.getByRole('progressbar')).toHaveAttribute('value', '43')
  await page.screenshot({ path: '../docs/ui-redesign/platform-training-summary-fixture.png' })
  run.state = {}
  await summary.getByRole('button', { name: '更新執行摘要', exact: true }).click()
  await expect(summary.locator('.training-kpi strong')).toHaveText('未知')
  await expect(summary.getByRole('progressbar')).toHaveCount(0)
  run.state = { last_checkpoint_step: 20 }
  await summary.getByRole('button', { name: '更新執行摘要', exact: true }).click()
  await expect(summary).toContainText('依最後保存 checkpoint')
  fail = true
  await summary.getByRole('button', { name: '更新執行摘要', exact: true }).click()
  await expect(summary).toContainText('保留上次快照')
  await expect(summary.locator('.training-kpi strong')).toHaveText('20')
  await summary.getByRole('button', { name: '查看日誌', exact: true }).click()
  await expect(page.locator('#training-run-log')).toHaveAttribute('open')
  expect(writes).toBe(0)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: '../docs/ui-redesign/platform-training-summary-warning-fixture.png',
  })
})

test('FLUX export guide opens the base exchange even when the cached extension was selected', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/#/studio/flux')
  await page.getByRole('button', { name: 'FLUX LoRA／圖生圖', exact: true }).click()
  await page.getByRole('navigation').getByRole('button', { name: '設定', exact: true }).click()
  await page.getByRole('tab', { name: '資料與隱私', exact: true }).click()
  await page.getByRole('button', { name: 'FLUX 設定匯出／匯入', exact: true }).click()
  await expect(page.locator('.settings-transfer')).toBeVisible()
  await expect(page.getByRole('button', { name: '匯出目前創作設定', exact: true })).toBeVisible()
  await expect(page.locator('#flux-extension-prompt')).toBeHidden()
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('dedicated studio fields show inline contract errors without submitting', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.route('**/api/engine/capabilities', async (route) => {
    const response = await route.fetch()
    await route.fulfill({ json: { ...(await response.json()), stale: true } })
  })
  for (const [route, selector, value, key] of [
    ['inpaint', '#inpaint-feather', '65', 'feather_radius'],
    ['control', '#control-end', '0', 'control_end'],
    ['reference', '#reference-weight', '3', 'reference_weight'],
    ['flux', '#flux-seed', '1e9', 'seed'],
  ]) {
    await page.goto('/#/studio/' + route)
    await openAncestors(page, selector)
    await page.locator(selector).fill(value)
    await expect(page.locator(selector)).toHaveAttribute('aria-invalid', 'true')
    if (route !== 'flux')
      await expect(page.locator('.preflight-blockers')).toContainText('取樣選項')
    await page.locator(selector).evaluate((element: HTMLElement) => {
      const details = element.closest('details')
      if (details) details.open = false
    })
    await page
      .locator('.preflight-fields')
      .getByRole('button')
      .filter({
        hasText:
          key === 'seed'
            ? 'Seed'
            : key === 'control_end'
              ? '控制結束比例'
              : key === 'reference_weight'
                ? '參考權重'
                : '羽化半徑',
      })
      .click()
    await expect(page.locator(selector)).toBeFocused()
    await expect(page.locator('.generation-submit > button.primary')).toBeDisabled()
  }
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})
