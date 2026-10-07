import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Download, Page } from '@playwright/test';
import { requireLiveModelProof } from './live-model-proof';

// PM-20261005-WEB-003-TERMINAL-UX, opt-in browser run against a REAL planning-enabled workspace server: the browser
// itself saves a request, the server runs the judgement (PlanningAgent with the server's own model settings), and the
// same run ID is reviewed, exported (actual downloaded files) and rerun — with a candidate excluded when the judgement
// was accepted, or a corrected condition when it was held/failed. It records what happened and never asserts that the
// model produced a good or accepted result. Skipped unless LGAX_E2E_PLANNING_TOKEN_FILE is set.
//
//   uv run python -m lgax_api.server --host 127.0.0.1 --port 18867
//   uv run python -m lgax_api.workspace_server --db <db> --credentials <server-credentials.json> --port 18879 --enable-planning
//     (LGAX_MODEL_* set for that server; no --dataset, so the browser bootstrap and the judged data are the same)
//   LGAX_WORKSPACE_PROXY=http://127.0.0.1:18879 LGAX_E2E_PLANNING_TOKEN_FILE=<editor-client.json> \
//     LGAX_E2E_PLANNING_PROOF_DIR=<dir> npx playwright test e2e/real-planning.spec.ts
// Optional: LGAX_E2E_PLANNING_MODEL (default FRIDGE-A), LGAX_E2E_PLANNING_TIMEOUT_MS (default 20 minutes per step).
// Set LGAX_E2E_REQUIRE_LIVE_MODEL=1 plus LGAX_E2E_EXPECTED_MODEL_ID / LGAX_E2E_EXPECTED_MODEL_DIGEST for a strict
// real-generation gate: missing credentials, zero calls, fixtures or incorrect model metadata fail instead of passing.
// Stop any other dev server on 5173 first; Playwright reuses an existing one, which may proxy to another workspace.
const tokenFile = process.env.LGAX_E2E_PLANNING_TOKEN_FILE;
const proofDir = process.env.LGAX_E2E_PLANNING_PROOF_DIR;
const model = process.env.LGAX_E2E_PLANNING_MODEL ?? 'FRIDGE-A';
// Per-product inputs for the three demo scenarios (data/demo/planning_requests.json). Any other model keeps the fridge
// wording and must already be in the default product group.
const SCENARIO_INPUTS: Record<string, { group: string | null; situation: string; condition: string }> = {
  'DISHWASHER-A': { group: '식기세척기', situation: '큰 접시와 냄비를 함께 넣을 때 어디에 둘지 몰라 다시 꺼내 배치함', condition: '적재 안내 서비스만 검토' },
  'MICROWAVE-A': { group: '전자레인지', situation: '매일 같은 데우기 설정을 반복해서 다시 입력함', condition: '기존 설정 저장 기능과 겹치는 안은 제외' },
};
const inputs = SCENARIO_INPUTS[model] ?? { group: null, situation: '작은 오염도 선반 전체를 꺼내 청소해야 함', condition: '분리형 선반 구조만 검토' };
const stepTimeout = Number(process.env.LGAX_E2E_PLANNING_TIMEOUT_MS ?? 20 * 60_000);
const requireGeneration = process.env.LGAX_E2E_REQUIRE_LIVE_MODEL === '1';
const expectedModelId = process.env.LGAX_E2E_EXPECTED_MODEL_ID;
const expectedModelDigest = process.env.LGAX_E2E_EXPECTED_MODEL_DIGEST;

interface StoredRun { run: { id: string; status: string; concepts: { id: string; title: string }[] }; previous_run_id: string | null; request_revision: number; request: { exclusions: string[] }; output: Record<string, unknown> | null }
type Execution = { execution_kind: string; status: string; decision: { action: string } | null; model_calls: { model_id: string; model_digest: string }[]; errors: { code: string }[] } | undefined;

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}
const readDownload = async (download: Download) => readFileSync(await download.path(), 'utf8');
const summary = (stored: StoredRun) => {
  const record = stored.output?.planning_execution as Execution;
  return {
    run_id: stored.run.id, previous_run_id: stored.previous_run_id, request_revision: stored.request_revision, run_status: stored.run.status,
    candidates: stored.run.concepts.length, execution_kind: record?.execution_kind ?? null, decision: record?.decision?.action ?? null,
    model_calls: record?.model_calls.length ?? 0, models: [...new Set(record?.model_calls.map(call => `${call.model_id}@${call.model_digest.slice(0, 12)}`) ?? [])],
    errors: record?.errors.map(item => item.code) ?? [],
  };
};

test('real planning server: browser-initiated run → same run ID review → downloaded exports → rerun, previous run unchanged', async ({ page }) => {
  if (requireGeneration) {
    expect(tokenFile, 'Strict live-model verification requires workspace credentials').toBeTruthy();
    expect(expectedModelId, 'Strict live-model verification requires an expected model ID').toBeTruthy();
    expect(expectedModelDigest, 'Strict live-model verification requires an expected model digest').toMatch(/^[0-9a-f]{64}$/);
  }
  test.skip(!tokenFile, 'LGAX_E2E_PLANNING_TOKEN_FILE not set; the real planning flow is opt-in');
  test.setTimeout(stepTimeout * 3);
  const token = (JSON.parse(readFileSync(tokenFile!, 'utf8')) as { token: string }).token;
  const proof: Record<string, unknown> = { kind: 'browser_initiated_real_planning', started_at: new Date().toISOString(), model_id: model, quality_asserted: false, live_model_required: requireGeneration };
  try { proof.web_commit = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(); } catch { proof.web_commit = null; }
  const fetchRun = async (id: string) => {
    const response = await page.request.get(`/api/workspace/runs/${id}`, { headers: { authorization: `Bearer ${token}` } });
    expect(response.ok()).toBe(true);
    return (await response.json()).data as StoredRun;
  };
  const save = () => { if (proofDir) { mkdirSync(proofDir, { recursive: true }); writeFileSync(join(proofDir, 'real-planning-proof.json'), `${JSON.stringify(proof, null, 2)}\n`); } };

  try {
    await page.goto('/');
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: '근거 대조' }).click();
    await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
    await page.getByLabel('작업실 토큰').fill(token);
    await page.getByRole('button', { name: '연결', exact: true }).click();
    await expect(page.locator('.workspace-state')).toContainText('연결됨');

    // 1. The browser saves a new request; the server runs the judgement before answering.
    if (inputs.group) {
      const card = page.getByRole('region', { name: '제품군 선택' }).getByRole('button', { name: new RegExp(inputs.group) });
      await card.click();
      await expect(card).toHaveAttribute('aria-pressed', 'true');
    }
    await openArea(page, '기획 요청');
    await page.getByRole('checkbox', { name: new RegExp(model) }).check();
    await page.getByLabel('사용 상황').fill(`E2E ${new Date().toISOString()} ${inputs.situation}`);
    await page.getByRole('button', { name: /새 프로젝트로 저장|변경 요청 저장/ }).click();
    const message = page.locator('.request-form .inline-message');
    // The message also names the previous run ("이전 실행 run-…") when the request continues a project; take the new one.
    await expect(message).toContainText(/실행 run-[0-9a-f]+ · 요청 회차/, { timeout: stepTimeout });
    const firstId = (await message.textContent())!.match(/실행 (run-[0-9a-f]+) · 요청 회차/)![1];
    const first = await fetchRun(firstId);
    proof.first = summary(first);
    if (requireGeneration) proof.first_verified_model_calls = requireLiveModelProof(first.output?.planning_execution, expectedModelId, expectedModelDigest);
    proof.save_heading = await message.locator('strong').textContent();
    // A run that the server judged must not be announced as "request only".
    if (first.run.status !== 'not_implemented') await expect(message).not.toContainText('분석 결과 아님');

    // 2. Same run ID on the review screen, with the stored core record.
    await openArea(page, '콘셉트 검토');
    const record = page.getByRole('region', { name: '판단 실행 기록' });
    await expect(record).toContainText(firstId);
    if (proofDir) await page.screenshot({ path: join(proofDir, 'real-planning-first.png'), fullPage: true });

    // 3. Actual downloaded files carry the judgement and the full original record of this run.
    const exportActions = page.locator('.export-actions').first();
    const [jsonDownload] = await Promise.all([page.waitForEvent('download'), exportActions.getByRole('button', { name: 'JSON' }).click()]);
    const exported = JSON.parse(await readDownload(jsonDownload));
    expect(exported.meta.run_id).toBe(firstId);
    expect(exported.execution_record).toEqual(first.output?.planning_execution ?? null);
    const [mdDownload] = await Promise.all([page.waitForEvent('download'), exportActions.getByRole('button', { name: '문서(Markdown)' }).click()]);
    const markdown = await readDownload(mdDownload);
    if (first.output?.planning_execution) expect(markdown).toContain('## 판단 실행 기록');
    proof.export = { json_complete: exported.completeness.complete, json_has_execution_record: exported.execution_record !== null, markdown_has_judgement: markdown.includes('## 판단 실행 기록') };
    if (proofDir) { writeFileSync(join(proofDir, 'first-export.json'), JSON.stringify(exported, null, 2)); writeFileSync(join(proofDir, 'first-export.md'), markdown); }

    // 4. Rerun from it: exclude a candidate when the judgement offered some, otherwise correct a condition.
    await openArea(page, '수정 이력');
    const rerun = page.getByRole('form', { name: '후보·조건 선택 후 재실행' });
    const groups = rerun.getByRole('radiogroup');
    const before = await page.locator('.timeline > li').count();
    if (await groups.count()) {
      proof.rerun_kind = 'candidate_exclude';
      await groups.first().getByText('제외').click();
    } else {
      proof.rerun_kind = 'condition';
      // Unique per run: a condition already in a continued project's request is refused as a duplicate.
      await rerun.getByLabel('추가 조건').fill(`${inputs.condition} (E2E ${Date.now()})`);
      await rerun.getByRole('button', { name: '조건 추가' }).click();
    }
    await rerun.getByRole('button', { name: '다시 실행 요청' }).click();
    await expect(page.locator('.timeline > li')).toHaveCount(before + 1, { timeout: stepTimeout });
    const secondId = (await page.locator('.timeline > li').last().textContent())!.match(/run-[0-9a-f]+/)![0];
    const second = await fetchRun(secondId);
    proof.second = summary(second);
    if (requireGeneration) proof.second_verified_model_calls = requireLiveModelProof(second.output?.planning_execution, expectedModelId, expectedModelDigest);
    expect(second.previous_run_id).toBe(firstId);
    expect(second.request_revision).toBe(first.request_revision + 1);
    await expect(page.getByRole('region', { name: '판단 실행 기록' })).toContainText(secondId);
    if (proofDir) await page.screenshot({ path: join(proofDir, 'real-planning-second.png'), fullPage: true });

    // 5. The first run is stored exactly as before.
    const again = await fetchRun(firstId);
    proof.first_run_unchanged = JSON.stringify(again) === JSON.stringify(first);
    expect(again).toEqual(first);
    proof.result = 'flow_completed';
  } catch (error) {
    proof.result = 'flow_failed';
    proof.failure = String(error).slice(0, 2000);
    throw error;
  } finally {
    proof.finished_at = new Date().toISOString();
    save();
  }
});
