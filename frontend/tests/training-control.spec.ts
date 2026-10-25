import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

for (const width of [1440, 390]) {
  test(`explicit training, lost responses, stop and new resume at ${width}px`, async ({ page }) => {
    const original = 'b5000000-0000-4000-8000-000000000001',
      resumed = 'b5000000-0000-4000-8000-000000000002'
    const exported = 'b5000000-0000-4000-8000-000000000003'
    const model = {
      run_id: original,
      status: 'prepared',
      resources_released: true,
      manifest_sha256: 'a'.repeat(64),
      configuration: { label: 'Synthetic web case', max_steps: 3, seed: 4294967295 },
      dataset: { id: 'self-authored-fixture' },
      base: { id: 'animagine-xl-4.0-opt' },
      environment: { trainer_revision: 'b'.repeat(40) },
      state: { steps_completed: 0 },
      resume: null,
      checkpoints: [] as { id: string; step: number }[],
      resources: null,
      artifacts: null,
      log_tail: '',
      start_requested: false,
    }
    let current = { ...model },
      receipt: Record<string, any> | null = null
    let starts = 0,
      prepares = 0,
      resumes = 0,
      stops = 0,
      evaluations = 0
    await page.route('**/api/training/**', async (route) => {
      const path = new URL(route.request().url()).pathname.replace('/api/training/', '')
      const method = route.request().method()
      if (path === 'control')
        return route.fulfill({
          json: {
            available: true,
            requests: receipt ? [receipt] : [],
            runs: receipt ? [current] : [],
            exports: [
              {
                request_id: exported,
                dataset_label: 'self-authored-fixture',
                revision: 2,
                kind: 'style',
              },
            ],
          },
        })
      if (path === 'runtime/check') return route.fulfill({ json: { ready: true, issues: [] } })
      if (path === 'requests' && method === 'POST') {
        prepares++
        const body = route.request().postDataJSON()
        expect(body.seed).toBe(4294967295)
        receipt = { request_id: body.request_id, status: 'prepared', run_id: original }
        return route.abort('failed')
      }
      if (path.startsWith('requests/')) return route.fulfill({ json: receipt })
      if (path === 'resume-requests') {
        resumes++
        const body = route.request().postDataJSON()
        expect(body.resume_run_id).toBe(original)
        expect(body.checkpoint).toBe('step-1')
        current = { ...model, run_id: resumed }
        receipt = { request_id: body.request_id, status: 'prepared', run_id: resumed }
        return route.fulfill({ status: 202, json: receipt })
      }
      if (path.endsWith('/start')) {
        starts++
        current = {
          ...current,
          status: 'running',
          resources_released: false,
          start_requested: true,
        }
        return route.abort('failed')
      }
      if (path.endsWith('/stop')) {
        stops++
        current = { ...current, status: 'stopping', resources_released: false }
        return route.fulfill({ json: { stop_requested: true } })
      }
      if (path.endsWith('/artifact'))
        return route.fulfill({
          json: {
            run_id: current.run_id,
            technical_only: true,
            weight: { sha256: 'c'.repeat(64) },
          },
        })
      if (path.endsWith('/publish'))
        return route.fulfill({ json: { catalog_entry: { name: 'technical.safetensors' } } })
      if (path === 'evaluation-requests') {
        evaluations++
        receipt = {
          request_id: route.request().postDataJSON().request_id,
          run_id: current.run_id,
          status: 'completed',
          evaluation: { plans: Array(6).fill({}), generation_started: false },
        }
        return route.fulfill({ status: 202, json: receipt })
      }
      if (path.startsWith('runs/')) return route.fulfill({ json: current })
      return route.fulfill({ status: 404, json: { detail: 'Unconfigured fixture route' } })
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/training')
    await page.getByRole('button', { name: '訓練執行', exact: true }).click()
    await page.getByRole('button', { name: '檢查獨立訓練環境', exact: true }).click()
    await expect(
      page.getByText('獨立環境檢查通過；不代表已開始訓練', { exact: true }),
    ).toBeVisible()
    await page.getByLabel('已封存資料包', { exact: true }).selectOption(exported)
    await page.getByLabel('訓練名稱', { exact: true }).fill('Synthetic web case')
    await page.getByLabel('訓練 seed', { exact: true }).fill('4294967295')
    await page.getByRole('button', { name: '準備新 run（不開始訓練）', exact: true }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await page.getByRole('button', { name: '查回原訓練請求', exact: true }).click()
    await page.getByRole('button', { name: '開啟新 run', exact: true }).click()
    expect(prepares).toBe(1)
    expect(starts).toBe(0)
    await page.getByRole('button', { name: '開始此 run 的訓練', exact: true }).click()
    await page.getByRole('button', { name: '查回原 run 狀態', exact: true }).click()
    await expect(page.getByText('狀態：訓練中 · 程序或租約尚未釋放', { exact: true })).toBeVisible()
    expect(starts).toBe(1)
    await expect(
      page.getByRole('button', { name: '開始此 run 的訓練', exact: true }),
    ).toBeDisabled()
    await page.getByRole('button', { name: '要求停止此 run', exact: true }).click()
    await expect(page.getByText('狀態：停止中 · 程序或租約尚未釋放', { exact: true })).toBeVisible()
    current = {
      ...current,
      status: 'stopped',
      resources_released: true,
      checkpoints: [{ id: 'step-1', step: 1 }],
    }
    await page.getByRole('button', { name: '查回原 run 狀態', exact: true }).click()
    await page.getByRole('button', { name: '準備另一個請求', exact: true }).click()
    await page.getByLabel('完整 checkpoint', { exact: true }).selectOption('step-1')
    await page.getByRole('button', { name: '以新 UUID 準備續訓（不開始）', exact: true }).click()
    await page.getByRole('button', { name: '開啟新 run', exact: true }).click()
    await expect(page.getByText('Run UUID：' + resumed, { exact: true })).toBeVisible()
    expect(resumes).toBe(1)
    expect(starts).toBe(1)
    expect(stops).toBe(1)
    current = { ...current, status: 'completed', resources_released: true }
    await page.getByRole('button', { name: '查回原 run 狀態', exact: true }).click()
    await page.getByRole('button', { name: '驗證並安裝 LoRA', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: '產物身分已驗證並安裝' })).toBeVisible()
    await page.getByRole('button', { name: '同步模型庫與來源登記', exact: true }).click()
    await page.getByRole('button', { name: '準備另一個請求', exact: true }).click()
    await page.getByRole('button', { name: '建立固定比較方案（不生成）', exact: true }).click()
    await expect(
      page.getByText('已保存 6 份比較方案，沒有生成圖片。', { exact: true }),
    ).toBeVisible()
    expect(evaluations).toBe(1)
    expect(starts).toBe(1)
    const accessibility = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze()
    expect(accessibility.violations).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
