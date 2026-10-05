// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoryView } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import type { Evidence } from './domain';
import { FIXTURE_BOOTSTRAP, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import { conceptDetailChanges } from './planning';
import type { Concept, Feature, RunSnapshot } from './planning';

const evidence = FIXTURE_BOOTSTRAP.evidence as Evidence[];
const features = FIXTURE_BOOTSTRAP.features as unknown as Feature[];
const [first] = FIXTURE_RUNS;
const target = first.run.concepts[0];
const LONG_KOREAN = `${'오염된 구획만 따로 꺼내 세척하고 나머지 식품은 그대로 둔다. '.repeat(12)}\n<b>굵게</b> **마크다운** & <script>x</script>`;

/** A linked follow-up run whose only difference is the supplied edit of the first candidate. */
function followUp(edit: Partial<Concept>): RunSnapshot {
  const concepts = first.run.concepts.map(item => item.id === target.id ? { ...item, ...edit } : item);
  return { ...first, run: { ...first.run, id: 'RUN-TEXT-2', status: 'completed', concepts }, previous_run_id: first.run.id, request_revision: first.request_revision + 1 };
}

describe('concept title and differentiation changes (data)', () => {
  it('reports a title-only change with both original texts and nothing else', () => {
    const [change] = conceptDetailChanges(first, followUp({ title: '새 제목' }));
    expect(change.text.title).toEqual({ before: target.title, after: '새 제목' });
    expect(change.text.differentiation).toBeNull();
    expect(change.status[0]).toBe(change.status[1]);
    expect(change.added).toEqual({ requirements: [], assumptions: [], evidence_ids: [] });
    expect(change.removed).toEqual({ requirements: [], assumptions: [], evidence_ids: [] });
  });
  it('reports a differentiation-only change', () => {
    const [change] = conceptDetailChanges(first, followUp({ differentiation: LONG_KOREAN }));
    expect(change.text.title).toBeNull();
    expect(change.text.differentiation).toEqual({ before: target.differentiation, after: LONG_KOREAN });
  });
  it('reports both changes, including an empty previous value', () => {
    const emptied = { ...first, run: { ...first.run, concepts: first.run.concepts.map(item => item.id === target.id ? { ...item, title: '', differentiation: '' } : item) } };
    const [change] = conceptDetailChanges(emptied, followUp({ title: '새 제목', differentiation: '새 차별점' }));
    expect(change.text.title).toEqual({ before: '', after: '새 제목' });
    expect(change.text.differentiation).toEqual({ before: '', after: '새 차별점' });
  });
  it('keeps unchanged candidates, status changes and added/removed candidates as before', () => {
    expect(conceptDetailChanges(first, followUp({}))).toEqual([]);
    expect(conceptDetailChanges(first, followUp({ status: 'rejected' }))[0].status).toEqual([target.status, 'rejected']);
    const [added] = conceptDetailChanges(undefined, first).filter(item => item.id === target.id);
    expect(added.status).toEqual([null, target.status]);
    expect(added.text).toEqual({ title: null, differentiation: null });
  });
  it('does not mutate either snapshot', () => {
    const before = structuredClone(first);
    const after = followUp({ title: '새 제목' });
    const afterCopy = structuredClone(after);
    conceptDetailChanges(first, after);
    expect(first).toEqual(before);
    expect(after).toEqual(afterCopy);
  });
});

describe('HistoryView renders concept text changes in the actual DOM', () => {
  let host: HTMLDivElement;
  let root: Root;
  const measure: MeasureControls = { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' };

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

  async function mount(selected: RunSnapshot) {
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'fixture', runs: [first, selected], selected, original: FIXTURE_ORIGINAL_REQUEST, onSelect: () => {},
      features, evidence, onRerun: vi.fn().mockResolvedValue(undefined), measure,
    })));
  }
  const diffs = () => [...host.querySelectorAll<HTMLElement>('.text-change')];

  it('shows a title-only change instead of "후보 변화가 없습니다"', async () => {
    await mount(followUp({ title: '새 제목' }));
    expect(host.textContent).not.toContain('후보 변화가 없습니다');
    expect(diffs()).toHaveLength(1);
    expect(diffs()[0].dataset.field).toBe('제목');
    expect(diffs()[0].textContent).toContain(`변경 전: ${target.title}`);
    expect(diffs()[0].textContent).toContain('변경 후: 새 제목');
  });
  it('shows a differentiation-only change with long Korean text verbatim and no HTML/markdown execution', async () => {
    await mount(followUp({ differentiation: LONG_KOREAN }));
    expect(host.textContent).not.toContain('후보 변화가 없습니다');
    expect(diffs()).toHaveLength(1);
    expect(diffs()[0].dataset.field).toBe('차별점');
    expect(diffs()[0].textContent).toContain(`변경 전: ${target.differentiation}`);
    expect(diffs()[0].textContent).toContain(`변경 후: ${LONG_KOREAN}`);
    expect(diffs()[0].querySelector('b, script, strong + strong')).toBeNull();
    expect(host.querySelectorAll('script')).toHaveLength(0);
  });
  it('shows both changes and labels an empty previous value', async () => {
    const emptied: RunSnapshot = { ...first, run: { ...first.run, id: 'RUN-TEXT-1', concepts: first.run.concepts.map(item => item.id === target.id ? { ...item, title: '', differentiation: '' } : item) } };
    const selected: RunSnapshot = { ...followUp({ title: '새 제목', differentiation: '새 차별점' }), previous_run_id: emptied.run.id };
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'fixture', runs: [emptied, selected], selected, original: FIXTURE_ORIGINAL_REQUEST, onSelect: () => {},
      features, evidence, onRerun: vi.fn().mockResolvedValue(undefined), measure,
    })));
    expect(diffs().map(item => item.dataset.field)).toEqual(['제목', '차별점']);
    for (const item of diffs()) expect(item.textContent).toContain('변경 전: (비어 있음)');
    expect(host.textContent).not.toContain('후보 변화가 없습니다');
  });
  it('keeps "후보 변화가 없습니다" when nothing changed and the not_implemented message for drafts', async () => {
    await mount(followUp({}));
    expect(host.textContent).toContain('후보 변화가 없습니다');
    expect(diffs()).toHaveLength(0);
    const draft: RunSnapshot = { ...followUp({ title: '새 제목' }), run: { ...followUp({}).run, status: 'not_implemented', concepts: [] }, output: null };
    await mount(draft);
    expect(host.textContent).toContain('Agent가 연결되지 않아 결과 변화가 없습니다.');
    expect(diffs()).toHaveLength(0);
  });
});
