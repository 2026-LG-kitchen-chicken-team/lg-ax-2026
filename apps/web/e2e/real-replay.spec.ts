import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

// Record 최길웅-20261006-034: PM's real model-study runs (27B held ×2, 8B failed ×2) stored through the actual workspace
// HTTP API by evals/web/20261006/web-real-replay/tools/replay_model_study.py, then served read-only (no planning runner)
// behind LGAX_WORKSPACE_PROXY. Opt-in: skipped unless LGAX_E2E_REPLAY_TOKEN_FILE and LGAX_E2E_REPLAY_SUMMARY are set.
// Only GETs are made, so a separate test Vite (LGAX_E2E_PORT) works without the user's 5173. No model is called.
const tokenFile = process.env.LGAX_E2E_REPLAY_TOKEN_FILE;
const summaryFile = process.env.LGAX_E2E_REPLAY_SUMMARY;
const proofDir = process.env.LGAX_E2E_REPLAY_PROOF_DIR;

interface Row { case: string; project_id: string; run_id: string; recorded_status: 'held' | 'failed'; historical_model_calls: number }

async function openArea(page: Page, label: string) {
  await page.getByRole('navigation', { name: '기획 작업 영역' }).getByRole('button', { name: label }).click();
}

test('real held/failed runs from the workspace server never read as accepted or successful', async ({ page }) => {
  test.skip(!tokenFile || !summaryFile, 'LGAX_E2E_REPLAY_TOKEN_FILE / LGAX_E2E_REPLAY_SUMMARY not set');
  test.setTimeout(5 * 60_000);
  const token = (JSON.parse(readFileSync(tokenFile!, 'utf8')) as { token: string }).token;
  const rows = (JSON.parse(readFileSync(summaryFile!, 'utf8')) as { cases: Row[] }).cases;
  const proof: Record<string, unknown> = { kind: 'real_model_replay_web_leg', started_at: new Date().toISOString(), cases: [] as unknown[] };
  try {
    await page.goto('/');
    await expect(page.locator('.connection-status')).toContainText('공통 API 연결됨');
    await page.getByLabel('작업실 토큰').fill(token);
    await page.getByRole('button', { name: '연결', exact: true }).click();
    await expect(page.locator('.workspace-state')).toContainText('연결됨');
    for (const row of rows) {
      await page.getByRole('combobox', { name: '프로젝트' }).selectOption(row.project_id);
      await openArea(page, '콘셉트 검토');
      const record = page.getByRole('region', { name: '판단 실행 기록' });
      await expect(record).toContainText(row.run_id);
      await expect(record).toContainText('실제 모델 실행 기록(저장된 결과)');
      const head = record.locator('.planning-head .run-status');
      const headClass = await head.getAttribute('class') ?? '';
      expect(headClass).toContain(row.recorded_status === 'failed' ? 'error' : 'notice');
      expect(headClass).not.toContain('done');
      await expect(record).not.toContainText('계약 검사 통과');
      await expect(page.locator('.concept-card')).toHaveCount(0);
      const candidatesText = row.recorded_status === 'held' ? '채택된 후보가 없습니다. 모델이 만든 후보' : '생성된 후보가 없습니다.';
      await expect(page.getByText(candidatesText, { exact: false }).first()).toBeVisible();
      if (row.recorded_status === 'held') {
        await expect(record).toContainText('보류를 일으킨 문제(근거 확인 필요)');
        await expect(record).toContainText('함께 발견된 판단 오류(보류로 내부 수정하지 않음)');
      }
      // R4 U5 (record 043): reported usage, model vs whole-run time, both round counters and the scope notice.
      const field = async (name: string) => (await record.locator(`[data-field="${name}"]`).first().textContent()) ?? '';
      const usage = { model_calls: await field('model-calls'), tokens: await field('tokens'), run_time: await field('run-time'), settings: await field('settings'), rounds: await field('rounds') };
      expect(usage.model_calls).toMatch(/^\d+회 · 모델 시간 \d+\.\d초$/);
      expect(usage.tokens).toMatch(/^입력 [\d,]+ · 출력 [\d,]+ · 합 [\d,]+$/);
      expect(usage.rounds).toContain('Agent 내부 수정');
      await expect(record.getByRole('region', { name: '검증 범위' })).toContainText('의미 정확성 미검증');
      await expect(record.getByRole('region', { name: '모델 호출 기록' }).locator('[data-call]')).toHaveCount(row.historical_model_calls);
      const shot = `${row.case.replace('/', '--')}.png`;
      if (proofDir) { mkdirSync(proofDir, { recursive: true }); await page.screenshot({ path: join(proofDir, shot), fullPage: true }); }
      await openArea(page, '수정 이력');
      const timeline = page.locator('[data-revision-timeline]');
      const candidates = (await timeline.locator('[data-field="candidates"]').first().textContent()) ?? '';
      expect(candidates).toContain('첫 실행에서 채택된 후보가 없습니다(');
      expect(candidates).not.toContain('첫 실행의 후보입니다.');
      const statusTitle = (await timeline.locator('[data-field="run-status"]').first().getAttribute('title')) ?? '';
      if (row.recorded_status === 'failed') expect(statusTitle).toContain('내부 수정 한도(2회)');
      (proof.cases as unknown[]).push({ case: row.case, run_id: row.run_id, status: row.recorded_status, head_class: headClass, usage, timeline_candidates: candidates, status_title: statusTitle, screenshot: proofDir ? shot : null });
    }
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
