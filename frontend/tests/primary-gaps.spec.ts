import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('completed stage shows original dimensions, handles offline and does not import', async ({
  page,
  request,
}) => {
  const state = await (await request.get('/qa/state')).json()
  const artwork = await (await request.get('/api/artworks/' + state.artwork_id)).json()
  const before = (await (await request.get('/api/artworks')).json()).length
  await page.goto('/#/studio/checkpoint')
  await expect(page.getByAltText('所選任務的生成結果')).toBeVisible()
  await expect(page.locator('.stage-dimensions')).toHaveText(artwork.width + ' × ' + artwork.height)
  await page
    .locator('.studio-advanced')
    .first()
    .evaluate((e: HTMLDetailsElement) => {
      e.open = true
    })
  const custom = page.getByText('自訂像素尺寸', { exact: true })
  await custom.click()
  await page.locator('#width').fill('768')
  await expect(page.locator('.stage-dimensions')).toHaveText(artwork.width + ' × ' + artwork.height)
  expect((await (await request.get('/api/artworks')).json()).length).toBe(before)
  await request.post('/qa/engine/offline')
  await page.reload()
  await expect(page.getByAltText('所選任務的生成結果')).toBeVisible()
  await request.post('/qa/engine/uncertain')
  await page.screenshot({
    path: '../docs/ui-redesign/platform-stage-result-fixture.png',
    fullPage: true,
  })
})

test('stage exposes unavailable output and recovers with retry', async ({ page }) => {
  let fail = true
  await page.route('**/api/jobs/*/results/0/image', async (route) => {
    if (fail) await route.fulfill({ status: 502, json: { detail: '原引擎離線，結果尚未保存。' } })
    else await route.continue()
  })
  await page.goto('/#/studio/checkpoint')
  await expect(
    page.getByRole('alert').filter({ hasText: '原引擎離線，結果尚未保存。' }),
  ).toBeVisible()
  fail = false
  await page.getByRole('button', { name: '重新讀取結果' }).click()
  await expect(page.getByAltText('所選任務的生成結果')).toBeVisible()
})

test('all model categories share layout and sync follows the selected category', async ({
  page,
}) => {
  const seen: string[] = []
  const base = { engine_url: 'http://mock-engine.invalid:8188', synced_at: null, sync_error: null }
  const item = {
    name: 'example.safetensors',
    version: 'v1',
    source_url: '',
    listed: true,
    architecture: 'sdxl',
    notes: '',
    metadata_updated_at: null,
  }
  await page.route(
    /\/api\/(loras|controlnets|reference-components|flux\/components)(\/sync)?$/,
    async (route) => {
      const url = new URL(route.request().url()),
        path = url.pathname
      if (route.request().method() === 'POST') seen.push(path)
      const body = path.includes('loras')
        ? { ...base, loras: [item] }
        : path.includes('controlnets')
          ? { ...base, controlnets: [{ ...item, kind: 'canny' }] }
          : path.includes('reference-components')
            ? {
                ...base,
                components: [
                  {
                    ...item,
                    role: 'ipadapter',
                    family: 'sdxl-plus-vit-h',
                    origin: 'user_registered',
                    captured_at: '',
                  },
                ],
              }
            : { ...base, groups: { diffusion_models: [item], text_encoders: [], vae: [] } }
      await route.fulfill({ json: body })
    },
  )
  await page.goto('/#/models')
  await expect(page.getByRole('button', { name: '清單', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  for (const [label, endpoint] of [
    ['LoRA', 'loras'],
    ['結構控制', 'controlnets'],
    ['元件', 'reference-components'],
    ['FLUX 元件', 'flux/components'],
  ]) {
    await page.getByRole('tab', { name: label, exact: true }).click()
    const panel = page.getByRole('tabpanel').filter({ visible: true })
    await expect(panel.locator('.model-collection.collection-list').first()).toBeVisible()
    await page.getByRole('button', { name: '同步' + label + '清單', exact: true }).click()
    await expect.poll(() => seen.at(-1)).toBe('/api/' + endpoint + '/sync')
    await page.getByRole('button', { name: '卡片', exact: true }).click()
    await expect(panel.locator('.model-collection.collection-cards').first()).toBeVisible()
    await page.getByRole('button', { name: '清單', exact: true }).click()
  }
  await page.getByRole('tab', { name: 'LoRA', exact: true }).click()
  await page
    .getByRole('tabpanel')
    .filter({ visible: true })
    .locator('.collection-details > summary')
    .click()
  await page.getByRole('button', { name: '編輯 LoRA 資料', exact: true }).click()
  await page.getByLabel('LoRA 版本', { exact: true }).fill('unsaved-value')
  await expect(page.getByRole('button', { name: '同步LoRA清單', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '卡片', exact: true }).click()
  await expect(page.getByLabel('LoRA 版本', { exact: true })).toHaveValue('unsaved-value')
  await page.getByRole('button', { name: '取消 LoRA 編輯', exact: true }).click()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({
    path: '../docs/ui-redesign/platform-model-categories-fixture.png',
    fullPage: true,
  })
})

test('asset detail keeps edits on cancelled close, saves, archives and restores focus', async ({
  page,
  request,
}) => {
  const editedTitle = '詳情測試素材 ' + Date.now()
  const state = await (await request.get('/qa/state')).json()
  await page.goto('/#/assets')
  const opener = page.locator('.asset-cover').first()
  await opener.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('link', { name: '另開原圖' })).toHaveAttribute('target', '_blank')
  const accessibility = await new AxeBuilder({ page }).include('.asset-dialog').analyze()
  expect(accessibility.violations).toEqual([])
  await dialog.getByRole('button', { name: '編輯素材資料', exact: true }).click()
  await dialog.getByLabel('素材名稱', { exact: true }).fill(editedTitle)
  page.once('dialog', (event) => event.dismiss())
  await page.keyboard.press('Escape')
  await expect(dialog.getByLabel('素材名稱', { exact: true })).toHaveValue(editedTitle)
  await dialog.getByRole('button', { name: '保存素材資料', exact: true }).click()
  await expect(dialog.getByRole('heading', { name: editedTitle, exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '封存素材', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '還原素材', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '還原素材', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '用於創作', exact: true })).toBeEnabled()
  await page.screenshot({
    path: '../docs/ui-redesign/platform-asset-detail-fixture.png',
    fullPage: true,
  })
  await dialog.getByRole('button', { name: '關閉', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.locator('.asset-cover').first()).toBeFocused()
  expect(
    (await (await request.get('/api/assets/' + state.asset_id)).json()).revision,
  ).toBeGreaterThan(0)
})

test('asset revision conflict retains dialog edits and prevents silent replacement', async ({
  page,
  request,
}) => {
  const listing = await (await request.get('/api/library/assets?scope=active&limit=40')).json()
  const item = listing.items[0]
  await page.goto('/#/assets')
  await page.locator('[data-asset-cover="' + item.id + '"]').click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: '編輯素材資料', exact: true }).click()
  await dialog.getByLabel('素材名稱', { exact: true }).fill('尚未保存的編輯')
  const external = await request.put('/api/assets/' + item.id, {
    data: {
      title: '另一視窗更新 ' + Date.now(),
      purpose: item.purpose,
      archived: false,
      revision: item.revision,
    },
  })
  expect(external.ok()).toBe(true)
  await dialog.getByRole('button', { name: '保存素材資料', exact: true }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  await expect(dialog.getByLabel('素材名稱', { exact: true })).toHaveValue('尚未保存的編輯')
  page.once('dialog', (event) => event.dismiss())
  await page.evaluate(() => {
    location.hash = '#/models'
  })
  await expect(dialog).toBeVisible()
})
