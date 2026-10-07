import type { Concept, Gap, Need } from './planning';

// W1 view-model (record 최길웅-20261007-056): planning scenes the shared contract does not define yet.
// The producer fields are the WEB proposal for P0 (#234 comment 6038169768) and may be renamed by P0; only this file
// reads them. Today Concept/Need/Gap forbid extra properties, so every validated run yields 'not_provided'.
//   Concept: target_user, usage_context, before_steps[], after_steps[] ({ text, basis: observed|inferred, evidence_ids }),
//            mechanism ({ summary, feature_ids?, conditions? })
//   Need/Gap: counter_evidence_ids[]
// Nothing is filled in on the web: a missing field stays 'not_provided', a wrong shape is 'malformed' and its content
// is not shown, and an observed step must cite evidence.

export type Field<T> = { state: 'not_provided' } | { state: 'malformed'; reason: string } | { state: 'ok'; value: T };
export type StepBasis = 'observed' | 'inferred';
export interface SceneStep { order: number; text: string; basis: StepBasis; evidenceIds: string[]; missingEvidenceIds: string[] }
export interface MechanismView { summary: string; featureIds: string[]; conditions: string[] }
export interface CounterEvidenceGroup { ownerId: string; evidenceIds: string[]; missingEvidenceIds: string[]; alsoSupportingIds: string[] }
export interface ConceptSceneView {
  conceptId: string;
  targetUser: Field<string>;
  usageContext: Field<string>;
  before: Field<SceneStep[]>;
  after: Field<SceneStep[]>;
  mechanism: Field<MechanismView>;
  counterEvidence: Field<CounterEvidenceGroup[]>;
  /** True when the run recorded at least one of these fields (well-formed or not); false means none was recorded. */
  provided: boolean;
}

const NOT_PROVIDED = { state: 'not_provided' } as const;
const malformed = (reason: string) => ({ state: 'malformed', reason }) as const;
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string' && item.trim() !== '');

function textField(record: Record<string, unknown>, key: string, label: string): Field<string> {
  const value = record[key];
  if (value === undefined || value === null) return NOT_PROVIDED;
  if (typeof value !== 'string' || !value.trim()) return malformed(`${label}이(가) 비어 있거나 문자열이 아닙니다`);
  return { state: 'ok', value: value.trim() };
}

function stepsField(record: Record<string, unknown>, key: string, label: string, known: Set<string>): Field<SceneStep[]> {
  const value = record[key];
  if (value === undefined || value === null) return NOT_PROVIDED;
  if (!Array.isArray(value) || !value.length) return malformed(`${label} 단계 목록이 비어 있거나 배열이 아닙니다`);
  const steps: SceneStep[] = [];
  for (const [index, item] of value.entries()) {
    const order = index + 1;
    if (!isRecord(item) || typeof item.text !== 'string' || !item.text.trim()) return malformed(`${label} ${order}단계의 내용이 없습니다`);
    if (item.basis !== 'observed' && item.basis !== 'inferred') return malformed(`${label} ${order}단계의 관찰/추정 구분이 없습니다`);
    const ids = item.evidence_ids ?? [];
    if (!isStringArray(ids)) return malformed(`${label} ${order}단계의 근거 ID 형식이 맞지 않습니다`);
    if (item.basis === 'observed' && !ids.length) return malformed(`${label} ${order}단계는 관찰이라고 했지만 근거가 없습니다`);
    steps.push({ order, text: item.text.trim(), basis: item.basis, evidenceIds: ids, missingEvidenceIds: ids.filter(id => !known.has(id)) });
  }
  return { state: 'ok', value: steps };
}

function mechanismField(record: Record<string, unknown>): Field<MechanismView> {
  const value = record.mechanism;
  if (value === undefined || value === null) return NOT_PROVIDED;
  if (!isRecord(value) || typeof value.summary !== 'string' || !value.summary.trim()) return malformed('작동 방식 요약이 없습니다');
  const featureIds = value.feature_ids ?? [];
  const conditions = value.conditions ?? [];
  if (!isStringArray(featureIds)) return malformed('작동 방식의 연결 기능 형식이 맞지 않습니다');
  if (!isStringArray(conditions)) return malformed('작동 방식의 조건 형식이 맞지 않습니다');
  return { state: 'ok', value: { summary: value.summary.trim(), featureIds, conditions } };
}

/** Counter evidence recorded on the concept's gaps and their needs. Present-but-empty means the producer recorded
 *  "no counter case"; absent on every owner means not provided. A counter citation that the same owner also uses as
 *  support is kept and flagged, never dropped. */
function counterField(concept: Concept, needs: Need[], gaps: Gap[], known: Set<string>): Field<CounterEvidenceGroup[]> {
  const linkedGaps = gaps.filter(gap => concept.gap_ids.includes(gap.id));
  const owners: { id: string; record: Record<string, unknown>; support: string[] }[] = [];
  for (const gap of linkedGaps) {
    owners.push({ id: gap.id, record: gap as unknown as Record<string, unknown>, support: gap.evidence_ids });
    const need = needs.find(item => item.id === gap.need_id);
    if (need && !owners.some(owner => owner.id === need.id)) owners.push({ id: need.id, record: need as unknown as Record<string, unknown>, support: need.evidence_ids });
  }
  const groups: CounterEvidenceGroup[] = [];
  for (const owner of owners) {
    const value = owner.record.counter_evidence_ids;
    if (value === undefined || value === null) continue;
    if (!isStringArray(value)) return malformed(`${owner.id}의 반대 사례 근거 형식이 맞지 않습니다`);
    groups.push({ ownerId: owner.id, evidenceIds: value, missingEvidenceIds: value.filter(id => !known.has(id)),
      alsoSupportingIds: value.filter(id => owner.support.includes(id)) });
  }
  return groups.length ? { state: 'ok', value: groups } : NOT_PROVIDED;
}

export function conceptSceneView(concept: Concept, output: { needs: Need[]; gaps: Gap[] } | null, knownEvidenceIds: Iterable<string>): ConceptSceneView {
  const record = concept as unknown as Record<string, unknown>;
  const known = new Set(knownEvidenceIds);
  const view = {
    conceptId: concept.id,
    targetUser: textField(record, 'target_user', '대상 사용자'),
    usageContext: textField(record, 'usage_context', '사용 상황'),
    before: stepsField(record, 'before_steps', '개선 전', known),
    after: stepsField(record, 'after_steps', '개선 후', known),
    mechanism: mechanismField(record),
    counterEvidence: counterField(concept, output?.needs ?? [], output?.gaps ?? [], known),
  };
  const fields = [view.targetUser, view.usageContext, view.before, view.after, view.mechanism, view.counterEvidence];
  return { ...view, provided: fields.some(field => field.state !== 'not_provided') };
}
