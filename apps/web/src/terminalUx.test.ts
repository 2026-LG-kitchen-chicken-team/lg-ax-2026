// @vitest-environment jsdom
// PM-20261005-WEB-003-TERMINAL-UX (doable before PM's round2 records land): malformed nested record items are shown as
// errors instead of breaking the screen, runs without an accepted judgement offer no candidates for selection, and
// exports carry the core record (decision, terminal reasons, semantic review). Records are the core-pipeline ones
// (mocked model, evals/web/20261005/p2-web-003-core-records) and the PM live record; malformed ones are derived copies.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { exportJudgement, planningExecutionView, rerunBaseNotice, runSources, selectableConcepts } from './judgement';
import type { PlanningExecution } from './judgement';
import { ConceptsView, HistoryView } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import { buildExport, exportCompleteness, exportMarkdown } from './planning';
import type { PlanningRequest, RunSnapshot } from './planning';

const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), '../..', path), 'utf-8'));
const MAIN = read('evals/web/20261005/p2-web-003-core-records/main-core.json').runs as Record<string, RunSnapshot>;
const PR60 = read('evals/web/20261005/p2-web-003-core-records/pr60-semantic-preview.json').runs as Record<string, RunSnapshot>;
const LIVE = read('evals/pm-integration/20261005/workspace-live.json');
const ACCEPTED: RunSnapshot = LIVE.second;
const execution = (snapshot: RunSnapshot) => (snapshot.output as unknown as { planning_execution: PlanningExecution }).planning_execution;
const derive = (base: RunSnapshot, change: (copy: RunSnapshot, record: Record<string, unknown>) => void) => {
  const copy = structuredClone(base);
  change(copy, execution(copy) as unknown as Record<string, unknown>);
  return copy;
};

// Derived copies (not core output): broken nested items, a stale candidate list on a held run, and the workspace
// server's own failure record (failed_execution: decision null, no output).
const BROKEN = derive(MAIN.duplicate_unresolved, (_copy, record) => {
  delete (record.model_calls as Record<string, unknown>[])[0].model_digest;
  (record.trace as unknown[])[1] = { stage: 'retrieve' };
  (record.errors as unknown[]).push('not an object');
});
const STALE = derive(MAIN.positive_held, copy => { copy.run.concepts = structuredClone(ACCEPTED.run.concepts); });
const NO_DECISION = derive(MAIN.generation_failed, (_copy, record) => {
  record.decision = null;
  record.model_calls = [];
  record.errors = [{ code: 'MODEL_UNAVAILABLE', message: '판단 실행을 완료하지 못했습니다. 서버 실행 설정과 근거를 확인해 주세요.' }];
  record.trace = [{ stage: 'review', operation: 'stop' }];
});
const RECORDS: [string, RunSnapshot][] = [...Object.entries(MAIN).map(([name, run]) => [`main/${name}`, run] as [string, RunSnapshot]), ...Object.entries(PR60).map(([name, run]) => [`pr60/${name}`, run] as [string, RunSnapshot])];

describe('malformed nested record items', () => {
  it('are listed as record errors with their paths', () => {
    const view = planningExecutionView(BROKEN);
    if (view.kind !== 'invalid') throw new Error('expected an invalid record');
    expect(view.errors).toEqual(expect.arrayContaining([
      '/trace/1/operation must be a non-empty string',
      '/model_calls/0/model_digest must be a non-empty string',
      `/errors/${execution(BROKEN).errors.length - 1} must be an object`,
    ]));
    expect(exportJudgement(BROKEN)).toEqual({ record_valid: false, record_errors: view.errors });
  });

  it('valid core records have no item errors', () => {
    for (const [name, snapshot] of [...RECORDS, ['live', ACCEPTED] as [string, RunSnapshot]]) expect(planningExecutionView(snapshot).kind, name).toBe('ok');
  });
});

describe('candidates are offered only from an accepted judgement', () => {
  it.each([['live accepted', ACCEPTED, true], ['main need_reference_revised', MAIN.need_reference_revised, true], ['pr60 semantic_accept', PR60.semantic_accept, true]] as const)(
    '%s keeps its candidates', (_name, snapshot, accepted) => {
      expect(selectableConcepts(snapshot)).toEqual(snapshot.run.concepts);
      expect(rerunBaseNotice(snapshot) === null).toBe(accepted && snapshot.run.concepts.length > 0);
    });

  it.each([
    ['held', MAIN.positive_held, '보류로 끝나'], ['failed', MAIN.duplicate_unresolved, '실패로 끝나'], ['no decision', NO_DECISION, '(코어 결정 없음)'],
    ['stale candidates on a held run', STALE, '보류로 끝나'], ['malformed record', BROKEN, '형식이 맞지 않아'], ['semantic hold', PR60.exclusion_uncertain_held, '보류로 끝나'],
  ] as const)('%s offers none and says why', (_name, snapshot, notice) => {
    expect(selectableConcepts(snapshot)).toEqual([]);
    expect(rerunBaseNotice(snapshot)).toContain(notice);
  });

  it('runs without a core record keep the earlier behaviour', () => {
    const draft = structuredClone(ACCEPTED);
    draft.output = { needs: [], gaps: [] } as unknown as RunSnapshot['output'];
    expect(selectableConcepts(draft)).toEqual(draft.run.concepts);
    expect(rerunBaseNotice(draft)).toBeNull();
  });
});

describe('exports carry the core record', () => {
  it.each(RECORDS)('%s: judgement section is complete and matches the record', (_name, snapshot) => {
    const scoped = runSources(snapshot, [], []);
    const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-05T03:00:00.000Z', [snapshot]);
    expect(doc.completeness.complete).toBe(true);
    const judgement = doc.judgement!;
    if (!judgement.record_valid) throw new Error('expected a valid record');
    expect(judgement.status).toBe(execution(snapshot).status);
    expect(judgement.decision).toBe(execution(snapshot).decision!.action);
    const markdown = exportMarkdown(doc);
    expect(markdown).toContain('## 판단 실행 기록');
    for (const item of [...judgement.violations, ...judgement.questions, ...judgement.hold_reasons, ...judgement.no_candidate_reasons]) expect(markdown).toContain(item);
    for (const item of judgement.rejected_candidates) expect(markdown).toContain(item.title);
    for (const row of judgement.semantic_rows) expect(markdown).toContain(row.reason);
    // A doctored judgement section is caught by the completeness check.
    const tampered = { ...doc, judgement: { ...judgement, hold_reasons: [] as string[], violations: [] as string[] } };
    if (judgement.hold_reasons.length || judgement.violations.length) expect(exportCompleteness(tampered, snapshot, scoped.features, scoped.evidence, [snapshot]).mismatched_fields).toContain('판단 실행 기록');
  });

  it('semantic review rows and rejected candidates are exported for a semantic failure', () => {
    const scoped = runSources(PR60.exclusion_violation_unresolved, [], []);
    const doc = buildExport('live', PR60.exclusion_violation_unresolved, scoped.features, scoped.evidence, '2026-10-05T03:00:00.000Z');
    const judgement = doc.judgement!;
    if (!judgement.record_valid) throw new Error('expected a valid record');
    expect(judgement.semantic_reviews).toHaveLength(3);
    expect(judgement.semantic_rows.filter(row => row.verdict === 'violation')).toHaveLength(3);
    expect(judgement.rejected_candidates.length).toBeGreaterThan(0);
    expect(exportMarkdown(doc)).toContain('의미 검토 3회 (판단과 같은 모델의 검토 선언, 독립 검증 아님)');
  });

  it('a malformed record and a run without one export as such', () => {
    const scoped = runSources(BROKEN, [], []);
    const doc = buildExport('live', BROKEN, scoped.features, scoped.evidence, '2026-10-05T03:00:00.000Z', [BROKEN]);
    expect(doc.judgement?.record_valid).toBe(false);
    expect(exportMarkdown(doc)).toContain('저장된 판단 기록의 형식이 맞지 않아 결과로 쓰지 않았습니다');
    const plain = structuredClone(ACCEPTED);
    plain.output = { needs: [], gaps: [] } as unknown as RunSnapshot['output'];
    const none = buildExport('live', plain, [], [], '2026-10-05T03:00:00.000Z', [plain]);
    expect(none.judgement).toBeNull();
    expect(exportMarkdown(none)).not.toContain('## 판단 실행 기록');
  });
});

describe('terminal runs in the actual React DOM', () => {
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
  const history = (snapshot: RunSnapshot) => act(async () => root.render(createElement(HistoryView, {
    mode: 'live', runs: [snapshot], selected: snapshot, original: snapshot.request, onSelect: () => {}, ...runSources(snapshot, [], []), onRerun, measure,
  })));

  it('a malformed record renders as an error instead of throwing', async () => {
    const scoped = runSources(BROKEN, [], []);
    await act(async () => root.render(createElement(ConceptsView, { mode: 'live', runs: [BROKEN], selected: BROKEN, onSelect: () => {}, ...scoped })));
    const text = host.querySelector('[aria-label="판단 실행 기록"]')?.textContent ?? '';
    expect(text).toContain('저장된 판단 기록의 형식이 맞지 않아 표시하지 않습니다');
    expect(text).toContain('/model_calls/0/model_digest must be a non-empty string');
  });

  it('stale candidates on a held run are flagged and not offered for selection', async () => {
    const scoped = runSources(STALE, [], []);
    await act(async () => root.render(createElement(ConceptsView, { mode: 'live', runs: [STALE], selected: STALE, onSelect: () => {}, ...scoped })));
    expect(host.textContent).toContain('저장된 판단 기록이 이 후보들을 채택하지 않았습니다');
    await history(STALE);
    expect(host.querySelectorAll('[role="radiogroup"]')).toHaveLength(0);
    expect(host.querySelector('form[aria-label="후보·조건 선택 후 재실행"]')?.textContent).toContain('보류로 끝나 채택된 후보가 없습니다');
  });

  it('a failed run with no core decision can only be rerun with corrected conditions, stated as a new judgement', async () => {
    await history(NO_DECISION);
    const form = host.querySelector('form[aria-label="후보·조건 선택 후 재실행"]') as HTMLFormElement;
    expect(form.textContent).toContain('(코어 결정 없음)');
    expect(form.textContent).toContain('이 실행에는 고를 후보가 없습니다');
    const input = host.querySelector('#extra-condition') as HTMLInputElement;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '자동 세척 장치 제안');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => ([...form.querySelectorAll('button')].find(item => item.textContent === '조건 추가') as HTMLButtonElement).click());
    const before = structuredClone(NO_DECISION);
    await act(async () => form.requestSubmit());
    expect(onRerun).toHaveBeenCalledTimes(1);
    expect(onRerun.mock.calls[0][0].exclusions).toEqual([...NO_DECISION.request.exclusions, '자동 세척 장치 제안']);
    expect(NO_DECISION).toEqual(before);
  });
});
