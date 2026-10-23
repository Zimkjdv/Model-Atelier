import { randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { expect, test } from '@playwright/test'

for (const width of [1440, 390]) {
  test.describe(`${width}px R06`, () => {
    test.use({ viewport: { width, height: 900 } })
    test('new axes round trip, manual load and traced result', async ({ page, request }, info) => {
      expect((await request.post('/qa/extended-models')).ok()).toBe(true)
      const before = await (await request.get('/qa/state')).json()
      const title = 'R06 ' + randomUUID()
      try {
        const creation = await (
          await request.get('/api/artworks/' + before.artwork_id + '/creation-settings')
        ).json()
        const settings = {
          ...creation.settings,
          title,
          width: 64,
          height: 64,
          workflow_mode: width === 390 ? 'image2image' : 'text2image',
          image_asset_id: width === 390 ? before.asset_id : null,
          reference_ids: width === 390 ? [before.asset_id] : [],
          reference_resize: 'fit',
          denoise: 0.45,
        }
        expect((await request.post('/api/drafts', { data: settings })).ok()).toBe(true)
        await page.goto('/#/studio/checkpoint')
        await page
          .locator('.draft-row')
          .filter({ has: page.getByText(title, { exact: true }) })
          .click()
        if (await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).isVisible())
          await page.getByRole('button', { name: '捨棄變更並載入', exact: true }).click()
        const area = page.locator('.experiment-planner')
        await area.locator(':scope > summary').click()
        await page.locator('#experiment-title').fill(title)
        for (const [axis, values] of [
          ['sampler_name', ['euler', 'dpmpp_2m']],
          ['scheduler', ['normal', 'karras']],
          ['checkpoint', ['demo.safetensors', 'alternate.safetensors']],
        ] as const) {
          await page.locator('#experiment-axis').selectOption(axis)
          await page.locator('#experiment-values').fill(JSON.stringify(values))
          await area.getByRole('button', { name: '預覽比較方案', exact: true }).click()
          await expect(area.getByRole('region', { name: '參數比較預覽' })).toContainText(
            '預計 2 次生成',
          )
        }
        await area.getByText('模型登記快照（非權重驗證）', { exact: true }).click()
        await expect(area.getByRole('region', { name: '參數比較預覽' })).toContainText(
          'fixture-r06-2',
        )
        await area.locator('.saved-experiments > summary').click()
        const saving = page.waitForResponse(
          (r) => r.url().endsWith('/api/experiments/plans') && r.request().method() === 'POST',
        )
        await area.getByRole('button', { name: '保存目前預覽方案', exact: true }).click()
        const savedResponse = await saving
        expect(savedResponse.ok(), await savedResponse.text()).toBe(true)
        const record = await savedResponse.json()
        expect(record.plan.schema_version).toBe(2)
        await area.getByRole('button', { name: '匯出比較方案 JSON', exact: true }).click()
        const downloaded = page.waitForEvent('download')
        await area.getByRole('link', { name: '下載上次匯出的比較方案' }).click()
        const download = await downloaded
        const path = info.outputPath('comparison-v2.json')
        await download.saveAs(path)
        const exported = JSON.parse(await readFile(path, 'utf8'))
        expect(exported.model_snapshots).toEqual(record.plan.model_snapshots)
        await area.getByRole('button', { name: '重載比較方案 ' + title, exact: true }).click()
        await expect(page.locator('#draft-title')).toHaveValue(title)
        await page.locator('#experiment-import-file').setInputFiles(path)
        await area.getByRole('button', { name: '驗證並預覽比較文件', exact: true }).click()
        await area.getByRole('button', { name: '使用此方案預覽', exact: true }).click()
        await expect(page.locator('#draft-title')).toHaveValue(title)
        // Reopen saved source before manual load so the job has an explicit association.
        await area.getByRole('button', { name: '重載比較方案 ' + title, exact: true }).click()
        await area.getByRole('button', { name: '載入比較設定 variant-1', exact: true }).click()
        await expect(page.locator('#draft-title')).toHaveValue(
          record.plan.variants[0].settings.title,
        )
        expect((await (await request.get('/qa/state')).json()).prompts).toBe(before.prompts)
        await page.screenshot({ path: info.outputPath('loaded.png'), fullPage: true })
        await request.post('/qa/engine/success')
        const generating = page.waitForResponse(
          (r) => r.url().endsWith('/api/generate') && r.request().method() === 'POST',
        )
        await page.getByRole('button', { name: '生成圖片', exact: true }).click()
        const submitted = await generating
        expect(submitted.ok(), await submitted.text()).toBe(true)
        const body = submitted.request().postDataJSON()
        expect(body.experiment).toEqual({
          plan_id: record.id,
          plan_sha256: record.plan.plan_sha256,
          variant_id: 'variant-1',
        })
        await expect
          .poll(
            async () =>
              (await (await request.post('/api/jobs/' + body.request_id + '/refresh')).json())
                .status,
          )
          .toBe('completed')
        const imported = await request.post('/api/jobs/' + body.request_id + '/artworks')
        expect(imported.ok(), await imported.text()).toBe(true)
        await area.getByRole('button', { name: '重讀已保存結果', exact: true }).click()
        await expect(area.locator('.result-group').first()).toContainText('已完成')
        await expect(area.locator('.result-group').nth(1)).toContainText('尚無關聯任務')
        const report = await request.get(
          '/api/experiments/plans/' +
            record.id +
            '/report?expected_plan_sha256=' +
            record.plan.plan_sha256,
        )
        expect(report.ok(), await report.text()).toBe(true)
        expect(
          (await report.json()).variants[0].runs[0].experiment_context.expected_model_metadata,
        ).toEqual(record.plan.model_snapshots[0])
        expect((await (await request.get('/qa/state')).json()).prompts).toBe(before.prompts + 1)
        await area.getByRole('region', { name: '比較方案的已保存結果' }).scrollIntoViewIfNeeded()
        await page.screenshot({ path: info.outputPath('results.png') })
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        )
      } finally {
        await request.post('/qa/engine/uncertain')
        await request.post('/qa/extended-models/reset')
      }
    })
  })
}
