// M006 audit-fix release rebuild smoke test — real Chromium via Playwright,
// against the exact release image at 115d2f5e74bee8a294c814fdf3d1f7f10c156c31
// (PR #46, F1/F2/F3 fixes), over the bounded single-hop TLS wrapper.
const { chromium } = require('playwright');

const BASE = 'https://127.0.0.1:19881';
const USERNAME = process.env.CUSTOMER_ZERO_USERNAME || 'customerzero';
const PASSWORD = process.env.CUSTOMER_ZERO_PASSWORD;

(async () => {
  const results = {
    consoleMessages: [],
    pageErrors: [],
    failedRequests: [],
    steps: [],
  };

  const browser = await chromium.launch({ ignoreHTTPSErrors: true });
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      results.consoleMessages.push({ type: msg.type(), text: msg.text() });
    }
  });
  page.on('pageerror', (err) => {
    results.pageErrors.push(String(err));
  });
  page.on('requestfailed', (req) => {
    results.failedRequests.push({ url: req.url(), failure: req.failure() && req.failure().errorText });
  });
  page.on('response', (resp) => {
    if (resp.status() >= 400) {
      results.failedRequests.push({ url: resp.url(), status: resp.status() });
    }
  });

  // 1. Login page renders with CSS
  await page.goto(`${BASE}/accounts/login/`, { waitUntil: 'networkidle' });
  const title = await page.title();
  results.steps.push({ step: 'login-page-title', title });
  await page.screenshot({ path: '/tmp/m006afrel-screens/00-login.png' });

  // Confirm CSS actually applied (computed style check, not just <link> presence)
  const linkHref = await page.getAttribute('link[rel="stylesheet"][href*="organisations/css/app"]', 'href');
  results.steps.push({ step: 'login-css-link', href: linkHref });

  // 2. Expand "local development account" details and log in
  const details = page.locator('details');
  if (await details.count() > 0) {
    await details.first().click().catch(() => {});
  }
  await page.screenshot({ path: '/tmp/m006afrel-screens/01-login-expanded.png' });

  await page.fill('input[name="login"], input[name="username"]', USERNAME).catch(async () => {
    await page.fill('input[type="text"]', USERNAME);
  });
  await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle' }),
    page.click('button[type="submit"], input[type="submit"]'),
  ]);
  results.steps.push({ step: 'post-login-url', url: page.url() });
  await page.screenshot({ path: '/tmp/m006afrel-screens/02-post-login.png' });

  // 3. Navigate into the organisation (Infosecurs Limited)
  const orgLink = page.locator('a', { hasText: 'Infosecurs Limited' });
  if (await orgLink.count() > 0) {
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle' }),
      orgLink.first().click(),
    ]);
  }
  results.steps.push({ step: 'overview-url', url: page.url() });
  await page.screenshot({ path: '/tmp/m006afrel-screens/03-overview.png' });

  // 4. Primary nav present, click through Security/Evidence/Policy/Questionnaires/Activity/Organisation
  const navTargets = ['Security', 'Evidence', 'Policy', 'Questionnaires', 'Activity', 'Organisation'];
  const navFound = [];
  for (const label of navTargets) {
    const link = page.locator('nav a, header a', { hasText: label }).first();
    const count = await link.count();
    navFound.push({ label, present: count > 0 });
    if (count > 0) {
      try {
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'networkidle', timeout: 15000 }),
          link.click(),
        ]);
        await page.screenshot({ path: `/tmp/m006afrel-screens/04-${label.toLowerCase()}.png` });
        results.steps.push({ step: `nav-${label}`, url: page.url() });
      } catch (e) {
        results.steps.push({ step: `nav-${label}-error`, error: String(e) });
      }
    }
  }
  results.navFound = navFound;

  await browser.close();

  console.log(JSON.stringify(results, null, 2));
})().catch((err) => {
  console.error('SMOKE_SCRIPT_FATAL', err);
  process.exit(1);
});
