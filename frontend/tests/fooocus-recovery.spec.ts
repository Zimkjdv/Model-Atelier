import { expect, test } from '@playwright/test'
for (const width of [1440, 390])
  test(`${width}px Fooocus: model, preview, frozen recovery and restoration`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    await request.post('/qa/fooocus/enable')
    await request.post('/qa/engine/success')
    try {
      const before = await (await request.get('/qa/state')).json()
      await page.goto('/#/studio/inpaint')
      await page.locator('#inpaint-checkpoint').selectOption('animagine-xl-4.0-opt.safetensors')
      await expect(page.locator('#inpaint-source')).toBeEnabled()
      await page.locator('#inpaint-source').selectOption(before.asset_id)
      await page.locator('#inpaint-mask').selectOption(before.mask_asset_id)
      await page.locator('#inpaint-model').selectOption('fooocus-v2.6')
      await page.locator('#inpaint-width').fill('64')
      await page.locator('#inpaint-height').fill('64')
      await page.locator('#inpaint-feather').fill('0')
      await page.locator('#inpaint-prompt').fill('flowers in a park')
      await page.locator('#inpaint-seed').fill('18446744073709551615')
      expect(await page.locator('#inpaint-denoise').inputValue()).toBe('1')
      await page.getByRole('button', { name: '預覽合成遮罩', exact: true }).click()
      await expect(page.getByAltText('本次表單已保存遮罩的內側羽化灰階預覽')).toBeVisible()
      const bodies: Record<string, unknown>[] = []
      let lose = true
      await page.route('**/api/fooocus-inpaint/generate', async (route) => {
        bodies.push(route.request().postDataJSON())
        const r = await route.fetch()
        if (lose) {
          lose = false
          await route.abort()
        } else await route.fulfill({ response: r })
      })
      await expect(page.getByRole('button', { name: '生成圖片', exact: true })).toBeEnabled()
      await page.getByRole('button', { name: '生成圖片', exact: true }).click()
      const recover = page.getByRole('button', { name: '恢復原提交請求', exact: true })
      await expect(recover).toBeEnabled()
      await page.reload()
      await expect(recover).toBeEnabled()
      await recover.click()
      await expect.poll(() => bodies.length).toBe(2)
      expect(bodies[0]).toEqual(bodies[1])
      expect(bodies[0]?.inpaint_model).toBe('fooocus-v2.6')
      expect(bodies[0]?.seed).toBe('18446744073709551615')
      await request.post('/api/jobs/' + bodies[0]?.request_id + '/refresh')
      await page.getByRole('button', { name: '更新任務狀態', exact: true }).click()
      await page
        .getByRole('button', { name: '載入原設定並調整：' + bodies[0]?.request_id, exact: true })
        .click()
      await expect(page.locator('#inpaint-model')).toHaveValue('fooocus-v2.6')
      await expect(page.locator('#inpaint-seed')).toHaveValue('18446744073709551615')
      const after = await (await request.get('/qa/state')).json()
      expect(after.prompts - before.prompts).toBe(1)
    } finally {
      await request.post('/qa/fooocus/reset')
      await request.post('/qa/engine/uncertain')
    }
  })
