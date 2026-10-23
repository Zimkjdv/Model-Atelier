import { expect, test } from '@playwright/test'

for (const width of [1440, 390])
  for (const kind of ['pose', 'depth']) {
    test(`${width}px ${kind}: frozen recovery and exact seed`, async ({ page, request }) => {
      await page.setViewportSize({ width, height: 900 })
      const before = await (await request.get('/qa/state')).json()
      const engine = 'http://mock-engine.invalid:8188',
        name = kind + '.safetensors'
      await request.post('/qa/engine/success')
      expect(
        (await request.post('/api/controlnets/sync', { data: { engine_url: engine } })).ok(),
      ).toBeTruthy()
      expect(
        (
          await request.put('/api/controlnets/metadata', {
            data: { engine_url: engine, name, kind, architecture: 'sdxl', version: 'fixture-r01' },
          })
        ).ok(),
      ).toBeTruthy()
      await page.goto('/#/studio/control')
      await expect(page.locator('#control-kind')).toBeEnabled()
      await page.locator('#control-kind').selectOption(kind)
      await page.locator('#control-checkpoint').selectOption('demo.safetensors')
      await expect(page.locator('#control-source')).toBeEnabled()
      await page.locator('#control-source').selectOption(before.asset_id)
      await page.locator('#control-model').selectOption(name)
      await page.locator('#control-prompt').fill('adult woman standing in a park')
      await page.locator('#control-seed').fill('18446744073709551615')
      await page.locator('#control-width').fill('64')
      await page.locator('#control-height').fill('64')
      let lose = true
      const bodies: Record<string, unknown>[] = []
      await page.route('**/api/structure/generate', async (route) => {
        bodies.push(route.request().postDataJSON())
        const result = await route.fetch()
        if (lose) {
          lose = false
          await route.abort()
        } else await route.fulfill({ response: result })
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
      expect(bodies[0]?.seed).toBe('18446744073709551615')
      expect(bodies[0]?.control_kind).toBe(kind)
      expect(bodies[0]).not.toHaveProperty('canny_low')
      await request.post('/api/jobs/' + bodies[0]?.request_id + '/refresh')
      await page.getByRole('button', { name: '更新任務狀態', exact: true }).click()
      await page
        .getByRole('button', { name: '載入原設定並調整：' + bodies[0]?.request_id, exact: true })
        .click()
      await expect(page.locator('#control-kind')).toHaveValue(kind)
      await expect(page.locator('#control-seed')).toHaveValue('18446744073709551615')
      const after = await (await request.get('/qa/state')).json()
      expect(after.prompts - before.prompts).toBe(1)
      await request.post('/qa/engine/uncertain')
    })
  }
