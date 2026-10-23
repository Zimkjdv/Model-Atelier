import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const width of [1440, 390]) {
  test(`frozen source-scoped resource observations at ${width}px`, async ({
    page,
    request,
  }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const response = await request.post('/qa/resource-samples')
    expect(response.ok()).toBe(true)
    const item = await response.json()
    await page.goto('/#/gallery')
    await page
      .getByRole('button', { name: '查看作品 ' + item.title, exact: true })
      .first()
      .click()
    const dialog = page.getByRole('dialog')
    await dialog.getByText('任務耗時與資源來源', { exact: true }).click()
    const samples = dialog.getByRole('group', { name: '連續資源取樣' })
    await expect(samples).toContainText('成功 3／嘗試 3 次')
    await expect(samples).toContainText('7.00 GiB')
    await expect(samples).toContainText('已確認任務終態，取樣已凍結')
    await expect(dialog).toContainText('任務專用 VRAM 峰值：未知')
    await samples.getByText('最近取樣（最多 120 筆）', { exact: true }).click()
    await expect(samples.getByRole('listitem')).toHaveCount(3)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
      true,
    )
    const audit = await new AxeBuilder({ page })
      .include('dialog[open]')
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze()
    expect(audit.violations).toEqual([])
    await samples.screenshot({ path: info.outputPath('resource-samples.png') })
    const frozen = await (await request.get('/api/artworks/' + item.id)).json()
    expect(frozen.measurements).toEqual(item.measurements)
  })
}
