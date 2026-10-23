import { randomUUID, createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import {
  test,
  expect,
  type Page,
  type APIRequestContext,
  type TestInfo,
  type Locator,
} from '@playwright/test'
import { newCreation, type CreationForm } from '../src/creationSettings'
import { newFlux, type FluxForm } from '../src/fluxSettings'

const area = (page: Page) => page.locator('.settings-transfer:visible')
const imported = (page: Page) => area(page).getByRole('region', { name: '匯入設定預覽' })
const digest = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')
type Mode = 'checkpoint' | 'image' | 'flux'
const family = (mode: Mode) => (mode === 'flux' ? 'flux' : 'checkpoint')

async function baseline(request: APIRequestContext, mode: Mode) {
  const state = await (await request.get('/qa/state')).json()
  const engine = (await (await request.get('/api/settings')).json()).comfy_url
  const common = {
    title: 'V05 山湖 ' + randomUUID(),
    prompt: '湖面與木船\n"晨光" — 測試設定',
    seed: '18446744073709551615',
    width: 512,
    height: 768,
  }
  if (mode === 'flux')
    return {
      ...newFlux(engine),
      ...common,
      diffusion_model: 'fixture-flux.safetensors',
      clip_l: 'fixture-clip.safetensors',
      t5xxl: 'fixture-t5.safetensors',
      vae: 'fixture-vae.safetensors',
      weight_dtype: 'fp8_e4m3fn',
      encoder_device: 'cpu',
    } as FluxForm
  return {
    ...newCreation(),
    ...common,
    engine_url: engine,
    checkpoint: 'demo.safetensors',
    negative_prompt: '模糊、文字\n浮水印',
    steps: 28,
    cfg: 5,
    loras: [
      { name: 'fixture-alpha', enabled: true, strength_model: 0.5, strength_clip: 0 },
      { name: 'fixture-disabled', enabled: false, strength_model: 2, strength_clip: -0.25 },
      { name: 'fixture-beta', enabled: true, strength_model: -0.5, strength_clip: 1.2 },
    ],
    ...(mode === 'image'
      ? {
          workflow_mode: 'image2image',
          image_asset_id: state.asset_id,
          reference_ids: [state.asset_id],
          reference_resize: 'stretch',
          denoise: 0.123,
        }
      : {}),
  } as CreationForm
}
function bundle(settings: CreationForm | FluxForm) {
  return {
    kind: 'model-atelier-creation',
    schema_version: 1,
    workflow_id:
      'workflow_id' in settings
        ? settings.workflow_id
        : settings.workflow_mode === 'image2image'
          ? 'checkpoint-image2image-v1'
          : 'checkpoint-text2image-v1',
    settings,
    source_snapshot: null,
  }
}
async function open(
  page: Page,
  request: APIRequestContext,
  mode: Mode,
  settings?: CreationForm | FluxForm,
) {
  const value = settings ?? (await baseline(request, mode))
  const path = mode === 'flux' ? '/api/flux/drafts' : '/api/drafts'
  const response = await request.post(path, { data: value })
  expect(response.ok()).toBe(true)
  const draft = await response.json()
  await page.goto('/#/studio/' + (mode === 'flux' ? 'flux' : 'checkpoint'))
  await page
    .locator(mode === 'flux' ? '.flux-draft' : '.draft-row')
    .filter({ has: page.getByText(value.title, { exact: true }) })
    .click()
  const discard = page.getByRole('button', {
    name: mode === 'flux' ? '捨棄變更並載入 FLUX' : '捨棄變更並載入',
    exact: true,
  })
  if (await discard.isVisible()) await discard.click()
  await expect(page.locator(mode === 'flux' ? '#flux-title' : '#draft-title')).toHaveValue(
    value.title,
  )
  await area(page).locator('summary').first().click()
  return { settings: value, draft, path }
}
async function paste(page: Page, text: string) {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
  const input = area(page).getByLabel('或貼上設定 JSON', { exact: true })
  await input.fill('')
  await page.evaluate((value) => navigator.clipboard.writeText(value), text)
  await input.focus()
  await page.keyboard.press('Control+V')
  await expect(input).toHaveValue(text)
}
async function validate(page: Page) {
  const pending = page.waitForResponse(
    (response) => new URL(response.url()).pathname === '/api/creation-settings/import',
  )
  await area(page).getByRole('button', { name: '驗證並預覽設定', exact: true }).click()
  const response = await pending
  return {
    status: response.status(),
    value: await response.json(),
    raw: response.request().postDataBuffer(),
  }
}
async function download(
  page: Page,
  link: Locator,
  info: TestInfo,
  name: string,
  expected?: Buffer,
) {
  const pending = page.waitForEvent('download')
  await link.click()
  const file = await pending
  expect(await file.failure()).toBeNull()
  const path = info.outputPath(name)
  await file.saveAs(path)
  const bytes = await readFile(path)
  if (expected) expect(bytes).toEqual(expected)
  await info.attach(name, { path, contentType: 'application/json' })
  return { bytes, filename: file.suggestedFilename(), path }
}
async function evidence(info: TestInfo, name: string, value: unknown) {
  const path = info.outputPath(name)
  await writeFile(path, JSON.stringify(value, null, 2))
  await info.attach(name, { path, contentType: 'application/json' })
}

for (const width of [1440, 390])
  test.describe(`${width}px V05`, () => {
    test.use({ viewport: { width, height: 900 } })
    test.beforeEach(async ({ request }, info) => {
      info.annotations.push({
        type: 'prompts-before',
        description: String((await (await request.get('/qa/state')).json()).prompts),
      })
    })
    test.afterEach(async ({ request, page }, info) => {
      expect((await (await request.get('/qa/state')).json()).prompts).toBe(
        Number(info.annotations.find((v) => v.type === 'prompts-before')!.description),
      )
      expect(await page.evaluate(() => innerWidth)).toBe(width)
    })

    for (const mode of ['checkpoint', 'image', 'flux'] as const)
      test(`${mode}: native download bytes, file chooser, clipboard, cancel and explicit new-draft apply`, async ({
        page,
        request,
      }, info) => {
        const source = await open(page, request, mode)
        const remote = page.waitForResponse(
          (r) => new URL(r.url()).pathname === '/api/creation-settings/export',
        )
        const file = await download(
          page,
          area(page).getByRole('button', { name: '匯出目前創作設定', exact: true }),
          info,
          mode + '-settings.json',
        )
        const response = await remote
        const raw = await response.body()
        expect(file.filename).toBe(`model-atelier-${family(mode)}-settings.json`)
        expect(file.bytes).toEqual(raw)
        expect(JSON.parse(raw.toString())).toEqual(bundle(source.settings))
        expect(raw.toString()).toContain('"seed": "18446744073709551615"')
        const prompt = page.locator(mode === 'flux' ? '#flux-prompt' : '#draft-prompt')
        await prompt.fill('unsaved local input stays until explicit apply')
        const frozen = await download(
          page,
          area(page).getByRole('link', { name: '下載上次匯出的設定', exact: true }),
          info,
          mode + '-last-export.json',
          raw,
        )
        expect(frozen.filename).toBe(file.filename)
        const chooser = page.waitForEvent('filechooser')
        await area(page).getByLabel('讀取創作設定 JSON 檔', { exact: true }).click()
        await (await chooser).setFiles(file.path)
        await expect(area(page).getByLabel('或貼上設定 JSON', { exact: true })).toHaveValue(
          raw.toString(),
        )
        const fromFile = await validate(page)
        expect(fromFile.status).toBe(200)
        expect(fromFile.raw).toEqual(raw)
        expect(fromFile.value.bundle.settings).toEqual(source.settings)
        await expect(imported(page)).toContainText('目前有未保存變更')
        await expect(prompt).toHaveValue('unsaved local input stays until explicit apply')
        await imported(page).getByRole('button', { name: '取消匯入', exact: true }).click()
        await expect(imported(page)).not.toBeVisible()
        await expect(prompt).toHaveValue('unsaved local input stays until explicit apply')
        await paste(page, raw.toString())
        const fromPaste = await validate(page)
        expect(fromPaste.status).toBe(200)
        expect(fromPaste.value.bundle).toEqual(fromFile.value.bundle)
        const seedRow = imported(page)
          .locator('tbody tr')
          .filter({ has: page.locator('th').filter({ hasText: /^seed$/ }) })
        await seedRow.scrollIntoViewIfNeeded()
        await expect(seedRow.getByRole('cell')).toHaveText([
          '18446744073709551615',
          '18446744073709551615',
        ])
        await imported(page).screenshot({ path: info.outputPath(mode + '-preview.png') })
        await imported(page).getByRole('button', { name: '套用為新草稿', exact: true }).click()
        await expect(prompt).toHaveValue(source.settings.prompt)
        await expect(imported(page)).not.toBeVisible()
        const savedResponse = page.waitForResponse(
          (r) => new URL(r.url()).pathname === source.path && r.request().method() === 'POST',
        )
        await page
          .getByRole('button', {
            name: mode === 'flux' ? '保存 FLUX 草稿' : '保存草稿',
            exact: true,
          })
          .click()
        const saved = await (await savedResponse).json()
        expect(saved.id).not.toBe(source.draft.id)
        expect(
          Object.fromEntries(Object.keys(source.settings).map((key) => [key, saved[key]])),
        ).toEqual(source.settings)
        const drafts = await (await request.get(source.path)).json()
        expect(drafts.find((v: any) => v.id === source.draft.id)).toEqual(source.draft)
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        ).toBe(true)
        await area(page).scrollIntoViewIfNeeded()
        await page.screenshot({ path: info.outputPath(mode + '-transfer.png') })
        await evidence(info, mode + '-receipt.json', {
          filename: file.filename,
          bytes: raw.length,
          sha256: digest(raw),
          fromFile,
          fromPaste,
          original: source.draft,
          saved,
        })
      })

    test('artwork source download preserves raw workflow integers and remains unverified on import', async ({
      page,
      request,
    }, info) => {
      const state = await (await request.get('/qa/state')).json()
      const before = await (await request.get('/api/artworks/' + state.artwork_id)).body()
      const raw = await (
        await request.get(`/api/artworks/${state.artwork_id}/settings-export`)
      ).body()
      await page.goto('/#/gallery')
      await page.getByRole('button', { name: '查看作品 qa-artwork.png', exact: true }).click()
      const response = page.waitForResponse(
        (r) => new URL(r.url()).pathname === `/api/artworks/${state.artwork_id}/settings-export`,
      )
      const file = await download(
        page,
        page
          .getByRole('dialog')
          .getByRole('link', { name: '匯出創作設定（含來源快照）', exact: true }),
        info,
        'artwork-settings.json',
      )
      expect((await response).status()).toBe(200)
      expect(file.bytes).toEqual(raw)
      expect(file.filename).toBe(state.artwork_id + '-settings.json')
      const doc = JSON.parse(raw.toString())
      expect(doc.settings.seed).toBe('18446744073709551615')
      const originalWorkflow = await (
        await request.get(`/api/artworks/${state.artwork_id}/workflow`)
      ).text()
      expect(doc.source_snapshot.workflow_json).toContain('18446744073709551615')
      expect(Buffer.from(doc.source_snapshot.workflow_json)).toEqual(Buffer.from(originalWorkflow))
      expect(doc.source_snapshot.id).toBe(state.artwork_id)
      await page.getByRole('button', { name: '關閉 ×', exact: true }).click()
      const source = await open(page, request, 'checkpoint')
      await paste(page, raw.toString())
      const result = await validate(page)
      expect(result.status).toBe(200)
      await expect(imported(page)).toContainText('文件提供的來源（未核實）')
      await expect(imported(page)).toContainText(state.artwork_id)
      await expect(imported(page)).toContainText('不作為新任務的版本或相容性證明')
      await expect(page.locator('#draft-prompt')).toHaveValue(source.settings.prompt)
      await imported(page).getByRole('button', { name: '取消匯入', exact: true }).click()
      expect(await (await request.get('/api/artworks/' + state.artwork_id)).body()).toEqual(before)
      await evidence(info, 'source-receipt.json', {
        filename: file.filename,
        sha256: digest(raw),
        workflow_sha256: digest(Buffer.from(originalWorkflow)),
        result,
      })
    })

    test('stale validation, invalid documents, wrong family and saving cannot silently apply settings', async ({
      page,
      request,
    }, info) => {
      const source = await open(page, request, 'checkpoint')
      const raw = JSON.stringify(bundle(source.settings))
      await paste(page, raw)
      const known = await (
        await request.post('/api/creation-settings/import', { data: bundle(source.settings) })
      ).json()
      let release!: () => void, settled!: () => void, received!: () => void
      const gate = new Promise<void>((resolve) => {
        release = resolve
      })
      const done = new Promise<void>((resolve) => {
        settled = resolve
      })
      const seen = new Promise<void>((resolve) => {
        received = resolve
      })
      await page.route('**/api/creation-settings/import', async (route) => {
        received()
        await gate
        try {
          await route.fulfill({ json: known })
        } catch {
        } finally {
          settled()
        }
      })
      await area(page).getByRole('button', { name: '驗證並預覽設定', exact: true }).click()
      await seen
      await expect(
        area(page).getByRole('button', { name: '匯出目前創作設定', exact: true }),
      ).toBeDisabled()
      await page.locator('#draft-prompt').fill('changed during validation')
      release()
      await done
      await expect(imported(page)).not.toBeVisible()
      await page.unroute('**/api/creation-settings/import')
      expect((await validate(page)).status).toBe(200)
      await expect(imported(page)).toBeVisible()
      await area(page)
        .getByLabel('或貼上設定 JSON', { exact: true })
        .fill(raw + ' ')
      await expect(imported(page)).not.toBeVisible()
      for (const invalid of [
        '{',
        JSON.stringify({ ...bundle(source.settings), schema_version: 2 }),
        JSON.stringify({ ...bundle(source.settings), settings: { ...source.settings, seed: 1 } }),
      ]) {
        await paste(page, invalid)
        expect((await validate(page)).status).toBe(422)
        await expect(imported(page)).not.toBeVisible()
        await expect(area(page).getByRole('alert')).toBeVisible()
        await expect(page.locator('#draft-prompt')).toHaveValue('changed during validation')
      }
      await paste(page, JSON.stringify(bundle(await baseline(request, 'flux'))))
      expect((await validate(page)).status).toBe(200)
      await expect(imported(page)).not.toBeVisible()
      await expect(area(page).getByRole('alert')).toContainText('請先切到對應工作台')
      const missing = {
        ...source.settings,
        workflow_mode: 'image2image',
        image_asset_id: randomUUID(),
        reference_ids: [],
        engine_url: 'http://other-engine.invalid:8188',
      } as CreationForm
      missing.reference_ids = [missing.image_asset_id!]
      await paste(page, JSON.stringify(bundle(missing)))
      expect((await validate(page)).status).toBe(200)
      await expect(imported(page)).toContainText('文件原引擎與目前設定不同')
      await expect(imported(page)).toContainText('檔案只保存素材 ID，不包含圖片')
      let finish!: () => void
      const saving = new Promise<void>((resolve) => {
        finish = resolve
      })
      await page.route(`**/api/drafts/${source.draft.id}`, async (route) => {
        await saving
        await route.continue()
      })
      const saved = page.waitForResponse(
        (r) => new URL(r.url()).pathname === '/api/drafts/' + source.draft.id,
      )
      await page.getByRole('button', { name: '保存草稿', exact: true }).click()
      await expect(
        imported(page).getByRole('button', { name: '套用為新草稿', exact: true }),
      ).toBeDisabled()
      await expect(area(page).getByLabel('讀取創作設定 JSON 檔', { exact: true })).toBeDisabled()
      await expect(page.locator('#draft-prompt')).toHaveValue('changed during validation')
      finish()
      expect((await saved).ok()).toBe(true)
      await expect(
        imported(page).getByRole('button', { name: '取消匯入', exact: true }),
      ).toBeEnabled()
      await imported(page).getByRole('button', { name: '取消匯入', exact: true }).click()
      await expect(page.locator('#draft-prompt')).toHaveValue('changed during validation')
      expect((await (await request.get('/api/settings')).json()).comfy_url).toBe(
        source.settings.engine_url,
      )
      await page.screenshot({ path: info.outputPath('apply-protection.png') })
    })

    test('failed file reads clear the previous candidate and reject malformed UTF-8', async ({
      page,
      request,
    }, info) => {
      const source = await open(page, request, 'checkpoint')
      const raw = JSON.stringify(bundle(source.settings))
      const input = area(page).getByLabel('或貼上設定 JSON', { exact: true })
      const files = area(page).getByLabel('讀取創作設定 JSON 檔', { exact: true })
      const invalidParts = JSON.stringify({
        ...bundle(source.settings),
        settings: { ...source.settings, prompt: 'UTF8_MARKER' },
      }).split('UTF8_MARKER')
      for (const fixture of [
        {
          name: 'too-large.json',
          mimeType: 'application/json',
          buffer: Buffer.alloc(256 * 1024 + 1, 'x'),
        },
        {
          name: 'invalid-utf8.json',
          mimeType: 'application/json',
          buffer: Buffer.concat([
            Buffer.from(invalidParts[0]!),
            Buffer.from([255]),
            Buffer.from(invalidParts[1]!),
          ]),
        },
      ]) {
        await paste(page, raw)
        expect((await validate(page)).status).toBe(200)
        await files.setInputFiles(fixture)
        await expect(area(page).getByRole('alert')).toBeVisible()
        await expect(
          area(page).getByRole('status').filter({ hasText: '正在讀取' }),
        ).not.toBeVisible()
        await expect(input).toHaveValue('')
        await expect(imported(page)).not.toBeVisible()
        await expect(
          area(page).getByRole('button', { name: '驗證並預覽設定', exact: true }),
        ).toBeDisabled()
        await expect(page.locator('#draft-prompt')).toHaveValue(source.settings.prompt)
        await area(page).getByRole('alert').scrollIntoViewIfNeeded()
        await page.screenshot({ path: info.outputPath(fixture.name + '-error.png') })
      }
      await paste(page, raw)
      expect((await validate(page)).status).toBe(200)
      await files.setInputFiles([])
      await expect(imported(page)).toBeVisible()
      await expect(input).toHaveValue(raw)
      await page.evaluate(() => {
        const original = File.prototype.arrayBuffer
        const state = window as typeof window & { releaseSettingsFile?: () => Promise<void> }
        File.prototype.arrayBuffer = function () {
          const pending = original.call(this)
          return new Promise<ArrayBuffer>((resolve) => {
            state.releaseSettingsFile = async () => {
              resolve(await pending)
              File.prototype.arrayBuffer = original
            }
          })
        }
      })
      await files.setInputFiles({
        name: 'delayed.json',
        mimeType: 'application/json',
        buffer: Buffer.from(raw),
      })
      await expect(input).toHaveValue('')
      await expect(input).toBeDisabled()
      await expect(imported(page)).not.toBeVisible()
      await page.locator('#draft-prompt').fill('keep edits while reading a file')
      await page.evaluate(async () => {
        await (
          window as typeof window & { releaseSettingsFile: () => Promise<void> }
        ).releaseSettingsFile()
      })
      await expect(input).toHaveValue('')
      await expect(imported(page)).not.toBeVisible()
      await expect(page.locator('#draft-prompt')).toHaveValue('keep edits while reading a file')
      await page.screenshot({ path: info.outputPath('file-read-error.png') })
    })
  })
