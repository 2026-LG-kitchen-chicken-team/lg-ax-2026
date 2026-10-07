// R8 source position display (record 최길웅-20261007-058). Copied into apps/web/e2e/__tmp only to run; not a product test.
// Real workspace server with the three committed R8 bundles (planning OFF). For every source row the readable position
// is read back and compared with the bundle's own locator keys; one detail per source type is opened and captured.
// Env: LOC_OUT (output folder), LOC_TOKEN_FILE, LOC_BUNDLE_DIR.
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

test('R8 source rows and details show where each original sits', async ({ page }) => {
  test.setTimeout(240_000);
  const token = (JSON.parse(readFileSync(process.env.LOC_TOKEN_FILE!, 'utf8')) as { token: string }).token;
  const out = process.env.LOC_OUT!; mkdirSync(out, { recursive: true });
  const bundles = readdirSync(process.env.LOC_BUNDLE_DIR!).map(name => JSON.parse(readFileSync(join(process.env.LOC_BUNDLE_DIR!, name), 'utf8')));
  await page.goto('/');
  await page.getByLabel('실제 자료 작업실 토큰').fill(token);
  await page.getByRole('button', { name: '실제 자료 연결' }).click();
  await expect(page.getByText('실제 자료 작업실 연결됨')).toBeVisible();
  const seen: Record<string, unknown> = {};
  for (const bundle of bundles) {
    await page.locator('#research-bundle').selectOption(bundle.bundle_id);
    const panel = page.getByRole('region', { name: '실제 자료 원문' });
    await expect(panel).toBeVisible();
    const rows = await panel.locator('.research-source-row').evaluateAll(nodes => nodes.map(node => {
      const id = node.querySelector('.research-source-check span')?.textContent?.trim() ?? '';
      const meta = [...node.querySelectorAll('p.research-muted')].map(p => p.textContent ?? '').join(' ');
      return { id, position: meta.includes(' · 위치 ') ? meta.slice(meta.indexOf(' · 위치 ') + 6) : null };
    }));
    const byType: Record<string, string[]> = {};
    const problems: string[] = [];
    for (const row of rows) {
      const source = bundle.sources.find((item: { source_id: string }) => item.source_id === row.id);
      const keys = Object.keys(source.locator ?? {}).filter(key => key !== 'selector' && source.locator[key] !== null && source.locator[key] !== '');
      if (!row.position) problems.push(`${row.id}: no position`);
      else if (keys.length && row.position.includes('위치 정보 없음')) problems.push(`${row.id}: locator ${keys.join(',')} shown as none`);
      (byType[source.source_type] ??= []).includes(row.position ?? '') || byType[source.source_type].length >= 3 || byType[source.source_type].push(row.position ?? '');
    }
    const details: Record<string, unknown> = {};
    for (const type of Object.keys(byType)) {
      const first = bundle.sources.find((item: { source_type: string }) => item.source_type === type);
      await panel.locator('.research-source-row').filter({ hasText: first.source_id }).first().getByRole('button').first().click();
      const detail = panel.getByRole('article', { name: '인용 원문 상세' });
      await expect(detail).toBeVisible();
      details[type] = { id: first.source_id, position: await detail.locator('[data-source-locator]').textContent(), technical: await detail.locator('.research-locator-technical code').allTextContents() };
      await detail.screenshot({ path: join(out, `${bundle.product_group}-${type}-detail.png`) });
      await detail.getByRole('button', { name: '상세 닫기' }).click();
    }
    seen[bundle.bundle_id] = { rows: rows.length, sources: bundle.sources.length, problems, samples_by_type: byType, details };
  }
  writeFileSync(join(out, 'observed.json'), `${JSON.stringify(seen, null, 1)}\n`);
  for (const value of Object.values(seen) as { rows: number; sources: number; problems: string[] }[]) { expect(value.problems).toEqual([]); expect(value.rows).toBe(value.sources); }
});
