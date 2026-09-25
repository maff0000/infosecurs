const { chromium } = require('playwright');

const BASE = 'https://127.0.0.1:19961';
const USERNAME = 'customerzero';
const PASSWORD = process.env.SMOKE_CZ_PASSWORD;

const consoleMessages = [];
const pageErrors = [];
const failedRequests = [];
let currentStep = 'pre-load';

function record(page) {
  page.on('console', (msg) => {
    consoleMessages.push({ step: currentStep, type: msg.type(), text: msg.text() });
  });
  page.on('pageerror', (err) => {
    pageErrors.push({ step: currentStep, text: String(err) });
  });
  page.on('requestfailed', (req) => {
    failedRequests.push({ step: currentStep, url: req.url(), failure: req.failure() && req.failure().errorText });
  });
  page.on('response', (res) => {
    if (res.status() >= 400) {
      failedRequests.push({ step: currentStep, url: res.url(), status: res.status() });
    }
  });
}

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  record(page);

  const results = {};

  currentStep = '0-unauth-login-page';
  await page.goto(BASE + '/accounts/login/', { waitUntil: 'networkidle' });
  await page.screenshot({ path: '/tmp/m006r7rel-playwright/screens/00-login.png' });
  results.step0_title = await page.title();
  results.step0_url = page.url();
  results.step0_css_loaded = await page.evaluate(() => {
    const link = document.querySelector('link[rel="stylesheet"]');
    return link ? link.href : null;
  });
  results.step0_body_has_styling = await page.evaluate(() => {
    const st = getComputedStyle(document.body);
    return st.margin !== '8px';
  });

  currentStep = '1-login';
  await page.click('summary:has-text("Use a local development account instead")');
  await page.fill('#id_username', USERNAME);
  await page.fill('#id_password', PASSWORD);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle' }),
    page.click('button[type=submit], input[type=submit]'),
  ]);
  results.step1_url_after_login = page.url();
  results.step1_title = await page.title();

  currentStep = '2-organisations-list';
  results.step2_has_org_link = (await page.content()).includes('Infosecurs Limited');

  currentStep = '3-open-organisation';
  const orgLink = page.locator('a', { hasText: 'Infosecurs Limited' }).first();
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle' }),
    orgLink.click(),
  ]);
  results.step3_url = page.url();
  results.step3_title = await page.title();
  results.step3_nav_present = await page.evaluate(() =>
    !!document.querySelector('nav.app-header__nav-primary')
  );
  await page.screenshot({ path: '/tmp/m006r7rel-playwright/screens/03-overview.png', fullPage: true });

  const navTargets = [
    ['security', 'Security'],
    ['evidence', 'Evidence'],
    ['policy', 'Policy'],
    ['questionnaires', 'Questionnaires'],
    ['activity', 'Activity'],
    ['organisation', 'Organisation'],
  ];
  results.nav = {};
  for (const [key, label] of navTargets) {
    currentStep = `4-nav-${key}`;
    const link = page.locator(`a.app-header__nav-primary-link:has-text("${label}")`).first();
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle' }),
      link.click(),
    ]);
    results.nav[key] = { url: page.url(), title: await page.title(), status_ok: true };
  }

  currentStep = 'zzz-done';
  await browser.close();

  console.log(JSON.stringify({
    results,
    consoleMessages,
    pageErrors,
    failedRequests,
  }, null, 2));
})().catch((e) => {
  console.error('SMOKE_FAILED', currentStep, e);
  process.exit(1);
});
