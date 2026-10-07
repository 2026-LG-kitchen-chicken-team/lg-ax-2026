// R5 independent web check (record 052): how a planning-OFF run on the public dataset reads in a real browser (GET only).
// Env: R5_DIR, R5_TOKEN_FILE, R5_PROJECT (project with one not_implemented run created over HTTP with Origin 5173).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

test('R5 public dataset: a planning-OFF run never reads as a result', async ({ page }) => {
  const token = (JSON.parse(readFileSync(process.env.R5_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = join(process.env.R5_DIR!, 'public-flow');
  mkdirSync(out, { recursive: true });
  await page.goto('/');
  await page.getByLabel('작업실 토큰').fill(token);
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page.locator('.workspace-state')).toContainText('연결됨');
  await page.getByRole('combobox', { name: '프로젝트' }).selectOption(process.env.R5_PROJECT!);
  const nav = page.getByRole('navigation', { name: '기획 작업 영역' });
  const seen: Record<string, unknown> = {};
  await nav.getByRole('button', { name: '콘셉트 검토' }).click();
  await page.waitForTimeout(1500);
  seen.concepts = ((await page.locator('main').textContent({ timeout: 5000 }).catch(() => '')) ?? '').split('03 / WORKSPACE')[1]?.slice(0, 900);
  seen.concept_cards = await page.locator('.concept-card').count();
  seen.status_pills = await page.locator('.run-status').allTextContents();
  await page.screenshot({ path: join(out, '5-not-implemented-run.png'), fullPage: true });
  await nav.getByRole('button', { name: '수정 이력' }).click();
  await page.waitForTimeout(1000);
  seen.history = ((await page.locator('[data-revision-timeline]').textContent({ timeout: 5000 }).catch(() => '')) ?? '').slice(0, 600);
  writeFileSync(join(out, 'run-view.observed.json'), `${JSON.stringify(seen, null, 1)}\n`);
  expect(seen.concept_cards).toBe(0);
});
