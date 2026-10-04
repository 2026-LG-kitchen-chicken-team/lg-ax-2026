// @vitest-environment jsdom
// Stored-run records produced by the real core pipeline with a mocked model
// (evals/web/20261005/p2-web-003-core-records/generate.py): main's PlanningAgent for failure/hold/revise paths the PM
// live record does not contain, and PR #60's draft semantic review as a preview. Model answers are the core tests'
// authored fixtures, so these show how the web reads what the core stores, not what a model would answer.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { judgementDecisionErrors, planningExecutionView, runSources, violationText } from './judgement';
import type { PlanningExecution } from './judgement';
import { ConceptsView } from './PlanningViews';
import { contractErrors } from './planning';
import type { RunSnapshot } from './planning';

const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), '../..', path), 'utf-8'));
const MAIN = read('evals/web/20261005/p2-web-003-core-records/main-core.json');
const PR60 = read('evals/web/20261005/p2-web-003-core-records/pr60-semantic-preview.json');
const run = (set: { runs: Record<string, RunSnapshot> }, name: string) => set.runs[name];
const execution = (snapshot: RunSnapshot) => (snapshot.output as unknown as { planning_execution: PlanningExecution }).planning_execution;
const ok = (snapshot: RunSnapshot) => {
  const view = planningExecutionView(snapshot);
  if (view.kind !== 'ok') throw new Error(JSON.stringify(view));
  return view;
};
const MISSING_NEXT = '코어 결정에 next_revision_count가 없습니다. 웹은 값을 채우지 않고 revision_count만 표시합니다.';

describe('core pipeline records (mocked model) are read, not rejected', () => {
  it('are stored-run contract snapshots from the core this branch is based on', () => {
    expect(MAIN.execution_kind).toBe('core_pipeline_with_mocked_model');
    for (const set of [MAIN, PR60]) for (const snapshot of Object.values(set.runs) as RunSnapshot[]) {
      expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
      expect(execution(snapshot).execution_kind).toBe('fixture');
    }
  });

  it('main: a stage that keeps failing stores a decision without next_revision_count; shown with its problems', () => {
    const snapshot = run(MAIN, 'generation_failed');
    const decision = execution(snapshot).decision!;
    expect(decision.next_revision_count).toBeUndefined();
    expect(decision.violations[0].details).toEqual({ reason: 'invalid_json' });
    // The strict CORE-001 check still rejects it; only the stored-record reader tolerates and reports the gap.
    expect(judgementDecisionErrors(decision)).not.toEqual([]);
    const view = ok(snapshot);
    expect(view.execution.output).toBeNull();
    expect(view.problems).toEqual(['코어 결정이 unresolved로 끝났는데 재실행 단계(rerun_from=needs)가 남아 있습니다.', MISSING_NEXT]);
  });

  it('main: turned-down candidates stay in rejected_output and the terminal output has none', () => {
    const view = ok(run(MAIN, 'duplicate_unresolved'));
    expect(view.problems).toEqual([]);
    expect(view.execution.output!.concepts).toEqual([]);
    expect(view.execution.rejected_output!.concepts.length).toBeGreaterThan(0);
    expect(run(MAIN, 'duplicate_unresolved').run.concepts).toEqual([]);
  });

  it.each([['positive_held', 'hold'], ['need_reference_revised', 'accept']] as const)('main: %s reads cleanly (%s)', (name, action) => {
    const view = ok(run(MAIN, name));
    expect(view.problems).toEqual([]);
    expect(view.execution.decision!.action).toBe(action);
  });

  it('PR #60 preview: semantic reviews and their violation details are readable', () => {
    const accepted = ok(run(PR60, 'semantic_accept'));
    expect(accepted.problems).toEqual([]);
    expect(accepted.execution.semantic_reviews).toHaveLength(1);
    const violated = ok(run(PR60, 'exclusion_violation_unresolved'));
    expect(violated.problems).toEqual([]);
    expect(violated.execution.semantic_reviews).toHaveLength(3);
    expect(violationText(violated.execution.decision!.violations[0])).toBe(
      "의미 검토: 후보가 제외 조건을 어겼습니다 (EXCLUSION_VIOLATION · concepts 단계) · 후보 DEV-01-CONCEPT × 제외 조건 '다른 모델 기능 혼용': 위반 · 후보 인용 '오염 구역만 분리하는 소형 트레이' — 테스트가 작성한 검토 선언: violation");
    const invalid = ok(run(PR60, 'semantic_review_invalid'));
    expect(invalid.problems).toContain(MISSING_NEXT);
    expect(invalid.execution.decision!.violations[0].code).toBe('INVALID_SEMANTIC_REVIEW');
  });

  it('a malformed semantic review is reported as an invalid record', () => {
    const copy = structuredClone(run(PR60, 'semantic_accept'));
    (execution(copy).semantic_reviews![0].report as unknown as Record<string, unknown>).exclusion_assessments = 'none';
    const view = planningExecutionView(copy);
    expect(view.kind === 'invalid' && view.errors).toContain('/semantic_reviews/0/report/exclusion_assessments must be an array');
  });
});

describe('core pipeline records in the actual React DOM', () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });
  async function panel(snapshot: RunSnapshot) {
    const scoped = runSources(snapshot, [], []);
    await act(async () => root.render(createElement(ConceptsView, { mode: 'live', runs: [snapshot], selected: snapshot, onSelect: () => {}, features: scoped.features, evidence: scoped.evidence })));
    expect(host.querySelectorAll('.concept-card')).toHaveLength(snapshot.run.concepts.length);
    return host.querySelector('[aria-label="판단 실행 기록"]')?.textContent ?? '';
  }

  it('failed stage: the decision and its reason are shown although no output was stored', async () => {
    const text = await panel(run(MAIN, 'generation_failed'));
    expect(text).not.toContain('형식이 맞지 않아 표시하지 않습니다');
    expect(text).toContain('미해결 종료');
    expect(text).toContain('모델 응답이 단계 규격에 맞지 않습니다 (VALIDATION_FAILED · needs 단계) · 사유: invalid_json');
    expect(text).toContain(MISSING_NEXT);
    expect(text).toContain('판단 출력이 저장되지 않았습니다(실패)');
  });

  it('turned-down candidates are listed as rejected, not offered', async () => {
    const snapshot = run(MAIN, 'duplicate_unresolved');
    const text = await panel(snapshot);
    expect(text).toContain('검사에서 거절된 마지막 후보');
    for (const concept of execution(snapshot).rejected_output!.concepts) expect(text).toContain(concept.title);
    expect(text).toContain('후보가 기존 기능과 중복됩니다');
  });

  it('PR #60 preview: exclusion rows, semantic hold text and the self-review caveat', async () => {
    const held = await panel(run(PR60, 'exclusion_uncertain_held'));
    expect(held).toContain('의미 검토에서 제외 조건·기획 기준 준수가 불확실하거나 확인할 질문이 남아 후보를 보류했습니다');
    expect(held).toContain("× 제외 조건 '다른 모델 기능 혼용'");
    expect(held).toContain('불확실');
    expect(held).toContain('후보가 기존 부품만으로 동작하는지 확인할 수 있나요?');
    expect(held).toContain('작성된 fixture 응답');
    const violated = await panel(run(PR60, 'exclusion_violation_unresolved'));
    expect(violated).toContain('의미 검토 3회');
    expect(violated).toContain('의미 검토: 후보가 제외 조건을 어겼습니다');
    const accepted = await panel(run(PR60, 'semantic_accept'));
    expect(accepted).toContain('같은 모델의 자기 검토입니다');
    expect(accepted).toContain('기획 품질 기준 4건 중 충족 선언 4건');
  });
});
