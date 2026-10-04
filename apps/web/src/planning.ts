/** Planner-side logic for the four workspace areas; pure functions shared by fixture and live modes. */
import Ajv2020 from 'ajv/dist/2020';
import schema from '../../../packages/contracts/schemas/lgax.schema.json';
import { ApiError } from './api';
import { evidenceLocation } from './domain';
import type { Evidence, ProductGroup } from './domain';

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
export interface RunOutput { needs: Need[]; gaps: Gap[] }
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
  return output.needs.map(need => {
    const gap = output.gaps.find(item => item.need_id === need.id);
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
const FOCUS_SUFFIX = /\s*\[집중 검토: [^\]]*\]$/;
const EXCLUDED_CANDIDATE = /^후보 제외: /;

export function candidateExclusion(concept: Pick<Concept, 'id' | 'title'>): string {
  return `후보 제외: ${concept.title} (${concept.id})`;
}

export function buildRerunRequest(base: PlanningRequest, concepts: Concept[], choices: Record<string, CandidateChoice>, conditions: string[]): PlanningRequest {
  const cleaned = [...new Set(conditions.map(item => item.trim()).filter(item => item && !EXCLUDED_CANDIDATE.test(item)))];
  const excluded = concepts.filter(concept => choices[concept.id] === 'exclude').map(candidateExclusion);
  const focused = concepts.filter(concept => choices[concept.id] === 'focus');
  const task = base.improvement_task.replace(FOCUS_SUFFIX, '');
  const request: PlanningRequest = {
    ...base,
    improvement_task: focused.length ? `${task} [집중 검토: ${focused.map(concept => `${concept.title} (${concept.id})`).join(', ')}]` : task,
    exclusions: [...cleaned, ...excluded],
  };
  const errors = contractErrors('PlanningRequest', request);
  if (errors.length) throw new ApiError('INVALID_ARGUMENT', `재실행 요청이 공통 규격과 다릅니다. ${errors.join('; ')}`);
  return request;
}

/** Splits a request's exclusions into planner conditions and candidate exclusions written by buildRerunRequest. */
export function splitConditions(request: PlanningRequest): { conditions: string[]; excludedCandidates: string[] } {
  return {
    conditions: request.exclusions.filter(item => !EXCLUDED_CANDIDATE.test(item)),
    excludedCandidates: request.exclusions.filter(item => EXCLUDED_CANDIDATE.test(item)),
  };
}

export interface ConceptDetailChange { id: string; title: string; status: [Concept['status'] | null, Concept['status'] | null]; added: { requirements: string[]; assumptions: string[]; evidence_ids: string[] }; removed: { requirements: string[]; assumptions: string[]; evidence_ids: string[] } }

/** Field-level before/after for each candidate, so a revision shows what changed inside a concept, not only its status. */
export function conceptDetailChanges(before: RunSnapshot | undefined, after: RunSnapshot): ConceptDetailChange[] {
  const previous = new Map((before?.run.concepts ?? []).map(item => [item.id, item]));
  const current = new Map(after.run.concepts.map(item => [item.id, item]));
  const diff = (a: string[] = [], b: string[] = []) => b.filter(item => !a.includes(item));
  return [...new Set([...previous.keys(), ...current.keys()])].map(id => {
    const old = previous.get(id); const next = current.get(id);
    return {
      id, title: (next ?? old)!.title, status: [old?.status ?? null, next?.status ?? null] as [Concept['status'] | null, Concept['status'] | null],
      added: { requirements: diff(old?.requirements, next?.requirements), assumptions: diff(old?.assumptions, next?.assumptions), evidence_ids: diff(old?.evidence_ids, next?.evidence_ids) },
      removed: { requirements: diff(next?.requirements, old?.requirements), assumptions: diff(next?.assumptions, old?.assumptions), evidence_ids: diff(next?.evidence_ids, old?.evidence_ids) },
    };
  }).filter(change => change.status[0] !== change.status[1] || Object.values(change.added).some(list => list.length) || Object.values(change.removed).some(list => list.length));
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
  comparison: { model_id: string; need_id: string; situation: string; pain: string; feature_ids: string[]; conditions: string[]; support_status: Gap['support_status'] | null; remaining_pain: string; evidence_ids: string[]; questions: string[]; missing_ids: string[] }[];
  concepts: Concept[];
  requirements: { concept_id: string; requirement: string }[];
  assumptions: { source_id: string; assumption: string }[];
  unresolved: string[];
  evidence: { id: string; model_id: string; document_version: string; source_type: string; source_kind: string; source_id: string; location: string; text: string }[];
}

export const FIXTURE_NOTICE = '계약 fixture(모의) 예시입니다. Agent 출력이나 서버 응답이 아니며 실제 수요·성능을 입증하지 않습니다.';
export const LIVE_NOTICE = '실제 서버 응답에서 내보낸 기록입니다.';

export function buildExport(mode: DataMode, snapshot: RunSnapshot, features: Feature[], evidence: Evidence[], generatedAt: string): ExportDocument {
  const output = snapshot.output ?? { needs: [], gaps: [] };
  const rows = buildComparison(output, features, evidence);
  const cited = new Set([
    ...snapshot.run.evidence_ids,
    ...output.needs.flatMap(item => item.evidence_ids),
    ...output.gaps.flatMap(item => item.evidence_ids),
    ...snapshot.run.concepts.flatMap(item => item.evidence_ids),
  ]);
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  return {
    meta: {
      mode, notice: mode === 'fixture' ? FIXTURE_NOTICE : LIVE_NOTICE, generated_at: generatedAt, run_id: snapshot.run.id,
      previous_run_id: snapshot.previous_run_id, run_status: snapshot.run.status, request_revision: snapshot.request_revision,
      dataset_version: snapshot.run.dataset_version, dataset_sha256: snapshot.dataset_sha256, document_versions: snapshot.document_versions,
    },
    request: snapshot.request,
    comparison: rows.map(row => ({
      model_id: row.need.model_id, need_id: row.need.id, situation: row.need.situation, pain: row.need.pain, feature_ids: row.gap?.feature_ids ?? [], conditions: row.conditions,
      support_status: row.gap?.support_status ?? null, remaining_pain: row.gap?.remaining_pain ?? '', evidence_ids: row.evidence.map(item => item.id),
      questions: [...row.need.uncertainties, ...(row.gap?.questions ?? [])], missing_ids: row.missingIds,
    })),
    concepts: snapshot.run.concepts,
    requirements: snapshot.run.concepts.flatMap(concept => concept.requirements.map(requirement => ({ concept_id: concept.id, requirement }))),
    assumptions: [
      ...snapshot.run.concepts.flatMap(concept => concept.assumptions.map(assumption => ({ source_id: concept.id, assumption }))),
      ...snapshot.unconfirmed.map(assumption => ({ source_id: snapshot.run.id, assumption })),
    ],
    unresolved: snapshot.run.unresolved,
    evidence: [...cited].sort().map(id => {
      const item = evidenceById.get(id);
      return item
        ? { id, model_id: item.model_id, document_version: item.document_version, source_type: item.source_type, source_kind: item.source_kind, source_id: item.source_id, location: evidenceLocation(item), text: item.text }
        : { id, model_id: '', document_version: '', source_type: '', source_kind: '', source_id: '', location: '자료 누락', text: '원문을 찾을 수 없습니다.' };
    }),
  };
}

const STATUS_LABELS: Record<string, string> = {
  supported: '기존 기능으로 해결', unsupported: '남은 불편 있음', insufficient_evidence: '근거 부족·보류',
  proposed: '제안', needs_review: '검토 필요', accepted: '채택', rejected: '제외',
};

export function statusLabel(status: string | null): string {
  return status ? STATUS_LABELS[status] ?? status : '없음';
}

function cell(text: string): string {
  return text.replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
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
    '| 모델 | 불편 | 연결 기능 | 기능 조건 | 판단 | 남은 불편 | 근거 | 확인할 질문 |', '|---|---|---|---|---|---|---|---|',
    ...doc.comparison.map(row => `| ${cell(row.model_id)} | ${cell(`${row.need_id}: ${row.pain}`)} | ${cell(row.feature_ids.join(', ') || '없음')} | ${cell(row.conditions.join(', ') || '없음')} | ${cell(statusLabel(row.support_status))} | ${cell(row.remaining_pain || '-')} | ${cell(row.evidence_ids.join(', '))} | ${cell(row.questions.join(' / ') || '-')} |`),
    '', '## 콘셉트 후보', '',
  ];
  if (!doc.concepts.length) lines.push('생성된 콘셉트가 없습니다.', '');
  for (const concept of doc.concepts) {
    lines.push(`### ${concept.id} — ${concept.title} (${statusLabel(concept.status)})`, '', `- 유형: ${concept.kind} · 대응 간극: ${concept.gap_ids.join(', ')}`, `- 차별점: ${concept.differentiation}`, `- 근거: ${concept.evidence_ids.join(', ')}`, '', '요구사항:', ...concept.requirements.map(item => `- ${item}`), '', '확인할 가정:', ...(concept.assumptions.length ? concept.assumptions.map(item => `- ${item}`) : ['- 없음']), '');
  }
  const runAssumptions = doc.assumptions.filter(item => item.source_id === doc.meta.run_id);
  lines.push('## 실행 단위 미확인 사항', '', ...(runAssumptions.length ? runAssumptions.map(item => `- ${item.assumption}`) : ['- 없음']), '');
  lines.push('## 미해결·보류', '', ...(doc.unresolved.length ? doc.unresolved.map(item => `- ${item}`) : ['- 없음']), '');
  lines.push('## 인용 근거 원문', '', ...doc.evidence.map(item => `- **${item.id}** (${item.model_id} · 문서 ${item.document_version} · ${item.location} · ${item.source_id}, ${item.source_kind}): ${item.text}`), '');
  return lines.join('\n');
}
