import { expect, test, type Page } from '@playwright/test'

const countPath = '/api/library/jobs/active-count'
const overviewPath = '/api/library/jobs/overview'

async function setVisibility(page: Page, state: DocumentVisibilityState) {
  await page.evaluate((value) => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value })
    document.dispatchEvent(new Event('visibilitychange'))
  }, state)
}

async function trackProgressStreams(page: Page) {
  await page.addInitScript(() => {
    const streams = new Map<EventTarget, string>()
    const stats = { ids: [] as string[], peak: 0 }
    Object.assign(window, { taskStreams: stats })
    // Track the lifecycle without opening sockets to either synthetic engine.
    window.EventSource = class extends EventTarget {
      constructor(url: string) {
        super()
        streams.set(this, url.split('/')[3])
        stats.ids = [...streams.values()]
        stats.peak = Math.max(stats.peak, streams.size)
      }

      close() {
        streams.delete(this)
        stats.ids = [...streams.values()]
      }
    } as unknown as typeof EventSource
  })

  return () =>
    page.evaluate(
      () => (window as Window & { taskStreams: { ids: string[]; peak: number } }).taskStreams,
    )
}

test.afterEach(async ({ page, request }) => {
  await page.close()
  expect((await request.post('/qa/task-drawer-jobs/reset')).ok()).toBeTruthy()
})

test('unfinished job pages reach the oldest original job with bounded read-only browsing', async ({
  page,
  request,
}) => {
  const fixture = await request.post('/qa/task-drawer-jobs')
  expect(fixture.ok()).toBeTruthy()
  const { active_ids: ids, other_engine: otherEngine } = (await fixture.json()) as {
    active_ids: string[]
    other_engine: string
  }
  const writes: string[] = []
  page.on('request', (value) => {
    if (value.url().includes('/api/') && value.method() !== 'GET') writes.push(value.url())
  })
  const streamStats = await trackProgressStreams(page)
  const before = (await (await request.get('/qa/state')).json()).prompts
  const oldest = ids[0]
  const overview = '**/api/library/jobs/overview?active_page=*'
  let failNextPage = true
  await page.route(overview, (route) => {
    if (failNextPage && new URL(route.request().url()).searchParams.get('active_page') === '2') {
      failNextPage = false
      return route.fulfill({ status: 503, json: { detail: '暫時無法讀取任務清單。' } })
    }
    return route.continue()
  })
  await page.goto('/#/system')
  const trigger = page.getByRole('button', { name: /任務抽屜/ })
  await trigger.click()
  const drawer = page.getByRole('dialog', { name: '生成任務' })
  const nav = drawer.getByRole('navigation', { name: '未完成任務分頁' })
  const active = drawer.getByRole('list', { name: '未完成任務' }).getByRole('listitem')
  const firstPage = [...ids].reverse().slice(0, 20)
  const secondPage = ids.slice(0, 5).reverse()
  const listedIds = () =>
    active.evaluateAll((entries) => entries.map((entry) => entry.getAttribute('data-task-id')))
  await expect(drawer.getByText('25 個未完成', { exact: true })).toBeVisible()
  await expect(nav.getByRole('status')).toHaveText('未完成任務第 1／2 頁')
  await expect.poll(listedIds).toEqual(firstPage)
  await expect(
    drawer.getByRole('list', { name: '最近結束的任務' }).getByRole('listitem'),
  ).toHaveCount(10)
  await expect.poll(async () => (await streamStats()).ids).toEqual(firstPage.slice(0, 4))

  await nav.getByRole('button', { name: '下一頁' }).click()
  await expect(drawer.getByRole('alert')).toContainText('暫時無法讀取任務清單')
  await expect(nav.getByRole('status')).toHaveText('未完成任務第 1／2 頁')
  await expect.poll(listedIds).toEqual(firstPage)
  const last = nav.getByRole('button', { name: '最早一頁' })
  await last.focus()
  await page.keyboard.press('Enter')
  await expect(nav.getByRole('status')).toHaveText('未完成任務第 2／2 頁')
  await expect(last).toBeFocused()
  await expect(last).toBeDisabled()
  await expect(drawer.getByRole('alert')).toHaveCount(0)
  await expect(drawer.getByText('25 個未完成', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('list', { name: '最近結束的任務' })).toHaveCount(0)
  await expect.poll(listedIds).toEqual(secondPage)
  await expect.poll(async () => (await streamStats()).ids).toEqual(secondPage.slice(0, 4))
  expect((await streamStats()).peak).toBe(4)

  await drawer.getByRole('button', { name: '更新任務清單' }).click()
  await expect(nav.getByRole('status')).toHaveText('未完成任務第 2／2 頁')
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
  await expect.poll(async () => (await streamStats()).ids).toEqual([])
  const reloaded = page.waitForResponse('**/api/library/jobs/overview?active_page=2')
  await trigger.click()
  expect((await reloaded).ok()).toBeTruthy()
  await expect.poll(listedIds).toEqual(secondPage)
  await nav.getByRole('button', { name: '上一頁' }).click()
  await expect.poll(listedIds).toEqual(firstPage)
  await nav.getByRole('button', { name: '下一頁' }).click()
  await expect.poll(listedIds).toEqual(secondPage)

  expect((await request.post('/qa/task-drawer-jobs/finish-five')).ok()).toBeTruthy()
  await drawer.getByRole('button', { name: '更新任務清單' }).click()
  await expect(drawer.getByText('20 個未完成', { exact: true })).toBeVisible()
  await expect(nav).toBeHidden()
  await expect.poll(listedIds).toEqual([...ids.slice(0, 20)].reverse())

  const oldJob = drawer.locator(`[data-task-id="${oldest}"]`)
  await expect(oldJob).toContainText('結果待確認')
  await expect(oldJob).toContainText(otherEngine)
  const detail = page.waitForResponse((value) => value.url().endsWith('/api/jobs/' + oldest))
  await oldJob.getByRole('button', { name: '前往原任務' }).click()
  await expect(drawer).toBeHidden()
  await expect(page).toHaveURL(/#\/studio\/checkpoint$/)
  await expect(page.locator('.job').filter({ hasText: oldest })).toBeFocused()
  expect((await detail).ok()).toBeTruthy()
  expect((await streamStats()).peak).toBe(4)
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
  expect(writes).toEqual([])
})

test('the closed drawer polls only for its count and reopening replaces a pending count', async ({
  page,
  request,
}) => {
  const { active_total: initial } = (await (await request.get(countPath)).json()) as {
    active_total: number
  }
  const streamStats = await trackProgressStreams(page)
  const reads: string[] = []
  page.on('request', (value) => {
    const path = new URL(value.url()).pathname
    if (path === countPath || path === overviewPath) reads.push(path)
  })
  let delayNextCount = false
  let releaseCount!: () => void
  const delayed = new Promise<void>((resolve) => (releaseCount = resolve))
  await page.route('**' + countPath, async (route) => {
    if (!delayNextCount) return route.continue()
    delayNextCount = false
    await delayed
    await route.fulfill({ json: { active_total: 999 } }).catch(() => {})
  })
  await page.clock.install()
  await page.goto('/#/system')
  const trigger = page.getByRole('button', { name: /任務抽屜/ })
  const badge = trigger.locator('.task-count')
  const drawer = page.getByRole('dialog', { name: '生成任務' })
  await expect(badge).toHaveText(String(initial))

  expect((await request.post('/qa/task-drawer-jobs')).ok()).toBeTruthy()
  await page.clock.fastForward(15000)
  await expect(badge).toHaveText(String(initial + 25))
  expect((await request.post('/qa/task-drawer-jobs/finish-five')).ok()).toBeTruthy()
  await page.clock.fastForward(15000)
  await expect(badge).toHaveText(String(initial + 20))
  expect(reads).toEqual([countPath, countPath, countPath])
  expect((await streamStats()).ids).toEqual([])

  await setVisibility(page, 'hidden')
  await page.clock.fastForward(45000)
  expect(reads).toHaveLength(3)
  const resumed = page.waitForResponse('**' + countPath)
  await setVisibility(page, 'visible')
  expect((await resumed).ok()).toBeTruthy()

  delayNextCount = true
  const pendingCount = page.waitForRequest('**' + countPath)
  try {
    await page.clock.fastForward(15000)
    await pendingCount
    await trigger.click()
    await expect(drawer.getByText(`${initial + 20} 個未完成`, { exact: true })).toBeVisible()
    await expect.poll(async () => (await streamStats()).ids.length).toBe(4)
    expect(reads.slice(-2)).toEqual([countPath, overviewPath])
  } finally {
    releaseCount()
  }

  await setVisibility(page, 'hidden')
  await expect.poll(async () => (await streamStats()).ids).toEqual([])
  const readsBefore = reads.length
  await page.clock.fastForward(45000)
  expect(reads).toHaveLength(readsBefore)
  const reopened = page.waitForResponse('**/api/library/jobs/overview?active_page=1')
  await setVisibility(page, 'visible')
  expect((await reopened).ok()).toBeTruthy()
  await expect.poll(async () => (await streamStats()).ids.length).toBe(4)
  const collapsed = page.waitForResponse('**' + countPath)
  await drawer.getByRole('button', { name: '關閉', exact: true }).click()
  expect((await collapsed).ok()).toBeTruthy()
  await expect(badge).toHaveText(String(initial + 20))
  expect(await streamStats()).toEqual({ ids: [], peak: 4 })
  expect(reads.slice(-2)).toEqual([overviewPath, countPath])
})
