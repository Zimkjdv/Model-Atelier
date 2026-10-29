import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.use({ viewport: { width: 1440, height: 900 } })

test('compatibility entries reveal the actual limits and focus their summary in every studio', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  for (const route of ['checkpoint', 'inpaint', 'control', 'reference', 'flux', 'flux-addon']) {
    await page.goto('/#/studio/' + (route === 'flux-addon' ? 'flux' : route))
    if (route === 'flux-addon')
      await page.getByRole('button', { name: 'FLUX LoRA／圖生圖', exact: true }).click()
    await expect(
      page
        .locator('.studio-fields-scroll')
        .filter({ visible: true })
        .locator('.studio-tools > summary'),
    ).toBeHidden()
    await page.getByRole('button', { name: '相容性與實測', exact: true }).click()
    const details = page.locator('.studio-validation').filter({ visible: true })
    await expect(details).toHaveAttribute('open')
    await expect(details.locator(':scope > summary')).toBeFocused()
    await expect(details.locator('p').first()).toBeVisible()
  }
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('image settings and utility entries preserve values while text mode clears the active image source', async ({
  page,
  request,
}) => {
  const state = await (await request.get('/qa/state')).json()
  await page.goto('/#/studio/checkpoint')
  await page.getByRole('button', { name: '圖片重繪', exact: true }).click()
  await page.locator('#image-asset').selectOption(state.asset_id)
  await page.locator('#draft-model').selectOption('demo.safetensors')
  await page.locator('#draft-prompt').fill('Keep this source and drawing settings')
  expect((await page.locator('#image-asset').boundingBox())!.y).toBeLessThan(
    (await page.locator('#draft-prompt').boundingBox())!.y,
  )
  await expect(page.locator('#image-denoise')).not.toBeVisible()
  await page.locator('.studio-advanced > summary').first().click()
  await page.getByText('重繪設定與輸入預覽', { exact: true }).click()
  await page.locator('#image-denoise').fill('0.42')
  await page.locator('#image-resize').selectOption('stretch')
  await page.getByRole('button', { name: '文字創作', exact: true }).click()
  await page.getByRole('button', { name: '圖片重繪', exact: true }).click()
  await expect(page.locator('#image-asset')).toHaveValue('')
  await expect(page.locator('#image-denoise')).toHaveValue('0.42')
  await expect(page.locator('#image-resize')).toHaveValue('stretch')
  await page.locator('#image-asset').selectOption(state.asset_id)
  await page.getByRole('button', { name: '草稿與設定交換', exact: true }).click()
  await expect(page.locator('.studio-tools')).toHaveAttribute('open')
  await expect(page.locator('.studio-tools > summary')).toBeFocused()
  await page.getByRole('button', { name: '相容性與實測', exact: true }).click()
  await expect(page.locator('.studio-validation')).toHaveAttribute('open')
  await expect(page.locator('#draft-prompt')).toHaveValue('Keep this source and drawing settings')
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(state.prompts)
})

test('control sources remain visible for Canny, Pose and Depth; CPU preview requires an explicit action', async ({
  page,
  request,
}, info) => {
  const state = await (await request.get('/qa/state')).json()
  let previews = 0
  await page.route('**/api/control/preview', (route) => {
    previews++
    return route.fulfill({ status: 503, json: { detail: 'CPU preview temporarily unavailable' } })
  })
  await page.goto('/#/studio/control')
  await page.locator('#control-source').selectOption(state.asset_id)
  await expect(page.locator('.control-source-stage img')).toBeVisible()
  for (const kind of ['pose', 'depth', 'canny']) {
    await page.locator('#control-kind').selectOption(kind)
    await expect(page.locator('.control-source-stage img')).toBeVisible()
    await expect(page.getByRole('button', { name: '預覽 Canny 邊緣', exact: true })).toHaveCount(
      kind === 'canny' ? 1 : 0,
    )
  }
  expect(previews).toBe(0)
  await page.getByRole('button', { name: '預覽 Canny 邊緣', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('CPU preview temporarily unavailable')
  await expect(page.locator('.control-source-stage img')).toBeVisible()
  expect(previews).toBe(1)
  await page.screenshot({ path: info.outputPath('control-source.png') })
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(state.prompts)
})

test('mask image and canvas keep the same ratio within the stage at all desktop sizes', async ({
  page,
  request,
}, info) => {
  const state = await (await request.get('/qa/state')).json()
  await page.goto('/#/studio/inpaint')
  const editor = page.getByRole('region', { name: '遮罩繪製', exact: true })
  for (const [width, height] of [
    [1280, 800],
    [1440, 900],
    [1920, 1080],
  ]) {
    await page.setViewportSize({ width: width!, height: height! })
    for (const [w, h] of [
      [320, 640],
      [640, 320],
      [512, 512],
    ]) {
      const image = await page.evaluate(
        ({ w, h }) => {
          const canvas = document.createElement('canvas')
          canvas.width = w!
          canvas.height = h!
          canvas.getContext('2d')!.fillRect(0, 0, w!, h!)
          return canvas.toDataURL('image/png').split(',')[1]!
        },
        { w, h },
      )
      const asset = await (
        await request.post('/api/assets?filename=studio-stage.png', {
          headers: { 'Content-Type': 'application/octet-stream' },
          data: Buffer.from(image, 'base64'),
        })
      ).json()
      await page.reload()
      await page.locator('#inpaint-source').selectOption(asset.id)
      const canvas = editor.locator('canvas')
      await expect(canvas).toHaveJSProperty('width', w)
      const frame = (await canvas.boundingBox())!
      const original = (await editor.locator('.mask-stage img').boundingBox())!
      expect(Math.abs(frame.width / frame.height - w! / h!)).toBeLessThan(0.01)
      for (const key of ['x', 'y', 'width', 'height'] as const)
        expect(Math.abs(frame[key] - original[key])).toBeLessThan(1)
      const footer = (await page.locator('.generation-statusbar').boundingBox())!
      expect(footer.y + footer.height).toBeLessThanOrEqual(height! + 1)
      await expect(page.locator('.stage-supplement')).not.toHaveAttribute('open')
    }
    await page.screenshot({ path: info.outputPath('mask-' + width + '.png') })
  }
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(state.prompts)
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations,
  ).toEqual([])
})
