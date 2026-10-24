import { test, expect } from '@playwright/test'

for (const width of [1440, 390]) {
  test(`container hardware scope is distinct from host and engine at ${width}px`, async ({
    page,
    request,
  }) => {
    const system = await (await request.get('/api/system')).json()
    const deployment = await (await request.get('/api/deployment')).json()
    await page.route('**/api/system', (route) =>
      route.fulfill({
        json: {
          ...system,
          runtime_kind: 'container',
          host: 'isolated-container',
          role: '容器平台',
        },
      }),
    )
    await page.route('**/api/deployment', (route) =>
      route.fulfill({
        json: {
          ...deployment,
          mode: 'container-local',
        },
      }),
    )
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/system')
    await expect(page.locator('.host-bar')).toContainText('容器平台')
    await expect(page.getByText('不是 Windows 宿主機的完整資訊', { exact: false })).toBeVisible()
    await expect(
      page.getByRole('button', { name: '檢查本機 ComfyUI 安裝', exact: true }),
    ).toHaveCount(0)
    await expect(
      page.getByText('容器無法檢查 Windows 的原生 Python 安裝', { exact: false }),
    ).toBeVisible()
    const panel = page
      .locator('article')
      .filter({ has: page.getByRole('heading', { name: '部署與存取', exact: true }) })
    await expect(panel).toContainText('本機容器')
    await expect(panel).toContainText('未開放區網或公開連線')
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
  })
}
