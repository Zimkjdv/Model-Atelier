import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

const canvasLabel = '在原圖上繪製白色編輯範圍'
const editor = (page: Page) => page.getByRole('region', { name: '遮罩繪製', exact: true })
const canvas = (page: Page) => page.getByLabel(canvasLabel, { exact: true })

async function png(page: Page, width = 800, height = 400, pattern = false) {
  const base64 = await page.evaluate(
    ({ width, height, pattern }) => {
      const image = document.createElement('canvas')
      image.width = width
      image.height = height
      const ctx = image.getContext('2d')!
      ctx.fillStyle = pattern ? 'white' : '#718d76'
      ctx.fillRect(0, 0, width, height)
      if (pattern) {
        ctx.fillStyle = '#7f7f7f'
        ctx.fillRect(width / 4, 0, width / 4, height)
        ctx.fillStyle = '#808080'
        ctx.fillRect(width / 2, 0, width / 4, height)
        ctx.clearRect((width * 3) / 4, 0, width / 4, height)
      }
      return image.toDataURL('image/png').split(',')[1]!
    },
    { width, height, pattern },
  )
  return Buffer.from(base64, 'base64')
}

async function asset(request: APIRequestContext, bytes: Buffer, name: string) {
  const response = await request.post('/api/assets?filename=' + name, {
    headers: { 'Content-Type': 'application/octet-stream' },
    data: bytes,
  })
  expect(response.ok()).toBe(true)
  return response.json() as Promise<{ id: string; width: number; height: number }>
}

async function openEditor(page: Page, request: APIRequestContext) {
  await page.goto('/qa/state')
  const source = await asset(request, await png(page), 'v01-source.png')
  await page.goto('/#/studio/inpaint')
  await page.locator('#inpaint-source').selectOption(source.id)
  await page.locator('#inpaint-checkpoint').selectOption('demo.safetensors')
  await expect(editor(page).getByRole('button', { name: '筆刷', exact: true })).toBeEnabled()
  await expect(canvas(page)).toHaveJSProperty('width', 800)
  return source
}

async function geometry(page: Page) {
  await canvas(page).scrollIntoViewIfNeeded()
  const box = (await canvas(page).boundingBox())!
  return {
    box,
    point: (x: number, y: number) => ({
      x: box.x + (x * box.width) / 800,
      y: box.y + (y * box.height) / 400,
    }),
  }
}

async function stroke(page: Page, from = [200, 100], to = [600, 100]) {
  const { point } = await geometry(page)
  const a = point(from[0]!, from[1]!),
    b = point(to[0]!, to[1]!)
  await page.mouse.move(a.x, a.y)
  await page.mouse.down()
  await page.mouse.move(b.x, b.y, { steps: 12 })
  await page.mouse.up()
}

async function pixels(target: Locator, url?: string) {
  return target.evaluate(async (element: HTMLCanvasElement, url) => {
    let image = element
    if (url) {
      const response = await fetch(url)
      if (!response.ok) throw new Error('Saved mask image unavailable')
      const bitmap = await createImageBitmap(await response.blob())
      image = document.createElement('canvas')
      image.width = bitmap.width
      image.height = bitmap.height
      image.getContext('2d')!.drawImage(bitmap, 0, 0)
      bitmap.close()
    }
    const rgba = image.getContext('2d')!.getImageData(0, 0, image.width, image.height).data
    let white = 0,
      invalid = 0,
      minX = image.width,
      minY = image.height,
      maxX = -1,
      maxY = -1
    const samples: number[] = []
    for (let i = 0; i < rgba.length; i += 4) {
      const value = rgba[i]!
      if (
        ![0, 255].includes(value) ||
        rgba[i + 1] !== value ||
        rgba[i + 2] !== value ||
        rgba[i + 3] !== 255
      )
        invalid++
      if (value === 255) {
        white++
        const x = (i / 4) % image.width,
          y = Math.floor(i / 4 / image.width)
        minX = Math.min(minX, x)
        maxX = Math.max(maxX, x)
        minY = Math.min(minY, y)
        maxY = Math.max(maxY, y)
      }
    }
    for (const [x, y] of [
      [100, 200],
      [300, 200],
      [500, 200],
      [700, 200],
      [400, 100],
      [300, 100],
    ])
      samples.push(rgba[(y! * image.width + x!) * 4]!)
    const digest = async (bytes: Uint8ClampedArray) =>
      Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
        .map((v) => v.toString(16).padStart(2, '0'))
        .join('')
    const hash = await digest(rgba)
    for (let i = 0; i < rgba.length; i += 4)
      for (let c = 0; c < 3; c++) rgba[i + c] = 255 - rgba[i + c]!
    return {
      width: image.width,
      height: image.height,
      white,
      invalid,
      minX,
      minY,
      maxX,
      maxY,
      samples,
      hash,
      inverseHash: await digest(rgba),
    }
  }, url)
}

async function choosePng(page: Page, bytes: Buffer, name = 'mask.png') {
  const choosing = page.waitForEvent('filechooser')
  await editor(page).getByRole('button', { name: '載入 PNG 遮罩', exact: true }).click()
  await (await choosing).setFiles({ name, mimeType: 'image/png', buffer: bytes })
}

async function cancelReload(page: Page) {
  const warning = page.waitForEvent('dialog')
  const reload = page.reload({ timeout: 2500 }).catch(() => null)
  const dialog = await warning
  expect(dialog.type()).toBe('beforeunload')
  await dialog.dismiss()
  await reload
}

for (const width of [1440, 390]) {
  test(`${width}px: scaled brush, eraser, invert, PNG and saved pixels`, async ({
    page,
    request,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const before = (await (await request.get('/qa/state')).json()).prompts
    const source = await openEditor(page, request)
    const mask = editor(page)
    const size = mask.getByRole('slider', { name: '大小' })
    await size.focus()
    await size.press('ArrowRight')
    await expect(size).toHaveValue('41')
    const { box } = await geometry(page)
    expect(Math.abs(box.width - 800)).toBeGreaterThan(50)
    expect(box.width / box.height).toBeCloseTo(2)
    await stroke(page)
    const painted = await pixels(canvas(page))
    expect(painted.invalid).toBe(0)
    expect(Math.abs(painted.minX - 180)).toBeLessThanOrEqual(4)
    expect(Math.abs(painted.maxX - 620)).toBeLessThanOrEqual(4)
    expect(Math.abs(painted.minY - 80)).toBeLessThanOrEqual(4)
    expect(Math.abs(painted.maxY - 120)).toBeLessThanOrEqual(4)
    expect(painted.samples[4]).toBe(255)
    await expect(mask).toContainText('遮罩尚未保存，生成已暫停')
    await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
    await mask.getByRole('button', { name: '擦除', exact: true }).click()
    await expect(mask.getByRole('button', { name: '擦除', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await stroke(page, [400, 100], [400, 100])
    const erased = await pixels(canvas(page))
    expect(erased.samples[4]).toBe(0)
    expect(erased.samples[5]).toBe(255)
    expect(erased.white).toBeLessThan(painted.white)
    await mask.getByRole('button', { name: '反相', exact: true }).click()
    const inverted = await pixels(canvas(page))
    expect(inverted.white).toBe(800 * 400 - erased.white)
    expect(inverted.hash).toBe(erased.inverseHash)
    await mask.getByRole('button', { name: '清空', exact: true }).click()
    expect((await pixels(canvas(page))).white).toBe(0)
    await expect(mask.getByRole('button', { name: '保存遮罩', exact: true })).toBeDisabled()
    await choosePng(page, await png(page, 800, 400, true))
    await expect(mask).toContainText('遮罩已載入畫布')
    const loaded = await pixels(canvas(page))
    expect(loaded.white).toBe(240000)
    expect(loaded.samples.slice(0, 4)).toEqual([255, 0, 255, 255])
    expect(loaded.invalid).toBe(0)
    await cancelReload(page)
    expect((await pixels(canvas(page))).hash).toBe(loaded.hash)

    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route('**/api/assets?*', async (route) => {
      await gate
      await route.continue()
    })
    const saving = page.waitForResponse(
      (response) =>
        response.url().includes('/api/assets?') && response.request().method() === 'POST',
    )
    await mask.getByRole('button', { name: '保存遮罩', exact: true }).click()
    await expect(mask.getByRole('button', { name: '處理中…', exact: true })).toBeDisabled()
    await expect(page.getByLabel('內容保存狀態')).toContainText('正在保存')
    await cancelReload(page)
    release()
    const response = await saving
    expect(response.ok()).toBe(true)
    const saved = await response.json()
    await expect(page.locator('#inpaint-mask')).toHaveValue(saved.id)
    await expect(mask).toContainText('使用已保存遮罩')
    await expect(mask.getByRole('button', { name: '筆刷', exact: true })).toBeEnabled()
    const stored = await pixels(canvas(page), '/api/assets/' + saved.id + '/image')
    expect([stored.width, stored.height, stored.white, stored.invalid, stored.hash]).toEqual([
      800,
      400,
      240000,
      0,
      loaded.hash,
    ])
    expect((await pixels(canvas(page))).hash).toBe(loaded.hash)
    await expect(page.getByLabel('內容保存狀態')).toContainText('有未保存變更')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
      true,
    )
    await canvas(page).scrollIntoViewIfNeeded()
    await page.screenshot({ path: testInfo.outputPath(`inpaint-${width}.png`), fullPage: true })
    await mask.screenshot({ path: testInfo.outputPath(`mask-${width}.png`) })
    await testInfo.attach('pixel-evidence', {
      body: JSON.stringify(
        { viewport: width, canvasBox: box, painted, erased, inverted, loaded, stored },
        null,
        2,
      ),
      contentType: 'application/json',
    })
    const leaving = page.waitForEvent('dialog')
    const reload = page.reload()
    await (await leaving).accept()
    await reload
    await page.locator('#inpaint-source').selectOption(source.id)
    await page.locator('#inpaint-mask').selectOption(saved.id)
    await expect(mask.getByRole('button', { name: '筆刷', exact: true })).toBeEnabled()
    expect((await pixels(canvas(page))).hash).toBe(loaded.hash)
    expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  })
}

test('cancelled source and saved-mask replacement retain the selected value and drawing', async ({
  page,
  request,
}) => {
  const source = await openEditor(page, request)
  const other = await asset(request, await png(page), 'v01-alternative.png')
  await page.getByRole('button', { name: '更新素材選項', exact: true }).click()
  await expect(page.locator('#inpaint-source option[value="' + other.id + '"]')).toBeAttached()
  await stroke(page)
  const painted = await pixels(canvas(page))
  for (const [selector, original] of [
    ['#inpaint-source', source.id],
    ['#inpaint-mask', ''],
  ]) {
    const dialog = page.waitForEvent('dialog')
    const selecting = page.locator(selector!).selectOption(other.id)
    const warning = await dialog
    expect(warning.type()).toBe('confirm')
    await warning.dismiss()
    await selecting
    await expect(page.locator(selector!)).toHaveValue(original!)
    expect((await pixels(canvas(page))).hash).toBe(painted.hash)
  }
  const refreshed = page.waitForResponse((response) =>
    response.url().includes('/api/library/assets?'),
  )
  await page.getByRole('button', { name: '更新素材選項', exact: true }).click()
  await refreshed
  await expect(page.getByRole('button', { name: '更新素材選項', exact: true })).toBeEnabled()
  expect((await pixels(canvas(page))).hash).toBe(painted.hash)
  await page.getByRole('button', { name: '系統資訊', exact: true }).click()
  await cancelReload(page)
  await page.getByRole('button', { name: '創作工作台', exact: true }).click()
  await expect(editor(page).getByRole('button', { name: '筆刷', exact: true })).toBeEnabled()
  expect((await pixels(canvas(page))).hash).toBe(painted.hash)
  page.once('dialog', (dialog) => dialog.accept())
  await page.locator('#inpaint-source').selectOption(other.id)
  await expect(page.locator('#inpaint-source')).toHaveValue(other.id)
  await expect(editor(page).getByRole('button', { name: '筆刷', exact: true })).toBeEnabled()
  expect((await pixels(canvas(page))).white).toBe(0)
  await expect(page.locator('#inpaint-mask')).toHaveValue('')
})

test('invalid PNG and failed saves retain editable pixels without uploading or generating', async ({
  page,
  request,
}) => {
  await openEditor(page, request)
  await stroke(page)
  const painted = await pixels(canvas(page))
  let uploads = 0
  await page.route('**/api/assets?*', async (route) => {
    uploads++
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'fixture save failure' }),
    })
  })
  const jpeg = await page.evaluate(() => {
    const image = document.createElement('canvas')
    image.width = 800
    image.height = 400
    return image.toDataURL('image/jpeg').split(',')[1]!
  })
  await choosePng(page, Buffer.from(jpeg, 'base64'), 'fake.png')
  await expect(editor(page).getByRole('alert')).toContainText('PNG')
  expect((await pixels(canvas(page))).hash).toBe(painted.hash)
  await choosePng(page, await png(page, 64, 64))
  await expect(editor(page).getByRole('alert')).toContainText('尺寸完全相同')
  expect((await pixels(canvas(page))).hash).toBe(painted.hash)
  await choosePng(page, Buffer.from('not a PNG'))
  await expect(editor(page).getByRole('alert')).toContainText('PNG')
  expect(uploads).toBe(0)
  await editor(page).getByRole('button', { name: '保存遮罩', exact: true }).click()
  await expect(editor(page).getByRole('alert')).toContainText('fixture save failure')
  expect(uploads).toBe(1)
  expect((await pixels(canvas(page))).hash).toBe(painted.hash)
  await expect(editor(page).getByRole('button', { name: '保存遮罩', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
  await cancelReload(page)
})

test('pointer capture, viewport resize and a lock during a stroke cannot extend stale drawing', async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await openEditor(page, request)
  let { box, point } = await geometry(page)
  const a = point(700, 200)
  await page.mouse.move(a.x, a.y)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width + 15, a.y, { steps: 5 })
  await page.mouse.up()
  const captured = await pixels(canvas(page))
  expect(captured.maxX).toBe(799)
  await page.mouse.move(box.x + 5, box.y + 5)
  expect((await pixels(canvas(page))).hash).toBe(captured.hash)
  await page.setViewportSize({ width: 390, height: 900 })
  await stroke(page, [200, 300], [400, 300])
  expect((await pixels(canvas(page))).maxY).toBeGreaterThanOrEqual(317)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/engine/capabilities/sync', async (route) => {
    await gate
    await route.continue()
  })
  ;({ box, point } = await geometry(page))
  const start = point(100, 100),
    end = point(600, 200)
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  await page.getByRole('button', { name: '更新清單與引擎選項', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(editor(page).getByRole('button', { name: '筆刷', exact: true })).toBeDisabled()
  const locked = await pixels(canvas(page))
  await page.mouse.move(end.x, end.y, { steps: 5 })
  await page.mouse.up()
  expect((await pixels(canvas(page))).hash).toBe(locked.hash)
  release()
  await expect(editor(page).getByRole('button', { name: '筆刷', exact: true })).toBeEnabled()
})

test.describe('emulated touch (does not certify touch hardware)', () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 900 } })
  test('primary touch, a second finger, cancellation and a new stroke', async ({
    page,
    request,
  }) => {
    await openEditor(page, request)
    const { point } = await geometry(page)
    await canvas(page).evaluate((element) => {
      element.dataset.touchEvents = '[]'
      for (const name of ['pointerdown', 'pointercancel'])
        element.addEventListener(name, (event) => {
          const pointer = event as PointerEvent
          const events = JSON.parse(element.dataset.touchEvents!)
          events.push({
            type: pointer.type,
            pointerType: pointer.pointerType,
            primary: pointer.isPrimary,
            trusted: pointer.isTrusted,
          })
          element.dataset.touchEvents = JSON.stringify(events)
        })
    })
    expect(await canvas(page).evaluate((element) => getComputedStyle(element).touchAction)).toBe(
      'none',
    )
    const a = point(200, 100),
      b = point(400, 100),
      c = point(600, 300)
    const session = await page.context().newCDPSession(page)
    const touch = (type: string, points: { x: number; y: number; id: number }[]) =>
      session.send('Input.dispatchTouchEvent', { type, touchPoints: points })
    const scroll = await page.evaluate(() => scrollY)
    await touch('touchStart', [{ ...a, id: 1 }])
    await touch('touchMove', [{ ...b, id: 1 }])
    await touch('touchStart', [
      { ...b, id: 1 },
      { ...c, id: 2 },
    ])
    await touch('touchMove', [
      { ...b, id: 1 },
      { ...point(700, 300), id: 2 },
    ])
    await touch('touchCancel', [])
    const cancelled = await pixels(canvas(page))
    expect(cancelled.invalid).toBe(0)
    expect(cancelled.maxY).toBeLessThan(125)
    expect(cancelled.maxX).toBeLessThan(425)
    await touch('touchStart', [{ ...c, id: 3 }])
    await touch('touchMove', [{ ...point(700, 300), id: 3 }])
    await touch('touchEnd', [])
    const restarted = await pixels(canvas(page))
    expect(restarted.invalid).toBe(0)
    expect(restarted.white).toBeGreaterThan(cancelled.white)
    expect(restarted.maxY).toBeGreaterThan(315)
    expect(await page.evaluate(() => scrollY)).toBe(scroll)
    const events = await canvas(page).evaluate((element) =>
      JSON.parse(element.dataset.touchEvents!),
    )
    expect(events).toContainEqual({
      type: 'pointerdown',
      pointerType: 'touch',
      primary: true,
      trusted: true,
    })
    expect(events).toContainEqual({
      type: 'pointerdown',
      pointerType: 'touch',
      primary: false,
      trusted: true,
    })
    expect(
      events.some(
        (event) => event.type === 'pointercancel' && event.pointerType === 'touch' && event.trusted,
      ),
    ).toBe(true)
    await expect(editor(page)).toContainText('遮罩尚未保存')
    await session.detach()
  })
})
