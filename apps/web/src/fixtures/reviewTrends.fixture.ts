// Explicit SYNTHETIC review-trend aggregates for the web panel (Issue #149) while the approved DATA collector is not
// connected (the server answers NOT_IMPLEMENTED). Dates, counts and texts are invented for the screen flow only. They
// are not approved source data, a computed snapshot, customer demand or sales evidence. The numbers below are typed in
// by hand and must pass aggregateProblems() (checked in reviewTrends.test.ts) so the chart is exercised on consistent data.
import type { Evidence } from '../domain';
import type { TrendAggregate, TrendBucket } from '../reviewTrends';
import type { ReviewTrendFilters, TrendEvidenceData } from '../workspace';

export const FIXTURE_TREND_NOTICE = '합성 fixture · 날짜·건수·원문은 화면 흐름 확인용으로 만든 값이며 실제 집계, 고객 수요나 판매량의 근거가 아닙니다.';
const MODEL = 'FRIDGE-A';
const SOURCE = 'SOURCE-TREND-SYNTHETIC';
const DOC = 'synthetic-trend.v1';
const TEXTS: Record<string, string> = {
  cleaning: '선반 위 식품을 다 꺼내야 해서 청소가 번거로워요',
  odor: '김치 냄새가 다른 칸 식품에 배어요',
};

type Row = [id: string, start: string, end: string, label: string, partial: boolean, total: number, counts: Record<string, number>];
function bucketsFrom(rows: Row[], topics: string[]): TrendBucket[] {
  return rows.map(([id, start, end, label, partial, total, counts]) => ({
    bucket_id: id, period_start: start, period_end_exclusive: end, label, partial_period: partial, total_reviews: total,
    topics: topics.map(topic => {
      const n = counts[topic] ?? 0;
      const ids = Array.from({ length: n }, (_, index) => `EV-TREND-${id}-${topic}-${String(index + 1).padStart(2, '0')}`);
      return { topic_id: topic, topic_review_count: n, ratio: total ? n / total : null, evidence_count: n, evidence_ids: ids, evidence_ids_truncated: false };
    }),
  }));
}

function aggregate(id: string, filters: ReviewTrendFilters, counts: TrendAggregate['counts'], buckets: TrendBucket[]): TrendAggregate {
  return {
    aggregate_id: `TREND-${id.padEnd(64, '0')}`, project_id: filters.project_id,
    dataset_version: filters.dataset_version, dataset_sha256: 'e'.repeat(64),
    annotation_version: 'synthetic-trend-annotations.v1', annotation_sha256: 'f'.repeat(64),
    trend_contract_version: 'review-trends.v1', filters, timezone: 'Asia/Seoul',
    aggregation_version: 'review-trends.aggregate.v1', classification: { method: 'rule', model_id: null, revision: 'synthetic-rules.v1' },
    topic_taxonomy_version: 'topics.v1', dedup_policy_version: 'scoped-original-review.v1',
    counts, buckets,
    warnings: ['합성 fixture이며 실제 집계 또는 고객 수요의 증거가 아닙니다.', '리뷰 수는 판매량을 뜻하지 않습니다.'],
    notes: '날짜가 없는 리뷰는 월·계절 수치에서 제외되고 제외 건수로만 표시됩니다.',
  };
}

const base = { project_id: 'PROJECT-TREND-FIXTURE', model_id: MODEL, source_ids: [SOURCE], dataset_version: 'synthetic-trend-fixture.v1', topic_ids: ['cleaning', 'odor'], source_kind: 'synthetic', timezone: 'Asia/Seoul' } as const;

// Monthly, 2026-01-01 to 2026-06-16 (June is a partial period). February has no reviews: an empty bucket, not 0%.
export const FIXTURE_TREND_MONTH: TrendAggregate = aggregate('a1', { ...base, source_ids: [SOURCE], topic_ids: ['cleaning', 'odor'], start_date: '2026-01-01', end_date_exclusive: '2026-06-16', granularity: 'month' }, {
  input_review_count: 120, excluded_out_of_scope_count: 20, in_scope_review_count: 100, excluded_undated_count: 10,
  excluded_outside_period_count: 4, duplicate_count: 2, eligible_unique_review_count: 84, unclassified_review_count: 3,
}, bucketsFrom([
  ['MONTH-2026-01', '2026-01-01', '2026-02-01', '2026년 1월', false, 12, { cleaning: 5, odor: 1 }],
  ['MONTH-2026-02', '2026-02-01', '2026-03-01', '2026년 2월', false, 0, {}],
  ['MONTH-2026-03', '2026-03-01', '2026-04-01', '2026년 3월', false, 8, { cleaning: 2, odor: 3 }],
  ['MONTH-2026-04', '2026-04-01', '2026-05-01', '2026년 4월', false, 25, { cleaning: 6, odor: 9 }],
  ['MONTH-2026-05', '2026-05-01', '2026-06-01', '2026년 5월', false, 30, { cleaning: 7, odor: 15 }],
  ['MONTH-2026-06', '2026-06-01', '2026-07-01', '2026년 6월', true, 9, { cleaning: 1, odor: 5 }],
], ['cleaning', 'odor']));

// Seasonal, winter 2025 = [2025-12-01, 2026-03-01). Each winter keeps its own year; winters are never merged.
export const FIXTURE_TREND_SEASON: TrendAggregate = aggregate('b2', { ...base, source_ids: [SOURCE], topic_ids: ['cleaning', 'odor'], start_date: '2025-12-01', end_date_exclusive: '2026-09-01', granularity: 'season' }, {
  input_review_count: 150, excluded_out_of_scope_count: 20, in_scope_review_count: 130, excluded_undated_count: 6,
  excluded_outside_period_count: 0, duplicate_count: 3, eligible_unique_review_count: 121, unclassified_review_count: 4,
}, bucketsFrom([
  ['SEASON-2025-WINTER', '2025-12-01', '2026-03-01', '2025년 겨울', false, 18, { cleaning: 7, odor: 2 }],
  ['SEASON-2026-SPRING', '2026-03-01', '2026-06-01', '2026년 봄', false, 63, { cleaning: 15, odor: 27 }],
  ['SEASON-2026-SUMMER', '2026-06-01', '2026-09-01', '2026년 여름', false, 40, { cleaning: 4, odor: 26 }],
], ['cleaning', 'odor']));

export const FIXTURE_TRENDS: Record<ReviewTrendFilters['granularity'], TrendAggregate | null> = { month: FIXTURE_TREND_MONTH, season: FIXTURE_TREND_SEASON, year: null };

/** Drill-down page for the fixture: only reviews that belong to that bucket/topic of that aggregate. */
export function fixtureTrendEvidence(aggregate: TrendAggregate, bucketId: string, topicId: string, offset = 0, limit = 50): TrendEvidenceData {
  const bucket = aggregate.buckets.find(item => item.bucket_id === bucketId);
  const topic = bucket?.topics.find(item => item.topic_id === topicId);
  const ids = topic?.evidence_ids ?? [];
  const page = ids.slice(offset, offset + limit);
  const evidence: Evidence[] = page.map((id, index) => ({
    id, model_id: MODEL, document_version: DOC, source_kind: 'synthetic', source_type: 'review', source_id: SOURCE,
    locator: { row: offset + index + 2 }, text: `${TEXTS[topicId] ?? topicId} (합성 ${bucket!.label} #${offset + index + 1})`, feature_ids: [],
  }));
  return {
    project_id: aggregate.project_id, aggregate_id: aggregate.aggregate_id, bucket_id: bucketId, topic_id: topicId,
    offset, limit, total: ids.length, next_offset: offset + limit < ids.length ? offset + limit : null,
    evidence: evidence as unknown as Array<Record<string, unknown>>, contract_version: '0.1.0',
  };
}
