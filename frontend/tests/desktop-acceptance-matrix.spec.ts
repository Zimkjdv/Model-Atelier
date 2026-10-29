import { test, expect, type Page, type Locator, type TestInfo } from '@playwright/test'
import { createHash, randomUUID } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'

const preview = new URL('../../docs/ui-redesign/preview.html', import.meta.url)
const hash = (value: Buffer) => createHash('sha256').update(value).digest('hex')
const dimensions = [
  [1280, 800],
  [1440, 900],
  [1920, 1080],
] as const
const purposes = ['文字創作', '圖片重繪', '局部修補', '結構引導', '風格參考']
const categories = ['Checkpoint', 'LoRA', '結構控制', '元件', 'FLUX 元件']
test.use({ viewport: { width: 1440, height: 900 } })

async function geometry(locator: Locator) {
  const box = await locator.first().boundingBox()
  expect(box).not.toBeNull()
  return box!
}
async function aligned(actual: Locator, reference: Locator, fields = ['x', 'width']) {
  const a = await geometry(actual),
    b = await geometry(reference)
  for (const field of fields as ('x' | 'y' | 'width' | 'height')[])
    expect(Math.abs(a[field] - b[field]), field).toBeLessThanOrEqual(3)
  return { actual: a, preview: b }
}
async function style(locator: Locator) {
  return locator.first().evaluate((element) => {
    const s = getComputedStyle(element)
    return { background: s.backgroundColor, border: s.borderColor, radius: s.borderRadius }
  })
}
async function svg(locator: Locator) {
  return locator.evaluate((element) => ({
    width: element.getBoundingClientRect().width,
    height: element.getBoundingClientRect().height,
    children: [...element.children].map((child) => ({
      tag: child.tagName,
      attributes: Object.fromEntries(
        [...child.attributes]
          .filter((a) => !a.name.startsWith('data-v-'))
          .map((a) => [a.name, a.value]),
      ),
    })),
  }))
}
async function fit(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
    true,
  )
}
async function reveal(page: Page, selector: string) {
  await page.locator(selector).evaluate((element) => {
    for (let parent = element.parentElement; parent; parent = parent.parentElement)
      if (parent instanceof HTMLDetailsElement) parent.open = true
  })
}
async function evidence(info: TestInfo, name: string, rows: unknown, page: Page) {
  const bytes = await readFile(preview)
  const path = info.outputPath(name + '.json')
  await writeFile(
    path,
    JSON.stringify({ preview_sha256: hash(bytes), viewport: page.viewportSize(), rows }, null, 2),
  )
  await info.attach(name, { path, contentType: 'application/json' })
}

test('five purpose icon shapes and sizes match the unchanged approved preview', async ({
  page,
  context,
}) => {
  await page.goto('/#/studio/checkpoint')
  const ref = await context.newPage()
  await ref.goto(preview.href + '#studio')
  for (let i = 0; i < purposes.length; i++)
    expect(await svg(page.locator('.workflow-switch button svg').nth(i)), purposes[i]).toEqual(
      await svg(ref.locator('.tasks button svg').nth(i)),
    )
  await ref.close()
})

for (const [width, height] of dimensions) {
  test(`model five-category two-layout matrix at ${width}x${height}`, async ({
    page,
    context,
    request,
  }, info) => {
    await page.setViewportSize({ width, height })
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await request.post('/qa/flux-extensions')
    const engine = (await (await request.get('/api/settings')).json()).comfy_url
    for (const endpoint of ['controlnets', 'reference-components']) {
      const r = await request.post('/api/' + endpoint + '/sync', {
        data: endpoint === 'reference-components' ? { comfy_url: engine } : { engine_url: engine },
      })
      expect(r.ok(), await r.text()).toBe(true)
    }
    const before = (await (await request.get('/qa/state')).json()).prompts
    const ref = await context.newPage()
    await ref.setViewportSize({ width, height })
    await ref.goto(preview.href + '#models')
    await page.goto('/#/models')
    await expect(page.getByRole('button', { name: '清單', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    const rows: unknown[] = []
    for (const category of categories) {
      await test.step(category + ' list and cards', async () => {
        await page.getByRole('tab', { name: category, exact: true }).click()
        await ref.locator('[data-modeltype="' + category + '"]').click()
        const panel = page.getByRole('tabpanel').filter({ visible: true })
        const collection =
          category === 'Checkpoint'
            ? panel.locator('.model-grid')
            : panel.locator('.model-collection').first()
        await expect(collection.locator(':scope > article').first()).toBeVisible()
        const beforeNames = await panel.locator('.model-entry-info > :is(h2, h3)').allTextContents()
        const sync = page.getByRole('button', {
          name: '同步' + category + '清單',
          exact: true,
        })
        await expect(sync).toBeEnabled()
        const endpoint = [
          '/api/models/sync',
          '/api/loras/sync',
          '/api/controlnets/sync',
          '/api/reference-components/sync',
          '/api/flux/components/sync',
        ][categories.indexOf(category)]
        const synced = page.waitForResponse(
          (r) => new URL(r.url()).pathname === endpoint && r.request().method() === 'POST',
        )
        await sync.click()
        const syncResponse = await synced
        expect(syncResponse.ok(), await syncResponse.text()).toBe(true)
        expect(beforeNames.length).toBeGreaterThan(0)
        // Reload the saved inventory before geometric comparison; transient sync feedback
        // deliberately occupies space and must remain available to the user.
        await page.reload()
        await page.getByRole('tab', { name: category, exact: true }).click()
        await expect(collection.locator(':scope > article').first()).toBeVisible()
        for (const layout of ['清單', '卡片']) {
          await page.getByRole('button', { name: layout, exact: true }).click()
          await ref.locator('[data-model-view="' + layout + '"]').click()
          const baseline = ref.locator(layout === '清單' ? '.model-list' : '.model-cards')
          const measured = await aligned(collection, baseline, ['x', 'y', 'width'])
          const entry = collection.locator(':scope > article').first()
          const referenceEntry = baseline.locator(':scope > article').first()
          // The row contents must follow the reference, not only its outer width.
          await expect(entry.locator(':scope > .model-entry-info > details')).toHaveCount(1)
          await expect(entry.locator(':scope > .model-entry-status > .status')).toBeVisible()
          await expect(entry.locator(':scope > .model-entry-action > button')).toBeVisible()
          const appearance = (locator: Locator) =>
            locator.evaluate((element) => {
              const s = getComputedStyle(element)
              return { font: s.fontSize, weight: s.fontWeight, color: s.color, margin: s.marginTop }
            })
          expect(await appearance(entry.locator('.model-entry-info > :is(h2, h3)'))).toEqual(
            await appearance(referenceEntry.locator('.model-info > strong')),
          )
          expect(await appearance(entry.locator('.model-entry-info > details > summary'))).toEqual(
            await appearance(referenceEntry.locator('.model-metadata > summary')),
          )
          expect(await style(entry.locator('.status'))).toEqual(
            await style(referenceEntry.locator('.model-status')),
          )
          expect(await style(entry.locator('.model-entry-action > button'))).toEqual(
            await style(referenceEntry.locator('.model-entry-action > button')),
          )
          expect(await appearance(page.getByRole('tab', { name: category, exact: true }))).toEqual(
            await appearance(ref.locator('[data-modeltype="' + category + '"]')),
          )
          if (layout === '清單') {
            const top = await geometry(entry.locator('.model-entry-status'))
            const action = await geometry(entry.locator('.model-entry-action'))
            expect(
              Math.abs(top.y + top.height / 2 - action.y - action.height / 2),
            ).toBeLessThanOrEqual(1)
          }
          if (layout === '卡片') {
            expect(
              await collection.evaluate(
                (e) => getComputedStyle(e).gridTemplateColumns.split(' ').length,
              ),
            ).toBe(3)
            expect(await style(collection.locator(':scope > article'))).toEqual(
              await style(baseline.locator(':scope > article')),
            )
            await aligned(
              collection.locator(':scope > article'),
              baseline.locator(':scope > article'),
              ['width'],
            )
          }
          await fit(page)
          rows.push({
            category,
            layout,
            count: await panel
              .locator(category === 'Checkpoint' ? '.model-card' : '.model-collection > article')
              .count(),
            geometry: measured,
          })
          await page.screenshot({
            path: info.outputPath(`${category}-${layout}.png`),
            fullPage: true,
          })
        }
        expect(await panel.locator('.model-entry-info > :is(h2, h3)').allTextContents()).toEqual(
          beforeNames,
        )
        const edit = {
          Checkpoint: ['編輯資料', '模型版本', '取消', '.model-details > summary'],
          LoRA: ['編輯 LoRA 資料', 'LoRA 版本', '取消 LoRA 編輯', '.collection-details > summary'],
          結構控制: [
            '編輯 ControlNet 資料',
            'ControlNet 版本',
            '取消 ControlNet 編輯',
            '.collection-details > summary',
          ],
          元件: ['編輯元件資料', '版本', '結束元件編輯', ''],
          'FLUX 元件': ['', '元件版本', '取消元件編輯', ''],
        }[category]!
        if (edit[3]) await panel.locator(edit[3]).first().click()
        await panel
          .getByRole('button', {
            name: category === 'FLUX 元件' ? /^編輯 FLUX 元件：/ : edit[0],
            exact: category !== 'FLUX 元件',
          })
          .first()
          .click()
        const input = panel.getByLabel(edit[1], { exact: true })
        await input.fill('matrix unsaved version')
        await expect(sync).toBeDisabled()
        await page.getByRole('button', { name: '清單', exact: true }).click()
        await expect(input).toHaveValue('matrix unsaved version')
        await page.getByRole('button', { name: '卡片', exact: true }).click()
        await expect(input).toHaveValue('matrix unsaved version')
        await panel.getByRole('button', { name: edit[2], exact: true }).click()
        await expect(sync).toBeEnabled()
        await page.getByRole('button', { name: '清單', exact: true }).click()
      })
    }
    expect(rows).toHaveLength(10)
    expect(errors).toEqual([])
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
    await evidence(info, `models-${width}`, rows, page)
    await ref.close()
  })

  test(`training four-stage matrix at ${width}x${height}`, async ({
    page,
    context,
    request,
  }, info) => {
    await page.setViewportSize({ width, height })
    const initial = (await (await request.get('/qa/state')).json()).prompts
    const prepared = await (await request.post('/qa/training-review')).json()
    const ref = await context.newPage()
    await ref.setViewportSize({ width, height })
    await ref.goto(preview.href + '#training')
    await page.goto('/#/training')
    await page.locator('.training-dataset-management > summary').click()
    await page.getByLabel('原圖來源目錄', { exact: true }).fill(prepared.source_root)
    await page.getByLabel('資料清單 JSON', { exact: true }).setInputFiles({
      name: 'matrix-review.json',
      mimeType: 'application/json',
      buffer: Buffer.from(prepared.manifest_json),
    })
    const importing = page.waitForResponse(
      (r) =>
        new URL(r.url()).pathname === '/api/training/datasets' && r.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '匯入待審查清單', exact: true }).click()
    const imported = await importing
    expect(imported.ok(), await imported.text()).toBe(true)
    const dataset = await imported.json()
    await expect(page.locator('.training-review-grid')).toBeVisible()
    const rows: unknown[] = []
    await page.evaluate(() => window.scrollTo(0, 0))
    const bar = await aligned(page.locator('.training-tabs'), ref.locator('.stagebar'), [
      'x',
      'y',
      'width',
    ])
    expect(
      await page
        .locator('.training-review-grid')
        .evaluate((e) => getComputedStyle(e).gridTemplateColumns),
    ).toBe(
      await ref
        .locator('.training-review')
        .evaluate((e) => getComputedStyle(e).gridTemplateColumns),
    )
    await expect(page.getByLabel('只顯示待補項目', { exact: true })).toBeChecked()
    await aligned(page.locator('.training-tabs'), ref.locator('.stagebar'), ['height'])
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
    ).toBeDisabled()
    await expect(page.locator('.training-check-row')).toHaveCount(4)
    await expect(page.locator('.training-check-row .warning').first()).toBeVisible()
    await page.getByRole('button', { name: '回到待補項目', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }),
    ).toHaveAttribute('aria-pressed', 'true')
    await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
    await page.getByLabel('內容標註', { exact: true }).fill('matrix self-authored illustration')
    await page.locator('.review-extra-fields > summary').click()
    await page.getByLabel('標註狀態', { exact: true }).selectOption('approved')
    await page.getByLabel('標註審查人', { exact: true }).fill('matrix reviewer')
    await page.getByLabel('訓練用途紀錄', { exact: true }).selectOption('recorded')
    await page
      .getByLabel('來源用途依據', { exact: true })
      .fill('Self-authored synthetic test image')
    await page.getByLabel('來源審查人', { exact: true }).fill('matrix reviewer')
    // Stage 1 -> 2 -> 1 must retain the unsaved review; moving to control requires a decision.
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
    await expect(page.getByLabel('內容標註', { exact: true })).toHaveValue(
      'matrix self-authored illustration',
    )
    page.once('dialog', (event) => event.dismiss())
    await page.getByRole('button', { name: '3 準備訓練 凍結設定', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }),
    ).toHaveAttribute('aria-pressed', 'true')
    await page.getByRole('button', { name: '保存並看下一張', exact: true }).click()
    await expect
      .poll(
        async () =>
          (await (await request.get('/api/training/datasets/' + dataset.id)).json()).revision,
      )
      .toBe(2)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.locator('.review-extra-fields > summary').click()
    await page.locator('.training-dataset-management > summary').click()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: info.outputPath('stage-1.png'), fullPage: true })
    rows.push({ stage: 1, dataset_id: dataset.id, revision: 2, stagebar: bar, dirty_guard: true })
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await ref.locator('[data-stage="1"]').click()
    await expect(page.getByRole('status').filter({ hasText: '資料出口檢查通過' })).toBeVisible()
    await expect(page.locator('.training-check-row .warning')).toHaveCount(0)
    await aligned(page.locator('.training-export-check'), ref.locator('.training-export'))
    const exporting = page.waitForResponse(
      (r) =>
        /\/api\/training\/datasets\/[^/]+\/exports$/.test(new URL(r.url()).pathname) &&
        r.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }).click()
    const response = await exporting
    expect(response.ok(), await response.text()).toBe(true)
    const bundle = await response.json()
    expect(bundle.dataset_id).toBe(dataset.id)
    expect(bundle.revision).toBe(2)
    expect(bundle.report.bundle_verified).toBe(true)
    expect(bundle.report.train_count).toBe(1)
    expect(bundle.report.training_started).toBe(false)
    await expect(page.getByRole('status').filter({ hasText: '匯出狀態：completed' })).toBeVisible()
    await page.screenshot({ path: info.outputPath('stage-2.png'), fullPage: true })
    rows.push({
      stage: 2,
      export_id: bundle.request_id,
      status: bundle.status,
      dataset_id: dataset.id,
      report: bundle.report,
    })
    const runId = randomUUID()
    const run: any = {
      run_id: runId,
      status: 'prepared',
      resources_released: true,
      manifest_sha256: bundle.manifest_sha256,
      configuration: { label: 'Synthetic stage matrix', max_steps: 12 },
      dataset: { id: dataset.id, export_id: bundle.request_id },
      base: {},
      environment: {},
      state: { steps_completed: 0 },
      resume: null,
      checkpoints: [],
      resources: null,
      artifacts: null,
      log_tail: 'matrix synthetic log',
      start_requested: false,
    }
    let receipt: any = null,
      prepares = 0,
      starts = 0,
      failRead = false
    await page.route('**/api/training/control', async (route) => {
      const actual = await (await route.fetch()).json()
      await route.fulfill({
        json: { ...actual, runs: receipt ? [run] : [], requests: receipt ? [receipt] : [] },
      })
    })
    await page.route('**/api/training/runtime/check', (route) =>
      route.fulfill({ json: { ready: true, issues: [] } }),
    )
    await page.route('**/api/training/requests', async (route) => {
      prepares++
      expect(route.request().postDataJSON().export_id).toBe(bundle.request_id)
      expect(route.request().postDataJSON().max_steps).toBe(12)
      run.configuration = { ...route.request().postDataJSON() }
      receipt = {
        request_id: route.request().postDataJSON().request_id,
        run_id: runId,
        status: 'prepared',
      }
      await route.fulfill({ status: 202, json: receipt })
    })
    await page.route('**/api/training/requests/*', (route) => route.fulfill({ json: receipt }))
    await page.route('**/api/training/runs/' + runId, (route) =>
      route.fulfill(
        failRead
          ? { status: 503, json: { detail: 'matrix temporarily unavailable' } }
          : { json: run },
      ),
    )
    await page.route('**/api/training/runs/*/start', (route) => {
      starts++
      return route.fulfill({ status: 500 })
    })
    await page.getByRole('button', { name: '3 準備訓練 凍結設定', exact: true }).click()
    await ref.locator('[data-stage="2"]').click()
    await page.locator('.training-runtime-check > summary').click()
    await page.getByRole('button', { name: '檢查獨立訓練環境', exact: true }).click()
    await page.getByLabel('已封存資料包', { exact: true }).selectOption(bundle.request_id)
    await page.getByLabel('訓練名稱', { exact: true }).fill('Synthetic stage matrix')
    await expect(page.getByLabel('基礎模型（固定）')).toHaveValue('Animagine XL 4.0 Opt')
    await expect(page.getByLabel('基礎模型（固定）')).toHaveAttribute('readonly', '')
    await page.locator('.training-prepare-parameters > summary').click()
    await page.getByLabel('訓練 seed', { exact: true }).fill('4294967295')
    await page.getByLabel('總更新步數', { exact: true }).fill('12')
    await page.getByLabel('保存間隔（步）', { exact: true }).fill('4')
    await page.getByLabel('總更新步數', { exact: true }).fill('0')
    await page.locator('.training-prepare-parameters > summary').click()
    await page.getByRole('button', { name: '準備新 run（不開始訓練）', exact: true }).click()
    await expect(page.getByLabel('總更新步數', { exact: true })).toBeVisible()
    expect(prepares).toBe(0)
    await page.getByLabel('總更新步數', { exact: true }).fill('12')
    await page.getByRole('button', { name: '4 執行與產物 追蹤結果', exact: true }).click()
    await page.getByRole('button', { name: '3 準備訓練 凍結設定', exact: true }).click()
    await expect(page.getByLabel('訓練 seed', { exact: true })).toHaveValue('4294967295')
    await page.getByRole('button', { name: '準備新 run（不開始訓練）', exact: true }).click()
    await page.getByRole('button', { name: '開啟新 run', exact: true }).click()
    await page.locator('.training-prepare-parameters > summary').click()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: info.outputPath('stage-3.png'), fullPage: true })
    rows.push({
      stage: 3,
      export_id: bundle.request_id,
      synthetic_run_id: runId,
      explicit_prepares: prepares,
      starts,
    })
    await page.getByRole('button', { name: '4 執行與產物 追蹤結果', exact: true }).click()
    await ref.locator('[data-stage="3"]').click()
    const summary = page.getByRole('region', { name: '訓練執行摘要', exact: true })
    await expect(summary.locator('.training-kpi strong')).toHaveText('0')
    await aligned(summary, ref.locator('.training-run-grid'))
    await expect(page.locator('.training-run-management')).not.toHaveAttribute('open', '')
    await summary.getByRole('button', { name: '查看日誌', exact: true }).click()
    await expect(page.locator('#training-run-log')).toHaveAttribute('open', '')
    await expect(page.locator('.training-run-management')).toHaveAttribute('open', '')
    await summary.getByRole('button', { name: '查看產物與固定比較', exact: true }).click()
    await expect(page.locator('#training-artifacts')).toBeFocused()
    await page.locator('.training-run-management > summary').click()
    run.state = { steps_completed: 5 }
    await summary.getByRole('button', { name: '更新執行摘要', exact: true }).click()
    await expect(summary.getByRole('progressbar')).toHaveAttribute('value', '5')
    failRead = true
    await summary.getByRole('button', { name: '更新執行摘要', exact: true }).click()
    await expect(summary.getByRole('status')).toContainText('保留上次快照')
    await expect(summary.locator('.training-kpi strong')).toHaveText('5')
    failRead = false
    run.state = {}
    await summary.getByRole('button', { name: '更新執行摘要', exact: true }).click()
    await expect(summary.locator('.training-kpi strong')).toHaveText('未知')
    await expect(summary.getByRole('progressbar')).toHaveCount(0)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: info.outputPath('stage-4.png'), fullPage: true })
    rows.push({
      stage: 4,
      synthetic_run_id: runId,
      progress: [0, 5, 'unknown'],
      stale_snapshot_guard: true,
      starts,
    })
    expect(prepares).toBe(1)
    expect(starts).toBe(0)
    await fit(page)
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(initial)
    await evidence(info, `training-${width}`, rows, page)
    await ref.close()
  })

  test(`purpose and architecture support matrix at ${width}x${height}`, async ({
    page,
    context,
    request,
  }, info) => {
    await page.setViewportSize({ width, height })
    const before = (await (await request.get('/qa/state')).json()).prompts
    const ref = await context.newPage()
    await ref.setViewportSize({ width, height })
    await ref.goto(preview.href + '#studio')
    await page.goto('/#/studio/checkpoint')
    const rows: unknown[] = []
    const workflow = page.getByRole('group', { name: '創作工作流程', exact: true })
    for (const [index, route, input] of [
      [0, 'checkpoint', '#draft-prompt'],
      [1, 'checkpoint', '#draft-prompt'],
      [2, 'inpaint', '#inpaint-prompt'],
      [3, 'control', '#control-prompt'],
      [4, 'reference', '#reference-prompt'],
    ] as const) {
      await workflow.getByRole('button', { name: purposes[index], exact: true }).click()
      await ref.locator('[data-vmode="' + index + '"]').click()
      await expect(page).toHaveURL(new RegExp('#/studio/' + route + '$'))
      await expect(
        workflow.getByRole('button', { name: purposes[index], exact: true }),
      ).toHaveAttribute('aria-pressed', 'true')
      await page.locator(input).fill('matrix preserve ' + purposes[index])
      if (index < 2)
        await expect(page.locator('#checkpoint-workflow')).toHaveValue(
          index ? 'image2image' : 'text2image',
        )
      if (index === 2)
        await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
      if (index === 2) {
        await reveal(page, '#inpaint-model')
        for (const variant of ['general', 'fooocus-v2.6']) {
          await page.locator('#inpaint-model').selectOption(variant)
          await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
        }
        await page.locator('#inpaint-model').selectOption('general')
        await expect(page.getByRole('button', { name: '遮罩編輯', exact: true })).toBeVisible()
        await expect(page.getByRole('button', { name: '生成結果', exact: true })).toBeVisible()
      }
      if (index === 3) {
        await reveal(page, '#control-kind')
        for (const kind of ['canny', 'pose', 'depth']) {
          await page.locator('#control-kind').selectOption(kind)
          await expect(page.locator('#control-kind')).toHaveValue(kind)
        }
        await page.locator('#control-kind').selectOption('canny')
        await expect(page.getByRole('button', { name: '結構預覽', exact: true })).toBeVisible()
      }
      if (index === 4) {
        await reveal(page, '#reference-mode')
        for (const mode of ['style', 'character']) {
          await page.locator('#reference-mode').selectOption(mode)
          await expect(page.locator('#reference-mode')).toHaveValue(mode)
        }
      }
      const measured = await aligned(
        page.locator('.studio-settings').filter({ visible: true }),
        ref.locator('.controls'),
        ['x', 'width'],
      )
      for (let i = 0; i < purposes.length; i++)
        expect(await svg(workflow.locator('svg').nth(i))).toEqual(
          await svg(ref.locator('.tasks svg').nth(i)),
        )
      const button = await geometry(
        page.locator('.generation-submit > button.primary').filter({ visible: true }),
      )
      expect(button.y + button.height).toBeLessThanOrEqual(height + 1)
      await fit(page)
      rows.push({
        family: 'Checkpoint',
        purpose: purposes[index],
        route,
        form_geometry: measured,
        no_implicit_submission: true,
      })
      await page.screenshot({ path: info.outputPath(`checkpoint-${index}.png`), fullPage: true })
    }
    await page.goto('/#/studio/flux')
    await workflow.getByRole('button', { name: purposes[0], exact: true }).click()
    await expect(page.locator('#flux-prompt')).toBeVisible()
    await page.locator('#flux-prompt').fill('independent flux text form')
    rows.push({
      family: 'FLUX',
      purpose: purposes[0],
      workflow: 'flux1-schnell-text2image-v1',
      form: 'split four components',
    })
    await workflow.getByRole('button', { name: purposes[1], exact: true }).click()
    await expect(page.locator('#flux-extension-kind')).toHaveValue('image')
    await expect(page.locator('.studio-settings').filter({ visible: true })).toContainText(
      '固定 512×512',
    )
    await page.locator('#flux-extension-prompt').fill('independent flux image form')
    await reveal(page, '#flux-extension-denoise')
    await page.locator('#flux-extension-denoise').fill('1')
    await expect(page.locator('#flux-extension-denoise')).toHaveAttribute('aria-invalid', 'true')
    await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
    rows.push({
      family: 'FLUX',
      purpose: purposes[1],
      workflow: 'flux1-schnell-image2image-v1',
      restriction: '512×512 / 4 steps / FP8 / CPU; denoise below 1',
    })
    for (const index of [2, 3, 4]) {
      await workflow.getByRole('button', { name: purposes[index], exact: true }).click()
      await expect(page).toHaveURL(
        new RegExp('#/studio/' + ['inpaint', 'control', 'reference'][index - 2] + '$'),
      )
      await expect(page.locator('.architecture-switch')).toHaveCount(0)
      rows.push({
        family: 'FLUX',
        purpose: purposes[index],
        supported: false,
        visible_behavior: 'opens independent Checkpoint workflow; no FLUX conversion or submission',
      })
      await page.goto('/#/studio/flux')
      await workflow.getByRole('button', { name: purposes[0], exact: true }).click()
      await expect(page.locator('#flux-prompt')).toHaveValue('independent flux text form')
    }
    await fit(page)
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
    await evidence(info, `purposes-${width}`, rows, page)
    await ref.close()
  })
}
