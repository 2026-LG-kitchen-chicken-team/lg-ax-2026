// @vitest-environment jsdom
// PM-20261005-WEB-003-TERMINAL-UX: the two runs PM stored on 10/5 through the real TypeScript client → authenticated
// workspace API → Qwen3:8B → storage (evals/pm-review/20261005-round2/api-live/workspace-live.json), replayed as data.
// Both ended held after a semantic review; the second is the changed-condition rerun (request revision 1, two internal
// revisions). No model is called here and nothing in the record is rewritten.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { exportJudgement, planningExecutionView, reasonText, rerunBaseNotice, runSources, selectableConcepts, violationText } from './judgement';
import type { PlanningExecution } from './judgement';
import { ConceptsView, HistoryView, outcomeChanges, outcomeOf } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import { buildExport, contractErrors, exportCompleteness, exportMarkdown, storedExecution } from './planning';
import type { PlanningRequest, RunSnapshot } from './planning';

const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), '../..', path), 'utf-8'));
const RECORD = read('evals/pm-review/20261005-round2/api-live/workspace-live.json');
const FIRST: RunSnapshot = RECORD.first;
const SECOND: RunSnapshot = RECORD.second;
const RUNS = [FIRST, SECOND];
const execution = (snapshot: RunSnapshot) => (snapshot.output as unknown as { planning_execution: PlanningExecution }).planning_execution;
const ok = (snapshot: RunSnapshot) => {
  const view = planningExecutionView(snapshot);
  if (view.kind !== 'ok') throw new Error(JSON.stringify(view));
  return view;
};
const exportOf = (snapshot: RunSnapshot) => {
  const scoped = runSources(snapshot, [], []);
  return { scoped, doc: buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-05T04:00:00.000Z', RUNS) };
};

describe('round2 live runs (PM, Qwen3:8B, real API and storage) read as stored', () => {
  it('are stored-run snapshots linked as first run and changed-condition rerun, both held', () => {
    expect(RECORD.execution_kind).toBe('live_model');
    expect(RECORD.first_run_unchanged).toBe(true);
    expect(RECORD.agent_quality_passed).toBeNull();
    for (const snapshot of RUNS) expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
    expect(SECOND.previous_run_id).toBe(FIRST.run.id);
    expect([FIRST.request_revision, SECOND.request_revision]).toEqual([0, 1]);
    expect(SECOND.request.exclusions).toEqual([...FIRST.request.exclusions, '자동 세척 장치 제안']);
    for (const snapshot of RUNS) expect([snapshot.run.status, execution(snapshot).status, execution(snapshot).decision!.action]).toEqual(['held', 'held', 'hold']);
  });

  it.each([['first', FIRST, 0, 4], ['changed', SECOND, 2, 6]] as const)('%s run: record reads cleanly under the same run ID', (_name, snapshot, revisions, calls) => {
    const view = ok(snapshot);
    expect(view.problems).toEqual([]);
    expect(view.execution.execution_kind).toBe('live_model');
    expect(view.execution.input.revision_count).toBe(revisions);
    expect(view.model_calls).toBe(calls);
    expect(view.models.every(item => item.startsWith('qwen3:8b · '))).toBe(true);
    expect(view.execution.original_input.request).toEqual(snapshot.request);
    expect(view.execution.semantic_reviews).toHaveLength(1);
    expect(view.execution.rejected_output!.concepts).toHaveLength(3);
    expect(snapshot.run.concepts).toEqual([]);
  });

  it('held runs offer no candidates; a rerun is a new judgement request', () => {
    for (const snapshot of RUNS) {
      expect(selectableConcepts(snapshot)).toEqual([]);
      expect(rerunBaseNotice(snapshot)).toContain('보류로 끝나 채택된 후보가 없습니다');
    }
  });

  it.each([['first', FIRST], ['changed', SECOND]] as const)('%s run: export keeps the summary, the terminal reasons and the full original record', (_name, snapshot) => {
    const { scoped, doc } = exportOf(snapshot);
    expect(doc.completeness.complete).toBe(true);
    expect(doc.lineage.map(item => item.run_id)).toEqual(RUNS.slice(0, RUNS.indexOf(snapshot) + 1).map(item => item.run.id));
    expect(doc.concepts).toEqual([]);
    const judgement = doc.judgement!;
    if (!judgement.record_valid) throw new Error('expected a valid record');
    const record = execution(snapshot);
    expect(judgement.decision).toBe('hold');
    expect(judgement.violations).toEqual(record.decision!.violations.map(violationText));
    for (const question of record.semantic_reviews![0].report.questions) expect(judgement.questions).toContain(question);
    expect(judgement.hold_reasons).toEqual(record.output!.hold_reasons);
    expect(judgement.rejected_candidates.map(item => item.title)).toEqual(record.rejected_output!.concepts.map(item => item.title));
    expect(judgement.semantic_rows).toHaveLength(record.semantic_reviews![0].report.exclusion_assessments.length + record.semantic_reviews![0].report.quality_assessments.length);
    // The raw record (prompts, raw completions, reviewed originals) is exported as stored.
    expect(doc.execution_record).toEqual(record);
    expect(JSON.parse(JSON.stringify(doc)).execution_record).toEqual(record);
    const markdown = exportMarkdown(doc);
    for (const item of [...judgement.questions, ...judgement.hold_reasons, ...judgement.no_candidate_reasons]) expect(markdown).toContain(item);
    for (const item of judgement.rejected_candidates) expect(markdown).toContain(item.title);
    expect(markdown).toContain('`execution_record`');
    // Dropping or editing the original record is caught.
    const trimmed = { ...doc, execution_record: { ...(doc.execution_record as object), model_calls: [] } };
    expect(exportCompleteness(trimmed, snapshot, scoped.features, scoped.evidence, RUNS).mismatched_fields).toEqual(['원 실행 기록']);
  });

  it.each([['first', FIRST], ['changed', SECOND]] as const)('%s run: the stored reasons and questions are non-empty and outcomeOf reports exactly them', (_name, snapshot) => {
    const record = execution(snapshot);
    // Expectations come from the raw fixture, not from outcomeOf/exportJudgement. A fixture that lost them must fail here.
    const holdReasons = record.output!.hold_reasons;
    const questions = record.semantic_reviews![0].report.questions;
    expect(holdReasons.length).toBeGreaterThan(0);
    expect(questions.length).toBeGreaterThan(0);
    expect(record.rejected_output!.concepts.length).toBeGreaterThan(0);
    const outcome = outcomeOf(snapshot);
    expect(outcome.decision).toBe('hold');
    for (const reason of holdReasons) expect(outcome.groups.reasons).toContain(reasonText(reason));
    for (const question of questions) expect(outcome.groups.questions).toContain(question);
    expect(outcome.groups.rejected).toEqual(record.rejected_output!.concepts.map(item => `${item.id} ${item.title}`));
    expect(outcome.groups.violations).toEqual(record.decision!.violations.map(violationText));
  });

  it('dropping the stored reasons or questions from the record is detected', () => {
    const record = execution(SECOND);
    const stripped = structuredClone(SECOND);
    const copy = execution(stripped);
    copy.output!.hold_reasons = [];
    copy.output!.unresolved = [];
    copy.semantic_reviews![0].report.questions = [];
    const outcome = outcomeOf(stripped);
    for (const reason of record.output!.hold_reasons) expect(outcome.groups.reasons).not.toContain(reasonText(reason));
    for (const question of record.semantic_reviews![0].report.questions) expect(outcome.groups.questions).not.toContain(question);
    // The comparison then reports them as gone from this run instead of silently matching.
    const rows = outcomeChanges(FIRST, stripped);
    expect(rows.find(row => row.key === 'questions')!.resolved.length + rows.find(row => row.key === 'reasons')!.resolved.length).toBeGreaterThan(0);
  });

  it('failed run with no core record falls back to the run\'s own stored unresolved items and gap questions', () => {
    const failed = structuredClone(FIRST);
    failed.run.status = 'failed';
    failed.run.unresolved = ['모델 응답을 받지 못했습니다'];
    failed.output = {
      needs: [{ id: 'NEED-X', pain: '손잡이 불편' }],
      gaps: [{ id: 'GAP-X', need_id: 'NEED-X', support_status: 'insufficient_evidence', feature_ids: [], questions: ['어떤 모델의 손잡이입니까?'] }],
      no_candidate_reasons: ['근거 부족'],
    } as unknown as RunSnapshot['output'];
    const outcome = outcomeOf(failed);
    expect(outcome.status).toBe('failed');
    expect(outcome.decision).toBeNull();
    expect(outcome.groups.questions).toEqual(['어떤 모델의 손잡이입니까?']);
    expect(outcome.groups.reasons).toEqual(['모델 응답을 받지 못했습니다', '근거 부족']);
    expect(outcome.groups.violations).toEqual([]);
    expect(outcome.groups.rejected).toEqual([]);
  });

  it('run with no stored output at all reports empty groups, not an invented result', () => {
    const empty = structuredClone(FIRST);
    empty.output = null;
    empty.run.unresolved = [];
    expect(outcomeOf(empty).groups).toEqual({ questions: [], reasons: [], violations: [], rejected: [] });
  });

  it('invalid core record is reported as record errors and never as a decision', () => {
    const broken = structuredClone(SECOND);
    (broken.output as unknown as { planning_execution: unknown }).planning_execution = { status: 'bogus' };
    const outcome = outcomeOf(broken);
    expect(outcome.decision).toBeNull();
    expect(outcome.groups.violations.length).toBeGreaterThan(0);
    expect(outcome.groups.violations).toContain('/status must be completed, held or failed');
    expect(outcome.groups.rejected).toEqual([]);
  });

  it('runs without a core record export no original record', () => {
    const plain = structuredClone(FIRST);
    plain.output = { needs: [], gaps: [] };
    expect(storedExecution(plain)).toBeNull();
    expect(exportJudgement(plain)).toBeNull();
    expect(buildExport('live', plain, [], [], '2026-10-05T04:00:00.000Z', [plain]).execution_record).toBeNull();
  });
});

describe('round2 live runs in the actual React DOM', () => {
  let host: HTMLDivElement;
  let root: Root;
  const onRerun = vi.fn<(request: PlanningRequest) => Promise<void>>().mockResolvedValue(undefined);
  const measure: MeasureControls = { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' };
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    onRerun.mockClear();
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });

  it.each([['first', FIRST], ['changed', SECOND]] as const)('%s run: held state, questions, semantic review and rejected candidates under its run ID', async (_name, snapshot) => {
    const scoped = runSources(snapshot, [], []);
    await act(async () => root.render(createElement(ConceptsView, { mode: 'live', runs: RUNS, selected: snapshot, onSelect: () => {}, ...scoped })));
    const text = host.querySelector('[aria-label="판단 실행 기록"]')?.textContent ?? '';
    const record = execution(snapshot);
    expect(text).toContain(snapshot.run.id);
    expect(text).toContain('실제 모델 실행 기록(저장된 결과)');
    expect(text).toContain('보류');
    expect(text).not.toContain('계약 검사 통과');
    for (const question of record.semantic_reviews![0].report.questions) expect(text).toContain(question);
    for (const concept of record.rejected_output!.concepts) expect(text).toContain(concept.title);
    expect(text).toContain('검사에서 거절된 마지막 후보');
    for (const row of record.semantic_reviews![0].report.exclusion_assessments) expect(text).toContain(row.reason);
    for (const exclusion of snapshot.request.exclusions) expect(text).toContain(exclusion);
    expect(host.querySelectorAll('.concept-card')).toHaveLength(0);
  });

  it('changed run: held reasons and questions are compared with the first run, both runs untouched', async () => {
    const before = structuredClone(RUNS);
    const firstRecord = execution(FIRST);
    const secondRecord = execution(SECOND);
    const secondQuestions = secondRecord.semantic_reviews![0].report.questions;
    expect(secondQuestions.length).toBeGreaterThan(0);
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'live', runs: RUNS, selected: SECOND, original: FIRST.request, onSelect: () => {}, ...runSources(SECOND, [], []), onRerun, measure,
    })));
    const panel = host.querySelector('[aria-label="이전 실행과 결과 비교"]');
    expect(panel?.textContent).toContain(`${FIRST.run.id} · held / hold`);
    expect(panel?.textContent).toContain(`${SECOND.run.id} · held / hold`);
    expect(panel?.textContent).toContain('이유가 사라졌다고 해서 문제가 해결됐다는 뜻은 아니며');
    expect(panel?.querySelectorAll('[data-outcome]')).toHaveLength(4);
    for (const question of secondQuestions) expect(panel?.textContent).toContain(question);
    for (const reason of secondRecord.output!.hold_reasons) expect(panel?.textContent).toContain(reasonText(reason));
    // A reason or question held in the first run appears in the panel as kept or as absent from this run; nothing is dropped.
    for (const reason of firstRecord.output!.hold_reasons) expect(panel?.textContent).toContain(reasonText(reason));
    expect(RUNS).toEqual(before);
  });

  it('first run has no earlier run to compare', async () => {
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'live', runs: RUNS, selected: FIRST, original: FIRST.request, onSelect: () => {}, ...runSources(FIRST, [], []), onRerun, measure,
    })));
    expect(host.querySelector('[aria-label="이전 실행과 결과 비교"]')).toBeNull();
    expect(host.textContent).toContain('이전 실행이 없어 비교하지 않습니다');
  });

  it('changed run: only conditions can be corrected; the new request links to it and stored runs stay unchanged', async () => {
    const before = structuredClone(RUNS);
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'live', runs: RUNS, selected: SECOND, original: FIRST.request, onSelect: () => {}, ...runSources(SECOND, [], []), onRerun, measure,
    })));
    const form = host.querySelector('form[aria-label="후보·조건 선택 후 재실행"]') as HTMLFormElement;
    expect(form.querySelectorAll('[role="radiogroup"]')).toHaveLength(0);
    expect(form.textContent).toContain('보류로 끝나 채택된 후보가 없습니다');
    const input = host.querySelector('#extra-condition') as HTMLInputElement;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '분리형 선반 구조만 검토');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => ([...form.querySelectorAll('button')].find(item => item.textContent === '조건 추가') as HTMLButtonElement).click());
    await act(async () => form.requestSubmit());
    expect(onRerun).toHaveBeenCalledTimes(1);
    expect(onRerun.mock.calls[0][0]).toEqual({ ...SECOND.request, exclusions: [...SECOND.request.exclusions, '분리형 선반 구조만 검토'] });
    expect(RUNS).toEqual(before);
  });
});
