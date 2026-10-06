// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { buildRevisionTimeline, RevisionTimeline } from './RevisionTimeline';
import { FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import type { DataMode, RunSnapshot } from './planning';

const [first, second] = FIXTURE_RUNS;
const original = FIXTURE_ORIGINAL_REQUEST;

/** A third run that changes only the data: new dataset/document versions, same request as its parent. */
function dataChanged(): RunSnapshot {
  return {
    ...second, run: { ...second.run, id: 'RUN-DATA-3', dataset_version: '0.2.0', revision_count: 2 },
    request: { ...second.request, dataset_version: '0.2.0' }, previous_run_id: second.run.id, request_revision: 2,
    created_at: '2026-10-04T08:20:00.000000Z', document_versions: { 'FRIDGE-A': '2.0' }, dataset_sha256: 'f'.repeat(64),
  };
}
/** A rerun with identical request and data. */
function sameRerun(): RunSnapshot {
  return { ...second, run: { ...second.run, id: 'RUN-SAME-3' }, previous_run_id: second.run.id, request_revision: second.request_revision, created_at: '2026-10-04T08:20:00.000000Z' };
}

describe('buildRevisionTimeline links rounds to their own previous run', () => {
  it('separates original, user condition change, data change and internal revision counts', () => {
    const third = dataChanged();
    const { entries, problems } = buildRevisionTimeline([first, second, third], third.run.id, original);
    expect(problems).toEqual([]);
    expect(entries.map(item => item.run_id)).toEqual([first.run.id, second.run.id, third.run.id]);
    expect(entries.map(item => item.causes)).toEqual([['original'], ['user_condition_change'], ['data_version_change']]);
    expect(entries[1].request_changes.map(item => item.field)).toEqual(['exclusions']);
    expect(entries[1].data_changes).toEqual({ dataset_version: null, dataset_sha256: null, documents: [] });
    expect(entries[2].data_changes).toEqual({
      dataset_version: ['0.1.0', '0.2.0'], dataset_sha256: [first.dataset_sha256, 'f'.repeat(64)],
      documents: [{ model_id: 'FRIDGE-A', before: '1.0', after: '2.0' }],
    });
    // Agent-internal revisions belong to the run itself and never create user-change causes.
    expect(entries.map(item => item.internal_revision)).toEqual([{ count: 1, max: 2 }, { count: 0, max: 2 }, { count: 2, max: 2 }]);
    expect(entries[0].causes).not.toContain('user_condition_change');
  });
  it('compares candidates against the linked previous run only', () => {
    const { entries } = buildRevisionTimeline([first, second], second.run.id, original);
    expect(entries[1].concept_changes?.map(item => [item.id, item.status])).toEqual([['CONCEPT-FX-001', ['needs_review', 'rejected']]]);
  });
  it('labels an unchanged rerun and a data-only change without inventing a user change', () => {
    const rerun = sameRerun();
    expect(buildRevisionTimeline([first, second, rerun], rerun.run.id, original).entries[2].causes).toEqual(['unchanged_rerun']);
    const dataOnly: RunSnapshot = { ...rerun, run: { ...rerun.run, id: 'RUN-DOC-3' }, document_versions: { 'FRIDGE-A': '2.0' } };
    const entry = buildRevisionTimeline([first, second, dataOnly], dataOnly.run.id, original).entries[2];
    expect(entry.causes).toEqual(['data_version_change']);
    expect(entry.request_changes).toEqual([]);
  });
  it('does not mutate its inputs', () => {
    const runs = [first, second, dataChanged()];
    const copy = structuredClone(runs);
    buildRevisionTimeline(runs, 'RUN-DATA-3', original);
    expect(runs).toEqual(copy);
  });
});

describe('wrong or inconsistent links are held, not guessed', () => {
  it('holds when the previous run is missing and does not compare against another run', () => {
    const orphan = { ...second, previous_run_id: 'RUN-NOPE' };
    const { entries, problems } = buildRevisionTimeline([first, orphan], orphan.run.id, original);
    expect(entries).toHaveLength(1);
    expect(entries[0].concept_changes).toBeNull();
    expect(problems.join('\n')).toContain('RUN-NOPE');
  });
  it('does not link a run from another project even when the ID exists', () => {
    const foreign: RunSnapshot = { ...first, run: { ...first.run, project_id: 'PROJECT-OTHER' } };
    const { entries, problems } = buildRevisionTimeline([foreign, second], second.run.id, original);
    expect(entries.map(item => item.run_id)).toEqual([second.run.id]);
    expect(entries[0].concept_changes).toBeNull();
    expect(problems.join('\n')).toContain('PROJECT-OTHER');
  });
  it('rejects cycles, self links and duplicate run IDs', () => {
    const a: RunSnapshot = { ...first, previous_run_id: second.run.id };
    expect(buildRevisionTimeline([a, second], second.run.id, original).problems.join('\n')).toContain('순환');
    const self: RunSnapshot = { ...second, previous_run_id: second.run.id };
    expect(buildRevisionTimeline([first, self], self.run.id, original).problems.join('\n')).toContain('순환');
    const copy: RunSnapshot = { ...first, run: { ...first.run, concepts: [] } };
    const dup = buildRevisionTimeline([first, copy, second], second.run.id, original);
    expect(dup.problems.join('\n')).toContain('중복');
    expect(dup.entries[0].concept_changes).toBeNull();
    expect(buildRevisionTimeline([first, copy], first.run.id, original).entries).toEqual([]);
  });
  it('reports an unknown selection and a revision number that does not match the request change', () => {
    expect(buildRevisionTimeline([first], 'RUN-X', original)).toEqual({ entries: [], problems: ['선택한 실행 RUN-X이 기록에 없습니다.'] });
    const wrong: RunSnapshot = { ...second, request_revision: 5 };
    const { entries, problems } = buildRevisionTimeline([first, wrong], wrong.run.id, original);
    expect(problems.join('\n')).toContain('계산한 1');
    expect(entries.map(item => item.run_id)).toEqual([wrong.run.id]);
    expect(entries[0].concept_changes).toBeNull();
  });
  it('rejects a parent recorded later than its child', () => {
    const late: RunSnapshot = { ...first, created_at: '2026-10-05T00:00:00.000000Z' };
    expect(buildRevisionTimeline([late, second], second.run.id, original).problems.join('\n')).toContain('늦습니다');
  });
  it('flags internal revision counts outside 0..2 and dataset version mismatches, without hiding them', () => {
    const bad: RunSnapshot = { ...second, run: { ...second.run, revision_count: 3, dataset_version: '9.9.9' } };
    const [, entry] = buildRevisionTimeline([first, bad], bad.run.id, original).entries;
    expect(entry.record_problems.some(text => text.includes('0~2'))).toBe(true);
    expect(entry.record_problems.some(text => text.includes('9.9.9'))).toBe(true);
  });
  it('does not compare candidates for a run the Agent never produced', () => {
    const draft: RunSnapshot = { ...second, run: { ...second.run, status: 'not_implemented', concepts: [] } };
    expect(buildRevisionTimeline([first, draft], draft.run.id, original).entries[1].concept_changes).toBeNull();
  });
  it.each(['pending', 'running'] as const)('does not turn an empty %s run into removed candidates', status => {
    const waiting: RunSnapshot = { ...second, output: null, run: { ...second.run, status, concepts: [] } };
    expect(buildRevisionTimeline([first, waiting], waiting.run.id, original).entries[1].concept_changes).toBeNull();
    const waitingParent: RunSnapshot = { ...first, output: null, run: { ...first.run, status, concepts: [] } };
    expect(buildRevisionTimeline([waitingParent, second], second.run.id, original).entries[1].concept_changes).toBeNull();
  });
});

describe('RevisionTimeline renders in the DOM', () => {
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
  const mount = (runs: RunSnapshot[], selectedId: string, onSelect = vi.fn(), mode: DataMode = 'fixture') =>
    act(async () => root.render(createElement(RevisionTimeline, { runs, selectedId, original, mode, onSelect })));

  it('shows causes, data versions and internal revisions per round', async () => {
    const third = dataChanged();
    await mount([first, second, third], third.run.id);
    expect(host.textContent).toContain('합성 예시 · 실제 Agent 실행 결과가 아닙니다');
    const items = [...host.querySelectorAll<HTMLElement>('li[data-run-id]')];
    expect(host.querySelectorAll('.timeline > li')).toHaveLength(3);
    // Data/candidate details contain their own list items; they are not runs.
    expect(host.querySelectorAll('.timeline li').length).toBeGreaterThan(3);
    expect(items.map(item => item.dataset.causes)).toEqual(['original', 'user_condition_change', 'data_version_change']);
    expect(items[2].querySelector('[data-field="internal"]')?.textContent).toContain('2 / 2회');
    expect(items[2].querySelector('[data-field="data-version"]')?.textContent).toContain('FRIDGE-A 2.0');
    expect(items[2].querySelector('[data-field="data-changes"]')?.textContent).toContain('FRIDGE-A 문서 1.0 → 2.0');
    expect(items[1].querySelector('[data-field="request-changes"]')?.textContent).toContain('문서 2.0 부분 분리 트레이와 같은 기능 제외');
    expect(host.querySelector('[data-held]')).toBeNull();
  });
  it.each([
    ['completed', '분석 완료'], ['held', '보류'], ['failed', '실패'],
    ['not_implemented', '요청만 저장됨'], ['pending', '진행 중'], ['running', '진행 중'],
  ] as const)('shows saved %s status and its stage on the run row', async (status, label) => {
    const saved: RunSnapshot = { ...first, run: { ...first.run, status, concepts: [] } };
    await mount([saved], saved.run.id, vi.fn(), 'live');
    const shown = host.querySelector('[data-field="run-status"]');
    expect(shown?.textContent).toContain(label);
    expect(shown?.textContent).toContain(`${status} · ${saved.run.stage}`);
    expect(shown?.textContent).not.toContain('fixture 예시');
  });
  it('marks hand-written fixture status as an example, but marks an unexecuted local draft as request-only', async () => {
    await mount([first], first.run.id);
    expect(host.querySelector('[data-field="run-status"]')?.textContent).toContain(`fixture 예시 · ${first.run.status}`);
    const draft: RunSnapshot = { ...second, run: { ...second.run, id: 'RUN-DRAFT-STATUS', status: 'not_implemented', concepts: [] },
      actor_id: 'local-draft', previous_run_id: second.run.id, created_at: '2026-10-04T08:20:00.000000Z' };
    await mount([first, second, draft], draft.run.id);
    const row = host.querySelector('[data-run-id="RUN-DRAFT-STATUS"] [data-field="run-status"]');
    expect(row?.textContent).toContain('요청만 저장됨');
    expect(row?.textContent).not.toContain('fixture 예시');
  });
  it('shows a held notice instead of a comparison for a broken link, and selection calls back', async () => {
    const orphan = { ...second, previous_run_id: 'RUN-NOPE' };
    const onSelect = vi.fn();
    await mount([first, orphan], orphan.run.id, onSelect);
    expect(host.querySelector('[role="alert"][data-held="true"]')?.textContent).toContain('RUN-NOPE');
    expect(host.querySelector('[data-field="candidates"][data-held="true"]')).not.toBeNull();
    await act(async () => host.querySelector<HTMLButtonElement>('li[data-run-id] button')!.click());
    expect(onSelect).toHaveBeenCalledWith(orphan.run.id);
  });
});
