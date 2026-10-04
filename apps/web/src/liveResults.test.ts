// @vitest-environment jsdom
// PM-20261005-WEB-003-LIVE-RESULTS: the two runs PM stored through the real workspace API with Qwen3:8B
// (evals/pm-integration/20261005/workspace-live.json) are replayed here as data. No model is called and nothing in the
// record is rewritten; the held/failed/zero-candidate/broken variants below are derived copies, labelled as such.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ACCEPT_DETAIL, planningExecutionView, runSources } from './judgement';
import type { PlanningExecution } from './judgement';
import { ConceptsView, HistoryView } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import { buildComparison, buildExport, candidateExclusion, contractErrors, exportCompleteness, exportMarkdown } from './planning';
import type { PlanningRequest, RunSnapshot } from './planning';

// vitest runs from apps/web (npm test); repository files are read as plain data, not bundled.
const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), '../..', path), 'utf-8'));
const RECORD = read('evals/pm-integration/20261005/workspace-live.json');
const FIRST: RunSnapshot = RECORD.first;
const SECOND: RunSnapshot = RECORD.second;
const RUNS = [FIRST, SECOND];
const execution = (snapshot: RunSnapshot) => (snapshot.output as unknown as { planning_execution: PlanningExecution }).planning_execution;
const variant = (base: RunSnapshot, change: (copy: RunSnapshot, record: PlanningExecution) => void) => {
  const copy = structuredClone(base);
  change(copy, execution(copy));
  return copy;
};

// Derived copies of the first recorded run (not model output): the stored shapes for held, failed and zero-candidate runs.
const HELD = variant(FIRST, (copy, record) => {
  record.status = 'held';
  record.output!.status = 'held';
  record.output!.concepts = [];
  record.output!.concept_assessments = [];
  record.output!.questions = ['선반 일부만 분리할 수 있는 구조인지 설명서에서 확인할 수 있나요?'];
  record.output!.hold_reasons = ['리뷰 근거가 한 건뿐이라 후보를 보류합니다.'];
  record.decision = { valid: true, action: 'hold', revision_count: 0, next_revision_count: 0, rerun_from: null, violations: [] };
  copy.run.status = 'held';
  copy.run.stage = 'review';
  copy.run.concepts = [];
  copy.run.unresolved = ['리뷰 근거가 한 건뿐이라 후보를 보류합니다.'];
});
const FAILED = variant(FIRST, (copy, record) => {
  record.status = 'failed';
  record.rejected_execution = structuredClone(execution(FIRST));
  record.output = null;
  record.decision = null;
  record.model_calls = [];
  record.errors = [{ code: 'CONTRACT_MISMATCH', message: '판단 실행을 완료하지 못했습니다. 서버 실행 설정과 근거를 확인해 주세요.' }];
  record.trace = [{ stage: 'review', operation: 'stop' }];
  copy.run.status = 'failed';
  copy.run.stage = 'review';
  copy.run.concepts = [];
  copy.run.unresolved = ['판단이 보류되었거나 실패했습니다. 실행 내역을 확인해 주세요.'];
  copy.output = { needs: [], gaps: [], planning_execution: record } as unknown as RunSnapshot['output'];
});
const ZERO = variant(FIRST, (copy, record) => {
  record.output!.concepts = [];
  record.output!.concept_assessments = [];
  copy.run.concepts = [];
});

describe('recorded live workspace runs (PM, Qwen3:8B, replayed as data)', () => {
  it('are stored-run contract snapshots linked as first run and changed rerun', () => {
    for (const snapshot of RUNS) expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
    expect(RECORD.execution_kind).toBe('live_model');
    expect(RECORD.first_run_unchanged).toBe(true);
    expect(SECOND.previous_run_id).toBe(FIRST.run.id);
    expect(SECOND.request_revision).toBe(1);
    expect(SECOND.request.exclusions).toContain('자동 세척 장치 제안');
  });

  it.each([['first', FIRST, 3], ['changed', SECOND, 5]] as const)('%s run: the core record reads cleanly under the same run ID', (_name, snapshot, calls) => {
    const view = planningExecutionView(snapshot);
    if (view.kind !== 'ok') throw new Error(JSON.stringify(view));
    expect(view.problems).toEqual([]);
    expect(view.execution.execution_kind).toBe('live_model');
    expect(view.execution.decision!.action).toBe('accept');
    expect(view.model_calls).toBe(calls);
    expect(view.models.every(item => item.startsWith('qwen3:8b · '))).toBe(true);
    expect(view.execution.original_input.request).toEqual(snapshot.request);
    expect(view.execution.output!.concepts).toEqual(snapshot.run.concepts);
  });

  it('quotes the sources the judgement received, not the bootstrap dataset', () => {
    for (const snapshot of RUNS) {
      // The browser bootstrap (kitchen-demo) does not contain DEV-01: without the run's own input every source is missing.
      expect(buildComparison(snapshot.output!, [], []).flatMap(row => row.missingIds)).not.toEqual([]);
      const scoped = runSources(snapshot, [], []);
      for (const row of buildComparison(snapshot.output!, scoped.features, scoped.evidence)) {
        expect(row.missingIds).toEqual([]);
        expect(row.evidence.length).toBeGreaterThan(0);
      }
      expect(scoped.evidence.map(item => item.id)).toEqual(execution(snapshot).input.sources.map(item => item.id));
    }
    expect(runSources(undefined, [], [])).toEqual({ features: [], evidence: [] });
  });

  it('exports each run with its lineage, candidates and no-candidate reasons, and catches tampering', () => {
    const scoped = runSources(SECOND, [], []);
    const doc = buildExport('live', SECOND, scoped.features, scoped.evidence, '2026-10-05T02:00:00.000Z', RUNS);
    expect(doc.completeness.complete).toBe(true);
    expect(doc.lineage.map(item => item.run_id)).toEqual([FIRST.run.id, SECOND.run.id]);
    expect(doc.concepts).toEqual(SECOND.run.concepts);
    // This record predates the server's separate output.no_candidate_reasons field: the reasons the model declared were
    // stored as run.unresolved, and the export keeps them there rather than inventing the newer field.
    expect((SECOND.output as unknown as Record<string, unknown>).no_candidate_reasons).toBeUndefined();
    expect(doc.no_candidate_reasons).toEqual([]);
    for (const item of execution(SECOND).output!.no_candidate_reasons) expect(doc.unresolved).toContain(item);
    for (const item of doc.evidence) expect(item.text).toBe(scoped.evidence.find(source => source.id === item.id)!.text);
    const markdown = exportMarkdown(doc);
    for (const concept of SECOND.run.concepts) expect(markdown).toContain(concept.title);
    const tampered = { ...doc, concepts: doc.concepts.slice(1) };
    expect(exportCompleteness(tampered, SECOND, scoped.features, scoped.evidence, RUNS).complete).toBe(false);
  });

  it('derived held, failed and zero-candidate shapes are read as such, never as success', () => {
    const held = planningExecutionView(HELD);
    if (held.kind !== 'ok') throw new Error(JSON.stringify(held));
    expect(held.problems).toEqual([]);
    const failed = planningExecutionView(FAILED);
    if (failed.kind !== 'ok') throw new Error(JSON.stringify(failed));
    expect(failed.execution.output).toBeNull();
    expect(failed.problems).toEqual(['규격에 맞지 않아 거절된 판단 기록이 있습니다. 완료 결과로 쓰지 않았습니다.']);
    const zero = planningExecutionView(ZERO);
    if (zero.kind !== 'ok') throw new Error(JSON.stringify(zero));
    expect(zero.problems).toEqual([]);
    expect(zero.execution.output!.no_candidate_reasons.length).toBeGreaterThan(0);
  });

  it('reports malformed or inconsistent records instead of displaying them as results', () => {
    expect(planningExecutionView({ ...FIRST, output: { needs: [], gaps: [] } }).kind).toBe('none');
    const malformed = variant(FIRST, (_copy, record) => { (record.output as unknown as Record<string, unknown>).extra = true; });
    const view = planningExecutionView(malformed);
    expect(view.kind).toBe('invalid');
    const badKind = variant(FIRST, (_copy, record) => { (record as unknown as Record<string, unknown>).execution_kind = 'sample'; });
    expect(planningExecutionView(badKind).kind).toBe('invalid');
    const mismatched = variant(FIRST, copy => { copy.run.status = 'held'; copy.run.concepts = []; });
    const problems = planningExecutionView(mismatched);
    if (problems.kind !== 'ok') throw new Error('expected a readable record');
    expect(problems.problems).toContain('저장된 실행 상태(held)와 판단 기록 상태(completed)가 다릅니다.');
    expect(problems.problems).toContain('실행에 저장된 후보가 판단 출력의 후보와 다릅니다.');
    const otherRequest = variant(FIRST, copy => { copy.request = { ...copy.request, exclusions: [] }; });
    const swapped = planningExecutionView(otherRequest);
    expect(swapped.kind === 'ok' && swapped.problems).toContain('판단에 들어간 원 요청이 이 실행의 요청과 다릅니다.');
  });
});

describe('recorded live runs in the actual React DOM', () => {
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

  async function showConcepts(selected: RunSnapshot, runs = RUNS) {
    const scoped = runSources(selected, [], []);
    await act(async () => root.render(createElement(ConceptsView, { mode: 'live', runs, selected, onSelect: () => {}, features: scoped.features, evidence: scoped.evidence })));
  }

  it('changed run: shows the core record, the exclusion and the candidate that still conflicts with it, under one run ID', async () => {
    await showConcepts(SECOND);
    const panel = host.querySelector('[aria-label="판단 실행 기록"]')!;
    const text = panel.textContent ?? '';
    expect(text).toContain(SECOND.run.id);
    expect(text).toContain('실제 모델 실행 기록(저장된 결과)');
    expect(text).toContain('qwen3:8b');
    expect(text).toContain('모델 호출5회');
    expect(text).toContain('자동 세척 장치 제안');
    expect(text).toContain('계약 검사 통과 · 의미 미검증');
    expect(text).toContain(ACCEPT_DETAIL);
    expect(text).not.toContain('모델이 생성한 결과가 아닙니다');
    for (const item of execution(SECOND).errors) expect(text).toContain(item.message);
    for (const concept of SECOND.run.concepts) expect(text).toContain(concept.title);
    expect(text).toContain('자동 세척 모드 추가');
    for (const step of execution(SECOND).trace) expect(text).toContain(step.operation);
    // The comparison table above quotes the run's own DEV-01 sources instead of reporting them missing.
    expect(host.querySelector('.comparison-table')?.textContent).not.toContain('원문을 찾을 수 없습니다');
    for (const source of execution(SECOND).input.sources.filter(item => item.source_type === 'review')) expect(host.textContent).toContain(source.text);
  });

  it.each([['held', HELD, '보류'], ['failed', FAILED, '판단 출력이 저장되지 않았습니다(실패)'], ['zero-candidate', ZERO, '후보 없음 사유']] as const)(
    'derived %s run shows its state without offering candidates', async (_name, snapshot, marker) => {
      await showConcepts(snapshot, [snapshot]);
      const text = host.querySelector('[aria-label="판단 실행 기록"]')?.textContent ?? '';
      expect(text).toContain(marker);
      expect(host.querySelectorAll('.concept-card')).toHaveLength(0);
      if (snapshot === HELD) for (const item of execution(HELD).output!.questions) expect(text).toContain(item);
      if (snapshot === FAILED) expect(text).toContain('거절된 판단 기록');
    });

  it('excluding a recorded candidate sends a new run request and leaves the stored runs untouched', async () => {
    const before = structuredClone(RUNS);
    const scoped = runSources(SECOND, [], []);
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'live', runs: RUNS, selected: SECOND, original: FIRST.request, onSelect: () => {},
      features: scoped.features, evidence: scoped.evidence, onRerun, measure,
    })));
    expect(host.querySelector('[aria-label="판단 실행 기록"]')?.textContent).toContain(SECOND.run.id);
    const concept = SECOND.run.concepts.find(item => item.title === '자동 세척 모드 추가')!;
    const group = host.querySelector(`[aria-label="${concept.title} 처리"]`)!;
    const exclude = [...group.querySelectorAll('label')].find(item => item.textContent === '제외')!.querySelector('input')!;
    await act(async () => exclude.click());
    await act(async () => (host.querySelector('form[aria-label="후보·조건 선택 후 재실행"]') as HTMLFormElement).requestSubmit());
    expect(onRerun).toHaveBeenCalledTimes(1);
    expect(onRerun.mock.calls[0][0]).toEqual({ ...SECOND.request, exclusions: [...SECOND.request.exclusions, candidateExclusion(concept)] });
    expect(RUNS).toEqual(before);
  });
});
