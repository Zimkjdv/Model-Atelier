import { test, expect, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'

async function studio(page: Page, mode = 'Checkpoint／SDXL') {
  await page.goto('/')
  await page.getByRole('button', { name: '創作工作台', exact: true }).click()
  await page.getByRole('button', { name: mode, exact: true }).click()
}

async function cancelReload(page: Page) {
  const dialog = page.waitForEvent('dialog')
  const reload = page.reload({ timeout: 2500 }).catch(() => null)
  const value = await dialog
  expect(value.type()).toBe('beforeunload')
  await value.dismiss()
  await reload
}

for (const [mode, prompt] of [
  ['Checkpoint／SDXL', '#draft-prompt'], ['FLUX.1 [schnell]', '#flux-prompt'],
  ['局部編輯', '#inpaint-prompt'], ['Canny 結構參考', '#control-prompt'],
]) {
  test(`${mode}: unsaved refresh, close and cached page`, async ({ page, request }) => {
    const before = (await (await request.get('/qa/state')).json()).prompts
    await studio(page, mode)
    await page.locator(prompt).fill('retained unsaved content')
    if (mode === '局部編輯') {
      const { asset_id } = await (await request.get('/qa/state')).json()
      await page.locator('#inpaint-source').selectOption(asset_id)
      const canvas = page.locator('canvas[aria-label="在原圖上繪製白色編輯範圍"]')
      await canvas.scrollIntoViewIfNeeded()
      const box = (await canvas.boundingBox())!
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
      const pixels = await canvas.evaluate((c: HTMLCanvasElement) => c.toDataURL())
      await cancelReload(page)
      expect(await canvas.evaluate((c: HTMLCanvasElement) => c.toDataURL())).toBe(pixels)
    }
    await page.getByRole('button', { name: '系統資訊', exact: true }).click()
    await cancelReload(page)
    await page.getByRole('button', { name: '創作工作台', exact: true }).click()
    await expect(page.locator(prompt)).toHaveValue('retained unsaved content')
    const closing = page.waitForEvent('dialog')
    const close = page.close({ runBeforeUnload: true })
    await (await closing).dismiss()
    await close
    expect(page.isClosed()).toBe(false)
    const leaving = page.waitForEvent('dialog')
    const reload = page.reload()
    await (await leaving).accept()
    await reload
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  })
}

test('draft save protects in flight and clears protection only after success', async ({ page }) => {
  for (const mode of ['Checkpoint／SDXL', 'FLUX.1 [schnell]']) {
    await studio(page, mode)
    const flux = mode.startsWith('FLUX')
    await page.locator(flux ? '#flux-prompt' : '#draft-prompt').fill('saved prompt')
    if (flux) for (const name of ['diffusion_model', 'clip_l', 't5xxl', 'vae']) await page.locator('#flux-' + name).fill(name + '.safetensors')
    await page.getByRole('button', { name: flux ? '保存 FLUX 草稿' : '保存草稿', exact: true }).click()
    await expect(page.getByLabel('內容保存狀態')).toContainText('正在保存')
    await cancelReload(page)
    await expect(page.getByLabel('內容保存狀態')).toContainText('草稿已保存到本機')
    let dialogs = 0
    const handler = async (dialog) => { dialogs++; await dialog.dismiss() }
    page.on('dialog', handler)
    await page.reload()
    page.off('dialog', handler)
    expect(dialogs).toBe(0)
  }
})

test('lost response recovers the original UUID, payload and endpoint once', async ({ page, request }) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  await studio(page)
  await page.locator('#draft-prompt').fill('original prompt')
  await page.getByText('進階設定', { exact: true }).click()
  await page.locator('#seed').fill('18446744073709551615')
  const bodies: string[] = []
  await page.route('**/api/generate', async route => {
    bodies.push(route.request().postData()!)
    if (bodies.length === 1) { await route.fetch(); await route.abort('failed') }
    else await route.continue()
  })
  await page.getByRole('button', { name: '生成圖片', exact: true }).click()
  await expect(page.getByRole('button', { name: '恢復原提交請求', exact: true })).toBeEnabled()
  await page.locator('#draft-prompt').fill('changed current form')
  await page.getByRole('button', { name: '恢復原提交請求', exact: true }).click()
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeVisible()
  expect(bodies).toHaveLength(2)
  expect(bodies[1]).toBe(bodies[0])
  expect(JSON.parse(bodies[0]).seed).toBe('18446744073709551615')
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 1)
})

test('keyboard preview, real JSON download and revision conflict preserve edits', async ({ page, request }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '作品庫', exact: true }).click()
  const cover = page.getByRole('button', { name: '查看作品 qa-artwork.png', exact: true })
  await cover.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('button', { name: '關閉 ×' })).toBeFocused()
  const downloadPromise = page.waitForEvent('download')
  await dialog.getByRole('link', { name: '下載完整工作流程', exact: true }).click()
  const download = await downloadPromise
  const text = await readFile((await download.path())!, 'utf8')
  expect(text).toContain('18446744073709551615')
  expect(JSON.parse(text)['5'].class_type).toBe('KSampler')
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(cover).toBeFocused()
  await page.keyboard.press('Enter')
  await page.locator('#artwork-notes').fill('keep local note')
  await request.post('/qa/conflict')
  await page.getByRole('button', { name: '保存筆記', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('另一個視窗')
  await expect(page.locator('#artwork-notes')).toHaveValue('keep local note')
})

test('390px basic navigation, preview and input stay operable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await studio(page)
  await page.locator('#draft-prompt').fill('narrow viewport')
  await page.getByRole('button', { name: 'Canny 結構參考', exact: true }).click()
  await page.locator('#control-prompt').fill('narrow Canny')
  await page.getByRole('button', { name: '作品庫', exact: true }).click()
  await page.getByRole('button', { name: '查看作品 qa-artwork.png', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '關閉 ×', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
})

