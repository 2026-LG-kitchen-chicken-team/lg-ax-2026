// O-R8-2 version label check (record 최길웅-20261007-059). Copied into apps/web/e2e/__tmp only to run; not a product test.
// Real workspace server with the three committed R8 bundles (planning OFF). Opens every review and manual detail of the
// fridge bundle and records how its document_version is labelled. Env: VER_OUT, VER_TOKEN_FILE, VER_BUNDLE.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

test('review versions read as page-model reference material, manual versions as document editions', async ({ page }) => {
  test.setTimeout(240_000);
  const token = (JSON.parse(readFileSync(process.env.VER_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const bundle = JSON.parse(readFileSync(process.env.VER_BUNDLE!, 'utf8'));
  const out = process.env.VER_OUT!; mkdirSync(out, { recursive: true });
  await page.goto('/');
  await page.getByLabel('실제 자료 작업실 토큰').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await expect(page.getByText('실제 자료 작업실 연결됨')).toBeVisible();
  await page.locator('#research-bundle').selectOption(bundle.bundle_id);
  const panel = page.getByRole('region', { name: '실제 자료 원문' });
  await expect(panel).toBeVisible();
  const rows: { id: string; type: string; raw: string | null; label: string | null; note: string | null }[] = [];
  for (const source of bundle.sources) {
    await panel.locator('.research-source-row').filter({ hasText: source.source_id }).first().getByRole('button').first().click();
    const detail = panel.getByRole('article', { name: '인용 원문 상세' });
    await expect(detail.locator('h3')).toContainText(source.source_id);
    rows.push({ id: source.source_id, type: source.source_type, raw: source.document_version ?? null,
      label: await detail.locator('[data-document-version]').textContent(),
      note: (await detail.locator('[data-document-version-note]').count()) ? await detail.locator('[data-document-version-note]').textContent() : null });
    if (rows.length === 1 || (source.source_type !== 'review' && !rows.slice(0, -1).some(row => row.type === source.source_type))) {
      await detail.screenshot({ path: join(out, `${source.source_type}-detail.png`) });
    }
    await detail.getByRole('button', { name: '상세 닫기' }).click();
  }
  const problems = rows.filter(row => row.type === 'review'
    ? row.label !== `페이지 모델의 연결 참고자료 버전: ${row.raw ?? '미확인'}` || !row.note
    : row.label !== `문서판: ${row.raw ?? '미확인'}` || row.note !== null).map(row => row.id);
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify({ bundle_id: bundle.bundle_id, rows: rows.length, by_type: rows.reduce((acc: Record<string, number>, row) => ({ ...acc, [row.type]: (acc[row.type] ?? 0) + 1 }), {}), problems, sample: rows.slice(0, 2).concat(rows.filter(row => row.type !== 'review').slice(0, 1)) }, null, 1)}\n`);
  expect(problems).toEqual([]);
});
