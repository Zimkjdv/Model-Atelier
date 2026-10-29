import { test, expect } from '@playwright/test'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const guide = pathToFileURL(path.resolve('../docs/guide/index.html')).href
for (const width of [1280, 1440, 1920, 390])
  test(`${width}px: offline guide, genuine examples, comparisons, zoom and print`, async ({
    page,
    context,
  }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const external: string[] = []
    const errors: string[] = []
    page.on('request', (request) => {
      if (/^https?:/.test(request.url())) external.push(request.url())
    })
    page.on('pageerror', (error) => errors.push(error.message))
    await context.setOffline(true)
    await page.goto(guide)
    await page.locator('img[src]').evaluateAll((nodes: HTMLImageElement[]) => {
      for (const image of nodes) image.loading = 'eager'
    })
    await expect
      .poll(() =>
        page
          .locator('img[src]')
          .evaluateAll((nodes: HTMLImageElement[]) =>
            nodes.every((image) => image.complete && image.naturalWidth > 0),
          ),
      )
      .toBe(true)
    await expect(page.locator('#examples article')).toHaveCount(3)
    await expect(page.locator('#more-recipes > details')).toHaveCount(12)
    await expect(page.locator('#style-tasks')).toContainText('套用像素風格 LoRA')
    await expect(page.locator('#style-tasks')).toContainText('使用自產示範參考圖')
    await expect(page.locator('#style-tasks')).toContainText('MODEL 1、CLIP 1')
    await expect(page.locator('#style-tasks')).toContainText('權重 0／0.6')
    await expect(page.locator('#style-tasks')).toContainText('藍色髮束')
    await page.getByRole('link', { name: '02 簡易創作與進階目的', exact: true }).click()
    await expect(page).toHaveURL(/#generate$/)
    const image = page.locator('#examples .zoom').first()
    await image.focus()
    await page.keyboard.press('Enter')
    await expect(page.locator('#image-dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('#image-dialog')).not.toBeVisible()
    await expect(image).toBeFocused()
    const before = await page.locator('details[open]').count()
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')))
    expect(await page.locator('details:not([open])').count()).toBe(0)
    await page.evaluate(() => window.dispatchEvent(new Event('afterprint')))
    expect(await page.locator('details[open]').count()).toBe(before)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(external).toEqual([])
    expect(errors).toEqual([])
    await page.locator('#examples').scrollIntoViewIfNeeded()
    await page.screenshot({ path: info.outputPath('guide-examples.png'), fullPage: false })
    await page.locator('#style-tasks').scrollIntoViewIfNeeded()
    await page.screenshot({ path: info.outputPath('guide-comparisons.png'), fullPage: false })
  })
