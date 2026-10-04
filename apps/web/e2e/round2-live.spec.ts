import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

// PM-20261005-WEB-003-TERMINAL-UX, recorded replay: the workspace API answers with the two held runs PM stored on 10/5
// through the real API with Qwen3:8B (evals/pm-review/20261005-round2/api-live/workspace-live.json). No model is called.
// A rerun posted here is stored request-only (not_implemented) and never turned into a model result. Checks the screen,
// the actual JSON/Markdown download files and that the stored runs stay unchanged. Kept out of CI's fixed planner-flow
// run; needs the public API (18867) for the bootstrap.
const RECORD = JSON.parse(readFileSync(resolve(process.cwd(), '../../evals/pm-review/20261005-round2/api-live/workspace-live.json'), 'utf8'));
const FIRST = RECORD.first;
const SECOND = RECORD.second;
const PROJECT = RECORD.project;
const TOKEN = 'replay-token-for-recorded-runs-only-0123456789';
const json = (route: Route, data: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, data }) });

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}

test('round2 held runs: record under the same run ID → JSON/Markdown files with the original record → condition-only rerun, stored runs unchanged', async ({ page }) => {
  const runs = [structuredClone(FIRST), structuredClone(SECOND)];
  const posted: Record<string, unknown>[] = [];
  await page.route('**/api/workspace/**', async route => {
    const request = route.request();
    expect(request.headers().authorization).toBe(`Bearer ${TOKEN}`);
    const path = new URL(request.url()).pathname.replace('/api/workspace', '');
    if (request.method() === 'GET' && path === '/projects') return json(route, { projects: [PROJECT], contract_version: '0.1.0' });
    if (request.method() === 'GET' && path === `/projects/${PROJECT.project.id}`) return json(route, PROJECT);
    if (request.method() === 'GET' && path === `/projects/${PROJECT.project.id}/runs`) return json(route, { runs, contract_version: '0.1.0' });
    if (request.method() === 'GET' && path.startsWith('/runs/')) return json(route, runs.find(item => item.run.id === path.slice(6)));
    if (request.method() === 'POST' && path === `/projects/${PROJECT.project.id}/runs`) {
      const body = request.postDataJSON();
      posted.push(body);
      const parent = runs.find(item => item.run.id === body.previous_run_id)!;
      const stored = {
        run: { id: 'run-replay-request-only', project_id: PROJECT.project.id, dataset_version: body.request.dataset_version, contract_version: '0.1.0',
          status: 'not_implemented', stage: 'plan', revision_count: 0, max_revisions: 2, concepts: [],
          unresolved: ['기록 재생 서버: 요청만 저장했고 모델을 호출하지 않았습니다.'], evidence_ids: [],
          events: [{ stage: 'plan', summary: '기획 요청과 자료 범위를 저장했습니다. 분석은 실행하지 않았습니다.', tool: null, evidence_ids: [] }] },
        request: body.request, previous_run_id: parent.run.id, request_revision: parent.request_revision + 1, actor_id: 'planner-demo', client: 'web',
        created_at: '2026-10-05T04:00:00.000000Z', document_versions: PROJECT.document_versions, dataset_sha256: PROJECT.dataset_sha256,
        unconfirmed: body.unconfirmed, output: null,
      };
      runs.push(stored);
      return json(route, stored);
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ ok: false, error: { code: 'NOT_FOUND', message: 'replay route' } }) });
  });

  await page.goto('/');
  await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
  await page.getByLabel('작업실 토큰').fill(TOKEN);
  await page.getByRole('button', { name: '연결', exact: true }).click();
  await expect(page.locator('.workspace-state')).toContainText('연결됨');

  // The latest run (changed conditions) under its own run ID: held, with the questions, semantic review and rejected candidates.
  const record2 = SECOND.output.planning_execution;
  await openArea(page, '콘셉트 검토');
  const record = page.getByRole('region', { name: '판단 실행 기록' });
  await expect(record).toContainText(SECOND.run.id);
  await expect(record).toContainText('실제 모델 실행 기록(저장된 결과)');
  await expect(record).toContainText('자동 세척 장치 제안');
  for (const question of record2.semantic_reviews[0].report.questions) await expect(record).toContainText(question);
  for (const concept of record2.rejected_output.concepts) await expect(record).toContainText(concept.title);
  await expect(record).not.toContainText('계약 검사 통과');
  await expect(page.locator('.concept-card')).toHaveCount(0);
  if (process.env.LGAX_E2E_SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.LGAX_E2E_SCREENSHOT_DIR}/round2-held-concepts.png`, fullPage: true });

  // The downloaded files, not just the in-page document.
  await expect(page.locator('.export-check').first()).toHaveText('내보내기 점검: 누락 없음');
  const [jsonDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.export-actions').first().getByRole('button', { name: 'JSON' }).click()]);
  const exported = JSON.parse(readFileSync(await jsonDownload.path(), 'utf8'));
  expect(exported.completeness.complete).toBe(true);
  expect(exported.meta.run_id).toBe(SECOND.run.id);
  expect(exported.lineage.map((item: { run_id: string }) => item.run_id)).toEqual([FIRST.run.id, SECOND.run.id]);
  expect(exported.judgement.decision).toBe('hold');
  expect(exported.judgement.questions).toEqual(expect.arrayContaining(record2.semantic_reviews[0].report.questions));
  expect(exported.execution_record).toEqual(record2);
  const [mdDownload] = await Promise.all([page.waitForEvent('download'), page.locator('.export-actions').first().getByRole('button', { name: '문서(Markdown)' }).click()]);
  const markdown = readFileSync(await mdDownload.path(), 'utf8');
  expect(markdown).toContain('## 판단 실행 기록');
  for (const question of record2.semantic_reviews[0].report.questions) expect(markdown).toContain(question);
  for (const concept of record2.rejected_output.concepts) expect(markdown).toContain(concept.title);

  // No candidate to pick from a held run: only a corrected condition starts a new, linked request.
  await openArea(page, '수정 이력');
  const rerun = page.getByRole('form', { name: '후보·조건 선택 후 재실행' });
  await expect(rerun.getByRole('radiogroup')).toHaveCount(0);
  await expect(rerun).toContainText('보류로 끝나 채택된 후보가 없습니다');
  await rerun.getByLabel('추가 조건').fill('분리형 선반 구조만 검토');
  await rerun.getByRole('button', { name: '조건 추가' }).click();
  await rerun.getByRole('button', { name: '다시 실행 요청' }).click();
  await expect(page.locator('.timeline li')).toHaveCount(3);
  await expect(page.locator('.timeline li').last()).toContainText('요청만 저장됨');
  expect(posted).toHaveLength(1);
  expect(posted[0].previous_run_id).toBe(SECOND.run.id);
  expect((posted[0].request as { exclusions: string[] }).exclusions).toEqual([...SECOND.request.exclusions, '분리형 선반 구조만 검토']);

  // Stored runs unchanged; the first run still shows its own held record.
  expect(runs[0]).toEqual(FIRST);
  expect(runs[1]).toEqual(SECOND);
  await page.locator('.timeline').getByRole('button', { name: new RegExp(`^${FIRST.run.id}`) }).click();
  await expect(page.getByRole('region', { name: '판단 실행 기록' })).toContainText(FIRST.run.id);
  for (const question of FIRST.output.planning_execution.semantic_reviews[0].report.questions) await expect(page.getByRole('region', { name: '판단 실행 기록' })).toContainText(question);
});
