import { expect, test, type Page } from '@playwright/test'

function scripts(page: Page) {
  return page.evaluate(() =>
    performance
      .getEntriesByType('resource')
      .filter(
        (entry): entry is PerformanceResourceTiming =>
          entry instanceof PerformanceResourceTiming &&
          /\/assets\/[^/]+\.js$/.test(new URL(entry.name).pathname),
      )
      .map(({ name, decodedBodySize }) => ({ name, decodedBodySize })),
  )
}

test('system entry keeps its JavaScript budget and loads training only on demand', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page.getByRole('tab', { name: '總覽', exact: true })).toBeVisible()
  const startup = await scripts(page)
  expect(startup.length).toBeGreaterThan(0)
  const initialBytes = startup.reduce((sum, resource) => sum + resource.decodedBodySize, 0)
  expect(initialBytes).toBeGreaterThan(0)
  expect(initialBytes).toBeLessThan(500_000)
  expect(startup.some(({ name }) => name.includes('/assets/TrainingWorkspace-'))).toBe(false)

  await page.getByRole('button', { name: '訓練工作區', exact: true }).click()
  await expect(page.getByRole('group', { name: '訓練階段', exact: true })).toBeVisible()
  expect(
    (await scripts(page)).some(({ name }) => name.includes('/assets/TrainingWorkspace-')),
  ).toBe(true)
})

test('settings downloads panels only when opened and keeps a visited panel mounted', async ({
  page,
}) => {
  await page.goto('/#/settings')
  await expect(page.getByRole('tab', { name: '引擎連線' })).toBeVisible()
  expect((await scripts(page)).map(({ name }) => name).join(' ')).not.toMatch(
    /\/(LocalModelPaths|DiagnosticsPanel)-/,
  )
  const paths = page.getByRole('tab', { name: '模型路徑' })
  await paths.click()
  await expect
    .poll(async () => (await scripts(page)).map(({ name }) => name).join(' '))
    .toMatch(/\/LocalModelPaths-/)
  expect((await scripts(page)).map(({ name }) => name).join(' ')).not.toMatch(/\/DiagnosticsPanel-/)
  const input = page.getByRole('tabpanel', { name: '模型路徑' }).locator('#local-checkpoint-paths')
  await input.fill('C:/qa-unsaved-models')
  await page.getByRole('tab', { name: '引擎連線' }).click()
  await paths.click()
  await expect(input).toHaveValue('C:/qa-unsaved-models')
})

test('failed workspace load shows a retry and reloads the same destination', async ({
  page,
  request,
}) => {
  const before = (await (await request.get('/qa/state')).json()).prompts
  let release!: () => void
  const blocked = new Promise<void>((resolve) => (release = resolve))
  await page.route(
    '**/assets/TrainingWorkspace-*.js',
    async (route) => {
      await blocked
      await route.abort('failed')
    },
    { times: 1 },
  )
  await page.goto('/#/system')
  await page.getByRole('button', { name: '訓練工作區', exact: true }).click()
  try {
    await expect(page.getByText('正在載入工作區…', { exact: true })).toBeVisible()
  } finally {
    release()
  }
  await expect(page.getByRole('alert')).toHaveText('工作區載入失敗。請重新載入頁面後再試。')
  await expect(page).toHaveURL(/#\/training$/)
  await page.getByRole('button', { name: '重新載入頁面', exact: true }).click()
  await expect(page.getByRole('group', { name: '訓練階段', exact: true })).toBeVisible()
  await expect(page).toHaveURL(/#\/training$/)
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})

test('leaving before the first studio load completes preserves the destination and later form', async ({
  page,
}) => {
  let release!: () => void
  const blocked = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/assets/CreationStudio-*.js', async (route) => {
    await blocked
    await route.continue()
  })
  let draftReads = 0
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/drafts') draftReads++
  })
  const studioResponse = page.waitForResponse('**/assets/CreationStudio-*.js')
  const navigate = (name: string) =>
    page.getByRole('navigation', { name: '主要導覽' }).getByRole('button', { name }).click()
  await page.goto('/#/studio/checkpoint', { waitUntil: 'commit' })
  try {
    await expect(page.getByText('正在載入工作區…', { exact: true })).toBeVisible()
    await navigate('系統資訊')
    await expect(page.getByRole('tab', { name: '總覽', exact: true })).toBeVisible()
  } finally {
    release()
  }
  const studioUrl = (await studioResponse).url()
  await page.evaluate(async (url) => {
    await import(url)
    await new Promise(requestAnimationFrame)
  }, studioUrl)
  expect(draftReads).toBe(0)
  const prompt = page.locator('#draft-prompt')
  await expect(prompt).toHaveCount(0)
  await navigate('創作工作台')
  await expect.poll(() => draftReads).toBeGreaterThan(0)
  await prompt.fill('保留未保存的提示詞')
  await navigate('系統資訊')
  await navigate('創作工作台')
  await expect(prompt).toHaveValue('保留未保存的提示詞')
})

test('the task drawer locates its original job on the first studio load', async ({
  page,
  request,
}) => {
  const source = await page.context().newPage()
  await request.post('/qa/engine/uncertain')
  await source.goto('/#/studio/checkpoint')
  await source.locator('#draft-model').selectOption('demo.safetensors')
  await source.locator('#draft-prompt').fill('Locate this task in a new tab')
  const submitted = source.waitForResponse(
    (response) =>
      response.url().endsWith('/api/generate') && response.request().method() === 'POST',
  )
  await source.getByRole('button', { name: '生成圖片', exact: true }).click()
  const response = await submitted
  expect(response.ok()).toBe(true)
  const job = await response.json()
  await source.close({ runBeforeUnload: false })
  const before = (await (await request.get('/qa/state')).json()).prompts
  await page.goto('/')
  expect((await scripts(page)).some(({ name }) => name.includes('/assets/CreationStudio-'))).toBe(
    false,
  )
  await page.getByRole('button', { name: /任務抽屜/ }).click()
  const drawer = page.getByRole('dialog', { name: '生成任務' })
  const entry = drawer.locator('[data-task-id="' + job.id + '"]')
  await entry.getByRole('button', { name: '前往原任務' }).click()
  await expect(drawer).toBeHidden()
  await expect(page).toHaveURL(/#\/studio\/checkpoint$/)
  await expect(page.locator('.job').filter({ hasText: job.id })).toBeFocused()
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(before)
})
