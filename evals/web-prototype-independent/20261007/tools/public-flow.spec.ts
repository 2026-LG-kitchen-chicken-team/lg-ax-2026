// R5 independent web check (record 최길웅-20261007-052). Copied into apps/web/e2e/__tmp only to run; not a product test.
// Real workspace server on main serving the R5 public development dataset (3 public products, verified manuals,
// 0 reviews because no exact purchase SKU/date is confirmed) over a DB that already holds a synthetic-version project.
// Checks with a real browser: source label/version/warnings after connect, honest 0 reviews, manual provenance,
// S8 (no reuse of the older-version project), a new project on the public version, what a run shows with planning
// OFF, and that disconnect clears the authenticated scope. No model is called.
// Env: R5_DIR (evals folder), R5_TOKEN_FILE, R5_VERSION (dataset_version), R5_OLD_PROJECT.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const dir = process.env.R5_DIR!;
const version = process.env.R5_VERSION!;
const area = (page: Page, label: string) => page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();

test('R5 public development dataset: real browser data-scope flow', async ({ page }) => {
  test.setTimeout(180_000);
  const token = (JSON.parse(readFileSync(process.env.R5_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = join(dir, 'public-flow');
  mkdirSync(out, { recursive: true });
  const seen: Record<string, unknown> = { version };
  await page.goto('/');
  await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
  seen.before_hero = await page.locator('.hero-stats').textContent({ timeout: 5000 }).catch(() => null);
  await page.getByLabel('작업실 토큰').fill(token);
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page.locator('.workspace-state')).toContainText('연결됨');
  seen.after_hero = await page.locator('.hero-stats').textContent({ timeout: 5000 }).catch(() => null);
  seen.warnings = await page.locator('[data-source-warnings]').allTextContents();
  seen.scenario_cards = await page.locator('.scenario-card').allTextContents();
  seen.dataset_change = await page.locator('[data-dataset-change]').allTextContents();
  seen.selected_project = await page.getByRole('combobox', { name: '프로젝트' }).inputValue({ timeout: 5000 }).catch(() => null);
  await page.screenshot({ path: join(out, '1-connected.png'), fullPage: true });
  // Evidence area: review count must be visible as 0, manuals carry public label and document version.
  await area(page, '근거 대조');
  seen.evidence_filters = await page.getByRole('group', { name: '근거 유형 필터' }).textContent({ timeout: 5000 }).catch(() => null);
  seen.workspace_panel = await page.getByRole('region', { name: '작업실 서버 연결' }).textContent({ timeout: 5000 }).catch(() => null);
  seen.review_model = await page.getByRole('combobox', { name: '검토 모델' }).inputValue({ timeout: 5000 }).catch(() => null);
  seen.first_evidence = await page.locator('.evidence-list button').first().textContent({ timeout: 5000 }).catch(() => null);
  await page.locator('.evidence-list button').first().click({ timeout: 5000 }).catch(() => {});
  seen.evidence_detail = await page.getByRole('complementary', { name: '선택한 근거 상세' }).textContent({ timeout: 5000 }).catch(() => null);
  await page.screenshot({ path: join(out, '2-evidence.png'), fullPage: true });
  // S8 + new project: save the request on the public version.
  await area(page, '기획 요청');
  seen.dataset_change_in_request = await page.locator('[data-dataset-change]').allTextContents();
  seen.request_footer = await page.locator('.form-footer').first().textContent({ timeout: 5000 }).catch(() => null);
  seen.submit_label = await page.locator('.request-form button[type="submit"]').first().textContent({ timeout: 5000 }).catch(() => null);
  const projectsBefore = await page.getByRole('combobox', { name: '프로젝트' }).locator('option').count();
  await page.locator('.request-form button[type="submit"]').first().click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(4000);
  seen.after_save_status = await page.locator('.inline-message, [role="status"], [role="alert"]').allTextContents();
  seen.projects_after = await page.getByRole('combobox', { name: '프로젝트' }).locator('option').allTextContents();
  seen.project_count_change = (seen.projects_after as string[]).length - projectsBefore;
  await page.screenshot({ path: join(out, '3-after-save.png'), fullPage: true });
  // F3 check: the old project's model is absent from the new dataset, so pick the current one and save again.
  seen.model_picker = await page.locator('.model-picker label').allTextContents();
  seen.model_picker_checked = await page.locator('.model-picker input:checked').count();
  await page.locator('.model-picker label').first().click({ timeout: 5000 }).catch(() => {});
  await page.locator('.request-form button[type="submit"]').first().click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(6000);
  seen.after_second_save = await page.locator('.inline-message, [role="status"], [role="alert"]').allTextContents();
  seen.projects_after_second = await page.getByRole('combobox', { name: '프로젝트' }).locator('option').allTextContents();
  seen.workspace_panel_after = await page.getByRole('region', { name: '작업실 서버 연결' }).textContent({ timeout: 5000 }).catch(() => null);
  await page.screenshot({ path: join(out, '3b-after-second-save.png'), fullPage: true });
  await area(page, '콘셉트 검토');
  seen.concepts_area = (await page.locator('main').textContent({ timeout: 5000 }).catch(() => ''))?.slice(0, 1500);
  seen.concept_cards = await page.locator('.concept-card').count();
  await page.screenshot({ path: join(out, '4-concepts.png'), fullPage: true });
  // Disconnect clears the authenticated scope.
  await page.getByRole('button', { name: /연결 해제/ }).click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(1000);
  seen.disconnected_hero = await page.locator('.hero-stats').textContent({ timeout: 5000 }).catch(() => null);
  await area(page, '기획 요청');
  seen.disconnected_prompt = await page.locator('#planning-prompt').inputValue({ timeout: 5000 }).catch(() => null);
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify(seen, null, 1)}\n`);
  expect(String(seen.after_hero)).toContain(version);
});
