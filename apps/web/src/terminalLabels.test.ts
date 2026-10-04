// A live run that stopped before calling the model (the server's failed_execution: decision null, no model calls) must
// not read as model output on screen or in exports. Derived from PM's round2 live record; labelled as a derived copy.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { executionKindText, runSources } from './judgement';
import { buildExport, exportMarkdown } from './planning';
import type { RunSnapshot } from './planning';

const RECORD = JSON.parse(readFileSync(resolve(process.cwd(), '../..', 'evals/pm-review/20261005-round2/api-live/workspace-live.json'), 'utf-8'));
const LIVE: RunSnapshot = RECORD.first;
const STOPPED = structuredClone(LIVE);
Object.assign((STOPPED.output as unknown as { planning_execution: Record<string, unknown> }).planning_execution, {
  status: 'failed', output: null, decision: null, model_calls: [], trace: [{ stage: 'review', operation: 'stop' }],
  errors: [{ code: 'MODEL_UNAVAILABLE', message: '판단 실행을 완료하지 못했습니다. 서버 실행 설정과 근거를 확인해 주세요.' }],
  rejected_output: undefined, semantic_reviews: undefined,
});
STOPPED.run = { ...STOPPED.run, status: 'failed' };

describe('execution kind wording', () => {
  it('names fixtures, model output and live runs stopped before any model call differently', () => {
    expect(executionKindText('fixture', 0)).toBe('fixture 실행 기록(모델 호출 아님)');
    expect(executionKindText('live_model', 4)).toBe('실제 모델 실행 기록(저장된 결과)');
    expect(executionKindText('live_model', 0)).toBe('실제 모델 경로 · 모델 호출 전에 중단');
  });

  it.each([['live with calls', LIVE, '실제 모델 실행 기록(저장된 결과)'], ['stopped before the model', STOPPED, '실제 모델 경로 · 모델 호출 전에 중단']] as const)('%s: export says so', (_name, snapshot, label) => {
    const scoped = runSources(snapshot, [], []);
    const markdown = exportMarkdown(buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-05T04:00:00.000Z', [snapshot]));
    expect(markdown).toContain(`- 실행 종류: ${label}`);
  });
});
