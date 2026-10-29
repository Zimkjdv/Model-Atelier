import { randomUUID } from 'node:crypto'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const key = 'atelier-pending-reference-submission'
const marker = '_atelier_reference_workflow_id'
const id = 'checkpoint-ipadapter-reference-v1'
const recover = (page: Page) => page.getByRole('button', { name: '恢復原提交請求', exact: true })

async function prepare(page: Page, request: APIRequestContext) {
  const before = await (await request.get('/qa/state')).json()
  await page.goto('/#/studio/reference')
  await expect(page.getByRole('region', { name: '畫風角色參考工作台' })).toBeVisible()
  await page.getByRole('button', { name: '來源與流程資訊', exact: true }).click()
  const editor = page.locator('.component-editor')
  await editor.locator('summary').click()
  await page.getByRole('button', { name: '同步 adapter 與編碼器清單', exact: true }).click()
  await expect(editor.getByRole('status')).toContainText('清單已同步')
  for (const [role, name, family, architecture] of [
    ['ipadapter', 'plus.safetensors', 'sdxl-plus-vit-h', 'sdxl'],
    ['clip_vision', 'vision.safetensors', 'clip-vit-h-14', 'other'],
  ]) {
    await page.locator('#reference-metadata-component').selectOption(JSON.stringify([role, name]))
    await page.locator('#reference-metadata-family').selectOption(family!)
    await page.locator('#reference-metadata-architecture').selectOption(architecture!)
    await page.locator('#reference-metadata-version').fill('fixture-r02')
    await page.locator('#reference-metadata-hash').fill('a'.repeat(64))
    await page.locator('#reference-metadata-size').fill('1234')
    await page.getByRole('button', { name: '保存參考元件登記', exact: true }).click()
    await expect(editor.getByRole('status')).toContainText('登記已保存')
    await expect(page.locator('#reference-metadata-component')).toBeEnabled()
  }
  await page.locator('.studio-advanced > summary').click()
  await page.locator('#reference-checkpoint').selectOption('demo.safetensors')
  await expect(page.locator('#reference-source')).toBeEnabled()
  await page.locator('#reference-source').selectOption(before.asset_id)
  await page.locator('#reference-ipadapter').selectOption('plus.safetensors')
  await page.locator('#reference-clip_vision').selectOption('vision.safetensors')
  await page.locator('#reference-mode').selectOption('character')
  await page.locator('#reference-prompt').fill('frozen adult character in a blue coat')
  await page.locator('#reference-seed').fill('18446744073709551615')
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeEnabled()
  return before
}

for (const width of [1440, 390]) {
  test.describe(`${width}px reference`, () => {
    test.use({ viewport: { width, height: 900 } })
    test('component registration, frozen lost response, reload, original UUID recovery and full restoration', async ({
      page,
      request,
    }, info) => {
      const before = await prepare(page, request)
      await request.post('/qa/engine/success')
      const bodies: Record<string, unknown>[] = []
      let lose = true
      await page.route('**/api/reference/generate', async (route) => {
        bodies.push(route.request().postDataJSON())
        const result = await route.fetch()
        if (lose) {
          lose = false
          await route.abort('failed')
        } else await route.fulfill({ response: result })
      })
      try {
        await page.getByRole('button', { name: '生成圖片', exact: true }).click()
        await expect(recover(page)).toBeEnabled()
        const frozenText = await page.evaluate((k) => localStorage.getItem(k), key)
        const frozen = JSON.parse(frozenText!)
        expect(frozen[marker]).toBe(id)
        expect(frozen.seed).toBe('18446744073709551615')
        expect(bodies).toHaveLength(1)
        expect(bodies[0]).not.toHaveProperty(marker)
        expect(bodies[0]!.reference_mode).toBe('character')
        const jobText = await (await request.get('/api/jobs/' + frozen.request_id)).text()
        expect(jobText).toMatch(/"seed"\s*:\s*18446744073709551615/)
        const job = JSON.parse(jobText)
        expect(job.component_metadata.map((r) => r.role)).toEqual(['ipadapter', 'clip_vision'])
        expect(job.reference_metadata[0].generation_preprocessing.width).toBe(224)
        page.on('dialog', (dialog) => dialog.accept())
        await page.reload()
        await expect(recover(page)).toBeEnabled()
        expect(await page.evaluate((k) => localStorage.getItem(k), key)).toBe(frozenText)
        expect(bodies).toHaveLength(1)
        await recover(page).click()
        await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeVisible()
        expect(bodies).toHaveLength(2)
        expect(bodies[1]).toEqual(bodies[0])
        expect(await page.evaluate((k) => localStorage.getItem(k), key)).toBeNull()
        const after = await (await request.get('/qa/state')).json()
        expect(after.prompts - before.prompts).toBe(1)
        expect(after.uploads - before.uploads).toBe(1)
        await page.getByRole('button', { name: '任務與歷史資訊', exact: true }).click()
        await page.getByRole('button', { name: '更新任務狀態', exact: true }).click()
        const restore = page.getByRole('button', {
          name: '載入原設定並調整：' + frozen.request_id,
          exact: true,
        })
        await expect(restore).toBeEnabled()
        await restore.click()
        if (await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).isVisible())
          await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).click()
        await expect(page.locator('#reference-seed')).toHaveValue('18446744073709551615')
        await expect(page.locator('#reference-mode')).toHaveValue('character')
        await expect(page.locator('#reference-source')).toHaveValue(before.asset_id)
        await expect(page.locator('#reference-prompt')).toHaveValue(
          'frozen adult character in a blue coat',
        )
        await page.getByRole('button', { name: '來源與流程資訊', exact: true }).click()
        await page.locator('.reference-components').first().locator('summary').click()
        await expect(page.locator('.reference-components').first()).toContainText('fixture-r02')
        await page.getByRole('button', { name: '文字創作', exact: true }).click()
        await page.getByRole('button', { name: '風格參考', exact: true }).click()
        await expect(page.locator('#reference-prompt')).toHaveValue(
          'frozen adult character in a blue coat',
        )
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        ).toBe(true)
        await page.screenshot({ path: info.outputPath('reference-studio.png'), fullPage: true })
        expect((await (await request.get('/qa/state')).json()).prompts).toBe(after.prompts)
      } finally {
        await request.post('/qa/engine/uncertain')
      }
    })
  })
}

test('unknown reference pending version survives recovery and refresh without dispatch', async ({
  page,
}) => {
  await page.goto('/#/system')
  const pending = {
    request_id: randomUUID(),
    [marker]: 'checkpoint-ipadapter-reference-v999',
    seed: '18446744073709551615',
    prompt: 'original',
  }
  await page.evaluate(({ key, pending }) => localStorage.setItem(key, JSON.stringify(pending)), {
    key,
    pending,
  })
  let submits = 0
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().endsWith('/generate')) submits++
  })
  await page.goto('/#/studio/reference')
  await expect(recover(page)).toBeEnabled()
  await recover(page).click()
  await expect(page.getByRole('alert').filter({ hasText: '流程版本未知' })).toBeVisible()
  expect(JSON.parse((await page.evaluate((k) => localStorage.getItem(k), key))!)).toEqual(pending)
  await page.reload()
  await expect(recover(page)).toBeEnabled()
  expect(submits).toBe(0)
})
