// @vitest-environment jsdom
// PM review of #158 (head 700cac9): after reading January's reviews, clicking May kept January's page (and its
// "add to planning" button) under the May title, and a slow earlier reply could overwrite the newer bucket. These DOM
// tests drive the panel against a mocked live workspace whose replies resolve in a chosen order. Synthetic fixture data
// only; no collector or server is involved (the real collector path is still the 501 shown in record 026).
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BootstrapData, ProductGroup } from './domain';
import { FIXTURE_TREND_MONTH, fixtureTrendEvidence } from './fixtures/reviewTrends.fixture';
import type { LiveWorkspace } from './liveWorkspace';
import { ReviewTrendsPanel } from './ReviewTrendsPanel';
import { aggregateProblems, topicsOf, trendCells } from './reviewTrends';
import type { TrendAggregate } from './reviewTrends';
import type { ReviewTrendData, TrendEvidenceData } from './workspace';
import * as downloads from './PlanningViews';

const AGGREGATE: TrendAggregate = {
  ...FIXTURE_TREND_MONTH, filters: { ...FIXTURE_TREND_MONTH.filters, topic_ids: [] },
};
const MODEL = AGGREGATE.filters.model_id;
const TOPIC = topicsOf(AGGREGATE)[0];
const CELLS = trendCells(AGGREGATE, TOPIC);
const VALUE = CELLS.map((cell, index) => ({ cell, index })).filter(item => item.cell.state === 'value');
const [A, B] = VALUE;
const page = (bucketId: string, offset = 0, limit = 50) => fixtureTrendEvidence(AGGREGATE, bucketId, TOPIC, offset, limit);
const ids = (data: TrendEvidenceData) => data.evidence.map(item => String(item.id));

// Assignment check "분모0": every in-scope review is undated, so the whole period has no denominator.
const ZERO: TrendAggregate = {
  ...AGGREGATE, aggregate_id: `TREND-${'z'.repeat(64)}`,
  counts: { ...AGGREGATE.counts, in_scope_review_count: 10, input_review_count: 10 + AGGREGATE.counts.excluded_out_of_scope_count,
    excluded_undated_count: 10, excluded_outside_period_count: 0, duplicate_count: 0, eligible_unique_review_count: 0, unclassified_review_count: 0 },
  buckets: AGGREGATE.buckets.map(bucket => ({ ...bucket, total_reviews: 0,
    topics: bucket.topics.map(topic => ({ ...topic, topic_review_count: 0, ratio: null, evidence_count: 0, evidence_ids: [], evidence_ids_truncated: false })) })),
};

function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

const DATA: BootstrapData = {
  products: [{ model_id: MODEL, product_group: 'fridge', document_version: 'synthetic-trend.v1' }],
  evidence: [{ id: 'R-1', model_id: MODEL, document_version: 'synthetic-trend.v1', source_type: 'review',
    source_id: AGGREGATE.filters.source_ids[0], source_kind: 'synthetic', text: '합성 리뷰', locator: { row: 1 }, feature_ids: [] }],
  reviews: [], features: [], manifest: { dataset_version: AGGREGATE.filters.dataset_version }, contract_version: '0.1.0',
};
function liveWorkspace(scopeVersion: number, trendEvidence: LiveWorkspace['trendEvidence'], connection: LiveWorkspace['connection'] = 'connected', aggregate: TrendAggregate = AGGREGATE): LiveWorkspace {
  return {
    connection, scopeVersion,
    project: { project: { id: 'PROJECT-TREND-FIXTURE', dataset_version: AGGREGATE.filters.dataset_version,
      request: { product_group: 'fridge', model_ids: [MODEL], dataset_version: AGGREGATE.filters.dataset_version } },
      owner_id: 'fixture-owner', dataset_sha256: AGGREGATE.dataset_sha256, document_versions: { [MODEL]: 'synthetic-trend.v1' } },
    reviewTrends: vi.fn().mockResolvedValue({ aggregate }),
    trendEvidence,
  } as unknown as LiveWorkspace;
}

describe('review trends drill-down accepts only the latest matching evidence (PM review of #158)', () => {
  let host: HTMLDivElement;
  let root: Root;
  let onUse: ReturnType<typeof vi.fn<(note: string, modelId: string) => void>>;
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); onUse = vi.fn<(note: string, modelId: string) => void>(); vi.spyOn(downloads, 'download').mockImplementation(() => undefined); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  const render = async (workspace: LiveWorkspace, options: { modelId?: string; data?: BootstrapData; productGroup?: ProductGroup } = {}) => {
    await act(async () => root.render(createElement(ReviewTrendsPanel, { mode: 'live', workspace, data: options.data ?? DATA,
      modelId: options.modelId ?? MODEL, productGroup: options.productGroup ?? 'fridge', onUseInPlanning: onUse })));
  };
  const openLive = async (workspace: LiveWorkspace) => {
    await render(workspace);
    await act(async () => host.querySelectorAll<HTMLInputElement>('input[name="trend-source"]')[1].click());
    await query();
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(CELLS.length);
  };
  const click = async (index: number) => { await act(async () => host.querySelectorAll<HTMLButtonElement>('.trend-bar')[index].click()); };
  const settle = async (fn: () => void) => { await act(async () => { fn(); await Promise.resolve(); }); };
  const title = () => host.querySelector('.trend-drilldown h4')?.textContent ?? '';
  const shownIds = () => [...host.querySelectorAll('.trend-evidence .id')].map(node => node.textContent);
  const addButton = () => [...host.querySelectorAll<HTMLButtonElement>('.trend-drilldown button')].find(node => node.textContent?.includes('기획 요청에 추가'));
  const exportButton = () => host.querySelector<HTMLButtonElement>('.trend-export button');
  const query = async () => {
    // The mocked fixed aggregate ends mid-June; request exactly that period rather than the form's July default.
    await act(async () => {
      const end = host.querySelectorAll<HTMLInputElement>('form input[type="date"]')[1];
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(end, AGGREGATE.filters.end_date_exclusive);
      end.dispatchEvent(new Event('input', { bubbles: true }));
      end.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await act(async () => { host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
  };

  it('changing the selected product/model clears the old chart, evidence and export, without querying a fallback model', async () => {
    const workspace = liveWorkspace(0, vi.fn(async (_aggregate, bucket) => page(bucket)));
    await openLive(workspace); await click(A.index);
    await act(async () => exportButton()!.click());
    expect(downloads.download).toHaveBeenCalledOnce();
    expect(addButton()).toBeDefined();

    await render(workspace, { modelId: 'DISHWASHER-A', productGroup: 'dishwasher' });
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(0);
    expect(shownIds()).toEqual([]);
    expect(addButton()).toBeUndefined();
    expect(exportButton()).toBeNull();
    expect(host.querySelector('[data-model-scope="invalid"]')?.textContent).toContain('새 프로젝트');
    expect(host.querySelector<HTMLButtonElement>('form button')!.disabled).toBe(true);
    // Even a directly dispatched submit must not silently use the old project's first model.
    await query();
    expect(workspace.reviewTrends).toHaveBeenCalledOnce();
    expect(onUse).not.toHaveBeenCalled();
    expect(downloads.download).toHaveBeenCalledOnce();
  });

  it.each(['project dataset', 'document version', 'review source', 'source kind', 'source content'] as const)(
    'a changed %s with the same project/model IDs invalidates a completed page and its snapshot', async changed => {
      const workspace = liveWorkspace(0, vi.fn(async (_aggregate, bucket) => page(bucket)));
      await openLive(workspace); await click(A.index);
      expect(addButton()).toBeDefined(); expect(exportButton()).not.toBeNull();
      const next = { ...workspace, project: structuredClone(workspace.project) };
      const data = structuredClone(DATA);
      if (changed === 'project dataset') next.project!.dataset_sha256 = 'b'.repeat(64);
      if (changed === 'document version') next.project!.document_versions[MODEL] = 'synthetic-trend.v2';
      if (changed === 'review source') data.evidence[0].source_id = 'SOURCE-REPLACED';
      if (changed === 'source kind') data.evidence[0].source_kind = 'public';
      if (changed === 'source content') data.evidence[0].text = '같은 ID의 교체된 원문';
      await render(next, { data });
      expect(host.querySelectorAll('.trend-bar')).toHaveLength(0);
      expect(shownIds()).toEqual([]); expect(addButton()).toBeUndefined(); expect(exportButton()).toBeNull();
      expect(onUse).not.toHaveBeenCalled(); expect(downloads.download).not.toHaveBeenCalled();
      expect(workspace.reviewTrends).toHaveBeenCalledOnce();
    },
  );

  it('a late aggregate cannot restore an old scope even after switching away and back to the same model', async () => {
    const reply = deferred<ReviewTrendData>();
    const workspace = liveWorkspace(0, vi.fn());
    workspace.reviewTrends = vi.fn(() => reply.promise);
    await render(workspace);
    await act(async () => host.querySelectorAll<HTMLInputElement>('input[name="trend-source"]')[1].click());
    await query();
    await render(workspace, { modelId: 'DISHWASHER-A', productGroup: 'dishwasher' });
    await render(workspace);
    await settle(() => reply.resolve({ aggregate: AGGREGATE, contract_version: '0.1.0' } as unknown as ReviewTrendData));
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(0);
    expect(exportButton()).toBeNull(); expect(addButton()).toBeUndefined();
  });

  it('a source scope change rejects a late original-text reply and keeps it out of planning and exports', async () => {
    const reply = deferred<TrendEvidenceData>();
    const workspace = liveWorkspace(0, vi.fn(() => reply.promise));
    await openLive(workspace); await click(A.index);
    const data = structuredClone(DATA); data.evidence[0].document_version = 'synthetic-trend.v2';
    await render(workspace, { data });
    await settle(() => reply.resolve(page(A.cell.bucket.bucket_id)));
    expect(host.querySelector('.trend-drilldown')).toBeNull();
    expect(shownIds()).toEqual([]); expect(addButton()).toBeUndefined(); expect(exportButton()).toBeNull();
    expect(onUse).not.toHaveBeenCalled(); expect(downloads.download).not.toHaveBeenCalled();
  });

  it('a fresh source snapshot remains usable and exportable when the older aggregate finishes afterwards', async () => {
    const oldReply = deferred<ReviewTrendData>();
    const fresh = structuredClone(AGGREGATE);
    fresh.aggregate_id = `TREND-${'c'.repeat(64)}`;
    fresh.dataset_sha256 = 'b'.repeat(64);
    fresh.filters.source_ids = ['SOURCE-REPLACED'];
    const reviewTrends = vi.fn().mockImplementationOnce(() => oldReply.promise)
      .mockResolvedValue({ aggregate: fresh, contract_version: '0.1.0' });
    const evidence = vi.fn(async (_aggregate: string, bucket: string) => {
      const result = page(bucket);
      return { ...result, aggregate_id: fresh.aggregate_id,
        evidence: result.evidence.map(item => ({ ...item, source_id: 'SOURCE-REPLACED' })) };
    });
    const workspace = liveWorkspace(0, evidence); workspace.reviewTrends = reviewTrends;
    await render(workspace);
    await act(async () => host.querySelectorAll<HTMLInputElement>('input[name="trend-source"]')[1].click());
    await query();
    const next = { ...workspace, project: structuredClone(workspace.project) };
    next.project!.dataset_sha256 = 'b'.repeat(64);
    const data = structuredClone(DATA); data.evidence[0].source_id = 'SOURCE-REPLACED';
    await render(next, { data });
    await query();
    await settle(() => oldReply.resolve({ aggregate: AGGREGATE, contract_version: '0.1.0' } as unknown as ReviewTrendData));
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(CELLS.length);
    await click(A.index);
    expect(shownIds()).toEqual(ids(page(A.cell.bucket.bucket_id)));
    await act(async () => exportButton()!.click());
    const doc = JSON.parse(String(vi.mocked(downloads.download).mock.calls[0][2]));
    expect(doc.aggregate_id).toBe(fresh.aggregate_id);
    expect(doc.aggregate.dataset_sha256).toBe('b'.repeat(64));
    expect(doc.aggregate.filters.source_ids).toEqual(['SOURCE-REPLACED']);
    expect(doc.viewed_evidence.evidence_ids).toEqual(ids(page(A.cell.bucket.bucket_id)));
    await act(async () => addButton()!.click());
    expect(String(onUse.mock.calls[0][0])).toContain(fresh.aggregate_id);
    expect(String(onUse.mock.calls[0][0])).not.toContain(AGGREGATE.aggregate_id);
  });

  it.each(['model', 'source', 'dataset', 'period', 'topic'] as const)('rejects a server aggregate for a different requested %s scope', async changed => {
    const wrong = structuredClone(AGGREGATE);
    if (changed === 'model') wrong.filters.model_id = 'DISHWASHER-A';
    if (changed === 'source') wrong.filters.source_ids = ['SOURCE-OTHER'];
    if (changed === 'dataset') wrong.dataset_sha256 = 'b'.repeat(64);
    if (changed === 'period') wrong.filters.end_date_exclusive = '2026-08-01';
    if (changed === 'topic') wrong.filters.topic_ids = ['cleaning'];
    await render(liveWorkspace(0, vi.fn(), 'connected', wrong));
    await act(async () => host.querySelectorAll<HTMLInputElement>('input[name="trend-source"]')[1].click());
    await query();
    expect(host.querySelector('[data-code="CONTRACT_MISMATCH"]')?.textContent).toContain('요청과 다릅니다');
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(0); expect(exportButton()).toBeNull();
  });

  it('rejects original text from a different model/source even when its aggregate/bucket/topic IDs match', async () => {
    const wrong = page(A.cell.bucket.bucket_id);
    wrong.evidence = wrong.evidence.map(item => ({ ...item, model_id: 'DISHWASHER-A', source_id: 'SOURCE-OTHER' }));
    await openLive(liveWorkspace(0, vi.fn(async () => wrong)));
    await click(A.index);
    expect(host.querySelector('.trend-drilldown [role="alert"]')?.textContent).toContain('모델·자료 출처');
    expect(shownIds()).toEqual([]); expect(addButton()).toBeUndefined();
    await act(async () => exportButton()!.click());
    const doc = JSON.parse(String(vi.mocked(downloads.download).mock.calls[0][2]));
    expect(doc.viewed_evidence).toBeNull();
    expect(onUse).not.toHaveBeenCalled();
  });

  it('rejects original text from a different pinned document version even when every lookup key and source matches', async () => {
    const wrong = page(A.cell.bucket.bucket_id);
    wrong.evidence = wrong.evidence.map(item => ({ ...item, document_version: 'synthetic-trend.v2' }));
    await openLive(liveWorkspace(0, vi.fn(async () => wrong)));
    await click(A.index);
    expect(host.querySelector('.trend-drilldown [role="alert"]')?.textContent).toContain('문서 버전');
    expect(shownIds()).toEqual([]); expect(addButton()).toBeUndefined();
    await act(async () => exportButton()!.click());
    const doc = JSON.parse(String(vi.mocked(downloads.download).mock.calls[0][2]));
    expect(doc.viewed_evidence).toBeNull();
    expect(onUse).not.toHaveBeenCalled();
  });

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

  it('a zero denominator draws every bucket as no data (never 0% or NaN) and says why', async () => {
    expect(aggregateProblems(ZERO)).toEqual([]);
    const evidence = vi.fn();
    await render(liveWorkspace(0, evidence, 'connected', ZERO));
    await act(async () => host.querySelectorAll<HTMLInputElement>('input[name="trend-source"]')[1].click());
    await query();
    const bars = [...host.querySelectorAll<HTMLButtonElement>('.trend-bar')];
    expect(bars).toHaveLength(ZERO.buckets.length);
    expect(bars.every(bar => bar.classList.contains('empty') && bar.textContent!.includes('자료 없음'))).toBe(true);
    expect(host.querySelector('.trend-chart')!.textContent).not.toMatch(/NaN|Infinity|%/);
    expect(host.querySelector('[data-denominator="zero"]')?.textContent).toContain('분모 0건');
    expect(host.querySelector('.trend-counts')!.textContent).toContain('날짜 없음 제외10건');
    await click(0);
    expect(host.querySelector('.trend-drilldown')!.textContent).toContain('유효한 리뷰가 없습니다');
    expect(evidence).not.toHaveBeenCalled();
    expect(addButton()).toBeUndefined();
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
