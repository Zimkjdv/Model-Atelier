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
    await page.getByRole('tab', { name: '主機與引擎', exact: true }).click()
    const host = page.getByRole('region', { name: '平台主機', exact: true })
    await expect(host).toContainText('isolated-container')
    await expect(host).toContainText('容器可見資源')
    await expect(host).toContainText('並非 Windows 宿主機完整資訊')
    await page.getByRole('tab', { name: '安裝與部署', exact: true }).click()
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
