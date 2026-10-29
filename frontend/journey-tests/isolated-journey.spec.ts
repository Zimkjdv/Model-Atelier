import { test, expect, type Page } from '@playwright/test'
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import path from 'node:path'

const digest = (raw: Buffer) => createHash('sha256').update(raw).digest('hex')
const nav = (page: Page, name: string) =>
  page.getByRole('navigation').getByRole('button', { name, exact: true }).click()
const dialog = (page: Page) => page.getByRole('dialog')
const selection = (page: Page) => page.getByRole('region', { name: '已選作品', exact: true })
async function reveal(page: Page, selector: string) {
  await page.locator(selector).evaluate((element: HTMLElement) => {
    for (let parent = element.parentElement; parent; parent = parent.parentElement)
      if (parent instanceof HTMLDetailsElement) parent.open = true
  })
}

test('one isolated source survives the complete creation, library and recovery journey', async ({
  page,
  request,
}, info) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const evidence: Record<string, unknown> = {
    synthetic_engine: true,
    viewport: '1440×900',
    executed_at: new Date().toISOString(),
  }
  const state = await (await request.get('/qa/state')).json()
  expect(state.empty_start, 'Use playwright.journey.config.ts with a fresh --empty fixture').toBe(
    true,
  )
  expect(state.prompts).toBe(0)
  let asset: any, primary: any, companion: any
  const jobs: string[] = []
  const originalHashes: Record<string, string> = {}
  const screenshot = async (name: string) => {
    if (/completed-stage|offline-saved-stage|failed-task/.test(name)) {
      await page.locator('.studio-stage, .studio-fields-scroll').evaluateAll((elements) => {
        for (const element of elements) element.scrollTop = 0
      })
    }
    const path = info.outputPath(name + '.png')
    await page.screenshot({ path, fullPage: true })
    await info.attach(name, { path, contentType: 'image/png' })
  }
  const artworks = async () =>
    (await request.get('/api/library/artworks?scope=all&limit=24')).json()
  const assetRecord = async () => (await request.get('/api/assets/' + asset.id)).json()
  const artworkRecord = async () => (await request.get('/api/artworks/' + primary.id)).json()
  const openArtwork = async () => {
    await page.getByRole('button', { name: '查看作品 ' + primary.title, exact: true }).click()
    await expect(
      dialog(page).getByRole('img', { name: primary.title, exact: true }),
    ).toHaveJSProperty('naturalWidth', 64)
  }

  await test.step('empty collections and empty stage use real zero-record responses', async () => {
    expect((await artworks()).all_total).toBe(0)
    expect(await (await request.get('/api/assets')).json()).toEqual([])
    expect(await (await request.get('/api/jobs')).json()).toEqual([])
    await page.goto('/#/gallery')
    await expect(page.getByRole('heading', { name: '作品庫還沒有作品', exact: true })).toBeVisible()
    await nav(page, '參考素材')
    await expect(
      page.getByRole('heading', { name: '收集你的第一張參考圖', exact: true }),
    ).toBeVisible()
    await nav(page, '創作工作台')
    await expect(page.locator('.empty-canvas')).toContainText('準備下一張作品')
    await screenshot('01-empty-stage')
  })

  await test.step('upload one source, search without results and clear back to the same UUID', async () => {
    await nav(page, '參考素材')
    await page
      .locator('.placeholder')
      .getByRole('button', { name: '上傳素材', exact: true })
      .click()
    const image = await page.evaluate(() => {
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 64
      const context = canvas.getContext('2d')!
      context.fillStyle = '#b8d19e'
      context.fillRect(0, 0, 64, 64)
      context.fillStyle = '#42665a'
      context.fillRect(0, 32, 64, 32)
      return canvas.toDataURL('image/png').split(',')[1]!
    })
    await page.getByLabel('選擇圖片', { exact: true }).setInputFiles({
      name: 'journey-source.png',
      mimeType: 'image/png',
      buffer: Buffer.from(image, 'base64'),
    })
    await expect(page.locator('.asset-card')).toHaveCount(1)
    asset = (await (await request.get('/api/assets')).json())[0]
    expect(asset.width).toBe(64)
    expect(asset.height).toBe(64)
    evidence.asset = { id: asset.id, sha256: asset.sha256 }
    await page
      .getByRole('searchbox', { name: '搜尋素材', exact: true })
      .fill('no-such-journey-source')
    await expect(page.getByRole('heading', { name: '沒有符合的素材', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '清除搜尋與用途篩選', exact: true }).click()
    await expect(page.locator('[data-asset-cover="' + asset.id + '"]')).toBeVisible()
  })

  await test.step('source details retain unsaved edits on cancelled navigation and failed save', async () => {
    await page.locator('[data-asset-cover="' + asset.id + '"]').click()
    await dialog(page).getByRole('button', { name: '編輯素材資料', exact: true }).click()
    await dialog(page).getByLabel('素材名稱', { exact: true }).fill('隔離旅程來源')
    page.once('dialog', (event) => event.dismiss())
    await page.keyboard.press('Escape')
    await expect(dialog(page).getByLabel('素材名稱', { exact: true })).toHaveValue('隔離旅程來源')
    page.once('dialog', (event) => event.dismiss())
    await page.evaluate(() => {
      location.hash = '#/models'
    })
    await expect(page).toHaveURL(/#\/assets$/)
    const pattern = '**/api/assets/' + asset.id
    await page.route(pattern, (route) =>
      route.request().method() === 'PUT'
        ? route.fulfill({ status: 503, json: { detail: '隔離驗收：保存暫時不可用' } })
        : route.continue(),
    )
    await dialog(page).getByRole('button', { name: '保存素材資料', exact: true }).click()
    await expect(dialog(page).getByRole('alert')).toContainText('保存暫時不可用')
    expect((await assetRecord()).title).toBe(asset.title)
    await expect(dialog(page).getByLabel('素材名稱', { exact: true })).toHaveValue('隔離旅程來源')
    await screenshot('02a-asset-save-error')
    await page.unroute(pattern)
    await dialog(page).getByRole('button', { name: '保存素材資料', exact: true }).click()
    await expect(
      dialog(page).getByRole('heading', { name: '隔離旅程來源', exact: true }),
    ).toBeVisible()
    expect((await assetRecord()).sha256).toBe(asset.sha256)
    await screenshot('02-asset-detail')
    await dialog(page).getByRole('button', { name: '用於創作', exact: true }).click()
    await expect(page.locator('#image-asset')).toHaveValue(asset.id)
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(0)
  })

  await test.step('field validation and explicit submissions complete two variants from that source', async () => {
    await request.post('/qa/engine/success')
    await page.locator('#draft-prompt').fill('isolated journey: green mountains')
    await reveal(page, '#seed')
    await page.locator('#seed').fill('18446744073709551616')
    await expect(page.locator('#seed')).toHaveAttribute('aria-invalid', 'true')
    await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
    await page.locator('#seed').fill('18446744073709551615')
    await reveal(page, '#width')
    await page.locator('#width').fill('64')
    await page.locator('#height').fill('64')
    for (const seed of ['18446744073709551615', '20261029']) {
      await page.locator('#seed').fill(seed)
      const response = page.waitForResponse(
        (r) => new URL(r.url()).pathname === '/api/generate' && r.request().method() === 'POST',
      )
      await page.getByRole('button', { name: '生成圖片', exact: true }).click()
      const submitted = await response
      expect(submitted.ok(), await submitted.text()).toBe(true)
      expect(submitted.request().postDataJSON().image_asset_id).toBe(asset.id)
      const job = await submitted.json()
      jobs.push(job.id)
      await reveal(page, '.generation-records > summary')
      await page.getByRole('button', { name: '更新任務狀態', exact: true }).click()
      await expect
        .poll(async () => (await (await request.get('/api/jobs/' + job.id)).json()).status)
        .toBe('completed')
      await page.locator('.stage-job-choice select').selectOption(job.id)
      await expect(page.getByAltText('所選任務的生成結果')).toBeVisible()
      await expect(page.locator('.stage-dimensions')).toHaveText('64 × 64')
      expect((await artworks()).all_total).toBe(0)
    }
    evidence.jobs = jobs
    await screenshot('03-completed-stage')
  })

  await test.step('unsaved result fails offline, recovers and imports only on explicit action', async () => {
    await request.post('/qa/engine/offline')
    await page.locator('.stage-job-choice select').selectOption(jobs[0])
    await expect(page.locator('.studio-preview [role=alert]')).toBeVisible()
    expect((await artworks()).all_total).toBe(0)
    await request.post('/qa/engine/success')
    await page.getByRole('button', { name: '重新讀取結果', exact: true }).click()
    await expect(page.getByAltText('所選任務的生成結果')).toBeVisible()
    await page.getByRole('button', { name: '前往作品庫匯入', exact: true }).click()
    await expect(page.locator('#artwork-job')).toHaveValue(jobs[0])
    for (const job of jobs) {
      await page.locator('#artwork-job').selectOption(job)
      await page.getByRole('button', { name: '匯入／補齊圖片', exact: true }).click()
      await expect(page.getByRole('status').filter({ hasText: '匯入' }).first()).toBeVisible()
      await expect.poll(async () => (await artworks()).all_total).toBe(jobs.indexOf(job) + 1)
    }
    const items = (await artworks()).items
    primary = items.find((item: any) => item.job_id === jobs[0])
    companion = items.find((item: any) => item.job_id === jobs[1])
    expect(primary).toBeTruthy()
    expect(companion).toBeTruthy()
    await page.getByRole('button', { name: '匯入／補齊圖片', exact: true }).click()
    await expect(page.getByRole('button', { name: '匯入／補齊圖片', exact: true })).toBeEnabled()
    expect((await artworks()).all_total).toBe(2)
    for (const item of [primary, companion]) {
      const record = await (await request.get('/api/artworks/' + item.id)).json()
      expect(record.reference_metadata.map((value: any) => value.id)).toContain(asset.id)
      expect(record.sha256).toBe(
        digest(await (await request.get('/api/artworks/' + item.id + '/image')).body()),
      )
      originalHashes[item.id + '.' + record.extension] = record.sha256
    }
    evidence.primary = {
      id: primary.id,
      job_id: primary.job_id,
      sha256: (await artworkRecord()).sha256,
    }
    evidence.companion = { id: companion.id, job_id: companion.job_id }
  })

  await test.step('same imported artwork survives no-results, dirty close, failed and conflicting saves', async () => {
    await page
      .getByRole('searchbox', { name: '搜尋作品', exact: true })
      .fill('no-such-journey-artwork')
    await expect(page.getByRole('heading', { name: '沒有符合的作品', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '清除搜尋與篩選', exact: true }).click()
    await expect(page.locator('.artwork-card')).toHaveCount(2)
    await openArtwork()
    const note = 'same record, still pending after failure'
    await page.getByLabel('作品筆記', { exact: true }).fill(note)
    page.once('dialog', (event) => event.dismiss())
    await dialog(page).getByRole('button', { name: '關閉', exact: true }).click()
    await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(note)
    const pattern = '**/api/artworks/' + primary.id + '/organization'
    await page.route(pattern, (route) =>
      route.fulfill({ status: 503, json: { detail: '隔離驗收：作品保存失敗' } }),
    )
    await dialog(page).getByRole('button', { name: '保存筆記', exact: true }).click()
    await expect(dialog(page).getByRole('alert')).toContainText('作品保存失敗')
    await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(note)
    expect((await artworkRecord()).notes).toBe('')
    await screenshot('03a-artwork-save-error')
    await page.unroute(pattern)
    const current = await artworkRecord()
    expect(
      (
        await request.patch('/api/artworks/' + primary.id + '/organization', {
          data: { revision: current.revision, notes: 'another window saved this' },
        })
      ).ok(),
    ).toBe(true)
    await dialog(page).getByRole('button', { name: '保存筆記', exact: true }).click()
    await expect(dialog(page).getByRole('alert')).toContainText('另一個視窗')
    await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(note)
    expect((await artworkRecord()).notes).toBe('another window saved this')
    page.once('dialog', (event) => event.accept())
    await dialog(page).getByRole('button', { name: '重新讀取筆記', exact: true }).click()
    await expect(page.getByLabel('作品筆記', { exact: true })).toHaveValue(
      'another window saved this',
    )
    await page.getByLabel('作品筆記', { exact: true }).fill('journey verified note')
    await dialog(page).getByRole('button', { name: '保存筆記', exact: true }).click()
    await expect(dialog(page).getByRole('status')).toContainText('筆記已保存')
    await dialog(page).getByRole('tab', { name: '人工評分', exact: true }).click()
    await page.locator('#rating-prompt_adherence').selectOption('3')
    await page.locator('#rating-visual_style').selectOption('5')
    await dialog(page).getByRole('button', { name: '保存評分', exact: true }).click()
    await expect(dialog(page).getByRole('status')).toContainText('評分已保存')
    await dialog(page).getByRole('button', { name: '關閉', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '查看作品 ' + primary.title, exact: true }),
    ).toBeFocused()
    const card = page
      .locator('.artwork-card')
      .filter({ has: page.getByRole('heading', { name: primary.title, exact: true }) })
    await expect(card.locator('.gallery-rating')).toContainText('平均 4.0 / 5 · 已評 2 / 4 項')
    await expect(card.locator('.gallery-date')).not.toBeEmpty()
  })

  await test.step('selection strip leads to explicit comparison; offline ZIP, archive and restore retain bytes', async () => {
    await request.post('/qa/engine/offline')
    for (const item of [primary, companion])
      await page.getByRole('button', { name: '選取作品：' + item.title, exact: true }).click()
    await expect(selection(page)).toContainText('已選 2 件')
    await expect(page.getByRole('region', { name: '作品並排比較', exact: true })).toHaveCount(0)
    await screenshot('04-selection')
    await selection(page).getByRole('button', { name: '並排比較（2–4 張）', exact: true }).click()
    await expect(page).toHaveURL(/#\/gallery\/compare(?:\?job=[^&]+)?$/)
    expect(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('job')).toBe(jobs[0])
    await expect(page.getByRole('region', { name: '作品並排比較', exact: true })).toContainText(
      '作品比較 · 2 / 4',
    )
    await screenshot('05-comparison')
    await page.getByRole('button', { name: '返回作品庫', exact: true }).click()
    const download = page.waitForEvent('download')
    await selection(page).getByRole('button', { name: '批次下載原圖（2 張）', exact: true }).click()
    const file = await download
    const output = info.outputPath('journey-originals.zip')
    await file.saveAs(output)
    const zip = await readFile(output)
    expect(zip.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 3, 4]))
    const python =
      process.env.ATELIER_TEST_PYTHON ||
      path.resolve('../.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
    const checked = await promisify(execFile)(python, [
      '-c',
      'import hashlib,json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print(json.dumps({n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}))',
      output,
    ])
    expect(JSON.parse(checked.stdout)).toEqual(originalHashes)
    evidence.zip_original_hashes = originalHashes
    await info.attach('originals', { path: output, contentType: 'application/zip' })
    await selection(page).getByRole('button', { name: '批次封存', exact: true }).click()
    await expect(page.locator('.artwork-card')).toHaveCount(0)
    await page.getByRole('button', { name: '已封存', exact: true }).click()
    await expect(page.locator('.artwork-card')).toHaveCount(2)
    for (const item of [primary, companion])
      await page.getByRole('button', { name: '選取作品：' + item.title, exact: true }).click()
    await selection(page).getByRole('button', { name: '批次還原', exact: true }).click()
    await expect(page.getByRole('heading', { name: '尚無封存作品', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '全部', exact: true }).click()
    await openArtwork()
    const final = await artworkRecord()
    expect(final.notes).toBe('journey verified note')
    expect(final.archived).toBe(false)
    expect(final.parameters.seed).toBe('18446744073709551615')
    expect(final.sha256).toBe((evidence.primary as any).sha256)
    await dialog(page).getByRole('button', { name: '關閉', exact: true }).click()
    await nav(page, '創作工作台')
    await page.locator('.stage-job-choice select').selectOption(jobs[0])
    await expect(page.getByAltText('所選任務的生成結果')).toBeVisible()
    await expect(page.locator('.stage-caption')).toContainText('顯示已保存原圖，可離線讀取')
    await screenshot('06-offline-saved-stage')
  })

  await test.step('a failed execution from the same source stays failed with no result or implicit retry', async () => {
    await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
    await request.post('/qa/engine/failed')
    await page
      .locator('.preflight-blockers')
      .getByRole('button', { name: '更新引擎選項', exact: true })
      .click()
    await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeEnabled()
    const response = page.waitForResponse(
      (r) => new URL(r.url()).pathname === '/api/generate' && r.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '生成圖片', exact: true }).click()
    const submitted = await response
    expect(submitted.ok(), await submitted.text()).toBe(true)
    expect(submitted.request().postDataJSON().image_asset_id).toBe(asset.id)
    const job = await submitted.json()
    await reveal(page, '.generation-records > summary')
    await page.getByRole('button', { name: '更新任務狀態', exact: true }).click()
    await expect
      .poll(async () => (await (await request.get('/api/jobs/' + job.id)).json()).status)
      .toBe('failed')
    await page.locator('.stage-job-choice select').selectOption(job.id)
    await expect(page.locator('.studio-preview .empty-canvas')).toContainText('此任務尚無完成結果')
    await expect(page.getByAltText('所選任務的生成結果')).toHaveCount(0)
    const failed = await (await request.get('/api/jobs/' + job.id)).json()
    expect(failed.failure_info.code).toBe('execution_failed')
    expect((await request.get('/api/jobs/' + job.id + '/results')).status()).toBe(409)
    evidence.failed_job = {
      id: job.id,
      status: failed.status,
      failure_code: failed.failure_info.code,
    }
    await screenshot('07-failed-task')
    expect((await artworks()).all_total).toBe(2)
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(3)
  })

  await test.step('cached parameters and settings export keep the same source without new submissions', async () => {
    await nav(page, '設定')
    await page.getByRole('tab', { name: '資料與隱私', exact: true }).click()
    await page.getByRole('button', { name: 'Checkpoint 設定匯出／匯入', exact: true }).click()
    await expect(page.locator('#image-asset')).toHaveValue(asset.id)
    await expect(page.locator('#draft-prompt')).toHaveValue('isolated journey: green mountains')
    await page.getByRole('button', { name: '匯出目前創作設定', exact: true }).click()
    await expect(page.getByRole('link', { name: '下載上次匯出的設定', exact: true })).toBeVisible()
    const finalState = await (await request.get('/qa/state')).json()
    expect(finalState.prompts).toBe(3)
    expect(finalState.uploads).toBe(3)
    expect((await artworks()).all_total).toBe(2)
    expect((await assetRecord()).sha256).toBe(asset.sha256)
    expect(errors).toEqual([])
    evidence.final = {
      prompts: finalState.prompts,
      input_uploads: finalState.uploads,
      artworks: 2,
      page_errors: errors,
    }
    const path = info.outputPath('journey-evidence.json')
    await writeFile(path, JSON.stringify(evidence, null, 2))
    await info.attach('identity-chain', { path, contentType: 'application/json' })
  })
})
