import { test, expect, type APIRequestContext } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { randomUUID } from 'node:crypto'
import { readFile, realpath, writeFile } from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import type { DatasetReview } from '../src/trainingTypes'

async function createReview(request: APIRequestContext, character = false) {
  const fixture = await (await request.post('/qa/training-review?count=6')).json()
  const manifest = JSON.parse(fixture.manifest_json)
  if (character) manifest.kind = 'character'
  for (const image of manifest.images) {
    if (image.split !== 'train') continue
    image.caption = {
      ...image.caption,
      content: 'Self-authored color block',
      status: 'approved',
      reviewed_by: 'fixture reviewer',
    }
    image.provenance = {
      ...image.provenance,
      training_use: 'recorded',
      usage_note: 'Self-authored fixture, not artist data',
      reviewed_by: 'fixture reviewer',
    }
    if (character) {
      image.identity = 'target'
      image.character_ids = [manifest.subject_id]
    }
  }
  const response = await request.post('/api/training/datasets', {
    data: {
      request_id: randomUUID(),
      source_root: fixture.source_root,
      manifest_json: JSON.stringify(manifest),
    },
  })
  expect(response.ok(), await response.text()).toBe(true)
  return { fixture, value: (await response.json()) as DatasetReview }
}

async function saveReview(request: APIRequestContext, value: DatasetReview) {
  const keys = [
    'id',
    'group_id',
    'split',
    'exclusion_reason',
    'exposure',
    'identity',
    'character_ids',
    'caption',
    'provenance',
  ] as const
  const response = await request.put('/api/training/datasets/' + value.id, {
    data: {
      revision: value.revision,
      version: 'review-' + (value.revision + 1),
      images: value.dataset.images.map((image) =>
        Object.fromEntries(keys.map((key) => [key, image[key]])),
      ),
    },
  })
  expect(response.ok(), await response.text()).toBe(true)
  return (await response.json()) as DatasetReview
}

for (const [width, height] of [
  [1280, 800],
  [1440, 900],
  [1920, 1080],
]) {
  test(`candidate review progress excludes holdouts and uses only saved checks at ${width}px`, async ({
    page,
    request,
  }, info) => {
    const { value } = await createReview(request)
    let finalPreviews = 0
    page.on('request', (request) => {
      if (request.url().includes('/images/img-0006')) finalPreviews++
    })
    await page.setViewportSize({ width: width!, height: height! })
    await page.goto('/#/training')
    await expect(page.locator('.training-progress')).toContainText('訓練候選標註：3 / 3 通過')
    await expect(page.locator('.training-progress')).toContainText('待處理候選 0 張')
    await expect(page.getByRole('progressbar', { name: '訓練候選標註審查進度' })).toHaveAttribute(
      'max',
      '3',
    )
    await expect(page.getByRole('progressbar', { name: '訓練候選標註審查進度' })).toHaveAttribute(
      'value',
      '3',
    )
    const groups = page.getByRole('group', { name: '已保存版本的圖片分組' })
    for (const label of ['訓練候選 3 張', '開發評估 1 張', '最終評估 1 張', '排除 1 張'])
      await expect(groups).toContainText(label)
    await expect(page.locator('.review-export-status')).toHaveText('資料出口：檢查通過')
    await page.getByLabel('只顯示待補項目', { exact: true }).uncheck()
    await page.getByRole('button', { name: 'img-0006 · test', exact: true }).click()
    await expect(page.getByLabel('內容標註', { exact: true })).toBeDisabled()
    await expect(
      page.getByText('最終評估圖保留不預覽，避免在資料審查階段提前曝光。', { exact: true }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'img-0006 · test', exact: true }),
    ).toHaveAttribute('aria-description', '最終評估圖，保留不預覽')
    for (const name of ['img-0002 · validation', 'img-0003 · excluded']) {
      await expect(page.getByRole('button', { name, exact: true })).toHaveAttribute(
        'aria-description',
        '不屬於訓練候選',
      )
    }
    expect(finalPreviews).toBe(0)
    await page.getByRole('button', { name: 'img-0001 · train', exact: true }).click()
    await page.locator('.review-navigation-details > summary').click()
    await expect(page.locator('.review-progress')).toContainText(
      '已保存訓練候選 3 張 · 待處理 0 張',
    )
    await page.locator('.review-navigation-details > summary').click()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: info.outputPath('review-ready.png') })
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
    ).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

    await page.getByLabel('圖片用途', { exact: true }).selectOption('excluded')
    await expect(groups).toContainText('訓練候選 3 張')
    await expect(groups).toContainText('排除 1 張')
    await expect(page.locator('.training-progress')).toContainText('3 / 3 通過')
    await expect(page.locator('.review-export-status')).toContainText('有未保存變更')
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
    ).toBeDisabled()
    await expect(
      page.getByRole('status').filter({ hasText: '有未保存變更，保存後重新檢查才能匯出' }),
    ).toBeVisible()
    await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
    await page.getByLabel('圖片用途', { exact: true }).selectOption('train')
    await page.locator('.review-extra-fields > summary').click()
    await page.getByLabel('標註狀態', { exact: true }).selectOption('rejected')
    await expect(page.locator('.training-progress')).toContainText('3 / 3 通過')
    await page.getByRole('button', { name: '保存並看下一張', exact: true }).click()
    await expect(page.locator('.training-progress')).toContainText('2 / 3 通過')
    await expect(page.locator('.training-progress')).toContainText('待處理候選 1 張')
    const saved = (await (
      await request.get('/api/training/datasets/' + value.id)
    ).json()) as DatasetReview
    expect(saved.dataset.images.map((image) => image.split)).toEqual(
      value.dataset.images.map((image) => image.split),
    )
    expect(saved.dataset.images.find((image) => image.split === 'test')!.caption.status).toBe(
      'pending',
    )
    expect(saved.readiness.data_ready).toBe(false)
    expect(finalPreviews).toBe(0)
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
    ).toBeDisabled()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: info.outputPath('export-blocked.png') })
  })
}

test('source, character and real source integrity failures remain export blockers after captions pass', async ({
  page,
  request,
}) => {
  const { fixture, value } = await createReview(request, true)
  value.dataset.images[0]!.provenance.training_use = 'unreviewed'
  value.dataset.images[0]!.identity = 'other'
  value.dataset.images[3]!.identity = 'other'
  let saved = await saveReview(request, value)
  await page.goto('/#/training')
  await expect(page.locator('.training-progress')).toContainText('3 / 3 通過')
  await expect(page.locator('.training-progress')).toContainText('待處理候選 2 張')
  await expect(page.locator('.review-export-status')).toContainText('未通過檢查')
  await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
  await expect(
    page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
  ).toBeDisabled()
  await expect(
    page.locator('.training-check-row').filter({ hasText: '來源與訓練用途依據' }),
  ).toContainText('1 項需處理')
  await expect(
    page.locator('.training-check-row').filter({ hasText: '分組與角色身分' }),
  ).toContainText('2 項需處理')
  for (const image of saved.dataset.images.filter((image) => image.split === 'train')) {
    image.identity = 'target'
    image.provenance.training_use = 'recorded'
  }
  saved = await saveReview(request, saved)
  expect(saved.readiness.data_ready).toBe(true)
  await page.reload()
  await expect(page.locator('.review-export-status')).toHaveText('資料出口：檢查通過')

  // Only touch the synthetic source made by this test's isolated fixture.
  const source = await realpath(fixture.source_root)
  expect(path.dirname(path.dirname(source)).toLowerCase()).toBe(
    (await realpath(os.tmpdir())).toLowerCase(),
  )
  expect(path.basename(path.dirname(source))).toMatch(/^atelier-browser-/)
  expect(path.basename(source)).toMatch(/^review-source-/)
  const file = path.join(source, 'a.png'),
    original = await readFile(file)
  try {
    await writeFile(file, Buffer.from('synthetic integrity failure'))
    await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
    await page.getByRole('button', { name: '重新檢查原圖與標註', exact: true }).click()
    await expect(
      page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
    ).toBeDisabled()
    await expect(
      page.locator('.training-check-row').filter({ hasText: '原圖與其他完整性' }),
    ).toContainText('1 項需處理')
    await page.getByRole('button', { name: '1 審查資料 補齊描述與來源', exact: true }).click()
    await expect(page.locator('.training-progress')).toContainText('3 / 3 通過')
    await expect(page.locator('.training-progress')).toContainText('待處理候選 1 張')
    await expect(page.locator('.review-export-status')).toContainText('未通過檢查')
  } finally {
    await writeFile(file, original)
  }
})

test('dataset blockers and no candidates never imply a completed review', async ({
  page,
  request,
}) => {
  const { value } = await createReview(request)
  value.dataset.images[1]!.split = 'excluded'
  value.dataset.images[1]!.exclusion_reason = 'Synthetic held-out exclusion'
  let saved = await saveReview(request, value)
  await page.goto('/#/training')
  await expect(page.locator('.training-progress')).toContainText('3 / 3 通過')
  await expect(page.locator('.training-progress')).toContainText('待處理候選 0 張')
  await expect(page.locator('.review-export-status')).toContainText('未通過檢查')
  await expect(page.getByText(/另有 1 項保留圖或資料集層級阻擋/)).toBeVisible()
  for (const image of saved.dataset.images.filter((image) => image.split === 'train')) {
    image.split = 'excluded'
    image.exclusion_reason = 'Synthetic candidate exclusion'
  }
  saved = await saveReview(request, saved)
  await page.reload()
  await expect(
    page.getByText('尚無訓練候選；請先核對資料分組，不將保留或排除圖當成已審查候選。', {
      exact: true,
    }),
  ).toBeVisible()
  await expect(page.getByRole('progressbar', { name: '訓練候選標註審查進度' })).toHaveCount(0)
  await expect(page.locator('.review-export-status')).toContainText('未通過檢查')
  expect(saved.readiness.data_ready).toBe(false)
  await page.getByRole('button', { name: '2 匯出資料包 建立固定版本', exact: true }).click()
  await expect(
    page.getByRole('button', { name: '匯出已審查訓練資料包', exact: true }),
  ).toBeDisabled()
})
