import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Download, Page } from '@playwright/test';

// WEB-INTEGRATION-R3 (record 최길웅-20261006-031): the web leg of the review-trend consumption path. It needs a
// workspace server with a trusted collector behind LGAX_WORKSPACE_PROXY and the API→MCP result of
// evals/web/20261006/web-integration-r3/tools/check_api_mcp_path.py (same project). Opt-in: skipped unless
// LGAX_E2E_TREND_TOKEN_FILE and LGAX_E2E_TREND_PATH_FILE are set. With the unit FixtureCollector this proves the
// wiring only (one fixture-dated review); with the DATA #148 collector the same steps check real numbers.
const tokenFile = process.env.LGAX_E2E_TREND_TOKEN_FILE;
const pathFile = process.env.LGAX_E2E_TREND_PATH_FILE;
const proofDir = process.env.LGAX_E2E_TREND_PROOF_DIR;

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}
const readDownload = async (download: Download) => readFileSync(await download.path(), 'utf8');

test('review trend: same aggregate ID from API/MCP → chart → original text → export → planning request', async ({ page }) => {
  test.skip(!tokenFile || !pathFile, 'LGAX_E2E_TREND_TOKEN_FILE / LGAX_E2E_TREND_PATH_FILE not set');
  test.setTimeout(5 * 60_000);
  const token = (JSON.parse(readFileSync(tokenFile!, 'utf8')) as { token: string }).token;
  const path = JSON.parse(readFileSync(pathFile!, 'utf8')) as {
    result: string; project_id: string; aggregate_id: string; dataset_sha256: string; filters: { start_date: string; end_date_exclusive: string; model_id: string };
    evidence_ids: string[]; counts: { eligible_unique_review_count: number; excluded_undated_count: number };
  };
  expect(path.result, 'API→MCP leg must have passed first').toBe('consumption_path_ok');
  const proof: Record<string, unknown> = { kind: 'review_trend_web_leg', started_at: new Date().toISOString(), project_id: path.project_id, mcp_aggregate_id: path.aggregate_id };
  try {
    await page.goto('/');
    await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
    await page.getByLabel('작업실 토큰').fill(token);
    await page.getByRole('button', { name: '연결', exact: true }).click();
    await expect(page.locator('.workspace-state')).toContainText('연결됨');
    await page.getByRole('combobox', { name: '프로젝트' }).selectOption(path.project_id);
    await expect(page.locator('#product-model')).toHaveValue(path.filters.model_id);

    // 1. Same aggregate as the API/MCP leg: the web asks the server, never draws a fixture here.
    await openArea(page, '리뷰 동향');
    await page.getByRole('radio', { name: /실제 서버/ }).check();
    await page.getByLabel('시작일').fill(path.filters.start_date);
    await page.getByLabel('종료일(미포함)').fill(path.filters.end_date_exclusive);
    await page.getByRole('button', { name: '동향 조회' }).click();
    await expect(page.locator('.trends-panel')).toContainText(`집계 ID ${path.aggregate_id}`);
    await expect(page.locator('.trend-counts')).toContainText(`분모(유효 고유 리뷰)${path.counts.eligible_unique_review_count}건`);
    proof.web_aggregate_id = path.aggregate_id;
    proof.fixture_note_shown = await page.locator('.fixture-note').count() > 0;
    expect(proof.fixture_note_shown).toBe(false);
    if (proofDir) { mkdirSync(proofDir, { recursive: true }); await page.screenshot({ path: join(proofDir, 'web-trend-chart.png'), fullPage: true }); }

    if (path.counts.eligible_unique_review_count === 0) {
      // Honest empty aggregate (e.g. a real collector over undated reviews): denominator 0, every bar "자료 없음",
      // never 0%, nothing to drill into, and the exports keep the same ID with no viewed evidence.
      await expect(page.locator('[data-denominator="zero"]')).toBeVisible();
      await expect(page.locator('.trend-counts')).toContainText(`날짜 없음 제외${path.counts.excluded_undated_count}건`);
      await expect(page.locator('.trend-bar.value')).toHaveCount(0);
      const bars = await page.locator('.trend-bar').allTextContents();
      expect(bars.length).toBeGreaterThan(0);
      expect(bars.every(text => text.includes('자료 없음') && !text.includes('0%'))).toBe(true);
      proof.empty_aggregate = { bars, undated: path.counts.excluded_undated_count };
      const [jsonDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: 'JSON' }).click()]);
      const snapshot = JSON.parse(await readDownload(jsonDownload));
      expect(snapshot.source).toBe('server');
      expect(snapshot.aggregate_id).toBe(path.aggregate_id);
      expect(snapshot.aggregate.dataset_sha256).toBe(path.dataset_sha256);
      expect(snapshot.aggregate.counts.eligible_unique_review_count).toBe(0);
      const [mdDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: '문서(Markdown)' }).click()]);
      const markdown = await readDownload(mdDownload);
      expect(markdown).toContain(path.aggregate_id);
      // Table rows only (the notes legitimately say "0%와 다릅니다"): every bucket × topic cell must read "자료 없음".
      const rows = markdown.split('\n').filter(line => line.startsWith('| ') && !line.startsWith('| 구간'));
      expect(rows.length).toBeGreaterThan(0);
      expect(rows.every(row => row.split('|').slice(2, -1).every(cell => cell.trim() === '자료 없음'))).toBe(true);
      expect(markdown).toContain('분모(유효 고유 리뷰) 0건');
      proof.export = { json_source: snapshot.source, json_aggregate_id: snapshot.aggregate_id, json_viewed_evidence: snapshot.viewed_evidence ?? null, markdown_has_id: true };
      if (proofDir) { writeFileSync(join(proofDir, 'web-snapshot.json'), JSON.stringify(snapshot, null, 2)); writeFileSync(join(proofDir, 'web-snapshot.md'), markdown); }
      proof.result = 'web_leg_ok_empty_aggregate';
      return;
    }

    // 2. Drill-down shows exactly the API/MCP evidence of that bucket/topic.
    await page.locator('.trend-bar.value').first().click();
    await expect(page.locator('.trend-evidence .id').first()).toBeVisible();
    const shown = await page.locator('.trend-evidence .id').allTextContents();
    expect([...shown].sort()).toEqual([...path.evidence_ids].sort());
    proof.web_evidence_ids = shown;

    // 3. Snapshot export carries the same aggregate and the opened page, labelled as a server result.
    const [jsonDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: 'JSON' }).click()]);
    const snapshot = JSON.parse(await readDownload(jsonDownload));
    expect(snapshot.source).toBe('server');
    expect(snapshot.aggregate_id).toBe(path.aggregate_id);
    expect(snapshot.aggregate.dataset_sha256).toBe(path.dataset_sha256);
    expect([...snapshot.viewed_evidence.evidence_ids].sort()).toEqual([...path.evidence_ids].sort());
    const [mdDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: '문서(Markdown)' }).click()]);
    const markdown = await readDownload(mdDownload);
    expect(markdown).toContain(path.aggregate_id);
    expect(markdown).toContain('작업실 서버 고정 집계');
    proof.export = { json_source: snapshot.source, json_aggregate_id: snapshot.aggregate_id, markdown_has_id: markdown.includes(path.aggregate_id) };
    if (proofDir) { writeFileSync(join(proofDir, 'web-snapshot.json'), JSON.stringify(snapshot, null, 2)); writeFileSync(join(proofDir, 'web-snapshot.md'), markdown); }

    // 4. Planning hand-off cites the same aggregate and evidence IDs, not the review texts.
    await page.getByRole('button', { name: '이 구간을 기획 요청에 추가' }).click();
    const task = page.locator('textarea').first();
    await expect(task).toHaveValue(new RegExp(path.aggregate_id));
    const value = await task.inputValue();
    for (const id of path.evidence_ids) expect(value).toContain(id);
    expect(value).toContain('판매량');
    proof.planning_note_has_id = true;
    proof.result = 'web_leg_ok';
  } catch (error) {
    proof.result = 'web_leg_failed';
    proof.failure = String(error).slice(0, 1500);
    throw error;
  } finally {
    proof.finished_at = new Date().toISOString();
    if (proofDir) { mkdirSync(proofDir, { recursive: true }); writeFileSync(join(proofDir, 'web-leg-proof.json'), `${JSON.stringify(proof, null, 2)}\n`); }
  }
});
