import { test, expect, type APIRequestContext } from '@playwright/test'
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
  await request.post('/qa/flux-extensions?enabled=false')
  await request.post('/api/engine/capabilities/sync')
})
async function register(request: APIRequestContext, manifest = animagine) {
  const result = await request.put('/api/models/metadata', {
    data: {
      engine_url: engine,
      name: 'demo.safetensors',
      architecture: 'sdxl',
      sha256: manifest.sha256,
    },
  })
  expect(result.ok()).toBeTruthy()
  await request.post('/api/engine/capabilities/sync')
}

test('first creation opens simple mode, remembers selection and keeps explicit advanced URLs', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/#/system')
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '創作工作台', exact: true })
    .click()
  await expect(page).toHaveURL(/#\/studio\/simple$/)
  await expect(page.getByRole('tab', { name: '簡易創作', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByRole('group', { name: '起始配方' }).getByRole('button')).toHaveCount(3)
  await page.getByRole('tab', { name: '進階工作台', exact: true }).click()
  await expect(page.locator('#draft-prompt')).toBeVisible()
  await page.getByRole('navigation').getByRole('button', { name: '系統資訊', exact: true }).click()
  await page.reload()
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '創作工作台', exact: true })
    .click()
  await expect(page).toHaveURL(/#\/studio\/checkpoint$/)
  await page.getByRole('tab', { name: '簡易創作', exact: true }).click()
  await page.goBack()
  await expect(page.locator('#draft-prompt')).toBeVisible()
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('unknown model, unavailable engine and incomplete FLUX never silently load a substitute', async ({
  page,
  request,
}) => {
  await page.route('**/api/flux/components', (route) =>
    route.fulfill({
      json: {
        engine_url: engine,
        groups: { diffusion_models: [], text_encoders: [], vae: [] },
        synced_at: null,
        sync_error: null,
      },
    }),
  )
  await page.goto('/#/studio/simple')
  await expect(page.getByRole('button', { name: '載入起始配方', exact: true })).toBeDisabled()
  await expect(page.locator('#simple-prompt')).toBeDisabled()
  await page
    .getByRole('group', { name: '起始配方' })
    .getByRole('button')
    .filter({ hasText: 'FLUX 插畫實驗' })
    .click()
  await expect(page.getByRole('button', { name: '載入起始配方', exact: true })).toBeDisabled()
  await request.post('/qa/engine/offline')
  await page.getByRole('button', { name: '重新檢查', exact: true }).click()
  await expect(
    page.getByRole('group', { name: '起始配方' }).getByRole('button').first(),
  ).toContainText('引擎離線')
})

for (const width of [1440, 390])
  test(`${width}px: full preset, explicit generation and direct artwork save`, async ({
    page,
    request,
  }, info) => {
    await register(request)
    const before = (await (await request.get('/qa/state')).json()).prompts
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/studio/simple')
    await page.getByRole('button', { name: '套用後修改', exact: true }).click()
    await expect(page.locator('#simple-prompt')).toHaveValue(/1girl/)
    await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeEnabled()
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
    await page.locator('#simple-prompt').fill('adult woman, blue hair, garden, illustration')
    await expect(page.getByText('已修改配方，不沿用原配置的驗收結論。')).toBeVisible()
    const response = page.waitForResponse(
      (value) => value.url().endsWith('/api/generate') && value.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '生成圖片', exact: true }).click()
    const submitted = await response
    expect(submitted.ok()).toBeTruthy()
    const body = submitted.request().postDataJSON()
    expect(body).toMatchObject({
      checkpoint: 'demo.safetensors',
      width: 1024,
      height: 1024,
      steps: 28,
      cfg: 5,
      sampler_name: 'euler_ancestral',
      scheduler: 'normal',
      seed: '9007199254740993',
      loras: [],
    })
    await expect(page.getByRole('button', { name: '存入作品庫', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '存入作品庫', exact: true }).click()
    await expect(page.getByRole('button', { name: '已存入作品庫', exact: true })).toBeDisabled()
    await page.screenshot({ path: info.outputPath('simple-creation.png'), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const accessibility = await new AxeBuilder({ page })
      .include('.atelier-shell')
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    expect(accessibility.violations).toEqual([])
  })

test('Pony transfers exact settings, preserves simple edits and protects an existing advanced form', async ({
  page,
  request,
}) => {
  await register(request, pony)
  await page.goto('/#/studio/checkpoint')
  await page.locator('#draft-prompt').fill('keep advanced draft')
  await page.getByRole('tab', { name: '簡易創作', exact: true }).click()
  await page
    .getByRole('group', { name: '起始配方' })
    .getByRole('button')
    .filter({ hasText: '動漫場景' })
    .click()
  await page.getByRole('button', { name: '套用後修改', exact: true }).click()
  await page.locator('#simple-prompt').fill('score_9, source_anime, mountain lake, no humans')
  page.once('dialog', (dialog) => dialog.dismiss())
  await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
  await expect(page.locator('#draft-prompt')).toHaveValue('keep advanced draft')
  await page.getByRole('tab', { name: '簡易創作', exact: true }).click()
  await expect(page.locator('#simple-prompt')).toHaveValue(
    'score_9, source_anime, mountain lake, no humans',
  )
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
  await expect(page.locator('#draft-prompt')).toHaveValue(
    'score_9, source_anime, mountain lake, no humans',
  )
  await expect(page.locator('#seed')).toHaveValue('9007199254740993')
  await expect(page.locator('#steps')).toHaveValue('20')
  await expect(page.locator('#cfg')).toHaveValue('5.5')
  await expect(page.locator('#sampler')).toHaveValue('dpmpp_2m')
  const submission = page.waitForResponse(
    (value) => value.url().endsWith('/api/generate') && value.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '生成圖片', exact: true }).click()
  expect((await submission).ok()).toBeTruthy()
})

test('Schnell resolves four registered components, never auto submits and transfers FP8/CPU settings', async ({
  page,
  request,
}) => {
  await request.post('/qa/flux-extensions')
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/#/studio/simple')
  await page
    .getByRole('group', { name: '起始配方' })
    .getByRole('button')
    .filter({ hasText: 'FLUX 插畫實驗' })
    .click()
  await page.getByRole('button', { name: '套用後修改', exact: true }).click()
  await expect(page.locator('#simple-prompt')).toHaveValue(/An anime background/)
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  const submission = page.waitForResponse(
    (value) => value.url().endsWith('/api/flux/generate') && value.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '生成圖片', exact: true }).click()
  const submitted = await submission
  expect(submitted.ok()).toBeTruthy()
  expect(submitted.request().postDataJSON()).toMatchObject({
    width: 512,
    height: 512,
    steps: 4,
    weight_dtype: 'fp8_e4m3fn',
    encoder_device: 'cpu',
    seed: '9007199254740993',
  })
  await expect(page.getByRole('button', { name: '存入作品庫', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
  await expect(page).toHaveURL(/#\/studio\/flux$/)
  await expect(page.locator('#flux-diffusion_model')).toHaveValue('flux1-schnell.safetensors')
  await expect(page.locator('#flux-dtype')).toHaveValue('fp8_e4m3fn')
  await expect(page.locator('#flux-device')).toHaveValue('cpu')
  await expect(page.locator('#flux-seed')).toHaveValue('9007199254740993')
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 1)
})

test('template cancellation retains edits; changing seed does not generate; engine change preserves the old source', async ({
  page,
  request,
}) => {
  await register(request)
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/#/studio/simple')
  await page.getByRole('button', { name: '套用後修改', exact: true }).click()
  await page.locator('#simple-prompt').fill('keep this English prompt')
  page.once('dialog', (dialog) => dialog.dismiss())
  await page
    .getByRole('group', { name: '起始配方' })
    .getByRole('button')
    .filter({ hasText: '動漫場景' })
    .click()
  await expect(page.locator('#simple-prompt')).toHaveValue('keep this English prompt')
  await page.getByRole('button', { name: '換 Seed，準備再畫一張', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: '已更換 Seed' })).toBeVisible()
  await page.route('**/api/settings', (route) =>
    route.fulfill({ json: { comfy_url: 'http://changed-engine.invalid:8188' } }),
  )
  await page.getByRole('button', { name: '重新檢查', exact: true }).click()
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
  await expect(page.locator('#simple-prompt')).toHaveValue('keep this English prompt')
  await page.getByText('查看完整設定', { exact: true }).click()
  await expect(page.locator('.simple-recipe pre')).toContainText(engine)
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('a text recipe opens a new advanced studio without inheriting a previous redraw purpose', async ({
  page,
  request,
}) => {
  await register(request)
  await page.goto('/#/studio/flux')
  await page.getByRole('button', { name: '圖片重繪', exact: true }).click()
  await page.getByRole('tab', { name: '簡易創作', exact: true }).click()
  await page.getByRole('button', { name: '套用後修改', exact: true }).click()
  await page.getByRole('button', { name: '帶到進階工作台', exact: true }).click()
  await expect(page.locator('#checkpoint-workflow')).toHaveValue('text2image')
  await expect(page.getByRole('button', { name: '文字創作', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.locator('#draft-prompt')).toHaveValue(/1girl/)
})

test('cached advanced panel recovers the original uncertain simple request without another submission', async ({
  page,
  request,
}) => {
  await register(request)
  await page.goto('/#/studio/checkpoint')
  await page.getByRole('tab', { name: '簡易創作', exact: true }).click()
  await page.getByRole('button', { name: '套用後修改', exact: true }).click()
  const bodies: string[] = []
  await page.route('**/api/generate', async (route) => {
    bodies.push(route.request().postData()!)
    const result = await route.fetch()
    if (bodies.length === 1) await route.abort('connectionfailed')
    else await route.fulfill({ response: result })
  })
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.getByRole('button', { name: '生成圖片', exact: true }).click()
  await expect(page.getByRole('button', { name: '恢復原提交請求', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: '進階工作台', exact: true }).click()
  await page.getByRole('button', { name: '恢復原提交請求', exact: true }).click()
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeVisible()
  expect(bodies).toHaveLength(2)
  expect(bodies[1]).toBe(bodies[0])
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 1)
})
