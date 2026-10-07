import Ajv2020 from 'ajv/dist/2020';
import schema from '../../../packages/contracts/schemas/research-planning.schema.json';
import { ApiError } from './api';
import { sourceDateDisplay } from './researchSourceDates';
import { locatorView } from './researchLocator';

export interface SourceFact {
  fact_id: string; kind: 'observed' | 'expectation' | 'document_fact' | 'unknown'; text: string;
  value?: string | number | null; unit?: string | null; locator?: Record<string, unknown>;
}
export interface ResearchSource {
  source_id: string; source_type: 'review' | 'qa' | 'faq' | 'manual' | 'spec' | 'installation';
  source_kind: 'public'; product_group: string; url: string; title: string; text: string;
  page_model: string | null; purchased_model: string | null; published_at: string | null;
  date_kind: 'posting' | 'purchase' | 'unknown'; coverage: 'excerpt' | 'full' | 'unknown';
  source_role: 'customer_experience' | 'customer_question' | 'official_answer' | 'official_document' | 'official_specification';
  locator: Record<string, unknown>; facts: SourceFact[]; document_version?: string | null;
  brand?: string | null; rating?: number | null; collected_at?: string | null;
  sort_order?: string | null; duplicate_group?: string | null; metadata?: Record<string, unknown>;
}
export interface ResearchBundle {
  schema_version: '1.0'; bundle_id: string; product_group: string; analysis_scope: 'product_group' | 'exact_model';
  sources: ResearchSource[]; collection_manifest: Record<string, unknown>;
}
export interface ResearchBundleSummary {
  bundle_id: string; product_group: string; analysis_scope: ResearchBundle['analysis_scope'];
  source_count: number | null; review_count: number | null; title?: string;
  bundle_sha256?: string;
}
export interface ResearchProblem {
  id: string; title: string; description: string; source_ids: string[]; counter_source_ids: string[]; scope_caveat: string;
}
export interface ResearchComparison {
  id: string; problem_id: string; product: string; existing_response: string; remaining_burden: string;
  source_ids: string[]; comparison_limits: string[];
}
export interface ResearchConcept {
  id: string; title: string; problem_ids: string[]; target_user: string; use_context: string;
  before_steps: string[]; after_steps: string[]; mechanism: string; proposed_changes: string[];
  source_ids: string[]; assumptions: string[]; validation_questions: string[];
  visual_scenes: Array<{ title: string; before: string; after: string }>;
  status: 'draft' | 'supported' | 'needs_sources';
}
export interface ResearchSummary { text: string; source_ids: string[] }
export interface PlanningBrief {
  schema_version: '1.0'; brief_id: string; bundle_id: string; run_id: string; revision: number;
  previous_brief_id: string | null; status: 'complete' | 'partial' | 'needs_sources';
  product_group: string; analysis_scope: ResearchBundle['analysis_scope']; goal: string; constraints: string[];
  problems: ResearchProblem[]; comparisons: ResearchComparison[]; concepts: ResearchConcept[];
  source_facts: Array<{ source_id: string; facts: SourceFact[] }>; uncertainties: string[];
  summaries: { positive: ResearchSummary[]; negative: ResearchSummary[]; mixed: ResearchSummary[] };
  relations: Array<{ from_id: string; to_id: string; relation: 'supports' | 'contradicts' | 'co_occurs' | 'addresses' | 'proposes'; source_ids: string[]; inferred: boolean }>;
  runtime: Record<string, unknown>;
}
export interface ResearchPlanningInput { bundle_id: string; goal: string; constraints: string[]; previous_run_id?: string | null }

const ajv = new Ajv2020({ allErrors: true, strict: false });
ajv.addFormat('uri', { type: 'string', validate: value => {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password; }
  catch { return false; }
} });
ajv.addSchema(schema, 'research');
const bundleValidator = ajv.compile({ $ref: 'research#/$defs/ResearchBundle' });
const briefValidator = ajv.compile({ $ref: 'research#/$defs/PlanningBrief' });

export function parseResearchBundle(value: unknown): ResearchBundle {
  if (!bundleValidator(value)) throw new ApiError('CONTRACT_MISMATCH', '실제 자료 응답이 공통 규격과 다릅니다.');
  const bundle = value as ResearchBundle;
  if (new Set(bundle.sources.map(source => source.source_id)).size !== bundle.sources.length
      || bundle.sources.some(source => source.product_group !== bundle.product_group)) {
    throw new ApiError('CONTRACT_MISMATCH', '자료 ID가 중복되거나 선택한 제품군 범위와 다릅니다.');
  }
  return bundle;
}

export function parsePlanningBrief(value: unknown, bundle: ResearchBundle): PlanningBrief {
  if (!briefValidator(value)) throw new ApiError('CONTRACT_MISMATCH', '기획 결과 응답이 공통 규격과 다릅니다.');
  const brief = value as PlanningBrief;
  if (brief.bundle_id !== bundle.bundle_id || brief.product_group !== bundle.product_group || brief.analysis_scope !== bundle.analysis_scope) {
    throw new ApiError('CONTRACT_MISMATCH', '기획 결과와 선택한 실제 자료의 범위가 다릅니다.');
  }
  const sources = new Set(bundle.sources.map(source => source.source_id));
  const referenced = [
    ...brief.problems.flatMap(problem => [...problem.source_ids, ...problem.counter_source_ids]),
    ...brief.comparisons.flatMap(comparison => comparison.source_ids), ...brief.concepts.flatMap(concept => concept.source_ids),
    ...Object.values(brief.summaries).flatMap(items => items.flatMap(item => item.source_ids)),
    ...brief.relations.flatMap(relation => relation.source_ids), ...brief.source_facts.map(item => item.source_id),
  ];
  const problems = new Set(brief.problems.map(problem => problem.id));
  if (referenced.some(id => !sources.has(id)) || brief.comparisons.some(item => !problems.has(item.problem_id))
      || brief.concepts.some(item => item.problem_ids.some(id => !problems.has(id)))) {
    throw new ApiError('CONTRACT_MISMATCH', '기획 결과의 인용 또는 문제 연결을 실제 자료에서 찾을 수 없습니다.');
  }
  return brief;
}

export function parseBundleList(value: unknown): ResearchBundleSummary[] {
  if (!value || typeof value !== 'object' || !('bundles' in value) || !Array.isArray(value.bundles)) {
    throw new ApiError('CONTRACT_MISMATCH', '실제 자료 목록의 응답 형식이 다릅니다.');
  }
  const count = (value: unknown) => value === undefined || value === null ? null
    : typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : undefined;
  const bundles = value.bundles.map((item: unknown): ResearchBundleSummary => {
    if (!item || typeof item !== 'object') throw new ApiError('CONTRACT_MISMATCH', '실제 자료 목록을 확인할 수 없습니다.');
    const row = item as Record<string, unknown>;
    if (typeof row.bundle_id !== 'string' || !row.bundle_id || typeof row.product_group !== 'string' || !row.product_group
        || !['product_group', 'exact_model'].includes(String(row.analysis_scope))
        || count(row.source_count) === undefined || count(row.review_count) === undefined
        || row.bundle_sha256 !== undefined && (typeof row.bundle_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(row.bundle_sha256))) {
      throw new ApiError('CONTRACT_MISMATCH', '실제 자료 목록의 범위·건수를 확인할 수 없습니다.');
    }
    return { bundle_id: row.bundle_id, product_group: row.product_group, analysis_scope: row.analysis_scope as ResearchBundle['analysis_scope'],
      source_count: count(row.source_count) ?? null, review_count: count(row.review_count) ?? null,
      ...(typeof row.title === 'string' ? { title: row.title } : {}),
      ...(typeof row.bundle_sha256 === 'string' ? { bundle_sha256: row.bundle_sha256 } : {}) };
  });
  if (new Set(bundles.map(bundle => bundle.bundle_id)).size !== bundles.length) throw new ApiError('CONTRACT_MISMATCH', '자료 묶음 ID가 중복됐습니다.');
  return bundles;
}

export const RESEARCH_TYPE_LABEL: Record<ResearchSource['source_type'], string> = {
  review: '고객 리뷰', qa: 'Q&A', faq: 'FAQ', manual: '설명서', spec: '제품 사양', installation: '설치 안내',
};
export const FACT_KIND_LABEL: Record<SourceFact['kind'], string> = { observed: '관찰 사실', expectation: '기대·추정', document_fact: '문서 사실', unknown: '미확인' };
/** Markdown line for one fact; its own position is added when the fact records one. */
export function factLine(fact: SourceFact): string {
  return `- ${FACT_KIND_LABEL[fact.kind]}: ${fact.text}${fact.locator && Object.keys(fact.locator).length ? ` (위치: ${locatorView(fact.locator).text})` : ''}`;
}
/** How a source's `document_version` reads. On a customer review it is the version of the reference material linked to
 *  the page model (DATA reply on #6, comment 6040922039): not the review's own edition, the purchased SKU or the manual
 *  in force at purchase. Which material it is (manual or product-page snapshot) is not in the bundle yet, so the review
 *  label stays generic until PM fixes how that basis is delivered. The raw value is shown unchanged. */
export function documentVersionView(source: ResearchSource): { label: string; value: string; note: string | null } {
  const value = source.document_version ?? '미확인';
  return source.source_type === 'review'
    ? { label: '페이지 모델의 연결 참고자료 버전', value, note: '후기 판본·구매 모델·구매 당시 설명서 판을 확인한 값이 아닙니다.' }
    : { label: '문서판', value, note: null };
}
export function researchGroupLabel(group: string): string {
  return ({ fridge: '냉장고', microwave: '전자레인지', dishwasher: '식기세척기' } as Record<string, string>)[group] ?? group;
}
export function researchScopeLabel(scope: ResearchBundle['analysis_scope']): string { return scope === 'exact_model' ? '정확 모델 분석' : '제품군 탐색'; }
export function filterResearchSources(sources: ResearchSource[], query: string, type: ResearchSource['source_type'] | 'all'): ResearchSource[] {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return sources.filter(source => (type === 'all' || source.source_type === type) && words.every(word =>
    `${source.title} ${source.text} ${source.page_model ?? ''} ${source.purchased_model ?? ''}`.toLocaleLowerCase().includes(word)));
}

/** Export the same selected revision and original sources; unknown dates/SKUs are kept intact. */
export function exportResearchPlan(bundle: ResearchBundle, brief: PlanningBrief): { json: string; markdown: string } {
  parsePlanningBrief(brief, bundle);
  const lines = [`# ${researchGroupLabel(brief.product_group)} 기획안`, '', `- 실행: ${brief.run_id} / 수정 ${brief.revision}`,
    `- 상태: ${brief.status}`, `- 자료 범위: ${researchScopeLabel(brief.analysis_scope)}`, `- 목적: ${brief.goal}`,
    '- 제약:', ...brief.constraints.map(item => `  - ${item}`), '', '## 발견한 문제'];
  for (const problem of brief.problems) lines.push(`### ${problem.title}`, problem.description, `근거: ${problem.source_ids.join(', ')}`,
    `반대 근거: ${problem.counter_source_ids.join(', ') || '확인된 자료 없음'}`, `범위: ${problem.scope_caveat}`, '');
  lines.push('## 기존·경쟁 제품 대조');
  for (const comparison of brief.comparisons) lines.push(`### ${comparison.product}`, `기존 대응: ${comparison.existing_response}`,
    `남은 부담: ${comparison.remaining_burden}`, `근거: ${comparison.source_ids.join(', ')}`, ...comparison.comparison_limits.map(item => `- 한계: ${item}`), '');
  lines.push('## 개선안과 장면');
  for (const concept of brief.concepts) {
    lines.push(`### ${concept.title}`, `상태: ${concept.status}`, `대상: ${concept.target_user}`, `사용 맥락: ${concept.use_context}`, concept.mechanism,
      '개선 전:', ...concept.before_steps.map((step, index) => `${index + 1}. ${step}`), '개선 후:', ...concept.after_steps.map((step, index) => `${index + 1}. ${step}`),
      '제안 변경:', ...concept.proposed_changes.map(item => `- ${item}`), `근거: ${concept.source_ids.join(', ')}`);
    for (const scene of concept.visual_scenes) lines.push(`#### ${scene.title}`, `이전: ${scene.before}`, `제안: ${scene.after}`);
    lines.push('가정:', ...concept.assumptions.map(item => `- ${item}`), '검증 질문:', ...concept.validation_questions.map(item => `- ${item}`), '');
  }
  for (const [key, label] of [['positive', '긍정'], ['negative', '불편·부정'], ['mixed', '혼합·조건부']] as const) {
    lines.push(`## ${label} 요약`, ...brief.summaries[key].map(item => `- ${item.text} (근거: ${item.source_ids.join(', ')})`), '');
  }
  lines.push('## 미확인 사항', ...brief.uncertainties.map(item => `- ${item}`), '', '## 원문·사실');
  for (const source of bundle.sources) {
    lines.push(`### ${source.source_id} · ${source.title}`, `유형: ${RESEARCH_TYPE_LABEL[source.source_type]} / 범위: ${source.coverage}`,
      `페이지 모델: ${source.page_model ?? '미확인'} / 구매 모델: ${source.purchased_model ?? '미확인'}`,
      sourceDateDisplay(source),
      `원문 위치: ${locatorView(source.locator).text}`, `출처: ${source.url}`, source.text, ...source.facts.map(factLine), '');
  }
  return { json: `${JSON.stringify({ bundle, brief }, null, 2)}\n`, markdown: `${lines.join('\n')}\n` };
}
