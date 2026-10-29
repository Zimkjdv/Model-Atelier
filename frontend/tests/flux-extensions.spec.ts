import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFile } from 'node:fs/promises'

for (const width of [1440, 390]) {
  test(`${width}px F04 synthetic UI: complete drafts, exact JSON, frozen recovery and image input`, async ({
    page,
    request,
  }, testInfo) => {
    const setup = await (await request.post('/qa/flux-extensions')).json()
    const before = (await (await request.get('/qa/state')).json()).prompts
    try {
      await page.setViewportSize({ width, height: 1000 })
      await page.goto('/')
      await page.getByRole('button', { name: '創作工作台', exact: true }).click()
      await page.getByRole('tab', { name: '進階工作台', exact: true }).click()
      await page.getByRole('button', { name: 'FLUX.1 [schnell]', exact: true }).click()
      await page.getByRole('button', { name: 'FLUX LoRA／圖生圖', exact: true }).click()
      const studio = page.getByRole('region', { name: 'FLUX LoRA 與圖生圖工作台', exact: true })
      await expect(page.locator('#extension-diffusion_model')).toHaveValue(
        'flux1-schnell.safetensors',
      )
      await page.locator('#flux-extension-title').fill('F04 lora ' + width)
      await page.locator('#flux-extension-prompt').fill('pvc figure, an adult woman holding a book')
      await page.locator('#flux-extension-seed').fill('18446744073709551615')
      await studio.getByRole('button', { name: '保存附加流程草稿', exact: true }).click()
      await expect(
        studio.getByRole('status').filter({ hasText: '附加流程草稿已完整保存' }),
      ).toBeVisible()
      await page.locator('#flux-extension-lora').fill('unknown-sdxl.safetensors')
      await expect(studio.getByRole('button', { name: '生成圖片', exact: true })).toBeDisabled()
      await page.locator('#flux-extension-lora').fill('flux-schnell-pvc-style.safetensors')
      const downloadPromise = page.waitForEvent('download')
      await studio.getByRole('button', { name: '匯出附加流程 JSON', exact: true }).click()
      const downloaded = await downloadPromise
      const raw = await readFile((await downloaded.path())!, 'utf8')
      expect(raw).toContain('"seed": 18446744073709551615')
      expect(raw).toContain('LoraLoaderModelOnly')
      expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
      const bodies: string[] = []
      await page.route('**/api/flux/extensions/generate', async (route) => {
        bodies.push(route.request().postData()!)
        if (bodies.length === 1) {
          await route.fetch()
          await route.abort('failed')
        } else await route.continue()
      })
      await studio.getByRole('button', { name: '生成圖片', exact: true }).click()
      await expect(
        studio.getByRole('button', { name: '恢復原提交請求', exact: true }),
      ).toBeEnabled()
      await studio.getByRole('button', { name: '恢復原提交請求', exact: true }).click()
      await expect.poll(() => bodies.length).toBe(2)
      expect(bodies[1]).toBe(bodies[0])
      expect(JSON.parse(bodies[0]).workflow_id).toBe('flux1-schnell-lora-v1')
      expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 1)
      const jobId = JSON.parse(bodies[0]).request_id
      await request.post('/api/jobs/' + jobId + '/refresh')
      const imported = await (await request.post('/api/jobs/' + jobId + '/artworks')).json()
      expect(imported.errors).toEqual([])
      const artwork = (imported.imported[0] || imported.existing[0]).id
      const restored = await (
        await request.get('/api/flux/artworks/' + artwork + '/creation-settings')
      ).json()
      expect(restored.settings.lora_strength).toBe(0.7)
      expect(restored.settings.seed).toBe('18446744073709551615')
      const artworkRecord = await (await request.get('/api/artworks/' + artwork)).json()
      await page.getByRole('button', { name: '作品庫', exact: true }).click()
      await page
        .getByRole('button', { name: '查看作品 ' + artworkRecord.title, exact: true })
        .click()
      await page
        .getByRole('dialog')
        .getByRole('button', { name: '載入創作設定 →', exact: true })
        .click()
      await expect(studio).toBeVisible()
      await expect(page.locator('#flux-extension-seed')).toHaveValue('18446744073709551615')
      await expect(
        studio.getByRole('status').filter({ hasText: '完整附加設定已載入' }),
      ).toBeVisible()
      await expect(page.locator('#flux-extension-kind')).toBeEnabled()
      await page.locator('#flux-extension-kind').selectOption('image')
      await page.locator('#flux-extension-image').selectOption(setup.asset_id)
      await page.locator('#flux-extension-title').fill('F04 image ' + width)
      await studio.getByRole('button', { name: '保存附加流程草稿', exact: true }).click()
      await expect(
        studio.getByRole('status').filter({ hasText: '附加流程草稿已完整保存' }),
      ).toBeVisible()
      const drafts = await (await request.get('/api/flux/extensions/drafts')).json()
      const image = drafts.find((entry: { title: string }) => entry.title === 'F04 image ' + width)
      expect(image.workflow_id).toBe('flux1-schnell-image2image-v1')
      expect(image.image_asset_id).toBe(setup.asset_id)
      expect(image.denoise).toBe(0.6)
      expect(image.lora_name).toBeUndefined()
      await studio.getByRole('button', { name: '生成圖片', exact: true }).click()
      await expect.poll(() => bodies.length).toBe(3)
      const imageRequest = JSON.parse(bodies[2])
      expect(imageRequest.workflow_id).toBe('flux1-schnell-image2image-v1')
      expect(imageRequest.lora_name).toBeUndefined()
      await request.post('/api/jobs/' + imageRequest.request_id + '/refresh')
      await studio.getByRole('button', { name: '更新任務狀態', exact: true }).click()
      await expect(studio.getByRole('alert')).toHaveCount(0)
      expect((await (await request.get('/qa/state')).json()).prompts).toBe(before + 2)
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true)
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
      await page.screenshot({
        path: testInfo.outputPath('flux-image-' + width + '.png'),
        fullPage: true,
      })
    } finally {
      await request.post('/qa/flux-extensions?enabled=false')
    }
  })
}
