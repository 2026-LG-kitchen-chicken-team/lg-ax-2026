// Synthetic counterexample to PR179's display claim, not a fresh model/transport run. The immutable 8B recording is
// used only for a valid input/output shape. A final correction can fail after CorrectionBudget.claim closed the budget.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { FIXTURE_RUNS } from './fixtures/planning.fixture';
import { exportJudgement, planningExecutionView, terminalReason } from './judgement';
import type { PlanningExecution } from './judgement';
import { runStatusView } from './liveWorkspace';
import { buildExport, exportMarkdown } from './planning';
import type { RunSnapshot } from './planning';

const recorded: PlanningExecution = JSON.parse(readFileSync(new URL(
  '../../../evals/pm-prototype/20261006/finite-model-study/8b-bounded12/fridge-normal.json', import.meta.url,
), 'utf8'));

function finalCorrectionConnectionFailure(): RunSnapshot {
  const execution = structuredClone(recorded);
  execution.execution_kind = 'fixture';
  execution.decision = null;
  execution.trace = [];
  execution.model_calls = [];
  execution.errors = [{ code: 'MODEL_UNAVAILABLE', message: '최종 수정의 모델 연결 실패(합성 반례)' }];
  delete execution.rejected_output;
  delete execution.semantic_reviews;
  const output = execution.output!;
  const base = structuredClone(FIXTURE_RUNS[0]);
  return {
    ...base,
    actor_id: 'pm-counterexample-fixture',
    request: execution.original_input.request,
    document_versions: { [execution.input.product.model_id]: execution.input.product.document_version },
    run: {
      ...base.run, status: 'failed', stage: 'finished', revision_count: 2, concepts: [],
      unresolved: [execution.errors[0].message], events: [],
    },
    output: { needs: output.needs, gaps: output.gaps, planning_execution: execution } as RunSnapshot['output'],
  };
}

describe('a closed correction budget does not rule out execution errors', () => {
  it('keeps the limit and failure tone without asserting the failure was only remaining violations', () => {
    const snapshot = finalCorrectionConnectionFailure();
    const record = planningExecutionView(snapshot);
    expect(record.kind).toBe('ok');
    expect(terminalReason(snapshot)).toBe('revision_limit');
    const view = runStatusView(snapshot.run.status, terminalReason(snapshot));
    expect(view.tone).toBe('error');
    expect(view.detail).toContain('내부 수정 한도(2회)');
    expect(view.detail).not.toContain('실행 오류가 아닙니다');
    expect(view.detail).not.toContain('검사 위반이 남아');
  });

  it('exports the recorded connection error alongside the budget limit without denying that error', () => {
    const snapshot = finalCorrectionConnectionFailure();
    const judgement = exportJudgement(snapshot)!;
    expect(judgement.record_valid).toBe(true);
    const doc = buildExport('fixture', snapshot, [], [], '2026-10-06T10:00:00.000Z');
    const markdown = exportMarkdown(doc);
    expect(markdown).toContain('내부 수정 한도 도달');
    expect(markdown).toContain('MODEL_UNAVAILABLE: 최종 수정의 모델 연결 실패(합성 반례)');
    expect(markdown).not.toContain('실행 오류 아님');
    expect(markdown).not.toContain('검사 위반이 남음');
  });
});
