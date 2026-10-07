import records from '../../../../data/research/r5-public-reviews-20261007/balanced-pilot-v2/records.json';
import type { PlanningBrief, ResearchBundle } from '../research';

// UI/transport checks use a committed public DOM capture. This is not a model-quality evaluation fixture.
export const REAL_RESEARCH_RECORD = records[0];
const record = REAL_RESEARCH_RECORD;
export const REAL_RESEARCH_BUNDLE: ResearchBundle = {
  schema_version: '1.0', bundle_id: 'WEB-actual-source-contract-check', product_group: 'fridge', analysis_scope: 'product_group',
  sources: [{ source_id: record.original_review_id, source_kind: 'public', source_type: 'review', product_group: 'fridge',
    url: record.source_url, title: 'LG 공개 후기 원문', text: record.text, page_model: record.displayed_model_id,
    purchased_model: record.actual_purchased_model_id, published_at: record.published_at, date_kind: 'unknown',
    coverage: 'full', source_role: 'customer_experience', locator: { selector: record.source_locator }, facts: [],
    rating: record.rating, metadata: { test_scope: 'transport_and_rendering_only', original_review_id: record.original_review_id } }],
  collection_manifest: { limitations: ['작성일·구매 SKU 미확인', '단일 원문을 이용한 UI 계약 검사이며 실모델 평가 아님'], synthetic_review_count: 0 },
};
export function heldBrief(bundle: ResearchBundle = REAL_RESEARCH_BUNDLE): PlanningBrief {
  return { schema_version: '1.0', brief_id: 'TEST-held-brief', bundle_id: bundle.bundle_id, run_id: 'TEST-held-run', revision: 0,
    previous_brief_id: null, status: 'needs_sources', product_group: bundle.product_group, analysis_scope: bundle.analysis_scope,
    goal: '고객 자료에서 아직 남은 사용 부담을 찾아 개선안을 제안하기', constraints: ['기존 기능을 새로운 발명으로 제안하지 않기'],
    problems: [], comparisons: [], concepts: [], source_facts: [], uncertainties: ['이 테스트는 실모델 기획 성능을 증명하지 않습니다.'],
    summaries: { positive: [{ text: bundle.sources[0].text, source_ids: [bundle.sources[0].source_id] }], negative: [], mixed: [] },
    relations: [], runtime: { test_only: true } };
}
