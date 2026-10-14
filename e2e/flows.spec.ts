import { expect, test, type Browser, type Page } from '@playwright/test'

// The tests run in order against one seeded backend: the client's request (1) is what the advocate reviews (2).
test.describe.configure({ mode: 'serial' })

const TITLE = 'E2E: bail for my cousin'

async function signIn(browser: Browser, persona: 'client' | 'lawyer' | 'admin' | 'compliance'): Promise<Page> {
  const page = await (await browser.newContext()).newPage()
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(m.text()) })
  ;(page as Page & { jsErrors: string[] }).jsErrors = errors
  await page.goto('/login')
  await page.getByRole('button', { name: persona, exact: true }).click()
  await expect(page).not.toHaveURL(/\/login/)
  return page
}

const jsErrors = (p: Page) => (p as Page & { jsErrors: string[] }).jsErrors

test('client describes a matter, uploads files, sees the review, compares fees with budget and consents', async ({ browser }) => {
  const page = await signIn(browser, 'client')
  await page.getByRole('link', { name: 'Get legal help' }).first().click()
  await page.getByLabel('Short title').fill(TITLE)
  await page.getByLabel(/What happened\?/).fill('SYNTHETIC E2E. Police arrested my cousin in Delhi on 2 October 2026 after an FIR was registered. We need bail urgently.')
  await page.getByLabel('Your city').fill('New Delhi')
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByLabel(/Who else is involved/).fill('Arjun Kumar')
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: /up to ₹25,000/ }).click()  // budget step
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.locator('input[type=file]').setInputFiles({ name: 'FIR.txt', mimeType: 'text/plain',
    buffer: Buffer.from('FIRST INFORMATION REPORT (SYNTHETIC). The accused was arrested on 12 March 2026 at his residence. The arrest memo is attached.') })
  await expect(page.getByText('FIR.txt')).toBeVisible()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Submit and review my files' }).click()

  // Review of the client's own files: the two arrest dates are shown side by side, nothing is chosen.
  await expect(page.getByText("Dates that don't match")).toBeVisible()
  await expect(page.getByText('12 March 2026').first()).toBeVisible()
  await expect(page.getByText(/not legal advice/).first()).toBeVisible()

  await page.getByRole('tab', { name: /Advocates/ }).click()
  await expect(page.getByText(/DEMO ONLY/).first()).toBeVisible()  // the demo policy is labelled as such
  const card = page.locator('li', { hasText: 'Adv. Meera Iyer' })
  await expect(card.getByText('Typical fee for a matter')).toBeVisible()
  await expect(card.getByText('Partly within your budget')).toBeVisible()
  await expect(card.getByText(/Declared by the advocate, not verified/)).toBeVisible()
  await card.getByRole('button', { name: 'Request this lawyer' }).click()

  const dialog = page.getByRole('dialog', { name: 'Share your matter?' })
  await expect(dialog.getByText('No advocate pays FormLaw')).toBeVisible()
  const confirm = dialog.getByRole('button', { name: 'Confirm & send' })
  await expect(confirm).toBeDisabled()  // nothing is sent without explicit agreement to the disclosures
  await dialog.getByRole('checkbox').check()
  await confirm.click()
  await expect(card.getByRole('button', { name: 'Requested' })).toBeVisible()
  await page.getByRole('tab', { name: 'Overview' }).click()
  await expect(page.getByText('waiting for reply')).toBeVisible()
  expect(jsErrors(page)).toEqual([])
})

test('the landing page renders full screen with 3D and no script errors', async ({ browser }) => {
  const page = await (await browser.newContext()).newPage()
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('clearly understood')
  await expect(page.locator('canvas')).toHaveCount(1)  // the WebGL scene mounted
  const hero = await page.locator('section').first().boundingBox()
  expect(hero!.height).toBeGreaterThan(600)  // full-screen hero
  await page.getByRole('link', { name: 'For clients' }).first().click()
  await expect(page.getByText('From a pile of papers to a clear picture.')).toBeVisible()
  expect(errors).toEqual([])
})

test('advocate checks for conflicts using names only, then sees and accepts the matter', async ({ browser }) => {
  const page = await signIn(browser, 'lawyer')
  await page.goto('/requests')
  const req = page.locator('li', { hasText: 'Arjun Kumar (other party)' })
  // The adverse party appears in a matter title, and the demo client is already this firm's client on that matter.
  await expect(req.getByText('Possible match: “Arjun Kumar')).toContainText('FL-2026-0001')
  await expect(req.getByText('Possible match: “Sunita Kumar')).toContainText('client name')
  await expect(req).not.toContainText(TITLE)  // no title or summary before the check
  await expect(req).not.toContainText('Police arrested')
  await req.getByRole('button', { name: /No conflict/ }).click()
  const cleared = page.locator('li', { hasText: TITLE })
  await expect(cleared.getByText('Police arrested my cousin').first()).toBeVisible()
  await cleared.getByRole('button', { name: 'Accept & open case' }).click()
  await expect(page).toHaveURL(/\/cases\//)
  expect(jsErrors(page)).toEqual([])
})

test('an administrator drafts a policy but only a compliance reviewer can approve it', async ({ browser }) => {
  const admin = await signIn(browser, 'admin')
  await admin.getByRole('tab', { name: 'Connection policy' }).click()
  await admin.getByRole('button', { name: 'Draft a new policy version' }).click()
  const boxes = admin.getByRole('checkbox')
  for (let i = 0; i < 3; i++) await boxes.nth(i).check()
  await admin.getByRole('button', { name: 'city', exact: true }).click()
  await admin.getByLabel(/Disclosures shown to clients/).fill('SYNTHETIC E2E disclosure: FormLaw does not recommend advocates.')
  await admin.getByLabel('Rationale').fill('SYNTHETIC end-to-end test policy version.')
  await admin.getByRole('button', { name: 'Save draft' }).click()
  await expect(admin.getByText('Waiting for a compliance reviewer')).toBeVisible()
  await expect(admin.getByRole('button', { name: 'Approve' })).toHaveCount(0)

  const reviewer = await signIn(browser, 'compliance')
  await expect(reviewer).toHaveURL(/\/compliance/)
  const draft = reviewer.locator('li', { hasText: 'SYNTHETIC end-to-end test policy version.' })
  await draft.getByLabel('Counsel review reference').fill('E2E-OPINION-1')
  await draft.getByLabel('Decision note').fill('Synthetic approval')
  const approve = draft.getByRole('button', { name: 'Approve' })
  await expect(approve).toBeDisabled()
  await draft.getByRole('checkbox').check()
  await approve.click()
  await expect(draft.getByText('Approved', { exact: true })).toBeVisible()
  const policy = await reviewer.request.get('/api/v1/connection-policy').then((r) => r.json())
  expect(policy.source).toBe('approved')
  expect(jsErrors(admin)).toEqual([])
  expect(jsErrors(reviewer)).toEqual([])
})

test('the corpus coverage view reports gaps instead of claiming coverage', async ({ browser }) => {
  const admin = await signIn(browser, 'admin')
  await admin.getByRole('tab', { name: 'Legal corpus' }).click()
  await expect(admin.getByText('INCOMPLETE', { exact: true })).toBeVisible()
  await expect(admin.getByText(/No High Court judgments are ingested/)).toBeVisible()
  expect(jsErrors(admin)).toEqual([])
})

test('client portal fits a phone screen without horizontal scrolling', async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage()
  await page.goto('/login')
  await page.getByRole('button', { name: 'client', exact: true }).click()
  await expect(page).toHaveURL(/\/portal/)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})
