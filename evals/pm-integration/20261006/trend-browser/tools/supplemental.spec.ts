import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

// Extra evidence assertions complement the unchanged member E2E. Runs only in the zero-auth guest.
test('PM trend proof: exact synthetic scope, ratio, original bytes and planning hand-off', async ({ page }) => {
  const tokenFile = process.env.LGAX_E2E_TREND_TOKEN_FILE!;
  const pathFile = process.env.LGAX_E2E_TREND_PATH_FILE!;
  const out = process.env.LGAX_E2E_TREND_PROOF_DIR!;
  test.skip(!tokenFile || !pathFile || !out);
  const token = JSON.parse(readFileSync(tokenFile, 'utf8')).token;
  const path = JSON.parse(readFileSync(pathFile, 'utf8'));
  const proof: Record<string, unknown> = { kind: 'pm_trend_browser_exact_scope', aggregate_id: path.aggregate_id, browser_version: page.context().browser()?.version() };
  const files: string[] = [];
  mkdirSync(out, { recursive: true });
  try {
    await page.goto('/');
    await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
    const secretInput = page.getByLabel('작업실 토큰');
    expect(await secretInput.getAttribute('type')).toBe('password');
    await secretInput.fill(token);
    await page.getByRole('button', { name: '연결', exact: true }).click();
    await expect(page.locator('.workspace-state')).toContainText('연결됨');
    await page.getByRole('combobox', { name: '프로젝트' }).selectOption(path.project_id);
    await expect(page.locator('#product-model')).toHaveValue('FRIDGE-A');
    await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: '리뷰 동향' }).click();
    await page.getByRole('radio', { name: /실제 서버/ }).check();
    await page.getByLabel('시작일').fill(path.filters.start_date);
    await page.getByLabel('종료일(미포함)').fill(path.filters.end_date_exclusive);
    await page.getByRole('button', { name: '동향 조회' }).click();
    const panel = page.locator('.trends-panel');
    await expect(panel).toContainText(`집계 ID ${path.aggregate_id}`);
    await expect(panel).toContainText('리뷰 주제 언급 비율');
    await expect(panel).toContainText('불편이나 감정의 비율을 의미하지 않습니다');
    await expect(panel.locator('.trends-controls select')).toHaveValue('cleaning');
    for (const warning of path.api_aggregate.warnings) await expect(page.locator('.trend-warnings')).toContainText(warning);
    expect(await page.locator('.fixture-note').count()).toBe(0);
    proof.counts_text = await page.locator('.trend-counts').innerText();
    proof.chart_aria = await page.locator('.trend-chart').getAttribute('aria-label');
    const bars = page.locator('.trend-bar');
    expect(await bars.count()).toBe(1);
    proof.bar_aria = await bars.first().getAttribute('aria-label');
    if (path.counts.eligible_unique_review_count === 0) {
      await expect(page.locator('[data-denominator="zero"]')).toBeVisible();
      await expect(bars.first()).toContainText('자료 없음');
      expect(await page.getByRole('button', { name: '이 구간을 기획 요청에 추가' }).count()).toBe(0);
      proof.result = 'exact_empty_scope_ok';
      proof.planning_handoff_executed = false;
      await page.screenshot({ path: join(out, 'pm-empty-scope.png'), fullPage: true });
      files.push('pm-empty-scope.png');
    } else {
      await expect(bars.first()).toContainText('33.3%');
      await expect(bars.first()).toContainText('1/3건');
      await expect(bars.first()).toContainText('작은 표본');
      await bars.first().click();
      await expect(bars.first()).toHaveAttribute('aria-pressed', 'true');
      const expected = path.api_evidence.evidence;
      const shown = page.locator('.trend-evidence li');
      await expect(shown).toHaveCount(expected.length);
      const originals = [];
      for (let i = 0; i < expected.length; i += 1) {
        const actual = shown.nth(i);
        const text = await actual.locator('blockquote').textContent();
        expect(text).toBe(expected[i].text);
        await expect(actual.locator('.id')).toHaveText(expected[i].id);
        await expect(actual.locator('small')).toContainText('합성자료');
        await expect(actual.locator('small')).toContainText('FRIDGE-A');
        await expect(actual.locator('small')).toContainText('문서 1.0');
        originals.push({ id: expected[i].id, text, text_sha256: createHash('sha256').update(text!).digest('hex'), model_id: expected[i].model_id, document_version: expected[i].document_version, source_id: expected[i].source_id, locator: expected[i].locator });
      }
      proof.selected_originals = originals;
      await panel.screenshot({ path: join(out, 'pm-selected-original.png') });
      files.push('pm-selected-original.png');
      const [jsonDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: 'JSON' }).click()]);
      const jsonText = readFileSync((await jsonDownload.path())!, 'utf8');
      const snapshot = JSON.parse(jsonText);
      expect(snapshot.aggregate).toEqual(path.api_aggregate);
      expect(snapshot.source).toBe('server');
      expect(snapshot.consistency_problems).toEqual([]);
      expect(snapshot.viewed_evidence).toEqual({ bucket_id: 'MONTH-2026-10', topic_id: 'cleaning', total: 1, evidence_ids: path.evidence_ids });
      const [mdDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: '문서(Markdown)' }).click()]);
      const markdown = readFileSync((await mdDownload.path())!, 'utf8');
      for (const value of [path.aggregate_id, path.dataset_sha256, path.api_aggregate.dataset_version, 'FRIDGE-A', '2026-10-01', '2026-11-01', 'synthetic', '1/3건 (33.3%)', 'MONTH-2026-10', path.evidence_ids[0], ...path.api_aggregate.warnings]) expect(markdown).toContain(value);
      writeFileSync(join(out, 'pm-snapshot.json'), jsonText);
      writeFileSync(join(out, 'pm-snapshot.md'), markdown);
      files.push('pm-snapshot.json', 'pm-snapshot.md');
      await page.getByRole('button', { name: '이 구간을 기획 요청에 추가' }).click();
      const task = page.locator('textarea').first();
      const value = await task.inputValue();
      for (const expectedValue of [path.aggregate_id, 'FRIDGE-A', '청소 관련 (cleaning)', '1/3건(33.3%)', '작은 표본', path.evidence_ids[0], '판매량·수요 증가를 뜻하지 않음']) expect(value).toContain(expectedValue);
      expect(value).not.toContain(expected[0].text);
      proof.planning_input = value;
      proof.planning_handoff_executed = true;
      proof.planning_saved_or_model_executed = false;
      await page.screenshot({ path: join(out, 'pm-planning-handoff.png'), fullPage: true });
      files.push('pm-planning-handoff.png');
      proof.result = 'exact_dated_scope_ok';
    }
  } finally {
    proof.files = files;
    proof.finished_at = new Date().toISOString();
    const raw = `${JSON.stringify(proof, null, 2)}\n`;
    expect(raw).not.toContain(token);
    writeFileSync(join(out, 'pm-exact-proof.json'), raw);
  }
});
