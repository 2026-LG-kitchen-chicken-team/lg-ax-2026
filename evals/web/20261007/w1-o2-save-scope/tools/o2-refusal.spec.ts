// W1 O2 check (record 최길웅-20261007-055). Copied into apps/web/e2e/__tmp only to run; not a product test.
// Same setup as record 054: a test workspace DB holding a synthetic-version (0.1.0, FRIDGE-A) project, served with the
// R5 public development dataset; this browser runs on a non-allowed origin, so the server refuses the new project.
// Before the fix the refused save left no project selected: the dataset-change and unavailable-model notices vanished
// while the project picker still showed the old project. Checks that after the refusal the screen still shows the
// old project, both notices, the planner's chosen model and the "new project" save button. No model is called.
// Env: O2_OUT (output folder), O2_TOKEN_FILE.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const area = (page: Page, label: string) => page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();

async function requestState(page: Page) {
  const picker = page.getByRole('combobox', { name: '프로젝트' });
  return {
    picker_value: await picker.inputValue(),
    picker_label: (await picker.locator('option:checked').textContent())?.trim() ?? null,
    workspace_state: (await page.locator('.workspace-state').textContent())?.trim() ?? null,
    dataset_change: await page.locator('[data-dataset-change]').allTextContents(),
    missing_models: await page.locator('[data-missing-project-models]').allTextContents(),
    checked_models: await page.locator('.model-picker input:checked').count(),
    submit_label: (await page.locator('.request-form button[type="submit"]').first().textContent())?.trim() ?? null,
    messages: await page.locator('.inline-message, [role="status"], [role="alert"]').allTextContents(),
  };
}

test('O2: a refused new-project save keeps the shown project and its notices', async ({ page }) => {
  test.setTimeout(120_000);
  const token = (JSON.parse(readFileSync(process.env.O2_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = process.env.O2_OUT!;
  mkdirSync(out, { recursive: true });
  const writes: { url: string; status: number }[] = [];
  page.on('response', response => {
    if (response.request().method() !== 'GET' && response.url().includes('/api/workspace/')) writes.push({ url: new URL(response.url()).pathname, status: response.status() });
  });
  await page.goto('/');
  await page.getByLabel('작업실 토큰').fill(token);
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page.locator('.workspace-state')).toContainText('연결됨');
  await area(page, '기획 요청');
  const before = await requestState(page);
  await page.locator('.model-picker label').first().click();
  const chosen = await requestState(page);
  await page.locator('.request-form button[type="submit"]').first().click();
  await expect(page.getByRole('alert').filter({ hasText: 'FORBIDDEN' })).toBeVisible();
  const after = await requestState(page);
  await page.screenshot({ path: join(out, 'after-refusal.png'), fullPage: true });
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify({ before, chosen, after, writes }, null, 1)}\n`);

  expect(writes).toEqual([{ url: '/api/workspace/projects', status: 403 }]);
  expect(before.dataset_change).toHaveLength(1);
  expect(before.missing_models).toHaveLength(1);
  expect(after.picker_value).toBe(before.picker_value);
  expect(after.dataset_change).toEqual(before.dataset_change);
  expect(after.missing_models).toEqual(before.missing_models);
  expect(after.checked_models).toBe(chosen.checked_models);
  expect(after.submit_label).toBe(before.submit_label);
});
