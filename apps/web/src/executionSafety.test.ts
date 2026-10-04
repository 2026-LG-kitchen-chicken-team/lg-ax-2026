// @vitest-environment jsdom
// Stored public records are replayed as data. Mutations below are malformed-record fixtures, never live model calls.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ExecutionPanel } from './JudgementViews';
import { planningExecutionView, runSources } from './judgement';
import type { PlanningExecution } from './judgement';
import type { RunSnapshot } from './planning';

const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), '../..', path), 'utf-8'));
const LIVE = read('evals/pm-integration/20261005/workspace-live.json').first as RunSnapshot;
const SEMANTIC = read('evals/web/20261005/p2-web-003-core-records/pr60-semantic-preview.json').runs.semantic_accept as RunSnapshot;
const execution = (snapshot: RunSnapshot) => (snapshot.output as unknown as { planning_execution: PlanningExecution }).planning_execution;

describe('stored execution safety and terminal failures', () => {
  const cases: [string, (raw: Record<string, unknown>) => void][] = [
    ['null model call', raw => { raw.model_calls = [null]; }],
    ['missing model digest', raw => { raw.model_calls = [{ model_id: 'fixture' }]; }],
    ['null trace entry', raw => { raw.trace = [null]; }],
    ['blank trace operation', raw => { raw.trace = [{ stage: 'review', operation: ' ' }]; }],
    ['null error entry', raw => { raw.errors = [null]; }],
    ['non-text error message', raw => { raw.errors = [{ code: 'FAILED', message: {} }]; }],
    ['missing product fields', raw => { (raw.input as Record<string, unknown>).product = {}; }],
  ];
  it.each(cases)('rejects %s before projecting sources or rendering', (_name, change) => {
    const copy = structuredClone(LIVE);
    change(execution(copy) as unknown as Record<string, unknown>);
    expect(() => planningExecutionView(copy)).not.toThrow();
    expect(planningExecutionView(copy).kind).toBe('invalid');
    expect(runSources(copy, [], [])).toEqual({ features: [], evidence: [] });
  });

  const semanticCases: [string, (raw: Record<string, unknown>) => void][] = [
    ['non-text reason', report => { ((report.quality_assessments as Record<string, unknown>[])[0]).reason = {}; }],
    ['null source quote', report => { ((report.quality_assessments as Record<string, unknown>[])[0]).source_quotes = [null]; }],
    ['non-array source quotes', report => { ((report.quality_assessments as Record<string, unknown>[])[0]).source_quotes = 'bad'; }],
    ['non-text question', report => { report.questions = [{}]; }],
  ];
  it.each(semanticCases)('rejects semantic %s before React reads it', (_name, change) => {
    const copy = structuredClone(SEMANTIC);
    change(execution(copy).semantic_reviews![0].report as unknown as Record<string, unknown>);
    expect(planningExecutionView(copy).kind).toBe('invalid');
  });

  it('keeps historical semantic input/output snapshots and rejects malformed retained originals', () => {
    const copy = structuredClone(SEMANTIC);
    const record = execution(copy);
    Object.assign(record.semantic_reviews![0], { reviewed_input: structuredClone(record.input), reviewed_output: structuredClone(record.output) });
    expect(planningExecutionView(copy).kind).toBe('ok');
    (record.semantic_reviews![0] as unknown as Record<string, unknown>).reviewed_output = { status: 'completed' };
    expect(planningExecutionView(copy).kind).toBe('invalid');
  });

  it('reports a changed final request rather than silently treating it as the original request', () => {
    const copy = structuredClone(LIVE);
    execution(copy).input.request.improvement_task = '다른 최종 요청';
    const view = planningExecutionView(copy);
    expect(view.kind === 'ok' && view.problems).toContain('판단의 최종 요청이 이 실행의 원 요청과 다릅니다.');
  });
});

describe('failed execution display with a retained output and no terminal decision', () => {
  let host: HTMLDivElement;
  let root: ReturnType<typeof createRoot>;
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

  it('shows the stored failed output and its questions/reasons without inventing an accept decision', async () => {
    const copy = structuredClone(LIVE);
    const record = execution(copy);
    record.status = 'failed'; record.decision = null;
    record.output!.status = 'failed'; record.output!.concepts = []; record.output!.concept_assessments = [];
    record.output!.questions = ['추가로 확인할 원문이 있나요?'];
    record.output!.hold_reasons = ['근거 보완이 필요합니다.'];
    record.output!.unresolved = ['최종 검토에 실패했습니다.'];
    record.output!.no_candidate_reasons = ['검수된 후보가 없습니다.'];
    copy.run.status = 'failed'; copy.run.concepts = [];
    await act(async () => root.render(createElement(ExecutionPanel, { snapshot: copy })));
    const text = host.textContent ?? '';
    expect(text).toContain('최종 코어 검사 결정이 없습니다');
    expect(text).toContain('저장된 판단 출력 · 실패');
    for (const item of [...record.output!.questions, ...record.output!.hold_reasons, ...record.output!.unresolved, ...record.output!.no_candidate_reasons]) expect(text).toContain(item);
    expect(text).not.toContain('판단 출력이 저장되지 않았습니다');
    expect(text).not.toContain('계약 검사 통과');
    expect(host.querySelectorAll('button')).toHaveLength(0);
  });

  it('renders a malformed nested record as an alert without throwing', async () => {
    const copy = structuredClone(LIVE);
    (execution(copy) as unknown as Record<string, unknown>).errors = [null];
    await act(async () => root.render(createElement(ExecutionPanel, { snapshot: copy })));
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('형식이 맞지 않아 표시하지 않습니다');
  });
});
