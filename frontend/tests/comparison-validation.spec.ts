import { randomUUID } from 'node:crypto'
import { writeFile } from 'node:fs/promises'
import { expect, test, type APIRequestContext, type Page, type TestInfo } from '@playwright/test'
import type { CreationForm } from '../src/creationSettings'

const planner = (page: Page) => page.locator('.experiment-planner')
const stack = (page: Page) => page.getByRole('region', { name: '有序 LoRA 組合實測紀錄' })
const prepare = async (request: APIRequestContext) => {
  const response = await request.post('/qa/comparison-context')
  expect(response.ok()).toBe(true)
  return response.json()
}
test.afterAll(async ({ request }) => {
  const response = await request.post('/qa/comparison-context/reset')
  expect(response.ok()).toBe(true)
})
async function attach(info: TestInfo, name: string, value: unknown) {
  const path = info.outputPath(name)
  await writeFile(path, JSON.stringify(value, null, 2))
  await info.attach(name, { path, contentType: 'application/json' })
}
async function openDraft(page: Page, request: APIRequestContext, settings: CreationForm) {
  const body = { ...settings, title: 'V04 ' + randomUUID() }
  const response = await request.post('/api/drafts', { data: body })
  expect(response.ok()).toBe(true)
  const draft = await response.json()
  await page.goto('/#/studio/checkpoint')
  await page
    .locator('.draft-row')
    .filter({ has: page.getByText(body.title, { exact: true }) })
    .click()
  if (await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).isVisible())
    await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).click()
  await expect(page.locator('#draft-title')).toHaveValue(body.title)
  if (!(await page.locator('#seed').isVisible()))
    await page.getByText('進階設定', { exact: true }).click()
  return draft
}
async function preview(page: Page) {
  const pending = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/experiments/preview' &&
      response.request().method() === 'POST',
  )
  await planner(page).getByRole('button', { name: '預覽比較方案', exact: true }).click()
  const response = await pending
  return {
    status: response.status(),
    request: response.request().postDataJSON(),
    value: await response.json(),
  }
}
async function checkForm(page: Page, settings: CreationForm) {
  for (const [id, key] of Object.entries({
    'draft-title': 'title',
    'draft-model': 'checkpoint',
    'draft-prompt': 'prompt',
    'draft-negative': 'negative_prompt',
    width: 'width',
    height: 'height',
    seed: 'seed',
    steps: 'steps',
    cfg: 'cfg',
    sampler: 'sampler_name',
    scheduler: 'scheduler',
    denoise: 'denoise',
  }))
    await expect(page.locator('#' + id)).toHaveValue(String(settings[key as keyof CreationForm]))
  const rows = page.locator('.lora-item')
  await expect(rows).toHaveCount(settings.loras.length)
  for (const [index, lora] of settings.loras.entries()) {
    await expect(rows.nth(index).getByRole('heading')).toContainText(lora.name)
    await expect(page.getByLabel(`啟用 LoRA ${index + 1}`, { exact: true })).toBeChecked({
      checked: lora.enabled,
    })
    await expect(page.getByLabel(`LoRA ${index + 1} 模型強度`, { exact: true })).toHaveValue(
      String(lora.strength_model),
    )
    await expect(page.getByLabel(`LoRA ${index + 1} CLIP 強度`, { exact: true })).toHaveValue(
      String(lora.strength_clip),
    )
  }
}
async function saveDraft(page: Page) {
  const pending = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/drafts' && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '保存草稿', exact: true }).click()
  const response = await pending
  expect(response.ok()).toBe(true)
  return response.json()
}

for (const width of [1440, 390]) {
  test.describe(`${width}px V04`, () => {
    test.use({ viewport: { width, height: 900 } })
    test.beforeEach(async ({ request }, info) => {
      info.annotations.push({
        type: 'prompts-before',
        description: String((await (await request.get('/qa/state')).json()).prompts),
      })
    })
    test.afterEach(async ({ request, page }, info) => {
      const before = info.annotations.find((item) => item.type === 'prompts-before')!.description
      expect((await (await request.get('/qa/state')).json()).prompts).toBe(Number(before))
      expect(await page.evaluate(() => innerWidth)).toBe(width)
    })

    test('8-step ordered evidence keeps forward and reverse quality conditions separate', async ({
      page,
      request,
    }, info) => {
      const data = await prepare(request)
      await openDraft(page, request, data.settings)
      const area = stack(page)
      await expect(area.getByRole('status')).toContainText('符合歷史條件')
      const forward = area
        .locator('details')
        .filter({ has: page.locator('summary').filter({ hasText: '2026-10-08' }) })
      await forward.locator('summary').click()
      await expect(forward).toContainText('8 steps · CFG 1 · lcm / sgm_uniform')
      await expect(forward.locator('li')).toHaveText([
        /LCM LoRA SDXL.*model 1 \/ CLIP 0/,
        /IKEA instructions SDXL.*model 1 \/ CLIP 1/,
      ])
      await expect(forward).toContainText('29.734 秒／引擎日誌 27.597 秒')
      await expect(forward).toContainText('冷載入')
      await expect(forward).toContainText('對比不足')
      await expect(forward).toContainText('不能推定所有 LoRA 順序等效')
      await expect(forward.getByRole('link')).toHaveAttribute(
        'href',
        /animagine-multi-lora-quality-rtx3060\.md$/,
      )
      await forward.scrollIntoViewIfNeeded()
      await page.screenshot({ path: info.outputPath('forward-8.png') })
      await page.locator('#steps').fill('9')
      await expect(area.getByRole('status')).toContainText('沒有匹配紀錄')
      await page.locator('#steps').fill('8')
      const reversed = page.waitForResponse(
        (response) =>
          response.url().endsWith('/api/loras/stack-validation') &&
          response.request().postDataJSON().loras[0].name === data.settings.loras[1].name,
      )
      await page.getByRole('button', { name: '上移 LoRA 2', exact: true }).click()
      const reverse = await (await reversed).json()
      expect(reverse.matching_parameter_records).toEqual(['animagine-style-lcm-8-rtx3060-20261008'])
      await expect(area.locator('details')).toHaveCount(1)
      await area.locator('summary').click()
      await expect(area.locator('li')).toHaveText([
        /IKEA instructions SDXL.*model 1 \/ CLIP 1/,
        /LCM LoRA SDXL.*model 1 \/ CLIP 0/,
      ])
      await expect(area).toContainText('13.907 秒／引擎日誌 13.422 秒')
      await expect(area).toContainText('部分節點快取')
      await expect(area).toContainText('未改善至推薦品質')
      await page.screenshot({ path: info.outputPath('reverse-8.png') })
      await page.getByLabel('LoRA 1 CLIP 強度', { exact: true }).fill('0.5')
      await expect(area.getByRole('status')).toContainText('沒有匹配紀錄')
      await attach(info, 'ordered-evidence.json', reverse)
    })

    test('targeted model and CLIP axes preserve order, disabled LoRA, exact seed and failed inputs', async ({
      page,
      request,
    }, info) => {
      const data = await prepare(request)
      const choices = [
        data.settings.loras[0],
        { name: 'fixture-disabled', enabled: false, strength_model: 2, strength_clip: -0.25 },
        data.settings.loras[1],
      ]
      const original = await openDraft(page, request, {
        ...data.settings,
        seed: '18446744073709551615',
        loras: choices,
      })
      await planner(page).locator('summary').first().click()
      await page.locator('#experiment-axis').selectOption('lora_strength_model')
      await page.locator('#experiment-values').fill('[-1, 0, 0.5]')
      expect((await preview(page)).status).toBe(422)
      await expect(planner(page).getByRole('alert')).toBeVisible()
      await expect(page.locator('#experiment-lora option')).toHaveCount(3)
      await page.locator('#experiment-lora').selectOption(choices[2].name)
      for (const values of ['[1, 1.0]', '[21]', '["0.5"]']) {
        await page.locator('#experiment-values').fill(values)
        expect((await preview(page)).status).toBe(422)
        await expect(planner(page).getByRole('alert')).toBeVisible()
        await expect(page.locator('#seed')).toHaveValue('18446744073709551615')
      }
      const receipts = []
      for (const [axis, field] of [
        ['lora_strength_model', 'strength_model'],
        ['lora_strength_clip', 'strength_clip'],
      ] as const) {
        await page.locator('#experiment-axis').selectOption(axis)
        await page.locator('#experiment-values').fill('[-1, 0, 0.5]')
        const result = await preview(page)
        expect(result.status).toBe(200)
        const plan = result.value
        for (const variant of plan.variants) {
          const expected = structuredClone(plan.baseline)
          expected.title = variant.settings.title
          expected.loras[2][field] = variant.value
          expect(variant.settings).toEqual(expected)
        }
        const variant = plan.variants[axis === 'lora_strength_model' ? 1 : 0]
        await page.getByRole('button', { name: '載入比較設定 ' + variant.id, exact: true }).click()
        await checkForm(page, variant.settings)
        const saved = await saveDraft(page)
        expect(
          Object.fromEntries(Object.keys(variant.settings).map((key) => [key, saved[key]])),
        ).toEqual(variant.settings)
        receipts.push({ result, saved })
      }
      await page.getByLabel('啟用 LoRA 3', { exact: true }).uncheck()
      expect((await preview(page)).status).toBe(422)
      await expect(page.getByLabel('啟用 LoRA 3', { exact: true })).not.toBeChecked()
      await expect(page.locator('#seed')).toHaveValue('18446744073709551615')
      await page.screenshot({ path: info.outputPath('strength-error.png') })
      const drafts = await (await request.get('/api/drafts')).json()
      expect(drafts.find((item: any) => item.id === original.id).loras).toEqual(choices)
      await attach(info, 'strength-axes.json', receipts)
    })

    test('all four fixed cases load for both checkpoints without dispatching or changing other controls', async ({
      page,
      request,
    }, info) => {
      const data = await prepare(request)
      await openDraft(page, request, {
        ...data.settings,
        loras: [],
        steps: 28,
        cfg: 5,
        sampler_name: 'euler_ancestral',
        scheduler: 'normal',
      })
      await planner(page).locator('summary').first().click()
      const suite = await (await request.get('/api/experiments/suite')).json()
      expect(suite.cases.map((item: any) => item.id)).toEqual([
        'chair',
        'lake',
        'traveler-bookshop',
        'traveler-station',
      ])
      for (const item of suite.cases)
        await planner(page).getByRole('checkbox', { name: item.name, exact: true }).check()
      await page.locator('#experiment-axis').selectOption('seed')
      await page.locator('#experiment-values').fill('["9007199254740993"]')
      const receipts = []
      for (const model of data.models) {
        await page.locator('#draft-model').selectOption(model)
        const result = await preview(page)
        expect(result.status).toBe(200)
        expect(result.value.expected_job_count).toBe(4)
        expect(result.value.suite.sha256).toBe(suite.sha256)
        for (const [index, item] of suite.cases.entries()) {
          const variant = result.value.variants[index]
          expect(variant.case_id).toBe(item.id)
          expect(variant.settings).toEqual({
            ...result.value.baseline,
            title: variant.settings.title,
            prompt: item.prompt,
            seed: '9007199254740993',
          })
          await page
            .getByRole('button', { name: '載入比較設定 ' + variant.id, exact: true })
            .click()
          await checkForm(page, variant.settings)
        }
        await page.screenshot({ path: info.outputPath(model + '-four-cases.png') })
        receipts.push(result)
      }
      await page.locator('#experiment-values').fill('["1", "2", "3"]')
      expect((await preview(page)).status).toBe(422)
      await expect(planner(page).getByRole('alert')).toBeVisible()
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true)
      await attach(info, 'four-cases.json', { suite, receipts })
    })

    test('job and artwork measurements retain original source, durations, zero and unknown values', async ({
      page,
      request,
    }, info) => {
      const data = await prepare(request)
      await page.goto('/#/studio/checkpoint')
      await page.getByRole('button', { name: '任務與歷史資訊', exact: true }).click()
      const snapshots = []
      async function check(area: ReturnType<Page['locator']>, kind: string) {
        await area.locator('summary').click()
        if (kind === 'legacy') {
          await expect(area).toContainText('沒有提交時的耗時與資源量測，保持未知')
        } else {
          await expect(area).toContainText('原引擎：http://original-measurement.invalid:8188')
          await expect(area).toContainText('http://original-measurement.invalid:8188/system_stats')
          await expect(area).toContainText(
            '平台提交至終態觀察：' + (kind === 'zero' ? '0.000' : '7.000') + ' 秒',
          )
          await expect(area).toContainText(
            '原引擎執行起訖：' + (kind === 'zero' ? '0.000' : '2.500') + ' 秒',
          )
          await expect(area).toContainText('任務專用 VRAM 峰值：未知')
          if (kind === 'measured') {
            await expect(area).toContainText('引擎 RAM 已用／可用：2.00 GiB／6.00 GiB')
            await expect(area).toContainText(
              'Fixture GPU · cuda · 裝置顯存已用／可用：1.00 GiB／3.00 GiB',
            )
            await expect(area).toContainText(
              'Fixture CPU · cpu · 裝置記憶體已用／可用：0.25 GiB／0.00 GiB',
            )
          } else await expect(area).toContainText('引擎 RAM 已用／可用：未知／未知')
        }
      }
      for (const entry of data.outputs) {
        const before = await (await request.get('/api/jobs/' + entry.job.id)).json()
        const row = page.locator('.job').filter({ hasText: entry.job.id })
        await row.getByRole('button', { name: '載入任務詳情', exact: true }).click()
        await check(row.locator('.job-measurements'), entry.kind)
        await row.locator('.job-measurements').scrollIntoViewIfNeeded()
        await page.screenshot({ path: info.outputPath('job-' + entry.kind + '.png') })
        snapshots.push(before)
      }
      await page.getByRole('button', { name: '作品庫', exact: true }).click()
      for (const entry of data.outputs) {
        await page
          .getByRole('button', { name: '查看作品 ' + entry.artwork.title, exact: true })
          .click()
        await page.getByRole('dialog').getByRole('tab', { name: '生成與來源', exact: true }).click()
        const area = page.getByRole('dialog').locator('.job-measurements')
        await check(area, entry.kind)
        await area.locator('p').last().scrollIntoViewIfNeeded()
        await page.screenshot({ path: info.outputPath('artwork-' + entry.kind + '.png') })
        const artwork = await (await request.get('/api/artworks/' + entry.artwork.id)).json()
        expect(artwork.measurements).toEqual(
          snapshots.find((v) => v.id === entry.job.id).measurements,
        )
        expect(await (await request.get('/api/jobs/' + entry.job.id)).json()).toEqual(
          snapshots.find((v) => v.id === entry.job.id),
        )
        await page.getByRole('button', { name: '關閉', exact: true }).click()
      }
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true)
      await attach(info, 'measurements.json', snapshots)
    })
  })
}
