// R8 research web flow, independent check by the WEB owner (record 최길웅-20261007-057). Copied into apps/web/e2e/__tmp
// only to run; not a product test. Real workspace server (PR #245 head) serving the three committed R8 public bundles with
// research planning OFF (no model). Vite runs on 5175, an origin that server allows, so the browser's own POST reaches it.
// Compares what the screen shows with expected.json computed from the bundle files only (expected_from_bundles.py).
// Env: R8_DIR (evals folder), R8_TOKEN_FILE.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const dir = process.env.R8_DIR!;
const expected = JSON.parse(readFileSync(join(dir, 'expected.json'), 'utf8')).bundles as Record<string, Record<string, any>>;
const sourcesPanel = (page: Page) => page.getByRole('region', { name: '실제 자료 원문' });
const panelCount = async (page: Page) => (await sourcesPanel(page).locator('.research-card-title span').first().textContent())?.trim() ?? '';

async function connect(page: Page, token: string) {
  await page.goto('/');
  await page.getByLabel('실제 자료 작업실 토큰').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await expect(page.getByText('실제 자료 작업실 연결됨')).toBeVisible();
}

test('R8 research flow: real bundles, honest unknowns, filters, reuse export, planning-off error', async ({ page }) => {
  test.setTimeout(240_000);
  const token = (JSON.parse(readFileSync(process.env.R8_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = join(dir, 'browser');
  mkdirSync(out, { recursive: true });
  const writes: { method: string; url: string; status: number }[] = [];
  page.on('response', response => {
    const request = response.request();
    if (request.method() !== 'GET' && response.url().includes('/api/research')) writes.push({ method: request.method(), url: new URL(response.url()).pathname, status: response.status() });
  });
  const seen: Record<string, any> = { bundles: {} };
  await page.goto('/');
  seen.first_screen = (await page.locator('.research-intro h1').textContent())?.trim() ?? null;
  seen.before_connect = (await page.locator('.research-empty').first().textContent())?.trim() ?? null;
  await connect(page, token);
  seen.bundle_options = (await page.locator('#research-bundle option').allTextContents()).slice(1);

  for (const [bundleId, want] of Object.entries(expected)) {
    await page.locator('#research-bundle').selectOption(bundleId);
    await expect(sourcesPanel(page)).toBeVisible();
    const row: Record<string, any> = {};
    row.setup_note = (await page.locator('.research-setup .research-note').first().textContent())?.trim();
    row.panel_count = await panelCount(page);
    row.posting_options = await sourcesPanel(page).locator('select').nth(2).locator('option').allTextContents();
    row.limitations = await sourcesPanel(page).getByRole('region', { name: '자료의 핵심 한계' }).locator('li').allTextContents();
    row.page_unknown_option = await sourcesPanel(page).locator('option[value="__unknown__"]').count();
    if (row.page_unknown_option) {
      await sourcesPanel(page).locator('select').nth(1).selectOption('__unknown__');
      row.page_unknown_count = await panelCount(page);
      await sourcesPanel(page).locator('select').nth(1).selectOption('');
    }
    row.keyword_counts = {};
    for (const word of Object.keys(want.keyword_hits_title_or_text)) {
      await page.locator('#research-keyword').fill(word);
      row.keyword_counts[word] = await panelCount(page);
    }
    await page.locator('#research-keyword').fill('');
    const unknownText = await sourcesPanel(page).locator('.research-source-row').first().textContent();
    row.first_row_unknowns = { purchase_unknown: unknownText?.includes('구매 모델 미확인') ?? false, posting_unknown: unknownText?.includes('게시일 미확인') ?? false };
    seen.bundles[bundleId] = row;
  }

  // Reuse export (W2): choose two fridge sources and export JSON; the exported text must equal the bundle text.
  const fridge = Object.keys(expected).find(id => id.includes('fridge'))!;
  await page.locator('#research-bundle').selectOption(fridge);
  await expect(sourcesPanel(page)).toBeVisible();
  const checks = sourcesPanel(page).locator('.research-source-check input');
  await checks.nth(0).check();
  await checks.nth(1).check();
  const chosenIds = await sourcesPanel(page).locator('.research-source-check span').evaluateAll(nodes => nodes.slice(0, 2).map(node => node.textContent?.trim()));
  const [download] = await Promise.all([page.waitForEvent('download'), sourcesPanel(page).getByRole('button', { name: '선택 자료 JSON' }).click()]);
  const exportPath = join(out, 'selection-export.json');
  await download.saveAs(exportPath);
  seen.selection_export = { chosen_ids: chosenIds, file: 'selection-export.json' };

  // Planning is OFF on this server: the browser's own POST must surface the server error, with no result drawn.
  await page.getByRole('button', { name: '새 기획 생성' }).click();
  await expect(page.locator('.research-error')).toBeVisible();
  seen.planning_off = {
    error: (await page.locator('.research-error').textContent())?.trim(),
    result_sections: await page.getByRole('region', { name: '실제 자료 기획 결과' }).count(),
    history_options: (await page.locator('#research-run-choice option').allTextContents()).slice(1),
  };
  await page.screenshot({ path: join(out, 'planning-off-error.png'), fullPage: true });
  // A stored run ID that does not exist must also fail visibly.
  await page.locator('#research-restore-id').fill('run-does-not-exist');
  await page.getByRole('button', { name: '불러오기' }).click();
  await expect(page.locator('.research-error')).toContainText('요청을 완료하지 못했습니다');
  seen.restore_missing = (await page.locator('.research-error').textContent())?.trim();
  // Disconnect clears the bundle list and the selected data.
  await page.getByRole('button', { name: '연결 해제' }).first().click();
  seen.after_disconnect = { bundle_select: await page.locator('#research-bundle').count(), sources_panel: await sourcesPanel(page).count() };
  seen.writes = writes;
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify(seen, null, 1)}\n`);
});
