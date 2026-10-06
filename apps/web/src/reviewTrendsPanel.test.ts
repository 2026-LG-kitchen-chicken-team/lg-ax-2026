// @vitest-environment jsdom
// PM review of #158 (head 700cac9): after reading January's reviews, clicking May kept January's page (and its
// "add to planning" button) under the May title, and a slow earlier reply could overwrite the newer bucket. These DOM
// tests drive the panel against a mocked live workspace whose replies resolve in a chosen order. Synthetic fixture data
// only; no collector or server is involved (the real collector path is still the 501 shown in record 026).
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BootstrapData } from './domain';
import { FIXTURE_TREND_MONTH, fixtureTrendEvidence } from './fixtures/reviewTrends.fixture';
import type { LiveWorkspace } from './liveWorkspace';
import { ReviewTrendsPanel } from './ReviewTrendsPanel';
import { topicsOf, trendCells } from './reviewTrends';
import type { TrendEvidenceData } from './workspace';

const AGGREGATE = FIXTURE_TREND_MONTH;
const MODEL = AGGREGATE.filters.model_id;
const TOPIC = topicsOf(AGGREGATE)[0];
const CELLS = trendCells(AGGREGATE, TOPIC);
const VALUE = CELLS.map((cell, index) => ({ cell, index })).filter(item => item.cell.state === 'value');
const [A, B] = VALUE;
const page = (bucketId: string, offset = 0, limit = 50) => fixtureTrendEvidence(AGGREGATE, bucketId, TOPIC, offset, limit);
const ids = (data: TrendEvidenceData) => data.evidence.map(item => String(item.id));

function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

const DATA = { evidence: [{ id: 'R-1', model_id: MODEL, source_type: 'review', source_id: AGGREGATE.filters.source_ids[0], source_kind: 'synthetic' }] } as unknown as BootstrapData;
function liveWorkspace(scopeVersion: number, trendEvidence: LiveWorkspace['trendEvidence'], connection: LiveWorkspace['connection'] = 'connected'): LiveWorkspace {
  return {
    connection, scopeVersion,
    project: { project: { id: 'PROJECT-TREND-FIXTURE', request: { model_ids: [MODEL], dataset_version: AGGREGATE.filters.dataset_version } } },
    reviewTrends: vi.fn().mockResolvedValue({ aggregate: AGGREGATE }),
    trendEvidence,
  } as unknown as LiveWorkspace;
}

describe('review trends drill-down accepts only the latest matching evidence (PM review of #158)', () => {
  let host: HTMLDivElement;
  let root: Root;
  let onUse: ReturnType<typeof vi.fn<(note: string, modelId: string) => void>>;
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); onUse = vi.fn<(note: string, modelId: string) => void>(); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

  const render = async (workspace: LiveWorkspace) => {
    await act(async () => root.render(createElement(ReviewTrendsPanel, { mode: 'live', workspace, data: DATA, modelId: MODEL, onUseInPlanning: onUse })));
  };
  const openLive = async (workspace: LiveWorkspace) => {
    await render(workspace);
    await act(async () => host.querySelectorAll<HTMLInputElement>('input[name="trend-source"]')[1].click());
    await act(async () => { host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(CELLS.length);
  };
  const click = async (index: number) => { await act(async () => host.querySelectorAll<HTMLButtonElement>('.trend-bar')[index].click()); };
  const settle = async (fn: () => void) => { await act(async () => { fn(); await Promise.resolve(); }); };
  const title = () => host.querySelector('.trend-drilldown h4')?.textContent ?? '';
  const shownIds = () => [...host.querySelectorAll('.trend-evidence .id')].map(node => node.textContent);
  const addButton = () => [...host.querySelectorAll<HTMLButtonElement>('.trend-drilldown button')].find(node => node.textContent?.includes('기획 요청에 추가'));

  it('has two value buckets with different evidence to compare', () => {
    expect(A && B).toBeTruthy();
    expect(ids(page(A.cell.bucket.bucket_id))).not.toEqual(ids(page(B.cell.bucket.bucket_id)));
  });

  it('A then B with replies in reverse order shows and sends only B', async () => {
    const replies = { [A.cell.bucket.bucket_id]: deferred<TrendEvidenceData>(), [B.cell.bucket.bucket_id]: deferred<TrendEvidenceData>() };
    await openLive(liveWorkspace(0, vi.fn((_aggregate: string, bucket: string) => replies[bucket].promise)));
    await click(A.index); await click(B.index);
    expect(title()).toContain(B.cell.bucket.label);
    expect(host.textContent).toContain('원문을 불러오는 중');
    expect(addButton()).toBeUndefined();

    await settle(() => replies[B.cell.bucket.bucket_id].resolve(page(B.cell.bucket.bucket_id)));
    await settle(() => replies[A.cell.bucket.bucket_id].resolve(page(A.cell.bucket.bucket_id)));
    expect(title()).toContain(B.cell.bucket.label);
    expect(shownIds()).toEqual(ids(page(B.cell.bucket.bucket_id)));

    await act(async () => addButton()!.click());
    expect(onUse).toHaveBeenCalledOnce();
    const note = String(onUse.mock.calls[0][0]);
    for (const id of ids(page(B.cell.bucket.bucket_id))) expect(note).toContain(id);
    for (const id of ids(page(A.cell.bucket.bucket_id))) expect(note).not.toContain(id);
  });

  it('a page loaded for A disappears as soon as B is selected, before B answers', async () => {
    const later = deferred<TrendEvidenceData>();
    await openLive(liveWorkspace(0, vi.fn((_aggregate: string, bucket: string) => bucket === A.cell.bucket.bucket_id ? Promise.resolve(page(bucket)) : later.promise)));
    await click(A.index);
    expect(shownIds()).toEqual(ids(page(A.cell.bucket.bucket_id)));
    await click(B.index);
    expect(title()).toContain(B.cell.bucket.label);
    expect(shownIds()).toEqual([]);
    expect(addButton()).toBeUndefined();
  });

  it('a failed B lookup shows the error, keeps no page, and a late A reply does not fill it', async () => {
    const replies = { [A.cell.bucket.bucket_id]: deferred<TrendEvidenceData>(), [B.cell.bucket.bucket_id]: deferred<TrendEvidenceData>() };
    await openLive(liveWorkspace(0, vi.fn((_aggregate: string, bucket: string) => replies[bucket].promise)));
    await click(A.index); await click(B.index);
    await settle(() => replies[B.cell.bucket.bucket_id].reject(new Error('원문 조회 실패(시험)')));
    await settle(() => replies[A.cell.bucket.bucket_id].resolve(page(A.cell.bucket.bucket_id)));
    expect(host.querySelector('.trend-drilldown [role="alert"]')?.textContent).toContain('원문 조회 실패(시험)');
    expect(shownIds()).toEqual([]);
    expect(addButton()).toBeUndefined();
  });

  it('a reply for a different aggregate/bucket/topic is refused instead of shown', async () => {
    await openLive(liveWorkspace(0, vi.fn(async () => page(A.cell.bucket.bucket_id))));
    await click(B.index);
    expect(host.querySelector('.trend-drilldown [role="alert"]')?.textContent).toContain('집계·구간·주제가 요청과 다릅니다');
    expect(shownIds()).toEqual([]);
  });

  it('a login/project scope change clears the aggregate, the selection and any in-flight reply', async () => {
    const reply = deferred<TrendEvidenceData>();
    const evidence = vi.fn(() => reply.promise);
    await openLive(liveWorkspace(0, evidence));
    await click(A.index);
    await render(liveWorkspace(1, evidence));
    await settle(() => reply.resolve(page(A.cell.bucket.bucket_id)));
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(0);
    expect(host.querySelector('.trend-drilldown')).toBeNull();
    expect(onUse).not.toHaveBeenCalled();
  });

  it('a dropped workspace connection clears the drill-down and ignores the reply that was in flight', async () => {
    const reply = deferred<TrendEvidenceData>();
    const evidence = vi.fn(() => reply.promise);
    await openLive(liveWorkspace(0, evidence));
    await click(A.index);
    await render(liveWorkspace(0, evidence, 'error'));
    await settle(() => reply.resolve(page(A.cell.bucket.bucket_id)));
    // Without a connected workspace the panel falls back to the labelled synthetic fixture; the live page never returns.
    expect(host.querySelector('.trend-drilldown')).toBeNull();
    expect(host.querySelector<HTMLInputElement>('input[name="trend-source"]')!.checked).toBe(true);
    expect(host.querySelectorAll<HTMLInputElement>('input[name="trend-source"]')[1].disabled).toBe(true);
    expect(host.querySelector('.fixture-note')).not.toBeNull();
    expect(onUse).not.toHaveBeenCalled();
  });

  it('locks "add to planning" while more evidence of the same bucket is loading', async () => {
    const more = deferred<TrendEvidenceData>();
    const bucket = A.cell.bucket.bucket_id;
    const first = page(bucket, 0, 1);
    expect(first.next_offset).not.toBeNull();
    await openLive(liveWorkspace(0, vi.fn((_aggregate: string, _bucket: string, _topic: string, offset = 0) => offset ? more.promise : Promise.resolve(first))));
    await click(A.index);
    expect(addButton()!.disabled).toBe(false);
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>('.trend-drilldown button')].find(node => node.textContent === '원문 더 보기')!.click());
    expect(addButton()!.disabled).toBe(true);
    await settle(() => more.resolve(page(bucket, first.next_offset!, 50)));
    expect(addButton()!.disabled).toBe(false);
    expect(shownIds()).toEqual([...ids(first), ...ids(page(bucket, first.next_offset!, 50))]);
  });
});
