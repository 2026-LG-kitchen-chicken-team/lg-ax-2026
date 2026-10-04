import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

// PM-20261005-WEB-003-LIVE-RESULTS, recorded replay: the workspace API answers with the two runs PM stored through the
// real API with Qwen3:8B (evals/pm-integration/20261005/workspace-live.json). No model is called. A rerun posted here is
// stored the way the default server stores it (request only, not_implemented); it is never turned into a model result.
// Kept out of CI's fixed three-case planner-flow run; needs the public API (18867) for the bootstrap.
const RECORD = JSON.parse(readFileSync(resolve(process.cwd(), '../../evals/pm-integration/20261005/workspace-live.json'), 'utf8'));
const FIRST = RECORD.first;
const SECOND = RECORD.second;
const PROJECT = RECORD.project;
const TOKEN = 'replay-token-for-recorded-runs-only-0123456789';
const json = (route: Route, data: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, data }) });

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}

test('recorded live runs: core record under the same run ID → exclude a candidate → new run, old runs unchanged → export', async ({ page }) => {
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
        created_at: '2026-10-05T03:00:00.000000Z', document_versions: PROJECT.document_versions, dataset_sha256: PROJECT.dataset_sha256,
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

  // Same run ID: comparison quotes the run's own DEV-01 sources, and the stored core record sits under it.
  await openArea(page, '콘셉트 검토');
  const record = page.getByRole('region', { name: '판단 실행 기록' });
  await expect(record).toContainText(SECOND.run.id);
  await expect(record).toContainText('실제 모델 실행 기록(저장된 결과)');
  await expect(record).toContainText('qwen3:8b');
  await expect(record).toContainText('자동 세척 장치 제안');
  await expect(record).toContainText('계약 검사 통과 · 의미 미검증');
  await expect(record).toContainText('자동 세척 모드 추가');
  await expect(page.locator('.comparison-table')).not.toContainText('원문을 찾을 수 없습니다');
  await expect(page.locator('.comparison-table')).toContainText(SECOND.output.needs[0].pain);
  if (process.env.LGAX_E2E_SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.LGAX_E2E_SCREENSHOT_DIR}/live-results-concepts.png`, fullPage: true });

  // Export the recorded run with its lineage and the sources the judgement saw.
  await expect(page.locator('.export-check').first()).toHaveText('내보내기 점검: 누락 없음');
  const [download] = await Promise.all([page.waitForEvent('download'), page.locator('.export-actions').first().getByRole('button', { name: 'JSON' }).click()]);
  const exported = JSON.parse(readFileSync(await download.path(), 'utf8'));
  expect(exported.completeness.complete).toBe(true);
  expect(exported.lineage.map((item: { run_id: string }) => item.run_id)).toEqual([FIRST.run.id, SECOND.run.id]);
  expect(exported.concepts).toEqual(SECOND.run.concepts);
  expect(exported.evidence.map((item: { id: string }) => item.id).sort()).toEqual([...new Set(SECOND.run.concepts.flatMap((item: { evidence_ids: string[] }) => item.evidence_ids)
    .concat(SECOND.output.needs.flatMap((item: { evidence_ids: string[] }) => item.evidence_ids), SECOND.output.gaps.flatMap((item: { evidence_ids: string[] }) => item.evidence_ids)))].sort());

  // Exclude the candidate that conflicts with the exclusion → a new run request linked to the stored run.
  await openArea(page, '수정 이력');
  await expect(page.getByRole('region', { name: '판단 실행 기록' })).toContainText(SECOND.run.id);
  const rerun = page.getByRole('form', { name: '후보·조건 선택 후 재실행' });
  await rerun.getByRole('radiogroup', { name: '자동 세척 모드 추가 처리' }).getByText('제외').click();
  await rerun.getByRole('button', { name: '다시 실행 요청' }).click();
  await expect(page.locator('.timeline li')).toHaveCount(3);
  await expect(page.locator('.timeline li').last()).toContainText('요청만 저장됨');
  expect(posted).toHaveLength(1);
  expect(posted[0].previous_run_id).toBe(SECOND.run.id);
  expect((posted[0].request as { exclusions: string[] }).exclusions).toContain(`후보 제외: 자동 세척 모드 추가 (${SECOND.run.concepts.find((item: { title: string }) => item.title === '자동 세척 모드 추가').id})`);

  // The stored runs are unchanged and still show their own record.
  expect(runs[0]).toEqual(FIRST);
  expect(runs[1]).toEqual(SECOND);
  await page.locator('.timeline').getByRole('button', { name: new RegExp(`^${SECOND.run.id}`) }).click();
  await expect(page.getByRole('region', { name: '판단 실행 기록' })).toContainText('모델 호출5회');
  await page.locator('.timeline').getByRole('button', { name: /run-replay-request-only/ }).click();
  await expect(page.getByRole('region', { name: '판단 실행 기록' })).toHaveCount(0);
});
