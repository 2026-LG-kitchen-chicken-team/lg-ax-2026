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
  // A changed output with the same request does not advance the server's user request revision.
  return { ...first, run: { ...first.run, id: 'RUN-TEXT-2', status: 'completed', concepts }, previous_run_id: first.run.id, request_revision: first.request_revision };
}
function withTarget(snapshot: RunSnapshot, id: string, edit: Partial<Concept>): RunSnapshot {
  return { ...snapshot, run: { ...snapshot.run, id, concepts: snapshot.run.concepts.map(item => item.id === target.id ? { ...item, ...edit } : item) } };
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
  it('reports a differentiation-only change verbatim', () => {
    const [change] = conceptDetailChanges(first, followUp({ differentiation: LONG_KOREAN }));
    expect(change.text.title).toBeNull();
    expect(change.text.differentiation).toEqual({ before: target.differentiation, after: LONG_KOREAN });
  });
  it('reports both changes, including an empty previous value', () => {
    const emptied = withTarget(first, 'RUN-TEXT-1', { title: '', differentiation: '' });
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

  async function mount(runs: RunSnapshot[], selected: RunSnapshot) {
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'fixture', runs, selected, original: FIXTURE_ORIGINAL_REQUEST, onSelect: () => {},
      features, evidence, onRerun: vi.fn().mockResolvedValue(undefined), measure,
    })));
  }
  const diffs = () => [...host.querySelectorAll<HTMLElement>('[data-text-change]')];
  const valueOf = (diff: HTMLElement, role: 'before' | 'after') => diff.querySelector<HTMLElement>(`[data-role="${role}"]`)?.textContent;

  it('shows a title-only change instead of "후보 변화가 없습니다"', async () => {
    const selected = followUp({ title: '새 제목' });
    await mount([first, selected], selected);
    expect(host.textContent).not.toContain('후보 변화가 없습니다');
    expect(diffs()).toHaveLength(1);
    expect(diffs()[0].dataset.textChange).toBe('title');
    expect(valueOf(diffs()[0], 'before')).toBe(target.title);
    expect(valueOf(diffs()[0], 'after')).toBe('새 제목');
  });
  it('shows a differentiation-only change with long Korean text verbatim and no HTML/markdown execution', async () => {
    const selected = followUp({ differentiation: LONG_KOREAN });
    await mount([first, selected], selected);
    expect(host.textContent).not.toContain('후보 변화가 없습니다');
    expect(diffs()).toHaveLength(1);
    expect(diffs()[0].dataset.textChange).toBe('differentiation');
    expect(valueOf(diffs()[0], 'before')).toBe(target.differentiation);
    expect(valueOf(diffs()[0], 'after')).toBe(LONG_KOREAN);
    expect(diffs()[0].querySelector('b, script, strong strong')).toBeNull();
    expect(host.querySelectorAll('script')).toHaveLength(0);
  });
  it('shows both changes and labels an empty previous value without inventing text', async () => {
    const emptied = withTarget(first, 'RUN-TEXT-1', { title: '', differentiation: '' });
    const selected: RunSnapshot = { ...followUp({ title: '새 제목', differentiation: '새 차별점' }), previous_run_id: emptied.run.id };
    await mount([emptied, selected], selected);
    expect(diffs().map(item => item.dataset.textChange)).toEqual(['title', 'differentiation']);
    for (const item of diffs()) {
      expect(item.querySelector('[data-role="before"]')).toBeNull();
      expect(item.querySelector('[data-empty="true"]')!.textContent).toBe('(비어 있음)');
    }
    expect(valueOf(diffs()[0], 'after')).toBe('새 제목');
    expect(valueOf(diffs()[1], 'after')).toBe('새 차별점');
    expect(host.textContent).not.toContain('후보 변화가 없습니다');
  });
  it('shows title and differentiation changes together with the status change kept', async () => {
    const selected = followUp({ title: '새 제목', differentiation: '새 차별점', status: 'rejected' });
    await mount([first, selected], selected);
    expect(diffs().map(item => item.dataset.textChange)).toEqual(['title', 'differentiation']);
    expect(host.querySelector('.status-flow')!.textContent).toContain('제외');
  });
  it('keeps "후보 변화가 없습니다" when nothing changed and the not_implemented message for drafts', async () => {
    const same = followUp({});
    await mount([first, same], same);
    expect(host.textContent).toContain('후보 변화가 없습니다');
    expect(diffs()).toHaveLength(0);
    const draft: RunSnapshot = { ...followUp({ title: '새 제목' }), run: { ...same.run, status: 'not_implemented', concepts: [] }, output: null };
    await mount([first, draft], draft);
    expect(host.textContent).toContain('Agent가 연결되지 않아 결과 변화가 없습니다.');
    expect(diffs()).toHaveLength(0);
  });
});
