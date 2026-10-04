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
    expect(done).toMatchObject({ status: 'completed', modification_seconds: 83.5, result_run_id: 'RUN-DRAFT-3', base_run_id: 'RUN-FX-002' });
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
  it('summarises candidate and condition edits', () => {
    expect(editSummary({ A: 'keep', B: 'keep' }, { A: 'exclude', B: 'keep' }, ['x', 'y'], ['y', 'z', 'w'])).toEqual({ candidates_changed: 1, conditions_added: 2, conditions_removed: 1 });
  });
  it('exports records with the start/end rules and the null convention', () => {
    const running = startMeasurement('조건 교정', 'run-1', 'live', 'M-4', start);
    const doc = exportMeasurements([running], '2026-10-04T10:10:00Z');
    expect(doc.rules).toEqual({ start: START_RULE, end: END_RULE, unit: 'seconds', unmeasured: 'null' });
    expect(doc.records[0].modification_seconds).toBeNull();
    expect(doc.notice).toContain('효과를 주장하지 않는다');
  });
});
