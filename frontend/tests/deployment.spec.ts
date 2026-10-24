import { test, expect } from '@playwright/test'

for (const width of [1440, 390]) {
  test(`local deployment boundary and readable roles at ${width}px`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/system')
    const panel = page
      .locator('article')
      .filter({ has: page.getByRole('heading', { name: '部署與存取', exact: true }) })
    await expect(panel).toContainText('未開放區網或公開連線')
    await expect(panel).toContainText('外部引擎')
    const before = await (await request.get('/api/settings')).json()
    const blocked = await request.put('/api/settings', {
      headers: { Origin: 'https://attacker.invalid' },
      data: { comfy_url: 'http://127.0.0.1:9999' },
    })
    expect(blocked.status()).toBe(403)
    expect(await (await request.get('/api/settings')).json()).toEqual(before)
    expect(
      (await request.get('/api/health', { headers: { Host: 'attacker.invalid' } })).status(),
    ).toBe(403)
    let gets = 0
    await page.route('**/api/deployment', async (route) => {
      gets++
      expect(route.request().method()).toBe('GET')
      await route.fulfill({ status: 503, json: { detail: 'offline' } })
    })
    const refresh = panel.getByRole('button', { name: '更新存取模式' })
    await refresh.focus()
    await refresh.press('Enter')
    await expect(panel.getByRole('alert')).toContainText('下方保留上次資料')
    await expect(panel).toContainText('外部引擎')
    expect(gets).toBe(1)
    expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
    await info.attach('deployment', { body: await panel.screenshot(), contentType: 'image/png' })
  })
}
