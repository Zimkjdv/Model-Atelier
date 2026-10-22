import { createHash } from 'node:crypto'
import { writeFile } from 'node:fs/promises'
import { expect, test, type APIRequestContext, type Page, type TestInfo } from '@playwright/test'

const pendingKey = 'atelier-pending-inpaint-submission'
const marker = '_atelier_inpaint_workflow_id'
const workflow = { v1: 'checkpoint-inpaint-v1', v2: 'checkpoint-inpaint-feather-v2' }
const endpoint = { v1: '/api/inpaint/generate', v2: '/api/inpaint-feather/generate' }
type Version = keyof typeof workflow
const state = async (request: APIRequestContext) => (await request.get('/qa/state')).json()
const pending = (page: Page) => page.evaluate((key) => localStorage.getItem(key), pendingKey)
const recover = (page: Page) => page.getByRole('button', { name: '恢復原提交請求', exact: true })
const panel = (page: Page) =>
  page
    .locator('article.panel')
    .filter({ has: page.getByRole('heading', { name: '生成任務', exact: true }) })
const hash = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')

function settings(source: string, mask: string) {
  return {
    title: 'V02 frozen inpaint',
    prompt: 'original frozen prompt',
    negative_prompt: 'original negative',
    engine_url: 'http://mock-engine.invalid:8188',
    checkpoint: 'demo.safetensors',
    width: 128,
    height: 64,
    seed: '18446744073709551615',
    steps: 20,
    cfg: 7,
    sampler_name: 'euler',
    scheduler: 'normal',
    denoise: 0.7,
    loras: [],
    workflow_mode: 'image2image',
    image_asset_id: source,
    mask_asset_id: mask,
    reference_ids: [source, mask],
    reference_resize: 'stretch',
    grow_mask_by: 4,
  }
}

async function prepare(page: Page, request: APIRequestContext) {
  const before = await state(request)
  await page.goto('/#/studio/inpaint')
  await page.locator('#inpaint-checkpoint').selectOption('demo.safetensors')
  await expect(page.locator('#inpaint-source')).toBeEnabled()
  await page.locator('#inpaint-source').selectOption(before.asset_id)
  await page.locator('#inpaint-mask').selectOption(before.mask_asset_id)
  for (const [id, value] of Object.entries({
    title: 'V02 frozen inpaint',
    prompt: 'original frozen prompt',
    negative: 'original negative',
    width: '128',
    height: '64',
    seed: '18446744073709551615',
    denoise: '0.7',
    grow: '4',
    feather: '8',
  }))
    await page.locator('#inpaint-' + id).fill(value)
  await page.locator('#inpaint-resize').selectOption('stretch')
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeEnabled()
  return { before, body: settings(before.asset_id, before.mask_asset_id) }
}

async function reload(page: Page) {
  // Unsaved current forms may warn; restored pending is a separate persistent record.
  const accept = async (dialog) => {
    expect(dialog.type()).toBe('beforeunload')
    await dialog.accept()
  }
  page.on('dialog', accept)
  try {
    await page.reload()
  } finally {
    page.off('dialog', accept)
  }
  await expect(recover(page)).toBeEnabled()
}

async function evidence(
  testInfo: TestInfo,
  name: string,
  bytes: string | Buffer,
  contentType: string,
) {
  const path = testInfo.outputPath(name)
  await writeFile(path, bytes)
  await testInfo.attach(name, { path, contentType })
}

async function inputs(request: APIRequestContext, job: any, version: Version, testInfo?: TestInfo) {
  const roles = version === 'v1' ? ['source', 'mask'] : ['source', 'mask', 'blend']
  const paths = { source: 'reference-image', mask: 'reference-mask', blend: 'reference-blend-mask' }
  const digests: Record<string, string> = {}
  for (const role of roles) {
    const response = await request.get(`/api/jobs/${job.id}/${paths[role]}`)
    expect(response.ok()).toBe(true)
    const bytes = await response.body()
    digests[role] = hash(bytes)
    const expected =
      role === 'blend'
        ? job.reference_metadata[1].blend_preprocessing
        : job.reference_metadata[role === 'source' ? 0 : 1].generation_preprocessing
    expect(digests[role]).toBe(expected.sha256)
    if (testInfo) await evidence(testInfo, 'prepared-' + role + '.png', bytes, 'image/png')
  }
  return digests
}

for (const width of [1440, 390])
  for (const version of ['v1', 'v2'] as const) {
    for (const fault of ['upstream-unknown', 'invalid-json'] as const) {
      test(`${width}px ${version} ${fault}: reload and recover only the frozen request`, async ({
        page,
        request,
      }, testInfo) => {
        await page.setViewportSize({ width, height: 900 })
        await page.clock.install()
        await request.post('/qa/engine/' + (fault === 'upstream-unknown' ? 'uncertain' : 'success'))
        const { before, body } = await prepare(page, request)
        const browserRequests: { path: string; body: string }[] = []
        let initialReply = ''
        let release!: () => void
        const gate = new Promise<void>((resolve) => {
          release = resolve
        })
        await page.route(/\/api\/inpaint(?:-feather)?\/generate$/, async (route) => {
          const index = browserRequests.length
          browserRequests.push({
            path: new URL(route.request().url()).pathname,
            body: route.request().postData()!,
          })
          if (index === 1) await gate
          const response = await route.fetch()
          expect(response.ok()).toBe(true)
          if (index === 0) {
            initialReply = await response.text()
            if (fault === 'upstream-unknown') await route.abort('failed')
            else
              await route.fulfill({ status: 200, contentType: 'application/json', body: '{"id":' })
          } else if (index === 1) {
            // A valid JSON receipt for another job must not clear our pending UUID.
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                id: '00000000-0000-4000-8000-000000000002',
                status: 'queued',
              }),
            })
          } else await route.fulfill({ response })
        })

        if (version === 'v2') {
          await page.getByRole('button', { name: '生成圖片', exact: true }).click()
          await expect(recover(page)).toBeEnabled()
        } else {
          // Reproduce a request from the old v1 client, before a version marker existed.
          const result = await page.evaluate(
            async ({ body, pendingKey, path }) => {
              const frozen = { ...body, request_id: crypto.randomUUID() }
              localStorage.setItem(pendingKey, JSON.stringify(frozen))
              try {
                await (
                  await fetch(path, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(frozen),
                  })
                ).json()
                return 'unexpected receipt'
              } catch {
                return 'response lost'
              }
            },
            { body, pendingKey, path: endpoint.v1 },
          )
          expect(result).toBe('response lost')
        }
        const original = (await pending(page))!
        const frozen = JSON.parse(original)
        const expected = {
          ...body,
          request_id: frozen.request_id,
          ...(version === 'v2' ? { feather_radius: 8 } : {}),
        }
        expect(frozen).toEqual({
          ...expected,
          ...(version === 'v2' ? { [marker]: workflow.v2 } : {}),
        })
        expect(browserRequests).toHaveLength(1)
        expect(browserRequests[0]!.path).toBe(endpoint[version])
        expect(JSON.parse(browserRequests[0]!.body)).toEqual(expected)
        const submitted = JSON.parse(initialReply)
        expect(submitted.id).toBe(frozen.request_id)
        expect(submitted.workflow_id).toBe(workflow[version])
        expect(submitted.reference_settings).toEqual(
          version === 'v2' ? { ...body, feather_radius: 8 } : body,
        )
        expect(Object.keys(submitted.workflow)).toHaveLength(version === 'v1' ? 10 : 11)
        expect(initialReply).toMatch(/"seed"\s*:\s*18446744073709551615/)
        if (fault === 'upstream-unknown') expect(submitted.status).toBe('unknown')
        else expect(submitted.status).toBe('queued')
        expect(submitted.workflow['14'].inputs.mask).toEqual([version === 'v1' ? '13' : '15', 0])
        const savedInputs = await inputs(request, submitted, version, testInfo)
        for (const reference of submitted.reference_metadata) {
          const response = await request.get('/api/assets/' + reference.id + '/image')
          expect(response.ok()).toBe(true)
          const bytes = await response.body()
          expect(hash(bytes)).toBe(reference.sha256)
          await evidence(testInfo, 'original-' + reference.input_role + '.png', bytes, 'image/png')
        }
        if (version === 'v1')
          expect(submitted.reference_metadata[1].blend_preprocessing).toBeUndefined()
        else expect(submitted.reference_metadata[1].blend_preprocessing.radius).toBe(8)
        const uploaded = (
          await (await request.get('/qa/engine-audit?after=' + before.engine_requests)).json()
        ).filter(
          (entry) =>
            entry.path === '/upload/image' &&
            entry.subfolder === 'model_atelier/' + frozen.request_id,
        )
        expect(uploaded.map((entry) => entry.name)).toEqual(
          version === 'v1'
            ? ['reference.png', 'mask.png']
            : ['reference.png', 'mask.png', 'blend.png'],
        )
        expect(uploaded.map((entry) => entry.sha256)).toEqual(Object.values(savedInputs))
        expect(uploaded.every((entry) => entry.overwrite === 'false')).toBe(true)

        await reload(page)
        await expect(page.locator('#inpaint-feather')).toHaveValue('0')
        await expect(page.locator('#inpaint-source')).toHaveValue('')
        expect(await pending(page)).toBe(original)
        expect(browserRequests).toHaveLength(1)
        await page.clock.fastForward(16000)
        await expect(page.getByRole('button', { name: '更新任務狀態', exact: true })).toBeEnabled()
        await page.getByRole('button', { name: '更新任務狀態', exact: true }).click()
        await expect(page.getByRole('button', { name: '更新任務狀態', exact: true })).toBeEnabled()
        expect(browserRequests).toHaveLength(1)
        const afterRefresh = await state(request)
        expect(afterRefresh.prompts).toBe(before.prompts + 1)
        expect(afterRefresh.uploads).toBe(before.uploads + (version === 'v1' ? 2 : 3))
        const refreshAudit = await (
          await request.get('/qa/engine-audit?after=' + before.engine_requests)
        ).json()
        expect(
          refreshAudit.some(
            (entry) => entry.method === 'GET' && entry.path === '/history/' + frozen.request_id,
          ),
        ).toBe(true)
        if (fault === 'upstream-unknown')
          expect((await (await request.get('/api/jobs/' + frozen.request_id)).json()).status).toBe(
            'unknown',
          )
        else
          expect((await (await request.get('/api/jobs/' + frozen.request_id)).json()).status).toBe(
            'completed',
          )
        await panel(page).scrollIntoViewIfNeeded()
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        ).toBe(true)
        await page.screenshot({ path: testInfo.outputPath('pending.png'), fullPage: true })
        await panel(page).screenshot({ path: testInfo.outputPath('pending-panel.png') })

        await request.post('/qa/engine/offline')
        const offline = await state(request)
        await recover(page).click()
        await expect(page.getByRole('button', { name: '處理中…', exact: true })).toBeDisabled()
        await page.keyboard.press('Enter')
        expect(browserRequests).toHaveLength(2)
        release()
        await expect(recover(page)).toBeEnabled()
        await expect(panel(page).getByRole('alert')).toContainText('任務 ID')
        expect(await pending(page)).toBe(original)
        await reload(page)
        expect(await pending(page)).toBe(original)
        expect(browserRequests).toHaveLength(2)
        await recover(page).click()
        await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeVisible()
        expect(await pending(page)).toBeNull()
        expect(browserRequests).toEqual(Array.from({ length: 3 }, () => browserRequests[0]))
        const finalResponse = await request.get('/api/jobs/' + frozen.request_id)
        const finalRaw = await finalResponse.text(),
          final = JSON.parse(finalRaw)
        expect(finalRaw).toMatch(/"seed"\s*:\s*18446744073709551615/)
        for (const key of [
          'id',
          'engine_url',
          'workflow_id',
          'workflow',
          'reference_settings',
          'reference_metadata',
          'input_uploads',
        ])
          expect(final[key]).toEqual(submitted[key])
        expect(await inputs(request, final, version)).toEqual(savedInputs)
        const audit = await (
          await request.get('/qa/engine-audit?after=' + offline.engine_requests)
        ).json()
        expect(audit.every((entry) => entry.method === 'GET')).toBe(true)
        const after = await state(request)
        expect(after.prompts).toBe(before.prompts + 1)
        expect(after.uploads).toBe(afterRefresh.uploads)
        await evidence(testInfo, 'original-pending.json', original, 'application/json')
        await evidence(
          testInfo,
          'recovery-evidence.json',
          JSON.stringify(
            {
              width,
              version,
              fault,
              browserRequests,
              initialReply,
              finalRaw,
              savedInputs,
              uploaded,
              refreshAudit,
              recoveryAudit: audit,
              before,
              after,
            },
            null,
            2,
          ),
          'application/json',
        )
      })
    }
  }

test('unknown inpaint version stays pending across reload and never dispatches', async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 900 })
  const before = await state(request)
  await page.goto('/qa/state')
  const raw = JSON.stringify({
    ...settings(before.asset_id, before.mask_asset_id),
    request_id: '00000000-0000-4000-8000-000000000003',
    feather_radius: 8,
    [marker]: 'unknown-version',
  })
  await page.evaluate(({ pendingKey, raw }) => localStorage.setItem(pendingKey, raw), {
    pendingKey,
    raw,
  })
  const sent: string[] = []
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      /\/inpaint(?:-feather)?\/generate$/.test(new URL(request.url()).pathname)
    )
      sent.push(request.url())
  })
  await page.goto('/#/studio/inpaint')
  await expect(recover(page)).toBeEnabled()
  await recover(page).click()
  await expect(panel(page).getByRole('alert')).toContainText('流程版本未知')
  expect(await pending(page)).toBe(raw)
  await reload(page)
  expect(await pending(page)).toBe(raw)
  await recover(page).click()
  await expect(panel(page).getByRole('alert')).toContainText('流程版本未知')
  expect(sent).toEqual([])
  expect((await state(request)).prompts).toBe(before.prompts)
  expect((await state(request)).uploads).toBe(before.uploads)
})

test.afterEach(async ({ request }) => {
  await request.post('/qa/engine/uncertain')
})
