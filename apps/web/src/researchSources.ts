import { ApiError } from './api';
import { canonical } from './planning';
import { factLine, filterResearchSources, parseResearchBundle, RESEARCH_TYPE_LABEL } from './research';
import { locatorView } from './researchLocator';
import type { ResearchBundle, ResearchSource } from './research';
import { calendarDay, confirmedPostingDay, sourceDateDisplay } from './researchSourceDates';
export { confirmedPostingDay, sourceDateDisplay } from './researchSourceDates';

export interface ResearchSourceFilters {
  query: string; type: ResearchSource['source_type'] | 'all'; page_model: string;
  posting_date_mode: 'all' | 'confirmed' | 'unknown'; start_date: string; end_date: string; expand_terms: boolean;
}
export const DEFAULT_SOURCE_FILTERS: ResearchSourceFilters = {
  query: '', type: 'all', page_model: '', posting_date_mode: 'all', start_date: '', end_date: '', expand_terms: false,
};
const TOPIC_TERMS = [['소음', '시끄럽', '시끄러', '조용'], ['냄새', '악취']] as const;
export function keywordGroups(query: string, expand: boolean): string[][] {
  return query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean).map(word => {
    const topic = expand ? TOPIC_TERMS.find(terms => terms.some(term => word.includes(term))) : undefined;
    return topic ? [...new Set([word, ...topic])] : [word];
  });
}
export function expandedKeywords(filters: ResearchSourceFilters): string[] {
  const originals = new Set(keywordGroups(filters.query, false).flat());
  return [...new Set(keywordGroups(filters.query, filters.expand_terms).flat())].filter(word => !originals.has(word));
}
export function selectFilteredSources(sources: ResearchSource[], filters: ResearchSourceFilters): ResearchSource[] {
  const groups = keywordGroups(filters.query, filters.expand_terms);
  const base = filterResearchSources(sources, filters.expand_terms ? '' : filters.query, filters.type);
  return base.filter(source => {
    if (filters.page_model === '__unknown__' ? source.page_model !== null : filters.page_model && source.page_model !== filters.page_model) return false;
    const day = confirmedPostingDay(source);
    if (filters.posting_date_mode === 'unknown') return day === null && (!filters.expand_terms || matches(source));
    if ((filters.posting_date_mode === 'confirmed' || filters.start_date || filters.end_date) && !day) return false;
    if (filters.start_date && (!calendarDay(filters.start_date) || day! < filters.start_date)) return false;
    if (filters.end_date && (!calendarDay(filters.end_date) || day! > filters.end_date)) return false;
    if (filters.start_date && filters.end_date && filters.start_date > filters.end_date) return false;
    return !filters.expand_terms || matches(source);
  });
  function matches(source: ResearchSource): boolean {
    const text = `${source.title} ${source.text} ${source.page_model ?? ''} ${source.purchased_model ?? ''}`.toLocaleLowerCase();
    return groups.every(terms => terms.some(term => text.includes(term)));
  }
}
export function koreanSourceLimitations(bundle: ResearchBundle): string[] {
  const manifest = bundle.collection_manifest; const reviews = bundle.sources.filter(source => source.source_type === 'review');
  const limits: string[] = [];
  if (Array.isArray(manifest.limitations) && manifest.limitations.some(item => typeof item === 'string' && /purposive|representative|임의|표본/i.test(item))) {
    limits.push('화면에서 골라 수집한 표본입니다. 전체 시장이나 전체 고객의 불편 발생 비율을 대표하지 않습니다.');
  }
  const missingDates = reviews.filter(source => !confirmedPostingDay(source)).length;
  const missingSku = reviews.filter(source => source.purchased_model === null).length;
  if (missingDates) limits.push(`후기 ${missingDates}/${reviews.length}건의 게시일이 미확인입니다. 구매일을 게시일로 바꾸어 기간 분석하지 않습니다.`);
  if (missingSku) limits.push(`후기 ${missingSku}/${reviews.length}건의 구매 모델이 미확인입니다. 페이지 모델과 구매 SKU가 같다고 단정하지 않습니다.`);
  if (manifest.independent_evaluation_approved === false) limits.push('독립평가용 사용은 승인되지 않았습니다. 공개 원문이라는 이유로 평가 자료 분리가 완료된 것으로 간주하지 않습니다.');
  else if (manifest.independent_evaluation_approved !== true) limits.push('독립평가용 사용 승인 여부가 미확인입니다. 공개 원문이라는 이유로 평가 자료 분리가 완료된 것으로 간주하지 않습니다.');
  const docs = bundle.sources.filter(source => ['manual', 'faq', 'spec', 'installation'].includes(source.source_type));
  const excerpts = docs.filter(source => source.coverage === 'excerpt').length; const unknown = docs.filter(source => source.coverage === 'unknown').length;
  if (excerpts || unknown) limits.push(`공식 자료 중 일부 발췌 ${excerpts}건 · 범위 미확인 ${unknown}건입니다. 발췌에 없는 기능을 제품에 없다고 단정하지 않습니다.`);
  if (manifest.selection_only === true) limits.push(`원래 자료에서 ${bundle.sources.length}건을 선택한 파일입니다. 선택 자료로 새 기획을 실행한 기록은 아닙니다.`);
  else if (typeof manifest.stored_group_review_count === 'number' && manifest.stored_group_review_count > reviews.length) {
    limits.push(`같은 제품군 수집 후기 ${manifest.stored_group_review_count}건 중 이 묶음의 ${reviews.length}건만 사용합니다. 다른 자료 분할을 포함하지 않습니다.`);
  }
  if (Array.isArray(manifest.missing_source_types) && manifest.missing_source_types.some(item => item && typeof item === 'object'
      && 'source_type' in item && item.source_type === 'qa' && 'verified_text_count' in item && item.verified_text_count === 0)) {
    limits.push('독립적으로 확인해 고정한 Q&A 원문은 현재 0건입니다. 없는 원문을 생성해 채우지 않았습니다.');
  }
  return limits;
}
async function sha256(value: unknown): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new ApiError('EXPORT_UNAVAILABLE', '브라우저에서 자료 지문을 계산할 수 없습니다. 로컬 작업실 주소로 다시 열어 주세요.');
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical(value)));
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}
/** Copy complete selected source objects. This export is a research selection, never a new planning run. */
export async function exportResearchSelection(bundle: ResearchBundle, selectedIds: string[], filters: ResearchSourceFilters,
  sourceHash: string | null, selectedAt = new Date().toISOString()): Promise<{ bundle: ResearchBundle; json: string; markdown: string }> {
  const ids = new Set(selectedIds); const sources = bundle.sources.filter(source => ids.has(source.source_id));
  if (!sources.length || ids.size !== sources.length) throw new ApiError('INVALID_ARGUMENT', '현재 실제 자료에 있는 원문을 하나 이상 선택해 주세요.');
  if (sourceHash !== null && !/^[a-f0-9]{64}$/.test(sourceHash)) throw new ApiError('INVALID_ARGUMENT', '원본 자료 지문을 확인해 주세요.');
  const originalHash = sourceHash ?? await sha256(bundle);
  const contentHash = await sha256(sources);
  const counts = Object.fromEntries(Object.keys(RESEARCH_TYPE_LABEL).map(type => [type, sources.filter(source => source.source_type === type).length]));
  const selected: ResearchBundle = {
    schema_version: bundle.schema_version, bundle_id: `${bundle.bundle_id}-selection-${contentHash.slice(0, 12)}`,
    product_group: bundle.product_group, analysis_scope: bundle.analysis_scope, sources: structuredClone(sources),
    collection_manifest: {
      ...structuredClone(bundle.collection_manifest), original_collection_manifest: structuredClone(bundle.collection_manifest),
      source_count: sources.length, review_count: counts.review, source_type_counts: counts,
      page_models: [...new Set(sources.map(source => source.page_model).filter(model => model !== null))],
      independent_evaluation_approved: false, selection_only: true, planning_executed: false,
      selection: { source_bundle_id: bundle.bundle_id, source_bundle_sha256: originalHash,
        source_hash_basis: sourceHash ? 'server_bundle_hash' : 'browser_canonical_json',
        source_bundle_source_count: bundle.sources.length, selected_content_sha256: contentHash,
        selected_source_ids: sources.map(source => source.source_id), selected_at: selectedAt,
        filters: structuredClone(filters), expanded_terms: expandedKeywords(filters), review_text_edits: 0, facts_edits: 0,
        independent_evaluation_approved: false, server_subset_planning_supported: false },
    },
  };
  parseResearchBundle(selected);
  const lines = ['# 선택한 공개 근거 자료', '', `원본 묶음: ${bundle.bundle_id}`, `원본 지문: ${originalHash}`,
    `선택 묶음: ${selected.bundle_id}`, `선택 자료: ${sources.length}건 / 후기 ${counts.review}건`,
    '후기 본문 수정: 0건 / facts 수정: 0건', '독립평가 승인: false', '이 파일은 자료 선택이며 새 기획 실행 결과가 아닙니다.', '', '## 자료 한계',
    ...koreanSourceLimitations(selected).map(item => `- ${item}`), '', '## 원문'];
  for (const source of selected.sources) lines.push(`### ${source.source_id} · ${source.title || RESEARCH_TYPE_LABEL[source.source_type]}`,
    `유형: ${RESEARCH_TYPE_LABEL[source.source_type]} · ${sourceDateDisplay(source)}`,
    `페이지 모델: ${source.page_model ?? '미확인'} · 구매 모델: ${source.purchased_model ?? '미확인'}`, `원문 위치: ${locatorView(source.locator).text}`, `출처: ${source.url}`,
    '', source.text, '', 'facts 원기록:', '```json', JSON.stringify(source.facts, null, 2), '```',
    ...source.facts.map(factLine), '');
  lines.push('## 수집·선택 manifest', '```json', JSON.stringify(selected.collection_manifest, null, 2), '```');
  return { bundle: selected, json: `${JSON.stringify(selected, null, 2)}\n`, markdown: `${lines.join('\n')}\n` };
}
