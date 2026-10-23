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

for (const width of [1440, 390]) {
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
    const panel = page.getByRole('region', { name: '目錄與磁碟容量' })
    await expect(panel).toContainText('400.00 GiB')
    await expect(panel.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '60')
    await expect(panel.getByRole('button', { name: '開啟作品庫輸出資料夾' })).toBeDisabled()
    await expect(panel).toContainText('尚未建立')
    const folder = panel.getByRole('button', { name: '開啟平台資料資料夾' })
    await folder.scrollIntoViewIfNeeded()
    const bounds = (await folder.boundingBox())!
    expect(bounds.width).toBeGreaterThanOrEqual(44)
    expect(bounds.height).toBeGreaterThanOrEqual(44)
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
  const panel = page.getByRole('region', { name: '目錄與磁碟容量' })
  await expect(panel).toContainText('請重新啟動平台後使用開啟資料夾功能')
  await expect(panel.getByRole('button', { name: '開啟平台資料資料夾' })).toBeDisabled()
  await expect(panel).toContainText(report.directories[0]!.path)
})
