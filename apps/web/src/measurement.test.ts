import { describe, expect, it } from 'vitest';
import { cancelMeasurement, editSummary, END_RULE, exportMeasurements, finishMeasurement, START_RULE, startMeasurement } from './measurement';

const start = new Date('2026-10-04T10:00:00.000Z');

describe('E03 planner modification time', () => {
  it('requires an explicit goal so only the same goal is compared', () => {
    expect(() => startMeasurement('  ', 'RUN-FX-002', 'fixture', 'M-1', start)).toThrow(/수정 목표/);
    expect(startMeasurement('중복 후보 제외', 'RUN-FX-002', 'fixture', 'M-1', start)).toMatchObject({ status: 'running', modification_seconds: null, ended_at: null });
  });
  it('measures from start to the saved rerun and records what was edited', () => {
    const running = startMeasurement('중복 후보 제외', 'RUN-FX-002', 'fixture', 'M-1', start);
    const done = finishMeasurement(running, 'RUN-DRAFT-3', { candidates_changed: 1, conditions_added: 1, conditions_removed: 0 }, new Date('2026-10-04T10:01:23.456Z'));
    expect(done).toMatchObject({ status: 'completed', modification_seconds: 83.456, result_run_id: 'RUN-DRAFT-3', base_run_id: 'RUN-FX-002' });
    expect(() => finishMeasurement(done, 'X', done.edits!, new Date())).toThrow();
  });
  it('keeps cancelled or unfinished attempts as null, never 0', () => {
    const running = startMeasurement('조건 교정', 'run-1', 'live', 'M-2', start);
    expect(cancelMeasurement(running, new Date('2026-10-04T10:05:00Z')).modification_seconds).toBeNull();
    expect(running.modification_seconds).toBeNull();
    const instant = finishMeasurement(running, 'run-2', { candidates_changed: 0, conditions_added: 1, conditions_removed: 0 }, start);
    expect(instant.modification_seconds).toBe(0);
  });
  it('rejects an end time before the start', () => {
    const running = startMeasurement('조건 교정', 'run-1', 'live', 'M-3', start);
    expect(() => finishMeasurement(running, 'run-2', { candidates_changed: 0, conditions_added: 0, conditions_removed: 0 }, new Date('2026-10-04T09:59:59Z'))).toThrow();
  });
  it('preserves positive sub-50ms measurements instead of rounding them to zero', () => {
    const running = startMeasurement('조건 교정', 'run-1', 'live', 'M-short', start);
    expect(finishMeasurement(running, 'run-2', { candidates_changed: 0, conditions_added: 1, conditions_removed: 0 }, new Date(start.getTime() + 20)).modification_seconds).toBe(0.02);
    expect(finishMeasurement(running, 'run-2', { candidates_changed: 0, conditions_added: 1, conditions_removed: 0 }, new Date(start.getTime() + 1)).modification_seconds).toBe(0.001);
  });
  it('requires the same session, project, mode and captured base for a scoped completion', () => {
    const scope = { scope_id: 'session-project-1', project_id: 'project-1', project_owner_id: 'owner-1' };
    const running = startMeasurement('조건 교정', 'run-1', 'live', 'M-scope', start, scope);
    const completion = { mode: 'live' as const, base_run_id: 'run-1', scope };
    const edits = { candidates_changed: 0, conditions_added: 1, conditions_removed: 0 };
    expect(() => finishMeasurement(running, 'run-2', edits, start)).toThrow(/작업 범위/);
    for (const changed of [
      { ...completion, mode: 'fixture' as const },
      { ...completion, base_run_id: 'another-base' },
      { ...completion, scope: { ...scope, scope_id: 'new-session' } },
      { ...completion, scope: { ...scope, project_id: 'project-2' } },
      { ...completion, scope: { ...scope, project_owner_id: 'owner-2' } },
    ]) expect(() => finishMeasurement(running, 'run-2', edits, start, changed)).toThrow(/작업 범위/);
    expect(finishMeasurement(running, 'run-2', edits, start, completion)).toMatchObject({ status: 'completed', scope, execution_kind: 'live_service', participant_kind: 'unconfirmed' });
    expect(startMeasurement('조건 교정', 'run-1', 'fixture', 'M-fixture', start, scope).execution_kind).toBe('fixture_browser');
  });
  it('summarises candidate and condition edits', () => {
    expect(editSummary({ A: 'keep', B: 'keep' }, { A: 'exclude', B: 'keep' }, ['x', 'y'], ['y', 'z', 'w'])).toEqual({ candidates_changed: 1, conditions_added: 2, conditions_removed: 1 });
  });
  it('exports records with the start/end rules and the null convention', () => {
    const running = startMeasurement('조건 교정', 'run-1', 'live', 'M-4', start);
    const doc = exportMeasurements([running], '2026-10-04T10:10:00Z');
    expect(doc.rules).toEqual({ start: START_RULE, end: END_RULE, unit: 'seconds', unmeasured: 'null' });
    expect(doc.records[0].modification_seconds).toBeNull();
    expect(doc.notice).toContain('효과를 주장하지 않는다');
    expect(doc.notice).toContain('사람의 조작인지 자동화인지 확인하지 않았');
    expect(doc.notice).toContain('Agent 실행 완료 시간은 아니다');
    expect(doc.records[0].participant_kind).toBe('unconfirmed');
  });
});
