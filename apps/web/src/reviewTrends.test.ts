// @vitest-environment jsdom
// Issue #149 (PM-20261006-WEB-TRENDS-QUALITY). Synthetic fixtures and a fake workspace only: no collector, no model.
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './api';
import { FIXTURE_TREND_MONTH, FIXTURE_TREND_SEASON, fixtureTrendEvidence } from './fixtures/reviewTrends.fixture';
import type { LiveWorkspace } from './liveWorkspace';
import { contractErrors } from './planning';
import {
  aggregateProblems, buildTrendFilters, isCalendarDate, percentText, planningTrendNote, topicLabel, trendCells,
} from './reviewTrends';
import type { TrendAggregate } from './reviewTrends';
import { ReviewTrendsPanel } from './ReviewTrendsPanel';

const clone = (value: TrendAggregate) => structuredClone(value);

describe('synthetic fixtures are contract-valid and internally consistent', () => {
  it.each([['month', FIXTURE_TREND_MONTH], ['season', FIXTURE_TREND_SEASON]] as const)('%s aggregate', (_name, aggregate) => {
    expect(contractErrors('ReviewTrendAggregate', aggregate)).toEqual([]);
    expect(contractErrors('ReviewTrendRequest', aggregate.filters)).toEqual([]);
    expect(aggregateProblems(aggregate)).toEqual([]);
    expect(aggregate.warnings.join(' ')).toContain('합성 fixture');
  });

  it('keeps winter 2025 as Dec 2025 to Feb 2026 and never merges winters', () => {
    const winter = FIXTURE_TREND_SEASON.buckets[0];
    expect([winter.bucket_id, winter.period_start, winter.period_end_exclusive]).toEqual(['SEASON-2025-WINTER', '2025-12-01', '2026-03-01']);
  });

  it('evidence pages come from the same aggregate/bucket/topic and are contract-valid', () => {
    const page = fixtureTrendEvidence(FIXTURE_TREND_MONTH, 'MONTH-2026-05', 'odor', 0, 10);
    expect(contractErrors('WorkspaceTrendEvidenceResponse', { ok: true, data: page })).toEqual([]);
    expect([page.total, page.evidence.length, page.next_offset]).toEqual([15, 10, 10]);
    const rest = fixtureTrendEvidence(FIXTURE_TREND_MONTH, 'MONTH-2026-05', 'odor', 10, 10);
    expect([rest.evidence.length, rest.next_offset]).toEqual([5, null]);
    const bucket = FIXTURE_TREND_MONTH.buckets.find(item => item.bucket_id === 'MONTH-2026-05')!;
    expect([...page.evidence, ...rest.evidence].map(item => item.id)).toEqual(bucket.topics.find(item => item.topic_id === 'odor')!.evidence_ids);
    expect(fixtureTrendEvidence(FIXTURE_TREND_MONTH, 'MONTH-2026-02', 'odor').total).toBe(0);
  });
});

describe('aggregateProblems refuses numbers that do not add up', () => {
  it('detects denominator, ratio, empty bucket, topic, evidence and continuity errors', () => {
    const bad = clone(FIXTURE_TREND_MONTH);
    bad.counts.duplicate_count += 1;
    expect(aggregateProblems(bad).join(' ')).toContain('범위 안 리뷰 수');

    const ratio = clone(FIXTURE_TREND_MONTH);
    ratio.buckets[0].topics[0].ratio = 0.9;
    expect(aggregateProblems(ratio).join(' ')).toContain('비율이 리뷰 수/분모와 맞지 않습니다');

    const empty = clone(FIXTURE_TREND_MONTH);
    empty.buckets[1].topics[0].ratio = 0;
    expect(aggregateProblems(empty).join(' ')).toContain('2026년 2월');

    const over = clone(FIXTURE_TREND_MONTH);
    over.buckets[2].topics[1].topic_review_count = 9;
    expect(aggregateProblems(over).join(' ')).toContain('주제 리뷰 수가 분모보다 큽니다');

    const unrequested = clone(FIXTURE_TREND_MONTH);
    unrequested.buckets[0].topics.push({ topic_id: 'noise', topic_review_count: 0, ratio: 0, evidence_count: 0, evidence_ids: [], evidence_ids_truncated: false });
    expect(aggregateProblems(unrequested).join(' ')).toContain('요청하지 않은 주제');

    const truncated = clone(FIXTURE_TREND_MONTH);
    truncated.buckets[0].topics[0].evidence_ids.pop();
    expect(aggregateProblems(truncated).join(' ')).toContain('잘림 표시');

    const gap = clone(FIXTURE_TREND_MONTH);
    gap.buckets.splice(1, 1);
    expect(aggregateProblems(gap).join(' ')).toContain('이어지지 않습니다');

    const total = clone(FIXTURE_TREND_MONTH);
    total.buckets[3].total_reviews = 26;
    total.buckets[3].topics.forEach(topic => { topic.ratio = topic.topic_review_count / 26; });
    expect(aggregateProblems(total).join(' ')).toContain('구간 분모의 합');
  });
});

describe('cells, labels and filters', () => {
  it('keeps an empty period, a measured 0% and small samples distinct', () => {
    const odor = trendCells(FIXTURE_TREND_MONTH, 'odor');
    expect(odor.map(cell => cell.state)).toEqual(['value', 'empty', 'value', 'value', 'value', 'value']);
    expect(odor[1].ratio).toBeNull();
    expect(odor.map(cell => cell.small)).toEqual([true, false, true, false, false, true]);
    const noise = trendCells(FIXTURE_TREND_MONTH, 'noise');
    expect(noise[0]).toMatchObject({ state: 'zero', ratio: 0, count: 0, total: 12 });
    expect(percentText(null)).toBe('—');
    expect(percentText(0.5)).toBe('50.0%');
    expect(topicLabel('odor')).toBe('냄새 (odor)');
    expect(topicLabel('constructor')).toBe('constructor');
  });

  it('builds contract-valid filters and refuses impossible or too long periods before sending', () => {
    const input = { projectId: 'project-1', modelId: 'FRIDGE-A', sourceIds: ['S1', 'S1', 'S2'], datasetVersion: '0.1.0', start: '2026-01-01', end: '2026-07-01', granularity: 'month' as const, topicIds: [], sourceKind: 'synthetic' as const };
    const built = buildTrendFilters(input);
    expect('filters' in built && built.filters.source_ids).toEqual(['S1', 'S2']);
    expect('filters' in built && contractErrors('ReviewTrendRequest', built.filters)).toEqual([]);
    expect(buildTrendFilters({ ...input, start: '2026-02-30' })).toHaveProperty('error');
    expect(buildTrendFilters({ ...input, end: '2026-01-01' })).toHaveProperty('error');
    expect(buildTrendFilters({ ...input, end: '2036-01-02' })).toHaveProperty('error');
    expect(buildTrendFilters({ ...input, end: '2036-01-01' })).toHaveProperty('filters');
    expect(buildTrendFilters({ ...input, sourceIds: [] })).toHaveProperty('error');
    expect([isCalendarDate('2028-02-29'), isCalendarDate('2026-02-29')]).toEqual([true, false]);
  });

  it('a planning note cites the aggregate and evidence IDs, not the review texts, and states what counts are not', () => {
    const cell = trendCells(FIXTURE_TREND_MONTH, 'odor')[4];
    const ids = cell.topic!.evidence_ids;
    const note = planningTrendNote(FIXTURE_TREND_MONTH, cell, ids, true);
    expect(note).toContain(FIXTURE_TREND_MONTH.aggregate_id);
    expect(note).toContain('2026년 5월');
    expect(note).toContain('15/30건(50.0%)');
    expect(note).not.toContain(' 외 '); // 15 IDs: no overflow suffix
    const many = planningTrendNote(FIXTURE_TREND_MONTH, cell, Array.from({ length: 25 }, (_, i) => `E${i}`), false);
    expect(many).toContain('외 5건');
    expect(many).not.toContain('합성 fixture');
    expect(note).toContain('합성 fixture');
    expect(note).toContain('판매량');
    expect(note).not.toContain('냄새가 다른 칸');
  });
});

function fakeWorkspace(overrides: Partial<LiveWorkspace> = {}): LiveWorkspace {
  return {
    connection: 'disconnected', error: null, projects: [], project: null, runs: [], busy: false, scopeVersion: 0,
    connect: vi.fn(), disconnect: vi.fn(), selectProject: vi.fn(), saveRequest: vi.fn(), addRun: vi.fn(), search: vi.fn(),
    reviewTrends: vi.fn(), trendEvidence: vi.fn(), clearError: vi.fn(), ...overrides,
  } as LiveWorkspace;
}

describe('ReviewTrendsPanel', () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
  const button = (label: string) => [...host.querySelectorAll('button')].find(item => item.textContent?.includes(label)) as HTMLButtonElement;

  it('fixture: labelled, denominators shown, empty period distinct, bar opens its own reviews and hands off to planning', async () => {
    const onUseInPlanning = vi.fn();
    await act(async () => root.render(createElement(ReviewTrendsPanel, { mode: 'fixture', workspace: fakeWorkspace(), data: undefined, modelId: 'FRIDGE-A', onUseInPlanning })));
    expect(host.textContent).toContain('합성 fixture');
    expect(host.textContent).toContain('분모(유효 고유 리뷰)84건');
    expect(host.textContent).toContain('날짜 없음 제외10건');
    const bars = [...host.querySelectorAll('.trend-bar')] as HTMLButtonElement[];
    expect(bars).toHaveLength(6);
    expect(bars.every(bar => bar.tagName === 'BUTTON')).toBe(true);
    expect(bars[1].getAttribute('aria-label')).toBe('2026년 2월: 리뷰 없음');
    expect(bars[1].textContent).toContain('자료 없음');
    expect(bars[5].getAttribute('aria-label')).toContain('부분 구간');
    expect(bars[0].getAttribute('aria-label')).toContain('5/12건 41.7% 작은 표본');

    await act(async () => bars[4].click());
    const items = host.querySelectorAll('.trend-evidence li');
    expect(items).toHaveLength(7);
    expect(host.textContent).toContain(`집계 ${FIXTURE_TREND_MONTH.aggregate_id}에 실제 포함된 원문만`);
    await act(async () => button('이 구간을 기획 요청에 추가').click());
    expect(onUseInPlanning).toHaveBeenCalledTimes(1);
    expect(onUseInPlanning.mock.calls[0][0]).toContain('7/30건(23.3%)');
    expect(onUseInPlanning.mock.calls[0][1]).toBe('FRIDGE-A');

    await act(async () => bars[1].click());
    expect(host.textContent).toContain('이 기간에는 유효한 리뷰가 없습니다.');
    expect(host.querySelector('.trend-evidence')).toBeNull();
  });

  it('fixture: refuses to draw an inconsistent aggregate', async () => {
    const bad = clone(FIXTURE_TREND_MONTH);
    bad.counts.eligible_unique_review_count = 90;
    bad.counts.in_scope_review_count = 106; bad.counts.input_review_count = 126;
    const module = await import('./fixtures/reviewTrends.fixture');
    const original = module.FIXTURE_TRENDS.month;
    module.FIXTURE_TRENDS.month = bad;
    try {
      await act(async () => root.render(createElement(ReviewTrendsPanel, { mode: 'fixture', workspace: fakeWorkspace(), data: undefined, modelId: 'FRIDGE-A', onUseInPlanning: vi.fn() })));
      expect(host.textContent).toContain('그래프를 그리지 않습니다');
      expect(host.querySelectorAll('.trend-bar')).toHaveLength(0);
    } finally { module.FIXTURE_TRENDS.month = original; }
  });

  it('live: a disconnected collector (501) is shown as not connected and no numbers are invented', async () => {
    const reviewTrends = vi.fn().mockRejectedValue(new ApiError('NOT_IMPLEMENTED', '승인된 리뷰 동향 집계기가 아직 연결되지 않았습니다.'));
    const project = { project: { id: 'project-1', request: { model_ids: ['FRIDGE-A'], dataset_version: '0.1.0' } } } as unknown as LiveWorkspace['project'];
    const data = { products: [], reviews: [], features: [], manifest: {}, contract_version: '0.1.0', evidence: [
      { id: 'R1', model_id: 'FRIDGE-A', document_version: '1.0', source_kind: 'synthetic', source_type: 'review', source_id: 'REVIEWS-CSV', locator: { row: 2 }, text: 't', feature_ids: [] },
    ] };
    await act(async () => root.render(createElement(ReviewTrendsPanel, { mode: 'live', workspace: fakeWorkspace({ connection: 'connected', project, reviewTrends }), data, modelId: 'FRIDGE-A', onUseInPlanning: vi.fn() })));
    const live = [...host.querySelectorAll('input[name="trend-source"]')][1] as HTMLInputElement;
    expect(live.disabled).toBe(false);
    await act(async () => live.click());
    await act(async () => button('동향 조회').click());
    expect(reviewTrends).toHaveBeenCalledTimes(1);
    const filters = reviewTrends.mock.calls[0][0];
    expect(contractErrors('ReviewTrendRequest', filters)).toEqual([]);
    expect(filters).toMatchObject({ project_id: 'project-1', model_id: 'FRIDGE-A', source_ids: ['REVIEWS-CSV'], granularity: 'month' });
    const message = host.querySelector('[data-code="NOT_IMPLEMENTED"]');
    expect(message?.textContent).toContain('실제 동향 집계 미연결');
    expect(host.querySelectorAll('.trend-bar')).toHaveLength(0);
    expect(host.textContent).not.toContain('분모(유효 고유 리뷰)');
  });
});
