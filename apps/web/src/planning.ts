/** Planner-side logic for the four workspace areas; pure functions shared by fixture and live modes. */
import Ajv2020 from 'ajv/dist/2020';
import schema from '../../../packages/contracts/schemas/lgax.schema.json';
import { ApiError } from './api';
import { evidenceLocation } from './domain';
import type { Evidence, ProductGroup } from './domain';
// judgement.ts also imports from this module; neither uses the other at module load, so the cycle is safe.
import { errorDetailText, executionKindText, exportJudgement, judgedNotes, reasonText, scopeLines, seconds, SUPPORT_FROM_BASIS, tokenText } from './judgement';
import type { ExportJudgement, JudgedNotes } from './judgement';

export type DataMode = 'live' | 'fixture';

export interface PlanningRequest {
  product_group: ProductGroup;
  target_customer: string;
  use_situation: string;
  improvement_task: string;
  exclusions: string[];
  model_ids: string[];
  dataset_version: string;
}

export interface Feature { id: string; model_id: string; document_version: string; name: string; description: string; conditions: string[]; evidence_ids: string[] }
export interface Need { id: string; model_id: string; situation: string; pain: string; evidence_ids: string[]; uncertainties: string[] }
export interface Gap { id: string; need_id: string; model_id: string; feature_ids: string[]; support_status: 'supported' | 'unsupported' | 'insufficient_evidence'; remaining_pain: string; evidence_ids: string[]; questions: string[] }
export interface Concept { id: string; title: string; kind: 'product' | 'feature' | 'service'; gap_ids: string[]; evidence_ids: string[]; differentiation: string; requirements: string[]; assumptions: string[]; status: 'proposed' | 'needs_review' | 'accepted' | 'rejected' }
export interface RunEvent { stage: string; summary: string; tool: string | null; evidence_ids: string[] }
export interface Run {
  id: string; project_id: string; dataset_version: string; contract_version: '0.1.0';
  status: 'pending' | 'running' | 'completed' | 'held' | 'failed' | 'not_implemented';
  stage: 'plan' | 'retrieve' | 'needs' | 'compare' | 'concepts' | 'review' | 'finished';
  revision_count: number; max_revisions: 2; concepts: Concept[]; unresolved: string[]; evidence_ids: string[]; events: RunEvent[];
}
export interface RunOutput { needs: Need[]; gaps: Gap[]; no_candidate_reasons?: string[] }
export interface RunSnapshot {
  run: Run; request: PlanningRequest; previous_run_id: string | null; request_revision: number; actor_id: string;
  client: 'api' | 'web' | 'mcp' | 'skill'; created_at: string; document_versions: Record<string, string>;
  dataset_sha256: string; unconfirmed: string[]; output: RunOutput | null;
}

const ajv = new Ajv2020({ allErrors: true, strict: false });
ajv.addFormat('date-time', { type: 'string', validate: value => /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value)) });
ajv.addSchema(schema, 'planning');
const validators = new Map<string, ReturnType<typeof ajv.compile>>();

/** Validates a value against a named definition of the shared contract and returns readable errors. */
export function contractErrors(definition: string, value: unknown): string[] {
  let validator = validators.get(definition);
  if (!validator) {
    validator = ajv.compile({ $ref: `planning#/$defs/${definition}` });
    validators.set(definition, validator);
  }
  if (validator(value)) return [];
  return (validator.errors ?? []).map(error => `${error.instancePath || '/'} ${error.message ?? ''}`.trim());
}

// R02: missing information becomes a question to the planner instead of a silent default.
const REQUIRED_TEXT: { field: 'target_customer' | 'use_situation' | 'improvement_task'; label: string; question: string }[] = [
  { field: 'improvement_task', label: '기획 요청', question: '어떤 불편을 줄이거나 어떤 기회를 검토할지 한 문장으로 적어 주세요.' },
  { field: 'target_customer', label: '대상 고객', question: '누구의 불편을 다루나요? 고객 유형이나 가구 형태를 알려 주세요.' },
  { field: 'use_situation', label: '사용 상황', question: '불편이 생기는 구체적인 사용 상황을 알려 주세요.' },
];

export interface MissingQuestion { field: string; label: string; question: string }

export function missingRequestQuestions(request: Partial<PlanningRequest>): MissingQuestion[] {
  const questions: MissingQuestion[] = REQUIRED_TEXT
    .filter(item => !String(request[item.field] ?? '').trim())
    .map(({ field, label, question }) => ({ field, label, question }));
  if (!request.product_group) questions.push({ field: 'product_group', label: '제품군', question: '냉장고·식기세척기·전자레인지 중 검토할 제품군을 선택해 주세요.' });
  if (!request.model_ids?.length) questions.push({ field: 'model_ids', label: '검토 모델', question: '비교할 기존 제품 모델을 하나 이상 선택해 주세요.' });
  if (!request.dataset_version) questions.push({ field: 'dataset_version', label: '자료 버전', question: '자료가 아직 연결되지 않았습니다. 자료 버전을 확인할 수 있을 때 다시 요청해 주세요.' });
  return questions;
}

const FIELD_LABELS: Record<keyof PlanningRequest, string> = {
  product_group: '제품군', target_customer: '대상 고객', use_situation: '사용 상황', improvement_task: '기획 요청',
  exclusions: '제외 조건', model_ids: '검토 모델', dataset_version: '자료 버전',
};

export interface RequestChange { field: keyof PlanningRequest; label: string; before: string; after: string }

function display(value: unknown): string {
  return Array.isArray(value) ? (value.length ? value.join(', ') : '(없음)') : String(value ?? '') || '(비어 있음)';
}

/** Field-level difference between two requests, used for change requests and run history. */
export function requestChanges(before: PlanningRequest, after: PlanningRequest): RequestChange[] {
  return (Object.keys(FIELD_LABELS) as (keyof PlanningRequest)[])
    .filter(field => canonical(before[field]) !== canonical(after[field]))
    .map(field => ({ field, label: FIELD_LABELS[field], before: display(before[field]), after: display(after[field]) }));
}

export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    const entries = Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`);
    return `{${entries.join(',')}}`;
  }
  return JSON.stringify(value);
}

/** Mirrors the workspace server rule: a run without parent starts a branch; changes from the parent add one revision. */
export function nextRequestRevision(original: PlanningRequest, parent: RunSnapshot | null, request: PlanningRequest): number {
  if (!parent) return canonical(original) === canonical(request) ? 0 : 1;
  return canonical(parent.request) === canonical(request) ? parent.request_revision : parent.request_revision + 1;
}

// R14: needs, existing features, their conditions, remaining pain and cited evidence side by side.
export interface ComparisonRow {
  need: Need;
  gap: Gap | undefined;
  features: Feature[];
  conditions: string[];
  evidence: Evidence[];
  missingIds: string[];
}

export function buildComparison(output: RunOutput, features: Feature[], evidence: Evidence[]): ComparisonRow[] {
  const featureById = new Map(features.map(item => [item.id, item]));
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  // One row per gap (record 034: a need with three gaps used to show only the first, so GAP-002/003 vanished from the
  // table and the export). A need without any gap keeps one row with no gap.
  return output.needs.flatMap(need => {
    const gaps = output.gaps.filter(item => item.need_id === need.id);
    return (gaps.length ? gaps : [undefined]).map(gap => {
      const featureIds = gap?.feature_ids ?? [];
      const evidenceIds = [...new Set([...need.evidence_ids, ...(gap?.evidence_ids ?? [])])];
      const rowFeatures = featureIds.flatMap(id => featureById.get(id) ?? []);
      return {
        need, gap,
        features: rowFeatures,
        conditions: [...new Set(rowFeatures.flatMap(item => item.conditions))],
        evidence: evidenceIds.flatMap(id => evidenceById.get(id) ?? []),
        missingIds: [...featureIds.filter(id => !featureById.has(id)), ...evidenceIds.filter(id => !evidenceById.has(id))],
      };
    });
  });
}

// R21: an added condition becomes a new linked run. Without a connected Agent the run stays not_implemented.
export function requestWithCondition(base: PlanningRequest, condition: string): PlanningRequest {
  const text = condition.trim();
  if (!text) throw new ApiError('INVALID_ARGUMENT', '추가할 조건을 입력해 주세요.');
  if (base.exclusions.includes(text)) throw new ApiError('INVALID_ARGUMENT', '이미 같은 조건이 요청에 포함되어 있습니다.');
  return { ...base, exclusions: [...base.exclusions, text] };
}

export function draftRunWithCondition(base: RunSnapshot, original: PlanningRequest, condition: string, id: string, createdAt: string): RunSnapshot {
  return draftRunFromRequest(base, original, requestWithCondition(base.request, condition), id, createdAt);
}

export function draftRunFromRequest(base: RunSnapshot, original: PlanningRequest, request: PlanningRequest, id: string, createdAt: string): RunSnapshot {
  const draft: RunSnapshot = {
    run: {
      id, project_id: base.run.project_id, dataset_version: base.run.dataset_version, contract_version: '0.1.0',
      status: 'not_implemented', stage: 'plan', revision_count: 0, max_revisions: 2, concepts: [], unresolved: [], evidence_ids: [], events: [],
    },
    request, previous_run_id: base.run.id, request_revision: nextRequestRevision(original, base, request),
    actor_id: 'local-draft', client: 'web', created_at: createdAt, document_versions: { ...base.document_versions },
    dataset_sha256: base.dataset_sha256, unconfirmed: [], output: null,
  };
  const errors = contractErrors('WorkspaceRunSnapshot', draft);
  if (errors.length) throw new ApiError('CONTRACT_MISMATCH', `새 실행 초안이 공통 규격과 다릅니다. ${errors.join('; ')}`);
  return draft;
}

// R21 (P2-WEB-003): candidate choices and corrected conditions become the next request. The shared contract has no
// candidate-selection field, so choices are written into the request text the Agent reads, in a stable form.
export type CandidateChoice = 'keep' | 'focus' | 'exclude';
const FOCUS_PREFIX = ' [집중 검토: ';

function candidateLabel(concept: Pick<Concept, 'id' | 'title'>): string {
  return `${concept.title} (${concept.id})`;
}

/** Only a suffix composed entirely of current candidate labels is managed by the choice controls. */
function knownFocus(task: string, concepts: Concept[]): { task: string; ids: string[] } | null {
  const at = task.lastIndexOf(FOCUS_PREFIX);
  if (at < 0 || !task.endsWith(']') || !concepts.length) return null;
  const labels = concepts.map(candidateLabel);
  const content = task.slice(at + FOCUS_PREFIX.length, -1);
  const alternatives = labels.map(label => label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  if (!new RegExp(`^(?:${alternatives})(?:, (?:${alternatives}))*$`).test(content)) return null;
  const labelIds = new Map(concepts.map(concept => [candidateLabel(concept), concept.id]));
  const matches = content.matchAll(new RegExp(`(?:^|, )(${alternatives})(?=, |$)`, 'g'));
  return { task: task.slice(0, at), ids: [...new Set([...matches].map(match => labelIds.get(match[1])!))] };
}

export function candidateExclusion(concept: Pick<Concept, 'id' | 'title'>): string {
  return `후보 제외: ${candidateLabel(concept)}`;
}

export function candidateChoicesFor(request: PlanningRequest, concepts: Concept[]): Record<string, CandidateChoice> {
  const focused = new Set(knownFocus(request.improvement_task, concepts)?.ids ?? []);
  return Object.fromEntries(concepts.map(concept => [concept.id,
    request.exclusions.includes(candidateExclusion(concept)) ? 'exclude' : focused.has(concept.id) ? 'focus' : 'keep']));
}

export function buildRerunRequest(base: PlanningRequest, concepts: Concept[], choices: Record<string, CandidateChoice>, conditions: string[]): PlanningRequest {
  const managedExclusions = new Set(concepts.map(candidateExclusion));
  const cleaned = [...new Set(conditions.map(item => base.exclusions.includes(item) ? item : item.trim()).filter(item => item.trim() && !managedExclusions.has(item)))];
  const effective = { ...candidateChoicesFor(base, concepts), ...choices };
  const excluded = concepts.filter(concept => effective[concept.id] === 'exclude').map(candidateExclusion);
  const focused = concepts.filter(concept => effective[concept.id] === 'focus');
  const priorFocus = knownFocus(base.improvement_task, concepts);
  const sameFocus = priorFocus && priorFocus.ids.length === focused.length && focused.every(concept => priorFocus.ids.includes(concept.id));
  const task = priorFocus?.task ?? base.improvement_task;
  const remaining = new Set([...cleaned, ...excluded]);
  // Keep existing condition order when nothing was removed, and append only new conditions/choices.
  const exclusions = base.exclusions.filter(item => remaining.delete(item));
  exclusions.push(...remaining);
  const request: PlanningRequest = {
    ...base,
    improvement_task: sameFocus ? base.improvement_task : focused.length ? `${task}${FOCUS_PREFIX}${focused.map(candidateLabel).join(', ')}]` : task,
    exclusions,
  };
  const errors = contractErrors('PlanningRequest', request);
  if (errors.length) throw new ApiError('INVALID_ARGUMENT', `재실행 요청이 공통 규격과 다릅니다. ${errors.join('; ')}`);
  return request;
}

/** Unknown candidate IDs and user-authored prefixed text remain editable conditions; absent candidates preserve everything. */
export function splitConditions(request: PlanningRequest, concepts: Concept[] = []): { conditions: string[]; excludedCandidates: string[] } {
  const managed = new Set(concepts.map(candidateExclusion));
  return {
    conditions: request.exclusions.filter(item => !managed.has(item)),
    excludedCandidates: request.exclusions.filter(item => managed.has(item)),
  };
}

export interface ConceptTextChange { before: string; after: string }
export interface ConceptDetailChange { id: string; title: string; status: [Concept['status'] | null, Concept['status'] | null]; added: { requirements: string[]; assumptions: string[]; evidence_ids: string[] }; removed: { requirements: string[]; assumptions: string[]; evidence_ids: string[] }; text: { title: ConceptTextChange | null; differentiation: ConceptTextChange | null } }

/** Field-level before/after for each candidate, so a revision shows what changed inside a concept, not only its status. */
export function conceptDetailChanges(before: RunSnapshot | undefined, after: RunSnapshot): ConceptDetailChange[] {
  const previous = new Map((before?.run.concepts ?? []).map(item => [item.id, item]));
  const current = new Map(after.run.concepts.map(item => [item.id, item]));
  const diff = (a: string[] = [], b: string[] = []) => b.filter(item => !a.includes(item));
  // Text is compared verbatim (no trimming); only a candidate present in both runs has a before/after pair.
  const textChange = (a: string | undefined, b: string | undefined): ConceptTextChange | null => a === undefined || b === undefined || a === b ? null : { before: a, after: b };
  return [...new Set([...previous.keys(), ...current.keys()])].map(id => {
    const old = previous.get(id); const next = current.get(id);
    return {
      id, title: (next ?? old)!.title, status: [old?.status ?? null, next?.status ?? null] as [Concept['status'] | null, Concept['status'] | null],
      text: { title: textChange(old?.title, next?.title), differentiation: textChange(old?.differentiation, next?.differentiation) },
      added: { requirements: diff(old?.requirements, next?.requirements), assumptions: diff(old?.assumptions, next?.assumptions), evidence_ids: diff(old?.evidence_ids, next?.evidence_ids) },
      removed: { requirements: diff(next?.requirements, old?.requirements), assumptions: diff(next?.assumptions, old?.assumptions), evidence_ids: diff(next?.evidence_ids, old?.evidence_ids) },
    };
  }).filter(change => change.status[0] !== change.status[1] || change.text.title || change.text.differentiation || Object.values(change.added).some(list => list.length) || Object.values(change.removed).some(list => list.length));
}

export interface HeldItem { kind: 'insufficient_evidence' | 'unresolved'; id: string | null; text: string; questions: string[] }

/** Everything the Agent held back: gaps without enough evidence and unresolved items, shown next to the candidates. */
export function heldItems(snapshot: RunSnapshot): HeldItem[] {
  const gaps = (snapshot.output?.gaps ?? []).filter(gap => gap.support_status === 'insufficient_evidence').map(gap => {
    const need = snapshot.output!.needs.find(item => item.id === gap.need_id);
    return { kind: 'insufficient_evidence' as const, id: gap.id, text: need ? `${need.pain} (${need.id})` : gap.need_id, questions: gap.questions };
  });
  return [...gaps, ...snapshot.run.unresolved.map(text => ({ kind: 'unresolved' as const, id: null, text, questions: [] }))];
}

// Document-update case: a run is pinned to one document version per model, so anything it cites from another version
// (or from a model outside its scope) is shown and exported as out of scope instead of silently mixed in.
export interface ScopeWarning { kind: 'evidence' | 'feature'; id: string; model_id: string; document_version: string; fixed_version: string | null }

export function scopeWarnings(snapshot: RunSnapshot, features: Feature[], evidence: Evidence[]): ScopeWarning[] {
  const fixed = (model: string) => (Object.hasOwn(snapshot.document_versions, model) ? snapshot.document_versions[model] : null);
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  const featureIds = new Set((snapshot.output?.gaps ?? []).flatMap(item => item.feature_ids));
  const items: ScopeWarning[] = [
    ...features.filter(item => featureIds.has(item.id)).map(item => ({ kind: 'feature' as const, id: item.id, model_id: item.model_id, document_version: item.document_version })),
    ...[...exportCitationIds(snapshot, features)].sort().flatMap(id => {
      const item = evidenceById.get(id);
      return item ? [{ kind: 'evidence' as const, id, model_id: item.model_id, document_version: item.document_version }] : [];
    }),
  ].map(item => ({ ...item, fixed_version: fixed(item.model_id) }));
  return items.filter(item => item.fixed_version !== item.document_version);
}

export function scopeWarningText(item: ScopeWarning): string {
  return item.fixed_version === null
    ? `${item.id}: ${item.model_id} 문서 ${item.document_version} — 검토 범위에 없는 모델`
    : `${item.id}: ${item.model_id} 문서 ${item.document_version} — 고정 범위는 문서 ${item.fixed_version}`;
}

export interface ConceptChange { id: string; title: string; before: Concept['status'] | null; after: Concept['status'] | null }

export function conceptChanges(before: RunSnapshot | undefined, after: RunSnapshot): ConceptChange[] {
  const previous = new Map((before?.run.concepts ?? []).map(item => [item.id, item]));
  const current = new Map(after.run.concepts.map(item => [item.id, item]));
  const ids = [...new Set([...previous.keys(), ...current.keys()])];
  return ids.map(id => ({ id, title: (current.get(id) ?? previous.get(id))!.title, before: previous.get(id)?.status ?? null, after: current.get(id)?.status ?? null }))
    .filter(change => change.before !== change.after);
}

// R27: meeting export with every cited source, requirement, assumption and open question.
export interface ExportDocument {
  meta: { mode: DataMode; notice: string; generated_at: string; run_id: string; previous_run_id: string | null; run_status: Run['status']; request_revision: number; dataset_version: string; dataset_sha256: string; document_versions: Record<string, string> };
  request: PlanningRequest;
  comparison: {
    model_id: string; need_id: string; gap_id: string | null; situation: string; pain: string; feature_ids: string[]; conditions: string[]; support_status: Gap['support_status'] | null; remaining_pain: string; evidence_ids: string[]; questions: string[]; missing_ids: string[];
    /** From the run's stored core record (null without one): resolution/basis per gap, desired outcome per need, and the cited reviews the same run did not judge a complaint. */
    resolution: string | null; support_basis: string | null; basis_mismatch: boolean; desired_outcome: string | null; non_complaint_reviews: { evidence_id: string; polarity: string }[];
  }[];
  concepts: Concept[];
  no_candidate_reasons?: string[];
  requirements: { concept_id: string; requirement: string }[];
  assumptions: { source_id: string; assumption: string }[];
  unresolved: string[];
  held: HeldItem[];
  scope_warnings: ScopeWarning[];
  lineage: { run_id: string; previous_run_id: string | null; request_revision: number; status: Run['status']; created_at: string }[];
  /** The stored core record (decision, terminal reasons, semantic review); null when the run has none. */
  judgement?: ExportJudgement | null;
  /**
   * The stored core record exactly as saved (trace, model calls with prompts and raw completions, semantic reviews with
   * their reviewed originals), so a meeting export keeps the full original and not only the summary above. JSON only.
   */
  execution_record?: unknown;
  evidence: { id: string; model_id: string; document_version: string; source_type: string; source_kind: string; source_id: string; location: string; text: string }[];
  /** Exported inputs the judgement itself never cites (only in the run's input scope); still exported in full, listed apart. */
  uncited_input_ids?: string[];
  completeness: ExportCompleteness;
}

export interface ExportCompleteness { complete: boolean; missing_evidence: string[]; missing_concepts: string[]; missing_requirements: string[]; missing_assumptions: string[]; missing_unresolved: string[]; missing_held: string[]; missing_scope_warnings: string[]; missing_gaps: string[]; mismatched_fields: string[] }

export const FIXTURE_NOTICE = '계약 fixture(모의) 예시입니다. Agent 출력이나 서버 응답이 아니며 실제 수요·성능을 입증하지 않습니다.';
export const LIVE_NOTICE = '실제 서버 응답에서 내보낸 기록입니다.';

/** Stored judgement facts for one comparison row; empty when the run has no readable core record. */
export function rowNotes(row: ComparisonRow, notes: JudgedNotes | null) {
  const basis = row.gap && notes ? notes.basis.get(row.gap.id) ?? null : null;
  return {
    resolution: row.gap && notes ? notes.resolution.get(row.gap.id) ?? null : null, support_basis: basis,
    // The declared status disagrees with what its manual basis allows (core SUPPORT_BASIS_MISMATCH).
    basis_mismatch: Boolean(basis && row.gap && SUPPORT_FROM_BASIS[basis] !== row.gap.support_status),
    desired_outcome: notes?.desired.get(row.need.id) ?? null,
    non_complaint_reviews: notes ? row.need.evidence_ids.flatMap(id => {
      const polarity = notes.polarity.get(id);
      return polarity && polarity !== 'complaint' && polarity !== 'conflicting' ? [{ evidence_id: id, polarity }] : [];
    }) : [],
  };
}

function exportComparison(output: RunOutput, features: Feature[], evidence: Evidence[], notes: JudgedNotes | null): ExportDocument['comparison'] {
  return buildComparison(output, features, evidence).map(row => ({
    model_id: row.need.model_id, need_id: row.need.id, gap_id: row.gap?.id ?? null, situation: row.need.situation, pain: row.need.pain, feature_ids: row.gap?.feature_ids ?? [], conditions: row.conditions,
    support_status: row.gap?.support_status ?? null, remaining_pain: row.gap?.remaining_pain ?? '', evidence_ids: row.evidence.map(item => item.id),
    questions: [...row.need.uncertainties, ...(row.gap?.questions ?? [])], missing_ids: row.missingIds, ...rowNotes(row, notes),
  }));
}

function exportEvidence(item: Evidence): ExportDocument['evidence'][number] {
  return { id: item.id, model_id: item.model_id, document_version: item.document_version, source_type: item.source_type, source_kind: item.source_kind, source_id: item.source_id, location: evidenceLocation(item), text: item.text };
}

function exportCitationIds(snapshot: RunSnapshot, features: Feature[]): Set<string> {
  return new Set([...snapshot.run.evidence_ids, ...judgedCitationIds(snapshot, features)]);
}

/** What the judgement actually cites: needs, gaps, candidates, events and the compared features (not the input scope). */
function judgedCitationIds(snapshot: RunSnapshot, features: Feature[]): Set<string> {
  const output = snapshot.output ?? { needs: [], gaps: [] };
  const featureIds = new Set(output.gaps.flatMap(item => item.feature_ids));
  return new Set([
    ...snapshot.run.events.flatMap(item => item.evidence_ids),
    ...output.needs.flatMap(item => item.evidence_ids), ...output.gaps.flatMap(item => item.evidence_ids),
    ...snapshot.run.concepts.flatMap(item => item.evidence_ids),
    ...features.filter(item => featureIds.has(item.id)).flatMap(item => item.evidence_ids),
  ]);
}

// Record 034 audit U4 (r2d6): the server's run.evidence_ids is the whole input scope, so uncited complaints looked cited.
function uncitedInputIds(snapshot: RunSnapshot, features: Feature[]): string[] {
  const judged = judgedCitationIds(snapshot, features);
  return [...exportCitationIds(snapshot, features)].filter(id => !judged.has(id)).sort();
}

export function buildExport(mode: DataMode, snapshot: RunSnapshot, features: Feature[], evidence: Evidence[], generatedAt: string, runs: RunSnapshot[] = [snapshot]): ExportDocument {
  const output = snapshot.output ?? { needs: [], gaps: [] };
  const cited = exportCitationIds(snapshot, features);
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  const doc: ExportDocument = {
    meta: {
      mode, notice: mode === 'fixture' ? FIXTURE_NOTICE : LIVE_NOTICE, generated_at: generatedAt, run_id: snapshot.run.id,
      previous_run_id: snapshot.previous_run_id, run_status: snapshot.run.status, request_revision: snapshot.request_revision,
      dataset_version: snapshot.run.dataset_version, dataset_sha256: snapshot.dataset_sha256, document_versions: { ...snapshot.document_versions },
    },
    request: structuredClone(snapshot.request),
    comparison: structuredClone(exportComparison(output, features, evidence, judgedNotes(snapshot))),
    uncited_input_ids: uncitedInputIds(snapshot, features),
    concepts: structuredClone(snapshot.run.concepts),
    no_candidate_reasons: [...(output.no_candidate_reasons ?? [])],
    requirements: snapshot.run.concepts.flatMap(concept => concept.requirements.map(requirement => ({ concept_id: concept.id, requirement }))),
    assumptions: [
      ...snapshot.run.concepts.flatMap(concept => concept.assumptions.map(assumption => ({ source_id: concept.id, assumption }))),
      ...snapshot.unconfirmed.map(assumption => ({ source_id: snapshot.run.id, assumption })),
    ],
    unresolved: [...snapshot.run.unresolved],
    held: structuredClone(heldItems(snapshot).filter(item => item.kind === 'insufficient_evidence')),
    scope_warnings: scopeWarnings(snapshot, features, evidence),
    lineage: runLineage(snapshot, runs).map(item => ({ run_id: item.run.id, previous_run_id: item.previous_run_id, request_revision: item.request_revision, status: item.run.status, created_at: item.created_at })),
    judgement: exportJudgement(snapshot),
    execution_record: storedExecution(snapshot),
    evidence: [...cited].sort().map(id => {
      const item = evidenceById.get(id);
      return item
        ? exportEvidence(item)
        : { id, model_id: '', document_version: '', source_type: '', source_kind: '', source_id: '', location: '자료 누락', text: '원문을 찾을 수 없습니다.' };
    }),
    completeness: { complete: false, missing_evidence: [], missing_concepts: [], missing_requirements: [], missing_assumptions: [], missing_unresolved: [], missing_held: [], missing_scope_warnings: [], missing_gaps: [], mismatched_fields: [] },
  };
  doc.completeness = exportCompleteness(doc, snapshot, features, evidence, runs);
  return doc;
}

/** Follows previous_run_id links back to the first run, so an export shows how the request evolved. */
export function runLineage(snapshot: RunSnapshot, runs: RunSnapshot[]): RunSnapshot[] {
  const byId = new Map(runs.map(item => [item.run.id, item]));
  const chain: RunSnapshot[] = [];
  for (let current: RunSnapshot | undefined = snapshot; current && !chain.includes(current); current = current.previous_run_id ? byId.get(current.previous_run_id) : undefined) chain.unshift(current);
  return chain;
}

/** Compares the downloadable document with the selected snapshot and source data, not with its own badge. */
export function exportCompleteness(doc: ExportDocument, snapshot: RunSnapshot, features: Feature[], evidence: Evidence[], runs: RunSnapshot[] = [snapshot]): ExportCompleteness {
  const output = snapshot.output ?? { needs: [], gaps: [] };
  const cited = exportCitationIds(snapshot, features);
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  const withText = new Set(doc.evidence.filter(item => {
    const source = evidenceById.get(item.id);
    return source && source.text.trim() && canonical(item) === canonical(exportEvidence(source));
  }).map(item => item.id));
  const requirements = new Set(doc.requirements.map(item => `${item.concept_id}
${item.requirement}`));
  const assumptions = new Set(doc.assumptions.map(item => canonical(item)));
  const expectedRequirements = snapshot.run.concepts.flatMap(concept => concept.requirements.map(requirement => ({ concept_id: concept.id, requirement })));
  const expectedAssumptions = [
    ...snapshot.run.concepts.flatMap(concept => concept.assumptions.map(assumption => ({ source_id: concept.id, assumption }))),
    ...snapshot.unconfirmed.map(assumption => ({ source_id: snapshot.run.id, assumption })),
  ];
  const expectedHeld = heldItems(snapshot).filter(item => item.kind === 'insufficient_evidence');
  const expectedScope = scopeWarnings(snapshot, features, evidence);
  const expectedLineage = runLineage(snapshot, runs).map(item => ({ run_id: item.run.id, previous_run_id: item.previous_run_id, request_revision: item.request_revision, status: item.run.status, created_at: item.created_at }));
  const expectedMeta = { run_id: snapshot.run.id, previous_run_id: snapshot.previous_run_id, run_status: snapshot.run.status, request_revision: snapshot.request_revision, dataset_version: snapshot.run.dataset_version, dataset_sha256: snapshot.dataset_sha256, document_versions: snapshot.document_versions };
  const actualMeta = { run_id: doc.meta.run_id, previous_run_id: doc.meta.previous_run_id, run_status: doc.meta.run_status, request_revision: doc.meta.request_revision, dataset_version: doc.meta.dataset_version, dataset_sha256: doc.meta.dataset_sha256, document_versions: doc.meta.document_versions };
  const fields: [string, unknown, unknown][] = [
    ['실행·자료 버전', actualMeta, expectedMeta], ['기획 요청', doc.request, snapshot.request],
    ['불편·기능 대조표', doc.comparison, exportComparison(output, features, evidence, judgedNotes(snapshot))],
    ['콘셉트 후보', doc.concepts, snapshot.run.concepts],
    ['후보 없음 사유', doc.no_candidate_reasons ?? [], output.no_candidate_reasons ?? []], ['요구사항', doc.requirements, expectedRequirements],
    ['가정·미확인', doc.assumptions, expectedAssumptions], ['미해결', doc.unresolved, snapshot.run.unresolved],
    ['근거 부족 보류', doc.held, expectedHeld], ['검토 범위 밖 문서 버전', doc.scope_warnings, expectedScope], ['실행 계보', doc.lineage, expectedLineage],
    ['인용 근거 ID', doc.evidence.map(item => item.id).sort(), [...cited].sort()],
    ['판단에 인용되지 않은 입력', doc.uncited_input_ids ?? [], uncitedInputIds(snapshot, features)],
    ['판단 실행 기록', doc.judgement ?? null, exportJudgement(snapshot)],
    ['원 실행 기록', doc.execution_record ?? null, storedExecution(snapshot)],
  ];
  const result = {
    missing_evidence: [...cited].filter(id => !withText.has(id)),
    missing_concepts: snapshot.run.concepts.filter(concept => !doc.concepts.some(item => canonical(item) === canonical(concept))).map(concept => concept.id),
    missing_requirements: snapshot.run.concepts.flatMap(concept => concept.requirements.filter(item => !requirements.has(`${concept.id}
${item}`))),
    missing_assumptions: expectedAssumptions.filter(item => !assumptions.has(canonical(item))).map(item => item.assumption),
    missing_unresolved: snapshot.run.unresolved.filter(item => !doc.unresolved.includes(item)),
    missing_held: expectedHeld.filter(item => !doc.held.some(held => canonical(held) === canonical(item))).map(item => item.id ?? item.text),
    missing_scope_warnings: expectedScope.filter(item => !(doc.scope_warnings ?? []).some(warning => canonical(warning) === canonical(item))).map(item => item.id),
    // Every stored gap must reach the export, including one whose need is missing from the output.
    missing_gaps: output.gaps.filter(gap => !doc.comparison.some(row => row.gap_id === gap.id)).map(gap => gap.id),
    mismatched_fields: [
      ...fields.filter(([, actual, expected]) => canonical(actual) !== canonical(expected)).map(([label]) => label),
      ...doc.comparison.filter(row => row.missing_ids.length).map(row => `대조표 연결 자료 누락: ${row.need_id} (${row.missing_ids.join(', ')})`),
    ],
  };
  return { complete: Object.values(result).every(list => !list.length), ...result };
}

const STATUS_LABELS: Record<string, string> = {
  supported: '기존 기능 제공', unsupported: '설명서상 미지원', insufficient_evidence: '근거 부족·보류',
  proposed: '제안', needs_review: '검토 필요', accepted: '채택', rejected: '제외',
};

export function statusLabel(status: string | null): string {
  return status ? STATUS_LABELS[status] ?? status : '없음';
}

function cell(text: string): string {
  return text.replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

const DECISION_TEXT: Record<string, string> = { accept: '계약 검사 통과(의미 검증 아님)', hold: '보류', revise: '수정 중', unresolved: '미해결 종료' };
const STATUS_TEXT: Record<string, string> = { completed: '완료', held: '보류', failed: '실패' };
export const RESOLUTION_TEXT: Record<string, string> = { resolved: '불편 해소', remaining: '불편 남음', unknown: '해소 여부 알 수 없음' };
export const POLARITY_TEXT: Record<string, string> = { complaint: '불편', positive: '긍정', conflicting: '상충', irrelevant: '무관', uncertain: '불확실' };
const BASIS_TEXT: Record<string, string> = { explicit_supported: '설명서에 지원 명시', explicit_unsupported: '설명서에 미지원 명시', unmentioned: '설명서 미언급', conflicting: '설명서 상충' };
const DUPLICATION_TEXT: Record<string, string> = { distinct: '기존 기능과 다름', duplicate: '기존 기능과 중복', uncertain: '중복 여부 불확실' };

/** The 판단 cell: current-feature support, then whether the pain was resolved, then a declared/basis mismatch. */
export function comparisonVerdict(row: Pick<ExportDocument['comparison'][number], 'support_status' | 'resolution' | 'support_basis' | 'basis_mismatch'>): string {
  return [
    statusLabel(row.support_status),
    row.resolution ? RESOLUTION_TEXT[row.resolution] ?? row.resolution : null,
    row.basis_mismatch && row.support_basis ? `선언과 설명서 근거(${BASIS_TEXT[row.support_basis] ?? row.support_basis}) 불일치` : null,
  ].filter(Boolean).join(' · ');
}

// The budget closes before the final correction runs. revision_limit can coexist with a connection/other execution error.
const SOURCE_KINDS: Record<string, string> = { synthetic: '합성자료', public: '공개자료', licensed: '이용허락 자료', private: '비공개 자료' };

/** Real vs synthetic origin stays visible wherever a source is quoted. */
export function sourceKindLabel(kind: string): string {
  return SOURCE_KINDS[kind] ?? kind;
}

export const TERMINAL_TEXT: Record<string, string> = {
  revision_limit: '내부 수정 한도 도달(구체적인 종료 경과는 실행 기록 확인)', hold: '보류로 종료(내부 수정 없음)', unresolved: '미해결 종료',
  backend_failure: '모델 연결 오류로 중단', policy_changed: '수정 정책 변경으로 중단', completed: '완료',
};

/** The run's stored planning_execution, copied as is (null when the run has none). */
export function storedExecution(snapshot: RunSnapshot): unknown {
  const raw = (snapshot.output as Record<string, unknown> | null)?.planning_execution;
  return raw === undefined || raw === null ? null : structuredClone(raw);
}

const RAW_NOTE = '- 원 실행 기록 전체(trace·모델 호출의 프롬프트와 원 응답·의미 검토 원본)는 JSON 내보내기의 `execution_record`에 저장된 그대로 들어 있습니다.';

function judgementMarkdown(judgement: ExportJudgement | null): string[] {
  if (!judgement) return [];
  const list = (title: string, items: string[]) => [`${title}:`, ...(items.length ? items.map(item => `- ${item}`) : ['- 없음']), ''];
  if (!judgement.record_valid) return ['## 판단 실행 기록', '', '- **저장된 판단 기록의 형식이 맞지 않아 결과로 쓰지 않았습니다.**', ...judgement.record_errors.map(item => `- ${item}`), RAW_NOTE, ''];
  return [
    '## 판단 실행 기록', '',
    `- 실행 종류: ${executionKindText(judgement.execution_kind, judgement.model_calls)} · 종료 상태: ${STATUS_TEXT[judgement.status]} · 코어 결정: ${judgement.decision ? DECISION_TEXT[judgement.decision] ?? judgement.decision : '없음'}`,
    `- 모델: ${judgement.models.join(', ') || '호출 기록 없음'} · 호출 ${judgement.model_calls}회${judgement.model_calls ? ` · 모델 시간 ${seconds(judgement.metrics.model_elapsed_ms)}` : ''}`,
    // Record 034 audit U5: reported usage (미기록, never 0, when absent); run time is cumulative and includes retrieval and checks.
    `- 토큰(모델 서버 보고): ${tokenText(judgement.metrics)} · 생성 설정: ${judgement.model_calls ? judgement.metrics.settings.join(' / ') || '미기록' : '호출 없음'} · 전체 실행 시간(조회·검사 포함): ${seconds(judgement.metrics.run_elapsed_ms)}`,
    `- Agent 내부 수정: ${judgement.internal_revisions.used}/${judgement.internal_revisions.max}회 (같은 요청 안 자동 수정 · 기획자 조건 변경은 위 요청 회차)`,
    ...(judgement.terminal_reason ? [`- 종료 사유: ${TERMINAL_TEXT[judgement.terminal_reason] ?? judgement.terminal_reason} (\`${judgement.terminal_reason}\`)`] : []), RAW_NOTE, '',
    ...list('검증 범위(이 실행이 확인하지 않은 것)', scopeLines(judgement.scope, judgement.execution_kind)),
    ...(judgement.unrevised_errors.length && judgement.hold_causes.length
      ? [...list('보류를 일으킨 문제(근거 확인 필요)', judgement.hold_causes), ...list('함께 발견된 판단 오류(보류로 내부 수정하지 않음)', judgement.unrevised_errors)]
      : list('검사에서 발견한 문제', judgement.violations)),
    ...(judgement.record_problems.length ? list('저장 기록 불일치', judgement.record_problems) : []),
    ...(judgement.errors.length ? list('실행 오류', judgement.errors.map(item => `${item.code}: ${item.message}${item.details.length ? ` — 세부 검사: ${item.details.map(errorDetailText).join(' / ')}` : ''}${item.notes.length ? ` — ${item.notes.join(' / ')}` : ''}`)) : []),
    ...list('확인할 질문', judgement.questions.map(reasonText)), ...list('보류 사유', judgement.hold_reasons.map(reasonText)),
    ...list('미해결', judgement.unresolved.map(reasonText)),
    ...list(`후보 없음 사유(판단 모델 작성 · 후보 없음 검토 ${judgement.no_candidate_reviews ? `${judgement.no_candidate_reviews}회` : '없음'})`, judgement.no_candidate_reasons.map(reasonText)),
    ...(judgement.rejected_candidates.length ? list('검사에서 거절된 후보(선택 대상 아님)', judgement.rejected_candidates.map(item => `${item.id} ${item.title} · 대응 Gap ${item.gap_ids.join(', ') || '없음'}${item.lineage_valid === null ? '' : item.lineage_valid ? ' · 확인된 불편 Gap에 연결됨' : ' · 확인되지 않은 Gap에 연결됨'} · ${item.codes.length ? `검사 위반: ${item.codes.map(reasonText).join(' / ')}` : item.lineage_valid === null ? '후보별 사유 기록 없음' : '자기 위반 없음, 실행 전체가 끝나 선택 불가'}`)) : []),
    // Record 034 audit U3: the Agent's internal check rounds (not the planner's request revisions), repeats marked.
    ...(judgement.check_rounds.length ? list('회차별 검사 결과(Agent 내부 수정 회차, 사용자 조건 변경 회차와 다름)', judgement.check_rounds.map(round => `${round.round}회차(내부 수정 ${round.revision_count}회 뒤): ${DECISION_TEXT[round.action] ?? round.action} · 위반 ${round.codes.join(', ') || '없음'}${round.details.length ? ` · 세부: ${round.details.join(' / ')}` : ''}${round.repeated ? ' · 이전 회차와 같은 위반 반복' : ''}`)) : []),
    // Record 034 audit U4: the model's own declarations behind the violations, so the export explains them like the screen.
    ...(judgement.review_assessments.length ? list('리뷰 판단(판단 모델의 선언, 독립 검증 아님)', judgement.review_assessments.map(item => `${item.evidence_id}: ${POLARITY_TEXT[item.polarity] ?? item.polarity} — ${item.reason}`)) : []),
    ...(judgement.unused_review_ids.length ? list('어느 불편·Gap에도 쓰이지 않은 리뷰', judgement.unused_review_ids.map(id => `${id}(${POLARITY_TEXT[judgement.review_assessments.find(item => item.evidence_id === id)?.polarity ?? ''] ?? '판단 없음'})`)) : []),
    ...(judgement.gap_assessments.length ? list('기능 대조 판단(판단 모델의 선언)', judgement.gap_assessments.map(item => `${item.gap_id}: ${BASIS_TEXT[item.support_basis] ?? item.support_basis} · ${RESOLUTION_TEXT[item.resolution] ?? item.resolution} — ${item.reason}`)) : []),
    ...(judgement.concept_assessments.length ? list('후보 중복 판단(판단 모델의 선언)', judgement.concept_assessments.map(item => `${item.concept_id}${item.from === 'rejected_output' ? '(거절된 출력)' : ''}: ${DUPLICATION_TEXT[item.duplication] ?? item.duplication} — ${item.reason}${item.has_candidate ? '' : ' · 이 ID의 후보 본문은 저장되지 않음'}`)) : []),
    ...(judgement.semantic_reviews.length ? [
      `의미 검토 ${judgement.semantic_reviews.length}회 (판단과 같은 모델의 검토 선언, 독립 검증 아님):`, '',
      '| 회차 | 후보 | 대상 | 판정 | 후보 인용 | 사유 |', '|---|---|---|---|---|---|',
      ...judgement.semantic_rows.map(row => `| ${row.round} | ${cell(row.concept_id)} | ${cell(row.target)} | ${cell(row.verdict)} | ${cell(row.candidate_quote)} | ${cell(row.reason)} |`), '',
    ] : []),
  ];
}

export function exportMarkdown(doc: ExportDocument): string {
  const lines = [
    `# 키친 상품기획 검토 — ${doc.meta.run_id}`, '',
    `> ${doc.meta.notice}`, '',
    `- 실행 상태: ${doc.meta.run_status} · 요청 회차: ${doc.meta.request_revision} · 이전 실행: ${doc.meta.previous_run_id ?? '없음'}`,
    `- 자료 버전: ${doc.meta.dataset_version} · 문서 버전: ${Object.entries(doc.meta.document_versions).map(([model, version]) => `${model} ${version}`).join(', ')}`,
    `- 내보낸 시각: ${doc.meta.generated_at}`, '',
    '## 기획 요청', '',
    `- 제품군: ${doc.request.product_group}`, `- 대상 고객: ${doc.request.target_customer}`, `- 사용 상황: ${doc.request.use_situation}`,
    `- 기획 요청: ${doc.request.improvement_task}`, `- 제외 조건: ${doc.request.exclusions.join(', ') || '(없음)'}`, `- 검토 모델: ${doc.request.model_ids.join(', ')}`, '',
    '## 불편·기존 기능 대조표', '',
    ...(doc.judgement?.record_valid && (doc.judgement.decision !== 'accept' || doc.judgement.status !== 'completed' || doc.judgement.violations.length > 0 || doc.judgement.record_problems.length > 0) ? [`> 코어가 채택하지 않은 실행이거나 저장 기록이 일치하지 않습니다(${STATUS_TEXT[doc.judgement.status]}). 원문 검토용이며 결론이 아닙니다. '판단'은 현재 기능의 설명서 지원이고, 불편 해소 여부는 따로 적었습니다.`, ''] : []),
    '| 모델 | 불편 | 연결 기능 | 기능 조건 | 판단 | 남은 불편 | 근거 | 확인할 질문 |', '|---|---|---|---|---|---|---|---|',
    ...doc.comparison.map(row => `| ${cell(row.model_id)} | ${cell(`${row.need_id}${row.gap_id ? `/${row.gap_id}` : ''}: ${row.pain}${row.desired_outcome ? ` → 바라는 결과: ${row.desired_outcome}` : ''}`)} | ${cell(row.feature_ids.join(', ') || '없음')} | ${cell(row.conditions.join(', ') || '없음')} | ${cell(comparisonVerdict(row))} | ${cell(row.remaining_pain || '-')} | ${cell(`${row.evidence_ids.join(', ')}${row.non_complaint_reviews.length ? ` · 불편 근거로 인용했지만 같은 실행이 불편으로 판단하지 않은 리뷰: ${row.non_complaint_reviews.map(item => `${item.evidence_id}(${POLARITY_TEXT[item.polarity] ?? item.polarity})`).join(', ')}` : ''}`)} | ${cell(row.questions.join(' / ') || '-')} |`),
    '', '## 콘셉트 후보', '',
  ];
  const rejected = doc.judgement?.record_valid ? doc.judgement.rejected_candidates : [];
  // Record 034: "none generated" is wrong when the model generated candidates that the core check turned down.
  if (!doc.concepts.length) lines.push(rejected.length
    ? `채택된 콘셉트가 없습니다. 모델이 만든 후보 ${rejected.length}개(${rejected.map(item => item.id).join(', ')})는 코어 검사에서 거절되어 선택 대상이 아닙니다(아래 '판단 실행 기록'의 거절 후보 참조).`
    : '생성된 콘셉트가 없습니다.', '');
  // With a core record the same reasons are listed once under '판단 실행 기록' (record 034 audit U4: they appeared three times).
  if (doc.no_candidate_reasons?.length) lines.push(...(doc.judgement?.record_valid
    ? [`후보 없음 사유 ${doc.no_candidate_reasons.length}건은 아래 '판단 실행 기록'에 있습니다.`]
    : ['후보 없음 사유:', ...doc.no_candidate_reasons.map(item => `- ${reasonText(item)}`)]), '');
  for (const concept of doc.concepts) {
    lines.push(`### ${concept.id} — ${concept.title} (${statusLabel(concept.status)})`, '', `- 유형: ${concept.kind} · 대응 간극: ${concept.gap_ids.join(', ')}`, `- 차별점: ${concept.differentiation}`, `- 근거: ${concept.evidence_ids.join(', ')}`, '', '요구사항:', ...concept.requirements.map(item => `- ${item}`), '', '확인할 가정:', ...(concept.assumptions.length ? concept.assumptions.map(item => `- ${item}`) : ['- 없음']), '');
  }
  const runAssumptions = doc.assumptions.filter(item => item.source_id === doc.meta.run_id);
  lines.push('## 실행 단위 미확인 사항', '', ...(runAssumptions.length ? runAssumptions.map(item => `- ${item.assumption}`) : ['- 없음']), '');
  lines.push('## 미해결·보류', '', ...(doc.unresolved.length ? doc.unresolved.map(item => `- ${reasonText(item)}`) : ['- 없음']), '');
  lines.push('## 근거 부족으로 보류한 불편', '', ...(doc.held.length ? doc.held.map(item => `- ${item.id}: ${item.text}${item.questions.length ? ` — 확인할 질문: ${item.questions.join(' / ')}` : ''}`) : ['- 없음']), '');
  lines.push('## 검토 범위 밖 문서 버전', '', ...(doc.scope_warnings.length ? doc.scope_warnings.map(item => `- ${scopeWarningText(item)}`) : ['- 없음']), '');
  lines.push(...judgementMarkdown(doc.judgement ?? null));
  lines.push('## 실행 계보', '', ...doc.lineage.map(item => `- ${item.run_id} · 요청 회차 ${item.request_revision} · ${item.status} · ${item.created_at}${item.previous_run_id ? ` (← ${item.previous_run_id})` : ' (첫 실행)'}`), '');
  const missing = Object.entries(doc.completeness).filter(([key, value]) => key !== 'complete' && Array.isArray(value) && value.length);
  lines.push('## 내보내기 점검', '', doc.completeness.complete ? '- 선택 실행의 요청·후보·인용 근거 원문·요구사항·가정·미확인·미해결·보류·계보가 모두 포함되었습니다.' : '- **누락이 있습니다. 원본과 일치하지 않거나 확인할 수 없는 항목을 검토하세요.**', ...missing.map(([key, value]) => `- ${key}: ${(value as string[]).join(', ')}`), '');
  const uncited = new Set(doc.uncited_input_ids ?? []);
  const evidenceLine = (item: ExportDocument['evidence'][number]) => `- **${item.id}** (${item.model_id} · 문서 ${item.document_version} · ${item.location} · ${item.source_id}, ${item.source_kind}): ${item.text}`;
  lines.push('## 인용 근거 원문', '', ...doc.evidence.filter(item => !uncited.has(item.id)).map(evidenceLine), '');
  if (uncited.size) lines.push('## 판단에 인용되지 않은 입력 원문', '', '- 판단에 입력됐지만 불편·Gap·후보·기능 근거로 인용되지 않은 원문입니다. 판단이 다루지 않은 불편이 있는지 확인하세요.', ...doc.evidence.filter(item => uncited.has(item.id)).map(evidenceLine), '');
  return lines.join('\n');
}
