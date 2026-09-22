const { chromium } = require('playwright');
const path = require('path');

const BASE = 'http://localhost:8000';
const USERNAME = 'auditor_customerzero';
const PASSWORD = process.env.AUDIT_CUSTOMER_ZERO_PASSWORD; // synthetic, disposable container only; never committed as a literal
const ORG_A_ID = '13771430-c3e1-48d3-b7eb-0344d0ec1a06';
const ORG_B_ID = '17661229-6c9b-4fd8-a416-788dc6405987'; // foreign tenant, Customer Zero is NOT a member
const SCREENS = path.join(__dirname, 'screens');

const consoleMessages = []; // {step, type, text}
let currentStep = 'pre-load';

function record(page) {
  page.on('console', (msg) => {
    consoleMessages.push({ step: currentStep, type: msg.type(), text: msg.text() });
  });
  page.on('pageerror', (err) => {
    consoleMessages.push({ step: currentStep, type: 'pageerror', text: String(err) });
  });
}

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  record(page);

  const results = {};

  // Step 0: base-commit console noise check - unauthenticated clean load, BEFORE login/interactions
  currentStep = '0-unauth-clean-load';
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  results.step0_title = await page.title();
  results.step0_url = page.url();
  await page.screenshot({ path: path.join(SCREENS, '00-unauth-load.png') });

  // Step 1: sign in as synthetic Customer Zero
  currentStep = '1-login';
  await page.goto(BASE + '/accounts/login/', { waitUntil: 'networkidle' }).catch(() => {});
  // Discover the actual login URL Django is using (LOGIN_URL = 'login')
  if (!page.url().includes('login')) {
    await page.goto(BASE + '/login/', { waitUntil: 'networkidle' });
  }
  await page.screenshot({ path: path.join(SCREENS, '01a-login-page.png') });
  results.login_page_url = page.url();
  results.login_page_has_form = await page.locator('form').count();

  const usernameField = page.locator('input[name="username"]');
  const passwordField = page.locator('input[name="password"]');
  await usernameField.fill(USERNAME);
  await passwordField.fill(PASSWORD);
  await page.screenshot({ path: path.join(SCREENS, '01b-login-filled.png') });
  await Promise.all([
    page.waitForLoadState('networkidle'),
    page.locator('button[type="submit"], input[type="submit"]').first().click(),
  ]);
  results.after_login_url = page.url();
  results.after_login_status_ok = !page.url().includes('/login/');
  await page.screenshot({ path: path.join(SCREENS, '01c-after-login.png') });

  // Step 2: open assigned organisation
  currentStep = '2-open-org';
  await page.goto(BASE + `/organisations/${ORG_A_ID}/`, { waitUntil: 'networkidle' });
  results.org_detail_status_visible_name = await page.locator('h1').first().innerText();
  await page.screenshot({ path: path.join(SCREENS, '02-org-detail.png') });

  // Step 3: open Organisation Profile
  currentStep = '3-open-profile';
  await page.locator('a:has-text("Start profile"), a:has-text("View / edit profile")').first().click();
  await page.waitForLoadState('networkidle');
  results.profile_page_url = page.url();
  results.profile_heading = await page.locator('h1').first().innerText();
  await page.screenshot({ path: path.join(SCREENS, '03-profile-form-empty.png') });

  // Step 4: complete representative fields across all sections
  currentStep = '4-fill-form';
  await page.locator('#id_legal_trading_name').fill('Auditor Synthetic Org A Ltd');
  await page.locator('#id_description').fill('A synthetic small business used for FORGE M001 browser audit.');
  await page.locator('#id_staff_count').fill('23');
  await page.locator('#id_working_model').selectOption('hybrid');
  await page.locator('#id_endpoint_management').selectOption('both');
  await page.locator('#id_productivity_platform').selectOption('microsoft_365');
  await page.locator('#id_primary_cloud_provider').selectOption('azure');
  await page.locator('#id_develops_hosts_own_software').selectOption('yes');
  await page.locator('#id_handles_personal_data').selectOption('yes');
  await page.locator('#id_handles_confidential_business_data').selectOption('yes');
  await page.locator('#id_handles_payment_card_data').selectOption('no');
  await page.locator('#id_handles_special_category_data').selectOption('unknown');
  await page.locator('#id_receives_security_questionnaires').selectOption('yes');
  await page.locator('#id_cyber_essentials_status').selectOption('in_progress');
  await page.locator('#id_iso27001_status').selectOption('not_certified');
  await page.locator('#id_commercial_security_driver').fill('A major enterprise prospect requires Cyber Essentials before signing.');
  await page.screenshot({ path: path.join(SCREENS, '04-profile-form-filled.png'), fullPage: true });

  // Step 5/6: save, verify visible confirmation
  currentStep = '5-save';
  await Promise.all([
    page.waitForLoadState('networkidle'),
    page.locator('button[type="submit"]:has-text("Save profile")').click(),
  ]);
  results.after_save_url = page.url();
  const messageText = await page.locator('.messages, [role="status"]').first().innerText().catch(() => '');
  results.after_save_message = messageText;
  await page.screenshot({ path: path.join(SCREENS, '05-after-save-confirmation.png') });

  // Step 7/8: reload/reopen, verify values persist
  currentStep = '7-reload-verify-persist';
  await page.goto(BASE + `/organisations/${ORG_A_ID}/profile/`, { waitUntil: 'networkidle' });
  results.reload_legal_name_value = await page.locator('#id_legal_trading_name').inputValue();
  results.reload_staff_count_value = await page.locator('#id_staff_count').inputValue();
  results.reload_working_model_value = await page.locator('#id_working_model').inputValue();
  results.reload_cyber_essentials_value = await page.locator('#id_cyber_essentials_status').inputValue();
  await page.screenshot({ path: path.join(SCREENS, '06-reload-persisted.png'), fullPage: true });

  // Step 9/10: change one meaningful value, save/reload and verify
  currentStep = '9-change-one-value';
  results.pre_change_staff_count = results.reload_staff_count_value;
  await page.locator('#id_staff_count').fill('47');
  await page.locator('#id_working_model').selectOption('remote');
  await Promise.all([
    page.waitForLoadState('networkidle'),
    page.locator('button[type="submit"]:has-text("Save profile")').click(),
  ]);
  await page.goto(BASE + `/organisations/${ORG_A_ID}/profile/`, { waitUntil: 'networkidle' });
  results.post_change_staff_count = await page.locator('#id_staff_count').inputValue();
  results.post_change_working_model = await page.locator('#id_working_model').inputValue();
  await page.screenshot({ path: path.join(SCREENS, '07-after-change-reload.png'), fullPage: true });

  // Step 11: submit at least one invalid value and verify visible validation
  currentStep = '11-invalid-submission';
  await page.locator('#id_legal_trading_name').fill('');
  await page.locator('#id_staff_count').fill('-9');
  await Promise.all([
    page.waitForLoadState('networkidle'),
    page.locator('button[type="submit"]:has-text("Save profile")').click(),
  ]);
  results.invalid_submit_url_after = page.url(); // should stay on profile form, not redirect
  results.invalid_submit_error_visible = await page.locator('.field__error, .message--error').count();
  const errorTexts = await page.locator('.field__error, .message--error').allInnerTexts();
  results.invalid_submit_error_texts = errorTexts;
  await page.screenshot({ path: path.join(SCREENS, '08-invalid-submission-errors.png'), fullPage: true });

  // Confirm the invalid submission did NOT overwrite the previously-saved valid data
  currentStep = '11b-verify-invalid-did-not-corrupt-data';
  await page.goto(BASE + `/organisations/${ORG_A_ID}/profile/`, { waitUntil: 'networkidle' });
  results.after_failed_invalid_submit_name_value = await page.locator('#id_legal_trading_name').inputValue();
  await page.screenshot({ path: path.join(SCREENS, '08b-data-not-corrupted.png') });

  // Step 12/13: attempt to reach a second synthetic organisation's data via manipulated ID/URL
  currentStep = '12-cross-tenant-attempt-detail';
  const crossDetailResp = await page.goto(BASE + `/organisations/${ORG_B_ID}/`, { waitUntil: 'networkidle' });
  results.cross_tenant_detail_status = crossDetailResp.status();
  results.cross_tenant_detail_body_snippet = (await page.content()).slice(0, 400);
  await page.screenshot({ path: path.join(SCREENS, '09-cross-tenant-detail-blocked.png') });

  currentStep = '13-cross-tenant-attempt-profile';
  const crossProfileResp = await page.goto(BASE + `/organisations/${ORG_B_ID}/profile/`, { waitUntil: 'networkidle' });
  results.cross_tenant_profile_status = crossProfileResp.status();
  await page.screenshot({ path: path.join(SCREENS, '10-cross-tenant-profile-blocked.png') });

  // Confirm org B's data never appeared anywhere in the page (extra rigor)
  results.cross_tenant_profile_leaked_name = (await page.content()).includes('Org B Foreign Ltd');

  currentStep = '13b-org-b-not-in-list';
  await page.goto(BASE + `/organisations/`, { waitUntil: 'networkidle' });
  const listContent = await page.content();
  results.org_list_contains_org_b = listContent.includes('Auditor Synthetic Org B');
  results.org_list_contains_org_a = listContent.includes('Auditor Synthetic Org A');
  await page.screenshot({ path: path.join(SCREENS, '11-org-list-no-org-b.png') });

  currentStep = 'done';
  await context.close();
  await browser.close();

  console.log('=== RESULTS ===');
  console.log(JSON.stringify(results, null, 2));
  console.log('=== CONSOLE MESSAGES ===');
  console.log(JSON.stringify(consoleMessages, null, 2));
})().catch((err) => {
  console.error('SCRIPT ERROR at step', currentStep, err);
  process.exit(1);
});
