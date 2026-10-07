import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Download, Page } from '@playwright/test';

// Record 최길웅-20261007-044: PM date pack (PR #188, pm-synthetic-trends.v1) beyond the single FRIDGE-A October check.
// Reads the API/MCP matrix written by evals/web/20261007/web-r4-pmdated/tools/check_pm_dated_matrix.py (which recomputed
// every aggregate independently) and checks the web for chosen scopes: the same aggregate ID for the same project and
// filters, every bar of every topic against the API bucket (count/denominator, "자료 없음" for empty buckets, never 0%),
// a drill-down, the KST year boundary, JSON/Markdown and the planning hand-off. Only GETs plus one project selection;
// no model is called. Opt-in: skipped unless LGAX_E2E_TREND_TOKEN_FILE and LGAX_E2E_TREND_MATRIX_FILE are set.
const tokenFile = process.env.LGAX_E2E_TREND_TOKEN_FILE;
const matrixFile = process.env.LGAX_E2E_TREND_MATRIX_FILE;
const proofDir = process.env.LGAX_E2E_TREND_PROOF_DIR;

interface Topic { topic_id: string; count: number; ratio: number | null; evidence_ids: string[] }
interface Bucket { bucket_id: string; label: string; partial_period: boolean; total_reviews: number; topics: Topic[] }
interface SnapshotBucket { bucket_id: string; total_reviews: number; topics: { topic_id: string; topic_review_count: number }[] }
interface Case {
  model_id: string; granularity: 'month' | 'season'; project_id: string; aggregate_id: string; ok: boolean; dataset_sha256: string;
  filters: { start_date: string; end_date_exclusive: string }; counts: { eligible_unique_review_count: number; excluded_undated_count: number }; buckets: Bucket[];
}
const GROUP_CARD: Record<string, string> = { FRIDGE: '냉장고', DISHWASHER: '식기세척기', MICROWAVE: '전자레인지' };
// FRIDGE-A month covers the KST year boundary and empty months; the others switch product group and granularity.
const PICK: [string, Case['granularity']][] = [['FRIDGE-A', 'month'], ['FRIDGE-A', 'season'], ['MICROWAVE-A', 'month'], ['DISHWASHER-A', 'season']];

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}
const readDownload = async (download: Download) => readFileSync(await download.path(), 'utf8');

test('PM date pack: every model scope, bar and topic on the web equals the API/MCP aggregate', async ({ page }) => {
  test.skip(!tokenFile || !matrixFile, 'LGAX_E2E_TREND_TOKEN_FILE / LGAX_E2E_TREND_MATRIX_FILE not set');
  test.setTimeout(5 * 60_000);
  const token = (JSON.parse(readFileSync(tokenFile!, 'utf8')) as { token: string }).token;
  const matrix = JSON.parse(readFileSync(matrixFile!, 'utf8')) as { result: string; cases: Case[] };
  expect(matrix.result, 'API/MCP matrix must have passed first').toBe('scope_matrix_ok');
  const proof: Record<string, unknown> = { kind: 'pm_dated_scope_web_leg', started_at: new Date().toISOString(), cases: [] as unknown[] };
  try {
    await page.goto('/');
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: '근거 대조' }).click();
    await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
    await page.getByLabel('작업실 토큰').fill(token);
    await page.getByRole('button', { name: '연결', exact: true }).click();
    await expect(page.locator('.workspace-state')).toContainText('연결됨');
    for (const [model, granularity] of PICK) {
      const item = matrix.cases.find(entry => entry.model_id === model && entry.granularity === granularity)!;
      await page.getByRole('combobox', { name: '프로젝트' }).selectOption(item.project_id);
      // The planner picks the project's product the way a user does (works with or without PR #201's automatic sync).
      await page.locator('.scenario-card', { hasText: GROUP_CARD[model.split('-')[0]] }).click();
      await page.locator('#product-model').selectOption(model);
      await openArea(page, '리뷰 동향');
      await page.getByRole('radio', { name: /실제 서버/ }).check();
      await page.getByRole('radio', { name: granularity === 'month' ? '월별' : '계절별' }).check();
      await page.getByLabel('시작일').fill(item.filters.start_date);
      await page.getByLabel('종료일(미포함)').fill(item.filters.end_date_exclusive);
      await page.getByRole('button', { name: '동향 조회' }).click();
      await expect(page.locator('.trends-panel')).toContainText(`집계 ID ${item.aggregate_id}`);
      await expect(page.locator('.trend-counts')).toContainText(`분모(유효 고유 리뷰)${item.counts.eligible_unique_review_count}건`);
      await expect(page.locator('.trend-counts')).toContainText(`날짜 없음 제외${item.counts.excluded_undated_count}건`);
      expect(await page.locator('.fixture-note').count()).toBe(0);
      const topics = await page.locator('.trends-field select').first().locator('option').evaluateAll(options => options.map(option => (option as HTMLOptionElement).value));
      expect([...topics].sort()).toEqual(item.buckets[0].topics.map(topic => topic.topic_id).sort());
      const bars: Record<string, string[]> = {};
      for (const topicId of topics) {
        await page.locator('.trends-field select').first().selectOption(topicId);
        const labels = await page.locator('.trend-bar').evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-label') ?? ''));
        const values = await page.locator('.trend-bar .trend-value').allTextContents();
        expect(labels).toHaveLength(item.buckets.length);
        item.buckets.forEach((bucket, index) => {
          const topic = bucket.topics.find(entry => entry.topic_id === topicId)!;
          expect(labels[index].startsWith(`${bucket.label}${bucket.partial_period ? ' 부분 구간' : ''}: `), labels[index]).toBe(true);
          if (bucket.total_reviews === 0) {
            expect(labels[index]).toContain('리뷰 없음');
            expect(values[index]).toBe('자료 없음');
          } else {
            expect(labels[index]).toContain(`${topic.count}/${bucket.total_reviews}건`);
            expect(values[index]).not.toBe('자료 없음');
          }
        });
        bars[topicId] = labels;
      }
      // Drill into the last non-empty cell: the KST boundary for FRIDGE-A month (2027-01, review 009 at 2026-12-31T15:00Z).
      const target = [...item.buckets].reverse().flatMap(bucket => bucket.topics.filter(topic => topic.count).map(topic => ({ bucket, topic })))[0];
      await page.locator('.trends-field select').first().selectOption(target.topic.topic_id);
      await page.locator('.trend-bar').nth(item.buckets.indexOf(target.bucket)).click();
      await expect(page.locator('.trend-evidence .id').first()).toBeVisible();
      const shown = await page.locator('.trend-evidence .id').allTextContents();
      expect([...shown].sort()).toEqual([...target.topic.evidence_ids].sort());
      const [jsonDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: 'JSON' }).click()]);
      const snapshot = JSON.parse(await readDownload(jsonDownload));
      expect([snapshot.source, snapshot.aggregate_id, snapshot.aggregate.dataset_sha256]).toEqual(['server', item.aggregate_id, item.dataset_sha256]);
      expect((snapshot.aggregate.buckets as SnapshotBucket[]).map(bucket => [bucket.bucket_id, bucket.total_reviews, bucket.topics.map(topic => `${topic.topic_id}:${topic.topic_review_count}`)]))
        .toEqual(item.buckets.map(bucket => [bucket.bucket_id, bucket.total_reviews, bucket.topics.map(topic => `${topic.topic_id}:${topic.count}`)]));
      expect([...snapshot.viewed_evidence.evidence_ids].sort()).toEqual([...target.topic.evidence_ids].sort());
      const [mdDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.trend-export').getByRole('button', { name: '문서(Markdown)' }).click()]);
      const markdown = await readDownload(mdDownload);
      expect(markdown).toContain(item.aggregate_id);
      for (const bucket of item.buckets.filter(entry => entry.total_reviews === 0)) expect(markdown).toMatch(new RegExp(`\\| ${bucket.label} \\|[^\\n]*자료 없음`));
      const name = `${model}--${granularity}`;
      if (proofDir) {
        mkdirSync(proofDir, { recursive: true });
        await page.locator('.trends-panel').screenshot({ path: join(proofDir, `${name}.png`) });
        writeFileSync(join(proofDir, `${name}.md`), markdown);
      }
      await page.getByRole('button', { name: '이 구간을 기획 요청에 추가' }).click();
      const task = await page.locator('textarea').first().inputValue();
      expect(task).toContain(item.aggregate_id);
      for (const id of target.topic.evidence_ids) expect(task).toContain(id);
      (proof.cases as unknown[]).push({ model_id: model, granularity, project_id: item.project_id, aggregate_id: item.aggregate_id, topics, bars,
        drilldown: { bucket_id: target.bucket.bucket_id, topic_id: target.topic.topic_id, evidence_ids: shown }, json_source: snapshot.source, planning_has_id: true, screenshot: proofDir ? `${name}.png` : null });
    }
    proof.result = 'web_scope_matrix_ok';
  } catch (error) {
    proof.result = 'web_scope_matrix_failed';
    proof.failure = String(error).slice(0, 1500);
    throw error;
  } finally {
    proof.finished_at = new Date().toISOString();
    if (proofDir) { mkdirSync(proofDir, { recursive: true }); writeFileSync(join(proofDir, 'web-leg-proof.json'), `${JSON.stringify(proof, null, 2)}\n`); }
  }
});
