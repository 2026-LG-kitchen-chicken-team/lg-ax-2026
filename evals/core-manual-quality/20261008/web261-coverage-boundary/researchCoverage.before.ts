import type { PlanningBrief } from './research';

// Summary citation coverage (record 최길웅-20261008-067). CORE writes runtime.summary_reference_coverage (PR #251,
// public_planning.summary_reference_coverage); its meaning and checks were fixed by CORE on #234 (comment 6045972338).
// The public API does not pass it yet, so today every brief reads 'not_provided'. Nothing is computed or filled in here:
// a missing block stays missing, an inconsistent one is rejected, and M=0 (ratio null) is a valid state of its own.
//   N input_customer_source_count · M denominator (successful discovery) · C covered · M-C unreferenced · N-M unprocessed

const POLARITIES = ['positive', 'negative', 'mixed'] as const;
type Polarity = typeof POLARITIES[number];
export interface CoverageView {
  input: number; denominator: number; covered: number; unreferenced: number; unprocessed: number;
  ratio: number | null; overlapping: number;
  polaritySources: Record<Polarity, number>; summaryItems: Record<Polarity, number>;
}
export type CoverageState = { state: 'not_provided'; reason: 'absent' | 'inheritance_invalid' } | { state: 'malformed'; reason: string } | { state: 'ok'; value: CoverageView };

const isCount = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0;
const isIdList = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string')
  && value.every((item, index) => index === 0 || (value[index - 1] as string) < item);

export function summaryCoverageView(brief: PlanningBrief): CoverageState {
  const runtime = brief.runtime ?? {};
  if (runtime.summary_reference_coverage_inheritance === 'invalid_previous_metadata') return { state: 'not_provided', reason: 'inheritance_invalid' };
  const raw = runtime.summary_reference_coverage;
  if (raw === undefined || raw === null) return { state: 'not_provided', reason: 'absent' };
  const fail = (reason: string): CoverageState => ({ state: 'malformed', reason });
  if (typeof raw !== 'object' || Array.isArray(raw)) return fail('집계 형식이 객체가 아닙니다');
  const c = raw as Record<string, unknown>;
  if (c.basis !== 'returned_summary_references_on_successful_discovery' || c.sample_unit !== 'unique_deduplicated_customer_source') return fail('집계 기준이 약속한 값과 다릅니다');
  if (c.classification_approved !== false || c.market_frequency_estimated !== false) return fail('분류 승인·시장 빈도 표시가 false가 아닙니다');
  const counts = ['input_customer_source_count', 'denominator_customer_source_count', 'covered_customer_source_count',
    'unreferenced_processed_source_count', 'unprocessed_input_source_count', 'overlapping_polarity_source_count'] as const;
  if (!counts.every(key => isCount(c[key]))) return fail('건수가 0 이상의 정수가 아닙니다');
  const [n, m, covered, unreferenced, unprocessed, overlapping] = counts.map(key => c[key] as number);
  const polarityCounts = c.polarity_source_counts as Record<string, unknown> | undefined;
  const itemCounts = c.summary_item_counts as Record<string, unknown> | undefined;
  const polarityIds = c.polarity_source_ids as Record<string, unknown> | undefined;
  if (!polarityCounts || !itemCounts || !polarityIds || !POLARITIES.every(key => isCount(polarityCounts[key]) && isCount(itemCounts[key]) && isIdList(polarityIds[key]))) {
    return fail('극성별 건수·ID 형식이 맞지 않습니다');
  }
  if (!isIdList(c.denominator_source_ids) || !isIdList(c.covered_source_ids)) return fail('분모·인용 ID 목록이 정렬된 고유 목록이 아닙니다');
  const known = new Set(brief.source_facts.map(item => item.source_id));
  const denominatorIds = new Set(c.denominator_source_ids);
  const coveredIds = c.covered_source_ids;
  if (![...denominatorIds].every(id => known.has(id))) return fail('분모 ID가 이 기획의 원문에 없습니다');
  const union = new Set<string>();
  const seen = new Map<string, number>();
  for (const key of POLARITIES) {
    const ids = polarityIds[key] as string[];
    if (!ids.every(id => denominatorIds.has(id))) return fail('극성별 인용이 분모 밖의 원문을 가리킵니다');
    if (ids.length !== polarityCounts[key]) return fail('극성별 건수와 ID 수가 다릅니다');
    ids.forEach(id => { union.add(id); seen.set(id, (seen.get(id) ?? 0) + 1); });
  }
  if (coveredIds.length !== union.size || !coveredIds.every(id => union.has(id))) return fail('인용 합집합이 극성별 인용과 다릅니다');
  if (m > n || denominatorIds.size !== m || covered !== coveredIds.length || unreferenced !== m - covered || unprocessed !== n - m) return fail('분모·인용·미인용·미처리 건수가 서로 맞지 않습니다');
  if (overlapping !== [...seen.values()].filter(count => count > 1).length) return fail('극성 겹침 건수가 ID와 맞지 않습니다');
  const ratio = c.coverage_ratio;
  if (m === 0 ? ratio !== null : !(typeof ratio === 'number' && Number.isFinite(ratio) && Math.abs(ratio - covered / m) < 1e-9)) return fail('인용률이 C/M(분모 0이면 null)과 다릅니다');
  return { state: 'ok', value: { input: n, denominator: m, covered, unreferenced, unprocessed, ratio: ratio as number | null, overlapping,
    polaritySources: { positive: polarityCounts.positive as number, negative: polarityCounts.negative as number, mixed: polarityCounts.mixed as number },
    summaryItems: { positive: itemCounts.positive as number, negative: itemCounts.negative as number, mixed: itemCounts.mixed as number } } };
}

export function coverageText(state: CoverageState): string {
  if (state.state === 'not_provided') return state.reason === 'inheritance_invalid'
    ? '요약 인용 집계: 이전 결과의 집계를 이어받지 못해 표시하지 않습니다.' : '요약 인용 집계: 이 실행 결과에 제공되지 않았습니다.';
  if (state.state === 'malformed') return `요약 인용 집계: 형식 불일치(${state.reason})로 표시하지 않습니다.`;
  const v = state.value;
  const ratio = v.ratio === null ? '인용률 없음(처리된 원문 0건)' : `인용률 ${Math.round(v.ratio * 1000) / 10}%`;
  return `요약 인용 집계: 처리된 고객 원문 ${v.denominator}건 중 ${v.covered}건 인용(${ratio}) · 미인용 ${v.unreferenced}건 · 처리되지 않은 입력 ${v.unprocessed}건(입력 ${v.input}건) · 둘 이상 극성에 인용 ${v.overlapping}건. 인용 범위이며 의견 분류 정확도나 시장 빈도가 아닙니다.`;
}
