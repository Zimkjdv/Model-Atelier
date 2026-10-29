import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import AxeBuilder from '@axe-core/playwright'

const read = async (file: string) => JSON.parse(await readFile('../models/' + file, 'utf8'))
const extras = (await read('simple-creation-extra-templates-v1.json')).templates
const styles = (await read('simple-style-templates-v1.json')).templates
const animagine = await read('animagine-xl-4.0-opt.json')
const pony = await read('pony-v6-xl.json')
let original: Record<string, string>

async function register(request: APIRequestContext, manifest = animagine) {
  expect(
    (
      await request.put('/api/models/metadata', {
        data: {
          engine_url: original.engine_url,
          name: 'demo.safetensors',
          architecture: 'sdxl',
          sha256: manifest.sha256,
        },
      })
    ).ok(),
  ).toBeTruthy()
}
test.beforeEach(async ({ request }) => {
  const catalog = await (await request.get('/api/models')).json()
  original = {
    ...catalog.models.find((v: { name: string }) => v.name === 'demo.safetensors'),
    engine_url: catalog.engine_url,
  }
  await request.post('/qa/engine/success')
  await request.post('/qa/simple-creation')
  await request.post('/qa/flux-extensions')
  await request.post('/qa/simple-style')
  await request.post('/api/engine/capabilities/sync')
  await register(request)
})
test.afterEach(async ({ request }) => {
  await request.put('/api/models/metadata', {
    data: {
      engine_url: original.engine_url,
      name: 'demo.safetensors',
      architecture: original.architecture,
      sha256: original.sha256,
      version: original.version,
    },
  })
  await request.post('/qa/simple-style?enabled=false')
  await request.post('/qa/simple-creation?enabled=false')
  await request.post('/qa/flux-extensions?enabled=false')
  await request.post('/qa/engine/uncertain')
  await request.post('/api/engine/capabilities/sync')
})
async function generate(page: Page, path = '/api/generate') {
  const response = page.waitForResponse(
    (r) => r.url().endsWith(path) && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '生成圖片', exact: true }).click()
  const result = await response
  expect(result.ok(), await result.text()).toBeTruthy()
  await expect(page.getByRole('button', { name: '存入作品庫', exact: true })).toBeVisible()
  return { job: await result.json(), body: result.request().postDataJSON() }
}

for (const [model, label, path] of [
  ['animagine', '日系人物插畫', '/api/generate'],
  ['pony', '動漫場景', '/api/generate'],
  ['flux', 'FLUX 插畫實驗', '/api/flux/generate'],
])
  test(`${model}: five recipes, exact extra prompts/seeds, explicit generation and source transfer`, async ({
    page,
    request,
  }) => {
    if (model === 'pony') await register(request, pony)
    const before = (await (await request.get('/qa/state')).json()).prompts
    await page.goto('/#/studio/simple')
    const models = page.getByRole('group', { name: '起始配方', exact: true })
    await expect(models.getByRole('button')).toHaveCount(3)
    await models.getByRole('button').filter({ hasText: label }).click()
    const choices = page.getByRole('group', { name: '模型內的起始配方' })
    await expect(choices.getByRole('button')).toHaveCount(5)
    for (const recipe of extras.filter((r: { model_id: string }) => r.model_id === model)) {
      await choices.getByRole('button').filter({ hasText: recipe.title }).click()
      await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
      await expect(page.locator('#simple-prompt')).toHaveValue(recipe.prompt)
      await page.locator('.simple-recipe > summary').first().click()
      await expect(page.locator('.simple-recipe pre')).toContainText(
        '"seed": "' + recipe.seed + '"',
      )
      await page.locator('.simple-recipe > summary').first().click()
      await page.locator('.simple-example > summary').click()
      const downloaded = page.waitForEvent('download')
      await page.getByRole('link', { name: '下載完整配方與實測紀錄（JSON）' }).click()
      const download = await downloaded
      expect(download.suggestedFilename()).toContain(recipe.id)
      await page.locator('.simple-example > summary').click()
    }
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
    const last = extras.filter((r: { model_id: string }) => r.model_id === model).at(-1)
    const { job, body } = await generate(page, path)
    expect(body.seed).toBe(last.seed)
    expect(body.prompt).toBe(last.prompt)
    expect(body.template_selection).toEqual({ template_id: last.id, template_version: 1 })
    expect(job.template_context.modified).toBe(false)
    await page.getByRole('button', { name: '存入作品庫', exact: true }).click()
    await expect(page.getByRole('button', { name: '已存入作品庫', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
    await expect(page.locator(model === 'flux' ? '#flux-prompt' : '#draft-prompt')).toHaveValue(
      last.prompt,
    )
  })

for (const width of [1440, 390])
  for (const task of ['lora', 'reference'])
    test(`${width}px ${task}: simple task, source, save, edit and advanced transfer`, async ({
      page,
      request,
    }, info) => {
      await page.setViewportSize({ width, height: 1000 })
      const recipe = styles.find((r: { task: string }) => r.task === task)
      const before = (await (await request.get('/qa/state')).json()).prompts
      await page.goto('/#/studio/simple')
      await page
        .getByRole('group', { name: '畫風控制任務' })
        .getByRole('button')
        .filter({ hasText: recipe.title })
        .click()
      await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
      await expect(page.locator('#simple-prompt')).toHaveValue(recipe.prompt)
      if (task === 'reference') {
        await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
        await page.getByRole('button', { name: '使用自產示範參考圖', exact: true }).click()
        await expect(page.locator('#simple-reference')).not.toHaveValue('')
        await expect(page.locator('.simple-reference-preview')).toBeVisible()
        await page.locator('#simple-reference-weight').fill('0.4')
        await expect(page.getByRole('status').filter({ hasText: '已修改配方' })).toBeVisible()
        await page.locator('#simple-reference-weight').fill('0.6')
      }
      expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
      if (width === 1440) {
        await page.locator('.simple-editor h3').scrollIntoViewIfNeeded()
        await page.screenshot({
          path: info.outputPath('simple-' + task + '-ready.png'),
          fullPage: false,
        })
      }
      const path = task === 'reference' ? '/api/reference/generate' : '/api/generate'
      const first = await generate(page, path)
      expect(first.job.template_context.modified).toBe(false)
      expect(first.job.template_context.selection.template_id).toBe(recipe.id)
      if (task === 'lora')
        expect(first.body.loras).toEqual([
          {
            name: 'pixel_art_lora_sdxl_comfy_v1.safetensors',
            enabled: true,
            strength_model: 1,
            strength_clip: 1,
          },
        ])
      else {
        expect(first.body.reference_ids).toEqual([first.body.image_asset_id])
        expect(first.body.reference_weight).toBe(0.6)
        expect(first.body.loras).toEqual([])
        expect(first.job.reference_metadata[0].id).toBe(first.body.image_asset_id)
      }
      await page.getByRole('button', { name: '存入作品庫', exact: true }).click()
      await expect(page.getByRole('button', { name: '已存入作品庫', exact: true })).toBeDisabled()
      await page.getByRole('button', { name: '編輯描述', exact: true }).click()
      await page.locator('#simple-prompt').fill(recipe.prompt + ', green coat')
      const edited = await generate(page, path)
      expect(edited.job.template_context.changed_fields).toContain('prompt')
      expect(edited.body.seed).toBe(first.body.seed)
      expect(
        (await (await request.get('/api/jobs/' + first.job.id)).json()).template_context.modified,
      ).toBe(false)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      expect(
        (
          await new AxeBuilder({ page })
            .include('.atelier-shell')
            .withTags(['wcag2a', 'wcag2aa'])
            .analyze()
        ).violations,
      ).toEqual([])
      await page.screenshot({ path: info.outputPath('simple-' + task + '.png'), fullPage: true })
      await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
      await expect(
        page.locator(task === 'reference' ? '#reference-prompt' : '#draft-prompt'),
      ).toHaveValue(edited.body.prompt)
      if (task === 'reference') {
        await expect(page.locator('#reference-source')).toHaveValue(first.body.image_asset_id)
        const response = page.waitForResponse(
          (r) => r.url().endsWith(path) && r.request().method() === 'POST',
        )
        await page.getByRole('button', { name: '生成圖片', exact: true }).click()
        const advanced = await response
        expect(advanced.ok(), await advanced.text()).toBeTruthy()
        expect((await advanced.json()).template_context.selection.template_id).toBe(recipe.id)
      }
    })

test('missing style dependencies are explicit and repair opens their model category', async ({
  page,
}) => {
  await page.route('**/api/loras', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    body.loras = []
    await route.fulfill({ json: body })
  })
  await page.route('**/api/reference-components', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    body.components = []
    await route.fulfill({ json: body })
  })
  await page.goto('/#/studio/simple')
  for (const [task, filename, tab] of [
    ['lora', 'pixel_art_lora_sdxl_comfy_v1.safetensors', 'LoRA'],
    ['reference', 'ip-adapter-plus_sdxl_vit-h.safetensors', '元件'],
  ]) {
    const recipe = styles.find((r: { task: string }) => r.task === task)
    await page
      .getByRole('group', { name: '畫風控制任務' })
      .getByRole('button')
      .filter({ hasText: recipe.title })
      .click()
    await expect(page.locator('.simple-repair')).toContainText(filename)
    await expect(page.getByRole('button', { name: '載入起始配方', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: '前往對應模型分類', exact: true }).first().click()
    await expect(page.getByRole('tab', { name: tab, exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await page
      .getByRole('navigation')
      .getByRole('button', { name: '創作工作台', exact: true })
      .click()
    await expect(page.locator('.simple-editor h3')).toHaveText(recipe.title)
  }
})

test('reference upload, uncertain response and advanced recovery retain the original UUID and template', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/#/studio/simple')
  await page
    .getByRole('group', { name: '畫風控制任務' })
    .getByRole('button')
    .filter({ hasText: '參考一張圖片的畫風' })
    .click()
  await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
  await page
    .locator('#simple-reference-upload')
    .setInputFiles('../docs/guide/images/examples/reference-source.png')
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeEnabled()
  const asset = await page.locator('#simple-reference').inputValue()
  await page.route('**/api/reference/generate', async (route) => {
    await route.fetch()
    await route.abort('failed')
  })
  await page.getByRole('button', { name: '生成圖片', exact: true }).click()
  const recover = page.getByRole('button', { name: '恢復原提交請求', exact: true })
  await expect(recover).toBeEnabled()
  const key = 'atelier-pending-reference-submission'
  const frozen = JSON.parse((await page.evaluate((k) => localStorage.getItem(k), key))!)
  expect(frozen.template_selection).toEqual({ template_id: 'style-reference', template_version: 1 })
  expect(frozen.image_asset_id).toBe(asset)
  await page.unroute('**/api/reference/generate')
  await page.goto('/#/studio/reference')
  await expect(recover).toBeEnabled()
  const response = page.waitForResponse(
    (r) => r.url().endsWith('/api/reference/generate') && r.request().method() === 'POST',
  )
  await recover.click()
  const recovered = await response
  expect(recovered.ok()).toBeTruthy()
  const job = await recovered.json()
  expect(job.id).toBe(frozen.request_id)
  expect(job.template_context.selection).toEqual(frozen.template_selection)
  expect(job.template_context.modified).toBe(false)
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 1)
  expect(await page.evaluate((k) => localStorage.getItem(k), key)).toBeNull()
})

test('reference transfer cancellation preserves both forms and source image', async ({ page }) => {
  await page.goto('/#/studio/reference')
  await page.locator('#reference-prompt').fill('keep existing advanced reference description')
  await page.getByRole('tab', { name: '簡易創作', exact: true }).click()
  await page
    .getByRole('group', { name: '畫風控制任務' })
    .getByRole('button')
    .filter({ hasText: '參考一張圖片的畫風' })
    .click()
  await page.getByRole('button', { name: '套用後修改', exact: true }).click()
  await page.getByRole('button', { name: '使用自產示範參考圖', exact: true }).click()
  await expect(page.locator('#simple-reference')).not.toHaveValue('')
  const asset = await page.locator('#simple-reference').inputValue()
  await page.locator('#simple-prompt').fill('keep simple reference description')
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
  await expect(page.locator('#reference-prompt')).toHaveValue(
    'keep existing advanced reference description',
  )
  await page.getByRole('tab', { name: '簡易創作', exact: true }).click()
  await expect(page.locator('#simple-prompt')).toHaveValue('keep simple reference description')
  await expect(page.locator('#simple-reference')).toHaveValue(asset)
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
  await expect(page.locator('#reference-prompt')).toHaveValue('keep simple reference description')
  await expect(page.locator('#reference-source')).toHaveValue(asset)
})
