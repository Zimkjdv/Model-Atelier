import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const width of [1440, 390]) {
  for (const family of ['inpaint', 'control'] as const) {
    test(`${width}px ${family}: versioned support and refusal preserve all inputs without dispatch`, async ({
      page,
      request,
    }, info) => {
      await page.setViewportSize({ width, height: 900 })
      const before = await (await request.get('/qa/state')).json()
      const drafts = await (await request.get('/api/drafts')).body()
      const plans = await (await request.get('/api/experiments/plans')).body()
      const jobs = (await (await request.get('/api/jobs')).json()).map((job: any) => job.id)
      const response = await request.get('/api/reference-workflows/support?family=' + family)
      expect(response.ok()).toBe(true)
      const report = await response.json()
      await page.goto('/#/studio/' + family)
      const panel = page.locator('.format-support')
      await panel.locator('summary').focus()
      await panel.locator('summary').press('Enter')
      await expect(panel.getByRole('listitem')).toHaveCount(report.workflows.length)
      await expect(panel).toContainText('workflow 不包含素材圖片')
      for (const workflow of report.workflows) {
        const row = panel.getByRole('listitem').filter({ hasText: workflow.name })
        await expect(row).toContainText('一般草稿尚未支援')
        await expect(row).toContainText('完整工作流程下載已提供')
        const settings = {
          title: 'R07 preserve inputs',
          prompt: 'R07 preserved prompt',
          negative_prompt: '',
          engine_url: 'http://mock-engine.invalid:8188',
          checkpoint: 'demo.safetensors',
          width: 128,
          height: 64,
          seed: '18446744073709551615',
          steps: 20,
          cfg: 7,
          sampler_name: 'euler',
          scheduler: 'normal',
          denoise: family === 'inpaint' ? 0.7 : 1,
          loras: [],
          reference_resize: 'stretch',
          image_asset_id: before.asset_id,
          workflow_mode: family === 'inpaint' ? 'image2image' : 'text2image',
          reference_ids:
            family === 'inpaint' ? [before.asset_id, before.mask_asset_id] : [before.asset_id],
          ...(family === 'inpaint'
            ? {
                mask_asset_id: before.mask_asset_id,
                grow_mask_by: 17,
                ...(workflow.version === 2 ? { feather_radius: 4 } : {}),
              }
            : {
                control_net_name: 'canny.safetensors',
                control_strength: 0.75,
                control_start: 0.1,
                control_end: 0.9,
                canny_low: 0.2,
                canny_high: 0.8,
              }),
        }
        const original = JSON.stringify(settings)
        const saved = await request.post('/api/drafts', { data: settings })
        expect(saved.status()).toBe(422)
        expect(await saved.text()).toContain('未部分保存')
        for (const action of ['export', 'import']) {
          const value = {
            workflow_id: workflow.id,
            settings,
            ...(action === 'import' ? { kind: 'model-atelier-creation', schema_version: 1 } : {}),
          }
          const rejected = await request.post('/api/creation-settings/' + action, { data: value })
          expect(rejected.status()).toBe(422)
          expect(await rejected.text()).toContain('完整工作流程 JSON')
        }
        const preview = await request.post('/api/experiments/preview', {
          data: { title: 'R07', settings, axis: 'steps', values: [4, 8], case_ids: [] },
        })
        expect(preview.status()).toBe(422)
        expect(JSON.stringify(settings)).toBe(original)
      }
      await page.locator('#' + family + '-prompt').fill('R07 unsubmitted form')
      await page.locator('#' + family + '-seed').fill('18446744073709551615')
      const audit = await new AxeBuilder({ page })
        .include('.format-support')
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze()
      expect(audit.violations).toEqual([])
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true)
      await panel.screenshot({ path: info.outputPath('format-support.png') })
      await page
        .getByRole('button', {
          name: family === 'inpaint' ? 'Canny 結構參考' : '局部編輯',
          exact: true,
        })
        .click()
      await page
        .getByRole('button', {
          name: family === 'inpaint' ? '局部編輯' : 'Canny 結構參考',
          exact: true,
        })
        .click()
      await expect(page.locator('#' + family + '-prompt')).toHaveValue('R07 unsubmitted form')
      await expect(page.locator('#' + family + '-seed')).toHaveValue('18446744073709551615')
      expect(await (await request.get('/api/drafts')).body()).toEqual(drafts)
      expect(await (await request.get('/api/experiments/plans')).body()).toEqual(plans)
      expect((await (await request.get('/api/jobs')).json()).map((job: any) => job.id)).toEqual(
        jobs,
      )
      const after = await (await request.get('/qa/state')).json()
      expect(after.prompts).toBe(before.prompts)
      expect(after.uploads).toBe(before.uploads)
    })
  }
}

test('support read failure and retry preserve the unsaved form', async ({ page }) => {
  await page.route('**/api/reference-workflows/support?*', (route) =>
    route.fulfill({ status: 503, json: { detail: '支援範圍暫時無法讀取' } }),
  )
  await page.goto('/#/studio/inpaint')
  await page.locator('#inpaint-prompt').fill('keep this prompt')
  const panel = page.locator('.format-support')
  await panel.locator('summary').click()
  await expect(panel.getByRole('alert')).toContainText('支援範圍暫時無法讀取')
  await page.unroute('**/api/reference-workflows/support?*')
  await panel.getByRole('button', { name: '重新讀取支援範圍', exact: true }).click()
  await expect(panel.getByRole('listitem')).toHaveCount(3)
  await expect(page.locator('#inpaint-prompt')).toHaveValue('keep this prompt')
})
