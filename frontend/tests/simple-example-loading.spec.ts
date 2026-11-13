import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { expect, test, type Page } from '@playwright/test'

const previewImages = /\/assets\/[^/]+\.webp$/
const originalImages = /\/assets\/[^/]+\.png$/
const cafeOriginal = /\/assets\/animagine-cafe-[^/]+\.png$/

async function openSimple(page: Page) {
  await page.goto('/#/studio/simple')
  await expect(page.locator('.simple-example > summary')).toBeVisible()
}

const hash = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')

test('simple creation loads card previews, then only the opened example and its original evidence', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  const originals: string[] = []
  page.on('request', (value) => {
    if (originalImages.test(new URL(value.url()).pathname)) originals.push(value.url())
  })
  await openSimple(page)
  const cards = page.locator('.simple-card-image img')
  await expect(cards).toHaveCount(3)
  await expect
    .poll(() =>
      cards.evaluateAll((nodes) =>
        nodes.every((node) => (node as HTMLImageElement).naturalWidth === 328),
      ),
    )
    .toBe(true)
  const previews = await page.evaluate(
    (pattern) =>
      performance
        .getEntriesByType('resource')
        .filter((value) => new RegExp(pattern).test(new URL(value.name).pathname))
        .map((value) => (value as PerformanceResourceTiming).encodedBodySize),
    previewImages.source,
  )
  expect(previews).toHaveLength(3)
  expect(previews.reduce((sum, bytes) => sum + bytes, 0)).toBeLessThan(80_000)
  const examples = page.locator('.simple-example')
  await expect(examples.locator('img')).toHaveCount(0)
  expect(originals).toEqual([])

  const variants = page.getByRole('group', { name: '模型內的起始配方' })
  await variants.getByRole('button', { name: /清晨咖啡館/ }).click()
  await expect(examples).toHaveJSProperty('open', false)
  await expect(examples.locator('img')).toHaveCount(0)
  expect(originals).toEqual([])

  const imageResponse = page.waitForResponse((value) =>
    cafeOriginal.test(new URL(value.url()).pathname),
  )
  await examples.locator('summary').click()
  const original = await imageResponse
  expect(original.ok()).toBeTruthy()
  await expect(examples.locator('img')).toBeVisible()
  const originalLink = examples.getByRole('link', { name: '開啟 animagine-cafe 範例原圖' })
  expect(new URL((await originalLink.getAttribute('href'))!, page.url()).href).toBe(original.url())
  const recipeDownload = page.waitForEvent('download')
  await examples.getByRole('link', { name: '下載完整配方與實測紀錄（JSON）' }).click()
  const download = await recipeDownload
  const recipeBytes = await readFile((await download.path())!)
  expect(recipeBytes.equals(await readFile('../docs/guide/examples/animagine-cafe-v1.json'))).toBe(
    true,
  )
  const recipe = JSON.parse(recipeBytes.toString('utf8'))
  expect(recipe.settings.seed).toBe('9007199254740994')
  expect(hash(await original.body())).toBe(recipe.image.sha256)
  expect(originals).toEqual([original.url()])

  await variants.getByRole('button', { name: /森林旅人/ }).click()
  await expect(examples).toHaveJSProperty('open', false)
  await expect(examples.locator('img')).toHaveCount(0)
  expect(originals).toHaveLength(1)

  const styles = page.getByRole('group', { name: '畫風控制任務' })
  await styles.getByRole('button', { name: /LoRA/ }).click()
  const comparison = page.locator('.simple-style-example')
  await expect(comparison.locator('img')).toHaveCount(0)
  expect(originals).toHaveLength(1)
  await comparison.locator('summary').click()
  await expect(comparison.locator('img')).toHaveCount(2)
  await expect.poll(() => originals.length).toBe(3)
  expect(originals.slice(1).every((url) => /\/lora-(baseline|style)-/.test(url))).toBe(true)
  await expect(examples.locator('img')).toHaveCount(0)
  await styles.getByRole('button', { name: /圖片的畫風/ }).click()
  await expect(comparison).toHaveJSProperty('open', false)
  await expect(comparison.locator('img')).toHaveCount(0)
  expect(originals).toHaveLength(3)
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('an example image reserves space and keeps its original link when loading fails', async ({
  page,
}) => {
  let release = () => {}
  const response = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(cafeOriginal, async (route) => {
    await response
    await route.abort()
  })
  await openSimple(page)
  await page
    .getByRole('group', { name: '模型內的起始配方' })
    .getByRole('button', { name: /清晨咖啡館/ })
    .click()
  const example = page.locator('.simple-example')
  await example.locator('summary').click()
  const frame = example.locator('.example-image')
  const bounds = () =>
    frame.evaluate((element) => {
      const { width, height } = element.getBoundingClientRect()
      return { width, height }
    })
  let pending
  try {
    await expect(frame).toBeVisible()
    pending = await bounds()
    expect(pending.width).toBeGreaterThan(0)
    expect(pending.height).toBeCloseTo(pending.width, 0)
  } finally {
    release()
  }
  await expect(frame.getByRole('status')).toHaveText('範例圖片無法載入。')
  expect(await bounds()).toEqual(pending)
  await expect(example.getByRole('link', { name: '開啟 animagine-cafe 範例原圖' })).toHaveAttribute(
    'href',
    cafeOriginal,
  )
})
