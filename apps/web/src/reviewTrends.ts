// Issue #149 (PM-20261006-WEB-TRENDS-QUALITY): display logic for review-trend aggregates (docs/pm/review-trends-contract-v1.md).
// The web never computes counts or ratios from reviews. It reads a fixed aggregate (server or explicit synthetic fixture),
// checks that its numbers are internally consistent before drawing them, and keeps the aggregate ID with every derived
// view so the chart, the drill-down and a planning request all point at the same result.
import type { ReviewTrendFilters } from './workspace';

export interface TrendTopic {
  topic_id: string; topic_review_count: number; ratio: number | null;
  evidence_count: number; evidence_ids: string[]; evidence_ids_truncated: boolean;
}
export interface TrendBucket {
  bucket_id: string; period_start: string; period_end_exclusive: string; label: string;
  partial_period: boolean; total_reviews: number; topics: TrendTopic[];
}
export interface TrendCounts {
  input_review_count: number; excluded_out_of_scope_count: number; in_scope_review_count: number;
  excluded_undated_count: number; excluded_outside_period_count: number; duplicate_count: number;
  eligible_unique_review_count: number; unclassified_review_count: number;
}
export interface TrendAggregate {
  aggregate_id: string; project_id: string; dataset_version: string; trend_contract_version: string;
  filters: ReviewTrendFilters; counts: TrendCounts; buckets: TrendBucket[]; warnings: string[]; notes?: string;
  classification?: { method: string; model_id: string | null; revision: string | null };
  topic_taxonomy_version?: string;
  [key: string]: unknown;
}

/** Below this the panel marks a small sample. It is a reading aid, not a significance test (contract v1). */
export const SMALL_SAMPLE = 20;

// PM decision 2026-10-06 (#176 review): the contract has no polarity, so a topic share is a share of reviews that MENTION
// the topic, never a complaint/sentiment ratio or seasonal demand. Labels name the topic only; DATA candidate topics
// (kitchen-review-topics-candidate.v1) stay labelled as a preview classification wherever the taxonomy says so.
const TOPIC_LABELS: Record<string, string> = {
  cleaning: '청소', odor: '냄새', storage: '수납·정리', noise: '소음', cooling: '냉각', loading: '적재', settings: '설정 반복',
  temporary_storage: '임시 보관', food_findability: '식품 찾기', manual_guidance: '설명서·사용 안내', dish_loading_guidance: '식기 적재 안내',
  rotating_arm_clearance: '회전 노즐 간섭', heating_preset_management: '가열 출력·설정 관리',
};
export const MENTION_NOTE = '비율은 그 주제를 언급한 리뷰의 비율입니다. 감정·불만 분류가 없어 불만 비율이나 계절 수요를 뜻하지 않습니다.';
/** A candidate (not yet approved) topic taxonomy is shown as a preview classification. */
export function taxonomyNote(version: string | null | undefined): string | null {
  if (!version) return null;
  return version.includes('candidate') ? `주제 분류 ${version}: PM 승인 전 미리보기 분류입니다.` : `주제 분류 ${version}`;
}
export function topicLabel(id: string): string {
  return Object.hasOwn(TOPIC_LABELS, id) ? `${TOPIC_LABELS[id]} (${id})` : id;
}

export function percentText(ratio: number | null): string {
  return ratio === null ? '—' : `${(ratio * 100).toFixed(1)}%`;
}

const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;
/** Strict calendar date (no Date.parse roll-over: 2026-02-30 is rejected). */
export function isCalendarDate(value: string): boolean {
  const match = DAY.exec(value);
  if (!match) return false;
  const [year, month, day] = match.slice(1).map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

export interface TrendQueryInput {
  projectId: string; modelId: string; sourceIds: string[]; datasetVersion: string; start: string; end: string;
  granularity: ReviewTrendFilters['granularity']; topicIds: string[]; sourceKind: ReviewTrendFilters['source_kind'];
}
/** Request filters for the server, refusing ranges the contract rejects so nothing is sent for an invalid period. */
export function buildTrendFilters(input: TrendQueryInput): { filters: ReviewTrendFilters } | { error: string } {
  if (!isCalendarDate(input.start) || !isCalendarDate(input.end)) return { error: '시작일과 종료일을 YYYY-MM-DD 형식의 실제 날짜로 입력해 주세요.' };
  if (input.start >= input.end) return { error: '종료일(포함하지 않음)은 시작일보다 뒤여야 합니다.' };
  const [y, m, d] = input.start.split('-').map(Number);
  const limit = `${String(y + 10).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  if (input.end > limit) return { error: '조회 기간은 최대 10년입니다.' };
  if (!input.sourceIds.length) return { error: '이 모델에 조회할 수 있는 리뷰 자료가 없습니다.' };
  const unique = (items: string[]) => [...new Set(items)];
  return { filters: {
    project_id: input.projectId, model_id: input.modelId, source_ids: unique(input.sourceIds).slice(0, 50),
    dataset_version: input.datasetVersion, start_date: input.start, end_date_exclusive: input.end,
    granularity: input.granularity, topic_ids: unique(input.topicIds), source_kind: input.sourceKind, timezone: 'Asia/Seoul',
  } };
}

/**
 * Cross-field checks a client can make without the source reviews. Any problem means the chart is not drawn: a
 * mismatched denominator or ratio would silently mislead the planner.
 */
export function aggregateProblems(aggregate: TrendAggregate): string[] {
  const problems: string[] = [];
  const c = aggregate.counts;
  if (c.input_review_count !== c.in_scope_review_count + c.excluded_out_of_scope_count) problems.push('입력 리뷰 수가 범위 안·범위 밖 합과 다릅니다.');
  if (c.in_scope_review_count !== c.excluded_undated_count + c.excluded_outside_period_count + c.duplicate_count + c.eligible_unique_review_count) {
    problems.push('범위 안 리뷰 수가 날짜 없음·기간 밖·중복·유효 리뷰의 합과 다릅니다.');
  }
  if (c.unclassified_review_count > c.eligible_unique_review_count) problems.push('미분류 리뷰가 유효 리뷰보다 많습니다.');
  const bucketTotal = aggregate.buckets.reduce((sum, bucket) => sum + bucket.total_reviews, 0);
  if (bucketTotal !== c.eligible_unique_review_count) problems.push(`구간 분모의 합(${bucketTotal})이 유효 고유 리뷰 수(${c.eligible_unique_review_count})와 다릅니다.`);
  const allowed = new Set(aggregate.filters.topic_ids);
  let previousEnd: string | null = null;
  for (const bucket of aggregate.buckets) {
    if (bucket.period_start >= bucket.period_end_exclusive) problems.push(`${bucket.label}: 구간 시작이 끝보다 늦습니다.`);
    if (previousEnd !== null && bucket.period_start !== previousEnd) problems.push(`${bucket.label}: 앞 구간과 이어지지 않습니다.`);
    previousEnd = bucket.period_end_exclusive;
    if (bucket.period_start < aggregate.filters.start_date && !bucket.partial_period) problems.push(`${bucket.label}: 조회 시작 전 기간이 포함됐지만 부분 구간 표시가 없습니다.`);
    if (bucket.period_end_exclusive > aggregate.filters.end_date_exclusive && !bucket.partial_period) problems.push(`${bucket.label}: 조회 끝 이후가 포함됐지만 부분 구간 표시가 없습니다.`);
    for (const topic of bucket.topics) {
      const where = `${bucket.label} · ${topic.topic_id}`;
      if (allowed.size && !allowed.has(topic.topic_id)) problems.push(`${where}: 요청하지 않은 주제입니다.`);
      if (topic.topic_review_count > bucket.total_reviews) problems.push(`${where}: 주제 리뷰 수가 분모보다 큽니다.`);
      if (bucket.total_reviews === 0 ? topic.ratio !== null : topic.ratio === null || Math.abs(topic.ratio - topic.topic_review_count / bucket.total_reviews) > 1e-9) {
        problems.push(`${where}: 비율이 리뷰 수/분모와 맞지 않습니다.`);
      }
      if (new Set(topic.evidence_ids).size !== topic.evidence_ids.length) problems.push(`${where}: 근거 ID가 중복됩니다.`);
      if (topic.evidence_ids.length > topic.evidence_count || topic.evidence_ids_truncated !== topic.evidence_ids.length < topic.evidence_count) {
        problems.push(`${where}: 근거 목록과 근거 수·잘림 표시가 맞지 않습니다.`);
      }
    }
  }
  if (previousEnd !== null && aggregate.buckets[0].period_start > aggregate.filters.start_date) problems.push('첫 구간이 조회 시작일보다 늦게 시작합니다.');
  return problems;
}

export type CellState = 'empty' | 'zero' | 'value';
export interface TrendCell {
  bucket: TrendBucket; topic: TrendTopic | null; state: CellState;
  count: number; total: number; ratio: number | null; small: boolean;
}
/** One cell per bucket for one topic. An empty period (no reviews) and a measured 0% stay different states. */
export function trendCells(aggregate: TrendAggregate, topicId: string): TrendCell[] {
  return aggregate.buckets.map(bucket => {
    const topic = bucket.topics.find(item => item.topic_id === topicId) ?? null;
    const count = topic?.topic_review_count ?? 0;
    const state: CellState = bucket.total_reviews === 0 ? 'empty' : count === 0 ? 'zero' : 'value';
    const ratio = bucket.total_reviews === 0 ? null : topic ? topic.ratio : 0;
    return { bucket, topic, state, count, total: bucket.total_reviews, ratio, small: bucket.total_reviews > 0 && bucket.total_reviews < SMALL_SAMPLE };
  });
}

export function topicsOf(aggregate: TrendAggregate): string[] {
  const seen = new Set<string>(aggregate.filters.topic_ids);
  for (const bucket of aggregate.buckets) for (const topic of bucket.topics) seen.add(topic.topic_id);
  return [...seen];
}

/**
 * Text appended to the planning request when the planner carries a selected bucket into a new request. It cites the
 * aggregate ID and evidence IDs (the existing evidence path) instead of resending all review text, and says what the
 * numbers are not. PlanningRequest is closed, so nothing outside the existing fields is added.
 */
export function planningTrendNote(aggregate: TrendAggregate, cell: TrendCell, evidenceIds: string[], fixture: boolean): string {
  const ids = evidenceIds.slice(0, 20);
  const more = evidenceIds.length > ids.length ? ` 외 ${evidenceIds.length - ids.length}건` : '';
  return `[리뷰 동향 근거 · ${aggregate.aggregate_id} · ${aggregate.filters.model_id} · ${cell.bucket.label}${cell.bucket.partial_period ? '(부분 구간)' : ''} · ${topicLabel(cell.topic?.topic_id ?? '')} ${cell.count}/${cell.total}건(${percentText(cell.ratio)})${cell.small ? ' · 작은 표본' : ''} · 근거 ${ids.join(', ')}${more}${fixture ? ' · 합성 fixture' : ''} · 리뷰 수는 판매량·수요 증가를 뜻하지 않음]`;
}

/** One drill-down page the planner actually opened, kept with its exact aggregate/bucket/topic key. */
export interface TrendViewedEvidence { bucket_id: string; topic_id: string; total: number; evidence_ids: string[] }

/**
 * review-trends-20261006.md "집계 스냅샷 내보내기": the aggregate exactly as received (never recomputed or edited), what
 * the planner opened, and where it came from. A fixture snapshot says so; it is not a real collector result.
 */
export interface TrendSnapshotExport {
  kind: 'review_trend_snapshot'; export_version: 1; exported_at: string;
  source: 'synthetic_fixture' | 'server'; aggregate_id: string; consistency_problems: string[];
  aggregate: TrendAggregate; viewed_evidence: TrendViewedEvidence | null; notices: string[];
}

export function trendSnapshotExport(aggregate: TrendAggregate, input: { fixture: boolean; exportedAt: string; viewed: TrendViewedEvidence | null }): TrendSnapshotExport {
  return {
    kind: 'review_trend_snapshot', export_version: 1, exported_at: input.exportedAt,
    source: input.fixture ? 'synthetic_fixture' : 'server', aggregate_id: aggregate.aggregate_id,
    consistency_problems: aggregateProblems(aggregate), aggregate: structuredClone(aggregate),
    viewed_evidence: input.viewed ? structuredClone(input.viewed) : null,
    notices: [
      ...(input.fixture ? ['합성 fixture 집계입니다. 실제 collector 결과나 고객 수요의 증거가 아닙니다.'] : []),
      '리뷰 수와 비율은 판매량이나 수요 증가를 뜻하지 않습니다.',
      MENTION_NOTE,
      ...[taxonomyNote(aggregate.topic_taxonomy_version)].filter((item): item is string => item !== null),
      '"자료 없음"은 그 구간 리뷰가 없다는 뜻이며 0%와 다릅니다.',
      `표본 ${SMALL_SAMPLE}건 미만은 작은 표본이며 통계적 유의성 판정이 아닙니다.`,
    ],
  };
}

const cellText = (cell: TrendCell) => cell.state === 'empty' ? '자료 없음' : `${cell.count}/${cell.total}건 (${percentText(cell.ratio)})${cell.small ? ' · 작은 표본' : ''}`;
const mdCell = (value: string) => value.replace(/\|/g, '\|').replace(/\r?\n/g, ' ');

export function trendSnapshotMarkdown(doc: TrendSnapshotExport): string {
  const a = doc.aggregate;
  const c = a.counts;
  const topics = topicsOf(a);
  const lines = [
    `# 리뷰 동향 집계 스냅샷 · ${a.filters.model_id}`, '',
    `- 집계 ID: \`${doc.aggregate_id}\``,
    `- 출처: ${doc.source === 'synthetic_fixture' ? '합성 fixture(실제 집계 아님)' : '작업실 서버 고정 집계'} · 내보낸 시각 ${doc.exported_at}`,
    `- 기간: ${a.filters.start_date} ~ ${a.filters.end_date_exclusive}(미포함) · ${a.filters.granularity === 'season' ? '계절별' : a.filters.granularity === 'year' ? '연도별' : '월별'} · 시간대 ${a.filters.timezone}`,
    `- 자료: ${a.dataset_version}${typeof a.dataset_sha256 === 'string' ? ` · sha256 ${a.dataset_sha256}` : ''} · ${a.filters.source_kind}`,
    `- 분모(유효 고유 리뷰) ${c.eligible_unique_review_count}건 · 날짜 없음 제외 ${c.excluded_undated_count}건 · 기간 밖 제외 ${c.excluded_outside_period_count}건 · 중복 제외 ${c.duplicate_count}건 · 범위 밖 ${c.excluded_out_of_scope_count}건 · 미분류 ${c.unclassified_review_count}건(분모 포함)`,
    '', `| 구간 | ${topics.map(id => mdCell(topicLabel(id))).join(' | ')} |`, `|---|${topics.map(() => '---').join('|')}|`,
    ...a.buckets.map((bucket, index) => `| ${mdCell(bucket.label)}${bucket.partial_period ? ' (부분 구간)' : ''} | ${topics.map(id => cellText(trendCells(a, id)[index])).join(' | ')} |`),
    '',
  ];
  if (doc.consistency_problems.length) lines.push('## 숫자 불일치(그래프를 그리지 않은 집계)', ...doc.consistency_problems.map(item => `- ${item}`), '');
  if (doc.viewed_evidence) {
    const v = doc.viewed_evidence;
    lines.push('## 열어 본 원문', `- ${v.bucket_id} · ${topicLabel(v.topic_id)} · ${v.total}건 중 ${v.evidence_ids.length}건`, `- 근거 ID: ${v.evidence_ids.join(', ')}`, '');
  }
  lines.push('## 읽을 때 주의', ...[...doc.notices, ...a.warnings].map(item => `- ${item}`), '');
  return lines.join('\n');
}
