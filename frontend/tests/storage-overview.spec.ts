import { test, expect } from '@playwright/test'

const gib = 1024 ** 3
const report = {
  checked_at: '2026-10-24T00:00:00Z',
  folder_open_supported: true,
  warnings: ['容量為磁碟區整體容量，同一磁碟區只計算一次。', '只顯示平台與受管理的本機目錄。'],
  totals: { total: 1000 * gib, free: 400 * gib, volume_count: 1, partial: true },
  volumes: [
    { id: 'drive-c', path: 'C:\\', total: 1000 * gib, free: 400 * gib, status: 'available' },
  ],
  directories: [
    {
      id: 'data',
      role: '平台資料',
      path: 'C:\\Users\\local user\\Desktop\\model-atelier\\data',
      resolved_path: 'C:\\Users\\local user\\Desktop\\model-atelier\\data',
      volume_id: 'drive-c',
      status: 'available',
      error: null,
      can_open: true,
    },
    {
      id: 'checkpoints',
      role: '受管理本機 checkpoint',
      path: 'C:\\Users\\local user\\Desktop\\model-atelier\\runtime\\ComfyUI\\models\\checkpoints\\a-very-long-local-folder-name',
      resolved_path:
        'C:\\Users\\local user\\Desktop\\model-atelier\\runtime\\ComfyUI\\models\\checkpoints\\a-very-long-local-folder-name',
      volume_id: 'drive-c',
      status: 'available',
      error: null,
      can_open: true,
    },
    {
      id: 'artworks',
      role: '作品庫輸出',
      path: 'C:\\Users\\local user\\Desktop\\model-atelier\\data\\artworks',
      resolved_path: null,
      volume_id: null,
      status: 'missing',
      error: '目錄尚不存在，容量未知',
      can_open: false,
    },
  ],
}

for (const width of [1440, 1280]) {
  test(`storage overview ${width}px: capacity, folder action and missing directory`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.route('**/api/storage', (route) => route.fulfill({ json: report }))
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const actions: unknown[] = []
    await page.route('**/api/storage/open-directory', async (route) => {
      expect(route.request().method()).toBe('POST')
      actions.push(route.request().postDataJSON())
      await gate
      await route.fulfill({ json: { opened: true, directory_id: 'data' } })
    })
    await page.goto('/#/system')
    await page.getByRole('tab', { name: '儲存與目錄', exact: true }).click()
    await page.getByText(/查看 [0-9]+ 個目錄/).click()
    const panel = page.getByRole('region', { name: '目錄與磁碟容量' })
    await panel.getByText('完整資訊與容量統計範圍', { exact: true }).click()
    await expect(panel).toContainText('429.5 GB')
    await expect(panel.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '60')
    await expect(panel.getByRole('button', { name: '開啟作品庫輸出資料夾' })).toBeDisabled()
    await expect(panel).toContainText('尚未建立')
    const folder = panel.getByRole('button', { name: '開啟平台資料資料夾' })
    await folder.scrollIntoViewIfNeeded()
    const bounds = (await folder.boundingBox())!
    expect(bounds.width).toBeGreaterThanOrEqual(36)
    expect(bounds.height).toBeGreaterThanOrEqual(36)
    try {
      if (width === 1440) {
        await folder.focus()
        await expect(folder).toBeFocused()
        await folder.press('Enter')
      } else await folder.click()
      await expect(folder).toBeDisabled()
      await expect(
        panel.getByRole('button', { name: '開啟受管理本機 checkpoint資料夾' }),
      ).toBeDisabled()
    } finally {
      release()
    }
    await expect(panel.getByRole('status')).toContainText('已要求檔案總管開啟「平台資料」')
    expect(actions).toEqual([
      { directory_id: 'data', expected_path: report.directories[0]!.resolved_path },
    ])
    await expect(folder).toBeEnabled()
    expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await panel.screenshot({ path: info.outputPath('storage-overview-' + width + '.png') })
  })
}

test('storage action errors do not retry; refresh failure keeps the last snapshot', async ({
  page,
}) => {
  let reads = 0,
    opens = 0
  await page.route('**/api/storage', (route) =>
    ++reads === 1
      ? route.fulfill({ json: report })
      : route.fulfill({ status: 503, json: { detail: '讀取失敗' } }),
  )
  await page.route('**/api/storage/open-directory', (route) => {
    opens++
    return route.fulfill({
      status: 409,
      json: { detail: '目錄位置已變更，請更新目錄資訊後重試。' },
    })
  })
  await page.goto('/#/system')
  await page.getByRole('tab', { name: '儲存與目錄', exact: true }).click()
  await page.getByText(/查看 [0-9]+ 個目錄/).click()
  const panel = page.getByRole('region', { name: '目錄與磁碟容量' })
  await panel.getByRole('button', { name: '開啟平台資料資料夾' }).click()
  await expect(panel.getByRole('alert')).toContainText('目錄位置已變更')
  await panel.getByRole('button', { name: '更新容量' }).click()
  await expect(panel.getByRole('alert').filter({ hasText: '目前顯示上次快照' })).toBeVisible()
  await expect(panel).toContainText(report.directories[0]!.path)
  expect(opens).toBe(1)
})

test('storage folder action is disabled on unsupported hosts', async ({ page }) => {
  await page.route('**/api/storage', (route) =>
    route.fulfill({
      json: {
        ...report,
        folder_open_supported: false,
        directories: report.directories.map((entry) => ({ ...entry, can_open: false })),
      },
    }),
  )
  await page.goto('/#/system')
  await page.getByRole('tab', { name: '儲存與目錄', exact: true }).click()
  await page.getByText(/查看 [0-9]+ 個目錄/).click()
  const panel = page.getByRole('region', { name: '目錄與磁碟容量' })
  await expect(panel.getByRole('button', { name: '開啟平台資料資料夾' })).toBeDisabled()
  await expect(panel).toContainText('開啟資料夾僅支援 Windows 本機平台')
})

test('storage older running platform asks for restart before folder actions', async ({ page }) => {
  await page.route('**/api/storage', (route) =>
    route.fulfill({
      json: {
        ...report,
        folder_open_supported: undefined,
        directories: report.directories.map((entry) => ({
          ...entry,
          id: undefined,
          can_open: undefined,
        })),
      },
    }),
  )
  await page.goto('/#/system')
  await page.getByRole('tab', { name: '儲存與目錄', exact: true }).click()
  await page.getByText(/查看 [0-9]+ 個目錄/).click()
  const panel = page.getByRole('region', { name: '目錄與磁碟容量' })
  await expect(panel).toContainText('請重新啟動平台後使用開啟資料夾功能')
  await expect(panel.getByRole('button', { name: '開啟平台資料資料夾' })).toBeDisabled()
  await expect(panel).toContainText(report.directories[0]!.path)
})

test('category scan is manual and retains reliable values through scope changes and cancellation', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 900 })
  const scope = {
    version: 'first',
    unavailable: [],
    external_engine: true,
    roots: [{ category: 'models', path: 'C:\\runtime\\ComfyUI\\models' }],
  }
  const first = {
    id: 'first',
    scope,
    status: 'running',
    started_at: report.checked_at,
    finished_at: null,
    visited: 12,
    stale_reason: null,
    error: null,
  }
  const finished = {
    ...first,
    status: 'completed',
    finished_at: report.checked_at,
    categories: {
      models: { status: 'complete', bytes: 820_000_000_000, observed_bytes: 820_000_000_000 },
      artworks: { status: 'complete', bytes: 96_000_000_000, observed_bytes: 96_000_000_000 },
    },
    volumes: [{ id: 'drive-c', path: 'C:\\', models: 820_000_000_000, artworks: 96_000_000_000 }],
  }
  const stale = '目錄或引擎設定已變更。'
  type Scan = typeof first | typeof finished
  const state: {
    scope: typeof scope
    scan: Scan | null
    last_completed: Scan | null
    known: Record<string, { bytes: number; checked_at: string; stale_reason: string | null }>
  } = { scope, scan: null, last_completed: null, known: {} }
  let starts = 0
  let cancels = 0
  const second = { ...first, id: 'second', scope: { ...scope, version: 'second' } }

  await page.route('**/api/storage/categories', (route) => route.fulfill({ json: state }))
  await page.route('**/api/storage/scans', (route) => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataJSON()).toEqual({})
    state.scan = ++starts === 1 ? first : second
    return route.fulfill({ status: 202, json: state })
  })
  await page.route('**/api/storage/scans/second/cancel', (route) => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataJSON()).toEqual({})
    ++cancels
    state.scan = { ...second, status: 'cancelled' }
    return route.fulfill({ json: state })
  })

  await page.goto('/#/system')
  await page.getByRole('button', { name: /查看容量與分類掃描/ }).click()
  const panel = page.getByRole('region', { name: '分類容量', exact: true })
  const start = panel.getByRole('button', { name: '開始分類掃描' })
  await expect(panel.getByRole('status')).toHaveText('尚未掃描。')
  expect(starts).toBe(0)
  await start.click()
  await expect(panel.getByRole('status')).toContainText('掃描中 · 已檢查 12 個項目')
  state.scan = state.last_completed = finished
  state.known = {
    models: {
      bytes: finished.categories.models.bytes,
      checked_at: report.checked_at,
      stale_reason: null,
    },
    artworks: {
      bytes: finished.categories.artworks.bytes,
      checked_at: report.checked_at,
      stale_reason: null,
    },
  }
  await expect(panel.getByRole('status')).toContainText('掃描完成')
  await panel.getByText('掃描明細', { exact: true }).click()
  await expect(panel.getByRole('listitem').filter({ hasText: '模型 820 GB' })).toBeVisible()
  await expect(panel.getByRole('listitem').filter({ hasText: '作品 96 GB' })).toBeVisible()
  await expect(panel.locator('.category-share')).toBeVisible()
  await expect(panel.getByText('未知', { exact: true })).toBeVisible()
  expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)

  state.scope = second.scope
  state.scan = state.last_completed = { ...finished, stale_reason: stale }
  state.known.models!.stale_reason = state.known.artworks!.stale_reason = stale
  await page.reload()
  await page.getByRole('tab', { name: '儲存與目錄', exact: true }).click()
  await expect(panel.getByText('掃描結果已過期。' + stale)).toBeVisible()
  await expect(panel.locator('.category-share')).toHaveCount(0)
  expect(starts).toBe(1)
  await start.click()
  await panel.getByRole('button', { name: '取消掃描' }).click()
  await expect(panel.getByRole('status')).toContainText('掃描已取消')
  await expect(panel.getByText('820 GB', { exact: true })).toBeVisible()
  expect(cancels).toBe(1)
})

test('partial category scan labels observed bytes and keeps unavailable categories unknown', async ({
  page,
}) => {
  const scope = { version: 'container', roots: [], unavailable: ['models'], external_engine: true }
  await page.route('**/api/storage/categories', (route) =>
    route.fulfill({
      json: {
        scope,
        last_completed: null,
        known: {},
        scan: {
          id: 'partial',
          scope,
          status: 'partial',
          finished_at: report.checked_at,
          visited: 1,
          stale_reason: null,
          categories: {
            models: { status: 'unavailable', bytes: null, observed_bytes: null },
            artworks: { status: 'partial', bytes: null, observed_bytes: 1_200_000_000 },
          },
          volumes: [{ id: 'volume', path: '/', models: 0, artworks: 1_200_000_000 }],
          issue_count: 1,
          issues: [
            {
              category: 'artworks',
              message: '檔案已移動或無法讀取。',
              path: '/data/artworks/test.png',
            },
          ],
        },
      },
    }),
  )
  await page.goto('/#/system')
  await page.getByRole('tab', { name: '儲存與目錄', exact: true }).click()
  const panel = page.getByRole('region', { name: '分類容量', exact: true })
  await expect(panel.getByRole('status')).toContainText('掃描不完整')
  await expect(panel.getByText('此部署或設定無法統計')).toBeVisible()
  await expect(panel.getByRole('listitem').filter({ hasText: /作品 1.2 GB.*已讀取/ })).toBeVisible()
  await expect(panel.getByText('/data/artworks/test.png')).toBeVisible()
  await expect(panel.locator('.category-share')).toHaveCount(0)
})
