import { test, expect } from '@playwright/test'

// UI validation is isolated from the deployed Docker assets.
// Only the anonymous session probe is stubbed; valid auth is covered by auth-integration.
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/session', route => route.fulfill({
    status: 401, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'UNAUTHENTICATED', message: '请先登录' }, requestId: 'ui-test' }),
  }))
})

for (const route of ['/login', '/register']) {
  test(route + ' starts clean, ignores empty blur, validates entered email and clears corrected errors', async ({ page }) => {
    let submits = 0
    page.on('request', request => { if (request.method() === 'POST') submits++ })
    await page.goto(route)
    await expect(page.locator('.el-form-item.is-error')).toHaveCount(0)
    const email = page.getByLabel('邮箱', { exact: true })
    await email.focus()
    await page.getByRole('heading', { level: 2 }).click()
    await expect(page.locator('.el-form-item.is-error')).toHaveCount(0)
    await email.fill('invalid')
    await expect(page.locator('.el-form-item.is-error')).toHaveCount(0)
    await page.getByRole('heading', { level: 2 }).click()
    await expect(page.getByText('请输入有效的邮箱地址')).toBeVisible()
    const buttonY = await page.locator('.submit-button').evaluate(element => element.getBoundingClientRect().y)
    await email.fill('reader@example.com')
    await expect(page.locator('.el-form-item.is-error')).toHaveCount(0)
    await page.getByRole('heading', { level: 2 }).click()
    expect(await page.locator('.submit-button').evaluate(element => element.getBoundingClientRect().y)).toBe(buttonY)
    await page.locator('.submit-button').click()
    await expect(page.getByText('请输入密码')).toBeVisible()
    expect(submits).toBe(0)
  })
}

test('password and confirm blur validation retain security rules and reset on tab changes', async ({ page }) => {
  await page.goto('/register')
  await page.getByLabel('密码', { exact: true }).fill('short')
  await page.getByRole('heading', { level: 2 }).click()
  await expect(page.getByText('密码长度为 8–128 个字符')).toBeVisible()
  await page.getByLabel('密码', { exact: true }).fill('valid-password')
  await expect(page.getByText('密码长度为 8–128 个字符')).toHaveCount(0)
  await page.getByLabel('确认密码', { exact: true }).fill('different')
  await page.getByRole('heading', { level: 2 }).click()
  await expect(page.getByText('两次密码输入不一致')).toBeVisible()
  await page.getByRole('link', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.locator('.el-form-item.is-error')).toHaveCount(0)
  await page.getByRole('link', { name: '注册', exact: true }).click()
  await expect(page).toHaveURL(/\/register$/)
  await expect(page.locator('.el-form-item.is-error')).toHaveCount(0)
  await expect(page.getByLabel('密码', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('确认密码', { exact: true })).toHaveValue('')
})

test('global tokens match button hover/active, links, logo and focus while error remains semantic', async ({ page }) => {
  await page.goto('/login')
  const tokens = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement)
    return ['--litera-primary', '--litera-primary-hover', '--litera-primary-active', '--litera-primary-soft',
      '--litera-page', '--litera-card'].map(name => style.getPropertyValue(name).trim().toUpperCase())
  })
  expect(tokens).toEqual(['#9B0000', '#B82A2A', '#750000', '#FFF4F4', '#F7F8FA', '#FFFFFF'])
  const button = page.locator('.submit-button')
  await expect(button).toHaveCSS('background-color', 'rgb(155, 0, 0)')
  await expect(page.locator('.brand-mark')).toHaveCSS('color', 'rgb(155, 0, 0)')
  await expect(page.locator('.auth-tabs .active')).toHaveCSS('color', 'rgb(155, 0, 0)')
  await button.hover()
  await expect(button).toHaveCSS('background-color', 'rgb(184, 42, 42)')
  await page.mouse.down()
  await expect(button).toHaveCSS('background-color', 'rgb(117, 0, 0)')
  await page.mouse.move(0, 0)
  await page.mouse.up()
  const email = page.getByLabel('邮箱', { exact: true })
  await email.focus()
  await expect(page.locator('.el-input__wrapper.is-focus')).toHaveCSS('box-shadow', 'rgb(155, 0, 0) 0px 0px 0px 1px inset')
  await email.fill('invalid')
  await page.getByRole('heading', { level: 2 }).click()
  expect(await page.locator('.el-form-item__error').evaluate(element => getComputedStyle(element).color)).not.toBe('rgb(155, 0, 0)')
})

for (const size of [{ width: 1280, height: 720 }, { width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test('registration fits desktop ' + size.width + 'x' + size.height + ' and login uses content height', async ({ page }) => {
    await page.setViewportSize(size)
    await page.goto('/register')
    await expect(page.locator('.el-form-item.is-error')).toHaveCount(0)
    const card = await page.locator('.auth-card').boundingBox()
    const button = await page.locator('.submit-button').boundingBox()
    expect(button!.y + button!.height).toBeLessThanOrEqual(size.height)
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(size.height)
    await page.screenshot({ path: 'test-results/ui-register-' + size.width + '.png', fullPage: true })
    await page.getByRole('link', { name: '登录', exact: true }).click()
    await expect(page).toHaveURL(/\/login$/)
    const loginCard = await page.locator('.auth-card').boundingBox()
    expect(loginCard!.height).toBeLessThan(card!.height)
    expect(loginCard!.y).toBeGreaterThanOrEqual(0)
    expect(loginCard!.y + loginCard!.height).toBeLessThanOrEqual(size.height)
    const subtitle = await page.locator('.card-subtitle').boundingBox()
    const emailLabel = await page.locator('label[for="email"]').boundingBox()
    expect(emailLabel!.y - subtitle!.y - subtitle!.height).toBeCloseTo(16, 0)
    await page.screenshot({ path: 'test-results/ui-login-' + size.width + '.png', fullPage: true })
    await page.getByRole('link', { name: '注册', exact: true }).click()
    await expect(page).toHaveURL(/\/register$/)
    const restoredCard = await page.locator('.auth-card').boundingBox()
    expect(restoredCard).toEqual(card)
  })
}

for (const size of [{ width: 390, height: 844 }, { width: 360, height: 560 }]) {
  test('small screens preserve complete form ' + size.width + 'x' + size.height, async ({ page }) => {
    await page.setViewportSize(size)
    await page.goto('/register')
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(size.width)
    await page.locator('.submit-button').scrollIntoViewIfNeeded()
    await expect(page.locator('.submit-button')).toBeInViewport()
    await expect(page.getByLabel('确认密码', { exact: true })).toBeVisible()
    await page.screenshot({ path: 'test-results/ui-register-mobile-' + size.width + '.png', fullPage: true })
    await page.getByRole('link', { name: '登录', exact: true }).click()
    await expect(page).toHaveURL(/\/login$/)
    const subtitle = await page.locator('.card-subtitle').boundingBox()
    const emailLabel = await page.locator('label[for="email"]').boundingBox()
    expect(emailLabel!.y - subtitle!.y - subtitle!.height).toBeCloseTo(16, 0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(size.width)
    await page.locator('.form-footnote').scrollIntoViewIfNeeded()
    await expect(page.locator('.form-footnote')).toBeInViewport()
    await page.screenshot({ path: 'test-results/ui-login-mobile-' + size.width + '.png', fullPage: true })
  })
}


test('valid registration keeps request contract and surfaces server errors without losing entered fields', async ({ page }) => {
  let payload: Record<string, string> | undefined
  await page.route('**/api/v1/auth/register', async route => {
    payload = route.request().postDataJSON()
    await route.fulfill({ status: 409, contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'EMAIL_EXISTS', message: '该邮箱已注册，请直接登录' }, requestId: 'ui-test' }) })
  })
  await page.goto('/register')
  await page.getByLabel('显示名称', { exact: true }).fill(' Researcher ')
  await page.getByLabel('邮箱', { exact: true }).fill('reader@example.com')
  await page.getByLabel('密码', { exact: true }).fill('valid-password')
  await page.getByLabel('确认密码', { exact: true }).fill('valid-password')
  await page.locator('.submit-button').click()
  await expect(page.getByText('该邮箱已注册，请直接登录')).toBeVisible()
  expect(payload).toEqual({ email: 'reader@example.com', password: 'valid-password', displayName: 'Researcher' })
  await expect(page.getByLabel('邮箱', { exact: true })).toHaveValue('reader@example.com')
  const statusColors = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement)
    return ['--el-color-success', '--el-color-warning', '--el-color-danger'].map(name => style.getPropertyValue(name).trim())
  })
  expect(statusColors.every(color => color.toUpperCase() !== '#9B0000')).toBe(true)
})
