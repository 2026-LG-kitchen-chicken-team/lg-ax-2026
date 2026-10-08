import { ApiError } from './api';
import { parsePlanningBrief } from './research';
import type { PlanningBrief, ResearchBundle } from './research';

export interface PlanningInputScope { kind: 'full_bundle' | 'user_selected_sources'; ids: string[] }

function sameOriginalValue(actual: unknown, original: unknown): boolean {
  if (actual === original) return true;
  if (!actual || !original || typeof actual !== 'object' || typeof original !== 'object') return false;
  if (Array.isArray(actual) || Array.isArray(original)) return Array.isArray(actual) && Array.isArray(original)
    && actual.length === original.length && actual.every((item, index) => sameOriginalValue(item, original[index]));
  const left = actual as Record<string, unknown>; const right = original as Record<string, unknown>;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every(key => Object.hasOwn(right, key) && sameOriginalValue(left[key], right[key]));
}

/** Keep the source order of the frozen bundle, independently of checkbox or model sampling order. */
export function normalizeSourceSelection(bundle: ResearchBundle, value: unknown): string[] {
  if (!Array.isArray(value) || !value.length || value.some(id => typeof id !== 'string') || new Set(value).size !== value.length) {
    throw new ApiError('INVALID_ARGUMENT', '현재 자료의 근거를 중복 없이 한 건 이상 선택해 주세요.');
  }
  const chosen = new Set<string>(value);
  const ids = bundle.sources.filter(source => chosen.has(source.source_id)).map(source => source.source_id);
  if (ids.length !== chosen.size) throw new ApiError('INVALID_ARGUMENT', '선택한 근거가 현재 자료 묶음에 없습니다. 자료를 다시 확인해 주세요.');
  return ids;
}

/** Legacy saved runs may omit scope; never infer a user selection from the model's selected_source_ids. */
export function planningInputScope(brief: PlanningBrief, bundle: ResearchBundle): PlanningInputScope | null {
  const kind = brief.runtime.input_scope;
  const rawIds = brief.runtime.user_selected_source_ids;
  if (kind === undefined && rawIds === undefined) return null;
  if (kind !== 'full_bundle' && kind !== 'user_selected_sources') throw new ApiError('CONTRACT_MISMATCH', '기획 결과의 입력 범위를 확인할 수 없습니다.');
  let ids: string[];
  try { ids = normalizeSourceSelection(bundle, rawIds); }
  catch { throw new ApiError('CONTRACT_MISMATCH', '기획 결과의 입력 근거가 현재 원문과 다릅니다.'); }
  if (JSON.stringify(ids) !== JSON.stringify(rawIds)
      || kind === 'full_bundle' && ids.length !== bundle.sources.length
      || JSON.stringify(brief.source_facts.map(item => item.source_id)) !== JSON.stringify(ids)) {
    throw new ApiError('CONTRACT_MISMATCH', '기획 결과의 입력 범위와 보존된 원문 사실이 다릅니다.');
  }
  const chosen = new Set(ids);
  const sources = bundle.sources.filter(source => chosen.has(source.source_id));
  if (!sameOriginalValue(brief.source_facts, sources.map(source => ({ source_id: source.source_id, facts: source.facts })))) {
    throw new ApiError('CONTRACT_MISMATCH', '기획 결과의 원문 사실이 선택한 자료에서 변경됐습니다.');
  }
  // A valid reference in the full bundle can still be outside the user's chosen subset.
  parsePlanningBrief(brief, { ...bundle, sources });
  return { kind, ids };
}

export function planningInputScopeLabel(brief: PlanningBrief): string {
  const ids = brief.runtime.user_selected_source_ids;
  if (!Array.isArray(ids)) return '기획 입력 범위: 이 저장 결과에 제공되지 않았습니다.';
  if (brief.runtime.input_scope === 'user_selected_sources') return `기획 입력 범위: 사용자 선택 원문 ${ids.length}건`;
  if (brief.runtime.input_scope === 'full_bundle') return `기획 입력 범위: 자료 묶음 전체 ${ids.length}건`;
  return '기획 입력 범위: 확인할 수 없습니다.';
}
