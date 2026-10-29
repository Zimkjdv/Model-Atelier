import { test, expect, type APIRequestContext, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import AxeBuilder from '@axe-core/playwright'

const manifest = JSON.parse(await readFile('../models/animagine-xl-4.0-opt.json', 'utf8'))
const registry = JSON.parse(await readFile('../models/simple-creation-templates-v1.json', 'utf8'))
const recipe = registry.templates.find((item: { id: string }) => item.id === 'animagine')
let original: { engine_url: string; architecture: string; sha256: string; version: string }

test.beforeEach(async ({ request }) => {
  const catalog = await (await request.get('/api/models')).json()
  original = {
    ...catalog.models.find((item: { name: string }) => item.name === 'demo.safetensors'),
    engine_url: catalog.engine_url,
  }
  await request.post('/qa/simple-creation')
  await request.post('/qa/engine/success')
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
  await request.post('/qa/simple-creation?enabled=false')
  await request.post('/qa/flux-extensions?enabled=false')
  await request.post('/api/engine/capabilities/sync')
})
async function ready(request: APIRequestContext) {
  const result = await request.put('/api/models/metadata', {
    data: {
      engine_url: original.engine_url,
      name: 'demo.safetensors',
      architecture: 'sdxl',
      sha256: manifest.sha256,
    },
  })
  expect(result.ok()).toBeTruthy()
  await request.post('/api/engine/capabilities/sync')
}
async function generate(page: Page, simple = true) {
  const response = page.waitForResponse(
    (value) => value.url().endsWith('/api/generate') && value.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '生成圖片', exact: true }).click()
  const result = await response
  expect(result.ok()).toBeTruthy()
  if (simple)
    await expect(page.getByRole('button', { name: '存入作品庫', exact: true })).toBeVisible()
  return result.json()
}

for (const width of [1440, 390])
  test(`${width}px: original, edit, restore, generate, save and modify again without technical settings`, async ({
    page,
    request,
  }, info) => {
    await ready(request)
    const before = (await (await request.get('/qa/state')).json()).prompts
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/studio/simple')
    await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
    await expect(page.locator('#simple-prompt')).toHaveAttribute('readonly', '')
    await expect(page.locator('#simple-prompt')).toHaveValue(recipe.prompt)
    await page.getByRole('button', { name: '編輯描述', exact: true }).click()
    await expect(page.locator('#simple-prompt')).toBeFocused()
    await page.locator('#simple-prompt').fill('custom description to restore')
    page.once('dialog', (dialog) => dialog.dismiss())
    await page.getByRole('button', { name: '還原配方設定', exact: true }).click()
    await expect(page.locator('#simple-prompt')).toHaveValue('custom description to restore')
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: '還原配方設定', exact: true }).click()
    await expect(page.locator('#simple-prompt')).toHaveValue(recipe.prompt)
    await expect(page.locator('#simple-prompt')).toHaveAttribute('readonly', '')
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
    const first = await generate(page)
    expect(first.template_context.modified).toBe(false)
    await page.getByRole('button', { name: '存入作品庫', exact: true }).click()
    await expect(page.getByRole('button', { name: '已存入作品庫', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: '編輯描述', exact: true }).click()
    await page.locator('#simple-prompt').fill('adult woman, red hair, forest, anime illustration')
    await expect(page.getByRole('status').filter({ hasText: '右側仍為既有任務結果' })).toBeVisible()
    await expect(page.locator('.simple-steps [aria-current="step"]')).toContainText(
      '確認或修改描述',
    )
    const second = await generate(page)
    expect(second.id).not.toBe(first.id)
    expect(second.template_context.modified).toBe(true)
    expect(second.template_context.changed_fields).toContain('prompt')
    expect(second.template_context.recipe_sha256).toBe(first.template_context.recipe_sha256)
    await page.getByRole('button', { name: '存入作品庫', exact: true }).click()
    await expect(page.getByRole('button', { name: '已存入作品庫', exact: true })).toBeDisabled()
    expect(
      (await (await request.get('/api/jobs/' + first.id)).json()).template_context.modified,
    ).toBe(false)
    await expect(page.locator('.simple-steps [aria-current="step"]')).toContainText('保存成果')
    const source = page.locator('.simple-stage > .template-snapshot')
    await source.locator(':scope > summary').click()
    await expect(source).toContainText(second.template_context.recipe_sha256)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(
      (
        await new AxeBuilder({ page })
          .include('.atelier-shell')
          .withTags(['wcag2a', 'wcag2aa'])
          .analyze()
      ).violations,
    ).toEqual([])
    await page.screenshot({ path: info.outputPath('simple-acceptance.png'), fullPage: true })
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 2)
  })

test('model repair opens the right classification and keeps selected recipe and unsaved input on return', async ({
  page,
  request,
}) => {
  await page.goto('/#/studio/simple')
  await expect(page.locator('.simple-repair')).toContainText(manifest.filename)
  await page.getByRole('button', { name: '前往對應模型分類', exact: true }).last().click()
  await expect(page.getByRole('tab', { name: 'Checkpoint', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await ready(request)
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '創作工作台', exact: true })
    .click()
  await page.getByRole('button', { name: '套用後修改', exact: true }).click()
  await page.locator('#simple-prompt').fill('keep edits while checking models')
  await page.getByRole('navigation').getByRole('button', { name: '模型庫', exact: true }).click()
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '創作工作台', exact: true })
    .click()
  await expect(page.locator('#simple-prompt')).toHaveValue('keep edits while checking models')
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeEnabled()
})

test('missing Schnell components are individually named and repair opens FLUX components', async ({
  page,
  request,
}) => {
  await page.goto('/#/studio/simple')
  await page
    .getByRole('group', { name: '起始配方' })
    .getByRole('button')
    .filter({ hasText: 'FLUX 插畫實驗' })
    .click()
  for (const filename of [
    'flux1-schnell.safetensors',
    'clip_l.safetensors',
    't5xxl_fp8_e4m3fn_scaled.safetensors',
    'ae.safetensors',
  ])
    await expect(page.locator('.simple-repair')).toContainText(filename)
  await page.getByRole('button', { name: '前往對應模型分類', exact: true }).first().click()
  await expect(page.getByRole('tab', { name: 'FLUX 元件', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await request.post('/qa/flux-extensions')
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '創作工作台', exact: true })
    .click()
  await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
  await expect(page.locator('#simple-prompt')).toHaveValue(/An anime background/)
  await page.getByRole('navigation').getByRole('button', { name: '模型庫', exact: true }).click()
  await expect(page.getByRole('tab', { name: 'Checkpoint', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

test('advanced draft, restored draft, offline artwork and artwork restoration retain template origin', async ({
  page,
  request,
}) => {
  await ready(request)
  await page.goto('/#/studio/simple')
  await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
  await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
  await page.locator('#studio-editor > fieldset > details.studio-advanced > summary').click()
  const saved = page.waitForResponse(
    (response) => response.url().endsWith('/api/drafts') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '保存草稿', exact: true }).click()
  const draftResponse = await saved
  expect(draftResponse.ok()).toBeTruthy()
  const draft = await draftResponse.json()
  expect(draft.template_selection).toEqual({ template_id: 'animagine', template_version: 1 })
  await page.reload()
  await page.locator('.saved-drafts > summary').click()
  await page.locator('.draft-row').filter({ hasText: draft.title }).click()
  const job = await generate(page, false)
  expect(job.template_context.selection).toEqual(draft.template_selection)
  await request.post('/api/jobs/' + job.id + '/refresh')
  const imported = await (await request.post('/api/jobs/' + job.id + '/artworks')).json()
  const artwork = imported.imported[0]
  await request.post('/qa/engine/offline')
  await page.getByRole('navigation').getByRole('button', { name: '作品庫', exact: true }).click()
  await page.getByLabel('搜尋作品', { exact: true }).fill(artwork.title)
  await page.getByRole('button', { name: '查看作品 ' + artwork.title, exact: true }).click()
  await page.getByRole('tab', { name: '生成與來源', exact: true }).click()
  const snapshot = page.locator('.artwork-detail-scroll .template-snapshot')
  await snapshot.locator(':scope > summary').click()
  await expect(snapshot).toContainText('animagine / 1')
  await expect(snapshot).toContainText(job.template_context.recipe_sha256)
  await page.getByRole('button', { name: '載入創作設定 →', exact: true }).click()
  await expect(page.locator('#draft-prompt')).toHaveValue(recipe.prompt)
  await request.post('/qa/engine/success')
  await request.post('/api/engine/capabilities/sync')
  await page.getByRole('navigation').getByRole('button', { name: '系統資訊', exact: true }).click()
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '創作工作台', exact: true })
    .click()
  const restored = await generate(page, false)
  expect(restored.template_context.selection).toEqual(draft.template_selection)
  expect(restored.template_context.recipe_sha256).toEqual(job.template_context.recipe_sha256)
})
