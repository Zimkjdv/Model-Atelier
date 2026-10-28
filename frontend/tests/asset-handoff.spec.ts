import { test, expect } from '@playwright/test'

test('cached text studio keeps its full form when source handoff is cancelled', async ({
  page,
  request,
}) => {
  const state = await (await request.get('/qa/state')).json()
  const input = await (await request.get('/api/assets/' + state.asset_id + '/image')).body()
  const source = await (
    await request.post('/api/assets?filename=fresh-source.png', {
      data: input,
      headers: { 'Content-Type': 'image/png' },
    })
  ).json()
  await page.goto('/#/studio/checkpoint')
  await page.locator('#draft-prompt').fill('keep my text creation settings')
  await expect(page.locator('#checkpoint-workflow')).toHaveValue('text2image')
  await page.getByRole('navigation').getByRole('button', { name: '參考素材', exact: true }).click()
  const card = page
    .locator('.asset-card')
    .filter({ has: page.locator('[data-asset-cover="' + source.id + '"]') })
  page.once('dialog', (event) => event.dismiss())
  await card.getByRole('button', { name: '用於創作', exact: true }).click()
  await expect(page.locator('#checkpoint-workflow')).toHaveValue('text2image')
  await expect(page.locator('#draft-prompt')).toHaveValue('keep my text creation settings')
  await page.getByRole('navigation').getByRole('button', { name: '參考素材', exact: true }).click()
  page.once('dialog', (event) => event.accept())
  await card.getByRole('button', { name: '用於創作', exact: true }).click()
  await expect(page.locator('#checkpoint-workflow')).toHaveValue('image2image')
  await expect(page.locator('#image-asset')).toHaveValue(source.id)
  await expect(page.locator('#draft-prompt')).toHaveValue('keep my text creation settings')
  expect((await (await request.get('/qa/state')).json()).prompts).toBe(state.prompts)
})
