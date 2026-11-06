import { test, expect, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import AxeBuilder from '@axe-core/playwright'

const converted = {
  prompt: 'TokenX, a black cat by a window, without a collar, watercolor',
  model: 'qwen3.5:2b',
  base_url: 'http://127.0.0.1:11434',
  elapsed_ms: 1234,
}
async function open(page: Page, prompt?: string) {
  await page.goto('/#/studio/checkpoint')
  if (prompt !== undefined) await page.locator('#draft-prompt').fill(prompt)
  await page.getByRole('button', { name: '中文轉英文', exact: true }).click()
  const widget = page.getByRole('dialog', { name: '提示詞助手', exact: true })
  await expect(widget.getByLabel('中文畫面描述')).toBeVisible()
  return widget
}
test.beforeEach(async ({ request }) => {
  await request.put('/api/prompt-converter/settings', {
    data: { base_url: 'http://127.0.0.1:11434', model: 'qwen3.5:2b' },
  })
})

for (const width of [1440, 390]) {
  test(`${width}px: preview, edit and explicit apply preserve generation settings`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const before = (await (await request.get('/qa/state')).json()).prompts
    let body: Record<string, unknown> | null = null
    await page.route('**/api/prompt-converter/convert', async (route) => {
      body = route.request().postDataJSON()
      await route.fulfill({ json: converted })
    })
    const widget = await open(page, 'original prompt')
    const negative = await page.locator('#draft-negative').inputValue()
    await expect(widget.locator('.converter-options')).not.toHaveAttribute('open')
    await expect(widget.locator('.converter-settings')).not.toHaveAttribute('open')
    await widget.getByLabel('中文畫面描述').fill('一隻黑貓坐在窗邊，不要項圈，水彩風格')
    await widget.locator('.converter-options > summary').click()
    await widget.getByLabel('必須保留的觸發詞', { exact: false }).fill('TokenX')
    await widget.locator('.converter-options > summary').click()
    await widget.getByRole('button', { name: '轉成英文提示詞', exact: true }).click()
    await expect(widget.getByLabel('英文提示詞預覽（可修改）')).toHaveValue(converted.prompt)
    expect(body).toMatchObject({
      description: '一隻黑貓坐在窗邊，不要項圈，水彩風格',
      protected_terms: ['TokenX'],
    })
    await expect(page.locator('#draft-prompt')).toHaveValue('original prompt')
    await widget.getByLabel('英文提示詞預覽（可修改）').fill(converted.prompt + ', ink')
    const shellBounds = await page.locator('.atelier-shell').boundingBox()
    expect(Math.round(shellBounds!.width)).toBe(width)
    const closeBounds = await widget
      .getByRole('button', { name: '關閉中文轉換器', exact: true })
      .boundingBox()
    expect(closeBounds!.x).toBeGreaterThanOrEqual(0)
    expect(closeBounds!.x + closeBounds!.width).toBeLessThanOrEqual(width)
    const sourceBounds = await widget.getByLabel('中文畫面描述').boundingBox()
    const previewBounds = await widget.getByLabel('英文提示詞預覽（可修改）').boundingBox()
    if (width > 640) expect(previewBounds!.x).toBeGreaterThan(sourceBounds!.x)
    else expect(previewBounds!.y).toBeGreaterThan(sourceBounds!.y)
    await page.screenshot({ path: info.outputPath(`converter-${width}.png`) })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(
      (await new AxeBuilder({ page }).include('.converter-dialog[open]').analyze()).violations,
    ).toEqual([])
    await widget.getByRole('button', { name: '套用英文提示詞', exact: true }).click()
    await expect(widget).not.toBeVisible()
    await expect(page.locator('#draft-prompt')).toHaveValue(converted.prompt + ', ink')
    await expect(page.locator('.prompt-editor:visible .prompt-editor-applied')).toHaveText(
      '已套用英文，可繼續編輯。',
    )
    await expect(page.locator('#draft-negative')).toHaveValue(negative)
    await expect(page.getByRole('button', { name: '中文轉英文', exact: true })).toBeFocused()
    await page.locator('#draft-prompt').scrollIntoViewIfNeeded()
    await page.screenshot({ path: info.outputPath(`prompt-editor-${width}.png`) })
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  })
}

for (const change of ['source', 'prompt', 'model', 'navigation', 'close']) {
  test(`discard late responses after ${change}, prevent duplicate conversion`, async ({ page }) => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let calls = 0
    await page.route('**/api/prompt-converter/convert', async (route) => {
      ++calls
      await gate
      await route.fulfill({ json: converted }).catch(() => {})
    })
    const widget = await open(page)
    await widget.getByLabel('中文畫面描述').fill('黑貓')
    const received = page.waitForRequest('**/api/prompt-converter/convert')
    await widget.getByRole('button', { name: '轉成英文提示詞', exact: true }).click()
    await received
    await expect(widget.getByRole('button', { name: '正在轉換…', exact: true })).toBeDisabled()
    if (change === 'source') await widget.getByLabel('中文畫面描述').fill('白狗')
    else if (change === 'prompt') {
      await page.locator('#draft-prompt').evaluate((element) => {
        const field = element as HTMLTextAreaElement
        field.value = 'manual edit'
        field.dispatchEvent(new Event('input', { bubbles: true }))
      })
    } else if (change === 'model') {
      await page.locator('#draft-model').evaluate((element) => {
        const field = element as HTMLSelectElement
        field.value = field.value ? '' : 'demo.safetensors'
        field.dispatchEvent(new Event('change', { bubbles: true }))
      })
    } else if (change === 'close') {
      await page.keyboard.press('Escape')
      await expect(widget).not.toBeVisible()
    } else {
      await page.evaluate(() => {
        location.hash = '/system'
      })
      await expect(widget).not.toBeVisible()
    }
    release()
    if (change === 'navigation') {
      await page
        .getByRole('navigation')
        .getByRole('button', { name: '創作工作台', exact: true })
        .click()
      await page.getByRole('tab', { name: '進階工作台', exact: true }).click()
    }
    if (change === 'navigation' || change === 'close')
      await page.getByRole('button', { name: '中文轉英文', exact: true }).click()
    await expect(page.getByLabel('英文提示詞預覽（可修改）')).toHaveCount(0)
    if (change === 'prompt') await expect(page.locator('#draft-prompt')).toHaveValue('manual edit')
    expect(calls).toBe(1)
  })
}

test('offline, missing model, timeout and malformed replies retain input without retry', async ({
  page,
}) => {
  let status = 503,
    calls = 0
  await page.route('**/api/prompt-converter/convert', async (route) => {
    ++calls
    await route.fulfill({
      status,
      json: status === 200 ? { unexpected: true } : { detail: `測試錯誤 ${status}` },
    })
  })
  const widget = await open(page, 'retained original')
  await widget.getByLabel('中文畫面描述').fill('黑貓')
  for (const code of [503, 404, 504, 502, 200]) {
    status = code
    await widget.getByRole('button', { name: '轉成英文提示詞', exact: true }).click()
    await expect(widget.getByRole('alert')).toContainText(
      code === 200 ? '轉換回覆格式無效' : `測試錯誤 ${code}`,
    )
    await expect(widget.getByLabel('中文畫面描述')).toHaveValue('黑貓')
    await expect(page.locator('#draft-prompt')).toHaveValue('retained original')
    await expect(widget.getByLabel('英文提示詞預覽（可修改）')).toHaveCount(0)
  }
  expect(calls).toBe(5)
})

test('LLM settings save explicitly and status checks do not submit images', async ({
  page,
  request,
}) => {
  const widget = await open(page)
  await widget.locator('.converter-settings > summary').click()
  await widget.getByLabel('已安裝模型名稱').fill('local-test:2b')
  await widget.getByLabel('中文畫面描述').fill('黑貓')
  await expect(widget.getByRole('button', { name: '轉成英文提示詞', exact: true })).toBeDisabled()
  await widget.getByRole('button', { name: '保存 LLM 設定', exact: true }).click()
  await expect(widget.getByText('已保存本機 LLM 設定。', { exact: true })).toBeVisible()
  expect((await (await request.get('/api/prompt-converter/settings')).json()).model).toBe(
    'local-test:2b',
  )
  await page.route('**/api/prompt-converter/status', (route) =>
    route.fulfill({ json: { available: true, model: 'local-test:2b' } }),
  )
  await widget.getByRole('button', { name: '檢查連線與模型', exact: true }).click()
  await expect(widget.getByText('本機模型可用：local-test:2b')).toBeVisible()
})

test('simple recipe requires editing, apply marks it modified; FLUX components still open', async ({
  page,
  request,
}) => {
  const manifest = JSON.parse(await readFile('../models/animagine-xl-4.0-opt.json', 'utf8'))
  const catalog = await (await request.get('/api/models')).json()
  const original = catalog.models.find((item: { name: string }) => item.name === 'demo.safetensors')
  try {
    await request.post('/qa/simple-creation')
    await request.put('/api/models/metadata', {
      data: {
        engine_url: catalog.engine_url,
        name: 'demo.safetensors',
        architecture: 'sdxl',
        sha256: manifest.sha256,
      },
    })
    await request.post('/api/engine/capabilities/sync')
    await page.route('**/api/prompt-converter/convert', (route) =>
      route.fulfill({ json: converted }),
    )
    await page.goto('/#/studio/simple')
    await page.getByRole('button', { name: '載入起始配方', exact: true }).click()
    await expect(page.getByRole('button', { name: '中文轉英文', exact: true })).toHaveCount(0)
    await expect(page.locator('#simple-prompt')).toHaveAttribute('readonly', '')
    await page.getByRole('button', { name: '編輯描述', exact: true }).click()
    await page.getByRole('button', { name: '中文轉英文', exact: true }).click()
    const widget = page.getByRole('dialog', { name: '提示詞助手', exact: true })
    await widget.getByLabel('中文畫面描述').fill('黑貓')
    await widget.getByRole('button', { name: '轉成英文提示詞', exact: true }).click()
    await widget.getByRole('button', { name: '套用英文提示詞', exact: true }).click()
    await expect(page.locator('#simple-prompt')).toHaveValue(converted.prompt)
    await expect(page.getByText('已修改配方，不沿用原配置的驗收結論。')).toBeVisible()
    await page.goto('/#/studio/flux')
    await expect(page.locator('.prompt-converter:visible')).toHaveCount(1)
    await page.getByRole('button', { name: '元件設定', exact: true }).click()
    await expect(page.locator('.flux-editor > fieldset > .studio-advanced')).toHaveAttribute(
      'open',
      '',
    )
  } finally {
    await request.put('/api/models/metadata', {
      data: { ...original, engine_url: catalog.engine_url },
    })
    await request.post('/qa/simple-creation?enabled=false')
  }
})

test('return and reopen preserve the draft and preview without applying or converting again', async ({
  page,
  request,
}) => {
  let calls = 0
  await page.route('**/api/prompt-converter/convert', (route) => {
    ++calls
    return route.fulfill({ json: converted })
  })
  const before = (await (await request.get('/qa/state')).json()).prompts
  const widget = await open(page, 'keep current English')
  await widget.getByLabel('中文畫面描述').fill('黑貓坐在窗邊')
  await widget.getByRole('button', { name: '轉成英文提示詞', exact: true }).click()
  await widget.getByLabel('英文提示詞預覽（可修改）').fill(converted.prompt + ', pencil sketch')
  expect(await widget.evaluate((dialog) => dialog.matches(':modal'))).toBe(true)
  await page.keyboard.press('Escape')
  await expect(widget).not.toBeVisible()
  await expect(page.locator('#draft-prompt')).toHaveValue('keep current English')
  await expect(page.getByRole('button', { name: '中文轉英文', exact: true })).toBeFocused()
  await page.getByRole('button', { name: '中文轉英文', exact: true }).click()
  await expect(widget.getByLabel('中文畫面描述')).toHaveValue('黑貓坐在窗邊')
  await expect(widget.getByLabel('英文提示詞預覽（可修改）')).toHaveValue(
    converted.prompt + ', pencil sketch',
  )
  await widget.getByRole('button', { name: '返回編輯', exact: true }).click()
  await expect(page.locator('#draft-prompt')).toHaveValue('keep current English')
  expect(calls).toBe(1)
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('short mobile dialog scrolls settings while keeping apply and close in view', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 640 })
  await page.route('**/api/prompt-converter/convert', (route) => route.fulfill({ json: converted }))
  const widget = await open(page)
  await widget.getByLabel('中文畫面描述').fill('山間湖泊')
  await widget.getByRole('button', { name: '轉成英文提示詞', exact: true }).click()
  await expect(widget.getByLabel('英文提示詞預覽（可修改）')).toHaveValue(converted.prompt)
  await widget.locator('.converter-options > summary').click()
  await widget.locator('.converter-settings > summary').click()
  const bounds = await widget
    .getByRole('button', { name: '套用英文提示詞', exact: true })
    .boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.y).toBeGreaterThanOrEqual(0)
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(640)
  expect(
    await widget
      .locator('.converter-body')
      .evaluate((element) => element.scrollHeight > element.clientHeight),
  ).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('converter-settings-390.png') })
  await widget.getByRole('button', { name: '套用英文提示詞', exact: true }).click()
  await expect(widget).not.toBeVisible()
  await expect(page.locator('#draft-prompt')).toHaveValue(converted.prompt)
})
