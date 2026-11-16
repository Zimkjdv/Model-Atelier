import { expect, type Locator, type Page } from '@playwright/test'

export async function expandDetails(details: Locator) {
  await expect(details).toBeVisible()
  if ((await details.getAttribute('open')) === null) {
    await details.locator(':scope > summary').click()
    await expect(details).toHaveAttribute('open', '')
  }
}

export async function loadCheckpointDraft(page: Page, title: string) {
  await page.goto('/#/studio/checkpoint')
  const drafts = page.locator('.saved-drafts')
  await expandDetails(drafts)
  await drafts
    .locator('.draft-row')
    .filter({ has: page.getByText(title, { exact: true }) })
    .click()
  const discard = page.getByRole('button', { name: '捨棄變更並載入', exact: true })
  if (await discard.isVisible()) await discard.click()
  await expect(page.locator('#draft-title')).toHaveValue(title)
}
