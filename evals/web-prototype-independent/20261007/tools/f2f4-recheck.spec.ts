// R5 independent re-check of F2–F4 on main 58feb9c (record 최길웅-20261007-054). Copied into apps/web/e2e/__tmp only to
// run; not a product test. Same setup as public-flow.spec.ts (record 052): a test workspace DB that already holds a
// synthetic-version (0.1.0, FRIDGE-A) project, served with the R5 public development dataset. No model is called.
//   F2: the evidence detail badge shows the Korean source label, not the raw `public`.
//   F3: after the dataset version changed, the request form says the old model is unavailable and asks for a choice.
//   F4: a write refused for its Origin shows a message that names the allowed address, not only "read-only token".
// The browser's refused request body is written out (no token) so the same body can be re-sent over HTTP from the
// allowed origin outside the browser, confirming the save itself works; the user's own 5173 server is never used.
// Env: R5_DIR (evals folder), R5_TOKEN_FILE, R5_VERSION (dataset_version).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const dir = process.env.R5_DIR!;
const version = process.env.R5_VERSION!;
const area = (page: Page, label: string) => page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
const messages = (page: Page) => page.locator('.inline-message, [role="status"], [role="alert"]').allTextContents();

test('R5 F2–F4 re-check on the public development dataset', async ({ page }) => {
  test.setTimeout(180_000);
  const token = (JSON.parse(readFileSync(process.env.R5_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = join(dir, 'web-main-58feb9c', 'f2f4');
  mkdirSync(out, { recursive: true });
  const seen: Record<string, unknown> = { version };
  const writes: { method: string; url: string; status: number }[] = [];
  let lastBody: string | null = null;
  page.on('response', response => {
    const request = response.request();
    if (request.method() === 'GET' || !response.url().includes('/api/workspace/')) return;
    writes.push({ method: request.method(), url: new URL(response.url()).pathname, status: response.status() });
    lastBody = request.postData();
  });
  await page.goto('/');
  await page.getByLabel('작업실 토큰').fill(token);
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page.locator('.workspace-state')).toContainText('연결됨');
  seen.after_hero = await page.locator('.hero-stats').textContent({ timeout: 5000 }).catch(() => null);
  seen.selected_project = await page.getByRole('combobox', { name: '프로젝트' }).inputValue({ timeout: 5000 }).catch(() => null);

  // F2
  await area(page, '근거 대조');
  await page.locator('.evidence-list button').first().click({ timeout: 5000 });
  const detail = page.getByRole('complementary', { name: '선택한 근거 상세' });
  seen.f2_detail_badge = await detail.locator('.sample-label').textContent({ timeout: 5000 }).catch(() => null);
  seen.f2_raw_public_badge = (await detail.locator('.sample-label').allTextContents()).some(text => text.trim() === 'public');
  await page.screenshot({ path: join(out, '1-evidence-detail.png'), fullPage: true });

  // F3
  await area(page, '기획 요청');
  seen.dataset_change = await page.locator('[data-dataset-change]').allTextContents();
  seen.f3_missing_models_notice = await page.locator('[data-missing-project-models]').allTextContents();
  seen.model_picker = await page.locator('.model-picker label').allTextContents();
  seen.model_picker_checked = await page.locator('.model-picker input:checked').count();
  seen.submit_label = await page.locator('.request-form button[type="submit"]').first().textContent({ timeout: 5000 }).catch(() => null);
  const projectsBefore = await page.getByRole('combobox', { name: '프로젝트' }).locator('option').count();
  await page.locator('.request-form button[type="submit"]').first().click({ timeout: 5000 });
  await page.waitForTimeout(3000);
  seen.f3_first_save_messages = await messages(page);
  await page.screenshot({ path: join(out, '2-model-notice.png'), fullPage: true });

  // F4: choose a current model; this browser runs on a non-allowed origin, so the server refuses the write.
  await page.locator('.model-picker label').first().click({ timeout: 5000 });
  seen.model_picker_checked_after_choice = await page.locator('.model-picker input:checked').count();
  await page.locator('.request-form button[type="submit"]').first().click({ timeout: 5000 });
  await page.waitForTimeout(4000);
  seen.f4_forbidden_messages = await messages(page);
  seen.f4_panel = await page.getByRole('region', { name: '작업실 서버 연결' }).textContent({ timeout: 5000 }).catch(() => null);
  await page.screenshot({ path: join(out, '3-origin-refused.png'), fullPage: true });

  seen.f3_notice_after_refusal = await page.locator('[data-missing-project-models]').allTextContents();
  seen.writes = writes;
  if (lastBody) writeFileSync(join(out, 'refused-request-body.json'), `${JSON.stringify(JSON.parse(lastBody), null, 1)}\n`);
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify(seen, null, 1)}\n`);
  expect(String(seen.after_hero)).toContain(version);
});
