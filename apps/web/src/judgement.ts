/**
 * Web side of the CORE-001 judgement contract (P2-CORE-001, PR #51): validates a core judgement output and the
 * core's review decision, and turns them into what the planner screens show. It never re-judges anything: the
 * decision (accept/hold/revise/unresolved) always comes from lgax_core.judgement_contract.review_judgement.
 * Fixture outputs from evals/core-contract are hand-written declarations, not model results.
 */
import Ajv2020 from 'ajv/dist/2020';
import inputSchema from '../../../evals/core-contract/schemas/input.json';
import outputSchema from '../../../evals/core-contract/schemas/output.json';
import type { Evidence } from './domain';
import { canonical } from './planning';
import type { Concept, Feature, Gap, Need, PlanningRequest, RunSnapshot } from './planning';

export interface JudgementInput {
  request: PlanningRequest;
  product: { model_id: string; name: string; product_group: PlanningRequest['product_group']; document_version: string; source_kind: string };
  sources: Evidence[]; features: Feature[]; revision_count: number; max_concepts: number; changed_evidence_ids: string[];
}

export interface JudgementOutput {
  input_sha256: string; model_id: string; document_version: string; revision_count: number;
  status: 'completed' | 'held' | 'failed';
  needs: Need[]; gaps: Gap[]; concepts: Concept[];
  desired_outcomes: { need_id: string; desired_outcome: string }[];
  review_assessments: { evidence_id: string; polarity: 'complaint' | 'positive' | 'conflicting' | 'irrelevant' | 'uncertain'; reason: string }[];
  gap_assessments: { gap_id: string; support_basis: 'explicit_supported' | 'explicit_unsupported' | 'unmentioned' | 'conflicting'; resolution: 'resolved' | 'remaining' | 'unknown'; reason: string }[];
  concept_assessments: { concept_id: string; duplication: 'distinct' | 'duplicate' | 'uncertain'; compared_feature_ids: string[]; reason: string }[];
  questions: string[]; hold_reasons: string[]; unresolved: string[]; no_candidate_reasons: string[];
}

export type JudgementStage = 'plan' | 'retrieve' | 'needs' | 'compare' | 'concepts' | 'review';
export interface JudgementDecision {
  valid: boolean; action: 'accept' | 'hold' | 'revise' | 'unresolved'; revision_count: number; next_revision_count: number;
  rerun_from: JudgementStage | null; violations: JudgementViolation[];
}
/** `details` is what the core attaches to its own decisions (a failed stage's error details, a semantic review row). */
export interface JudgementViolation { code: string; stage: JudgementStage; details?: unknown }
/** A decision as stored in a run record. next_revision_count is checked separately so its absence stays visible. */
export type StoredDecision = Omit<JudgementDecision, 'next_revision_count'> & { next_revision_count?: number };

const STAGES: JudgementStage[] = ['plan', 'retrieve', 'needs', 'compare', 'concepts', 'review'];
const decisionProperties = {
  valid: { type: 'boolean' }, action: { enum: ['accept', 'hold', 'revise', 'unresolved'] },
  revision_count: { type: 'integer', minimum: 0, maximum: 2 }, next_revision_count: { type: 'integer', minimum: 0, maximum: 2 },
  rerun_from: { enum: [...STAGES, null] },
  violations: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['code', 'stage'], properties: { code: { type: 'string', minLength: 1 }, stage: { enum: STAGES }, details: {} } } },
};
const decisionSchema = { type: 'object', additionalProperties: false, required: ['valid', 'action', 'revision_count', 'next_revision_count', 'rerun_from', 'violations'], properties: decisionProperties };
const storedDecisionSchema = { ...decisionSchema, required: decisionSchema.required.filter(key => key !== 'next_revision_count') };

const ajv = new Ajv2020({ allErrors: true, strict: false });
const validateInput = ajv.compile(inputSchema);
const validateOutput = ajv.compile(outputSchema);
const validateDecision = ajv.compile(decisionSchema);
const validateStoredDecision = ajv.compile(storedDecisionSchema);

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

function errors(validator: ReturnType<typeof ajv.compile>, value: unknown): string[] {
  if (validator(value)) return [];
  return (validator.errors ?? []).map(error => `${error.instancePath || '/'} ${error.message ?? ''}`.trim());
}

/** Shape check against the reviewed copy of the core output Schema (pinned to schema_for by the Python tests). */
export function judgementOutputErrors(value: unknown): string[] {
  return errors(validateOutput, value);
}

/** Shape check of review_judgement's decision plus the relations the core guarantees between its fields. */
export function judgementDecisionErrors(value: unknown): string[] {
  const found = errors(validateDecision, value);
  if (found.length) return found;
  const decision = value as JudgementDecision;
  if (decision.valid !== (decision.violations.length === 0)) found.push('/valid does not match violations');
  if ((decision.action === 'revise') !== (decision.rerun_from !== null)) found.push('/rerun_from is set only for revise');
  if (decision.next_revision_count !== decision.revision_count + (decision.action === 'revise' ? 1 : 0)) found.push('/next_revision_count must count only an actual revise');
  return found;
}

/**
 * Field relations a stored decision should keep. Main's PlanningAgent writes the decision of a failed stage itself
 * (without next_revision_count, keeping rerun_from after it gave up), so these are listed as record problems and the
 * web never fills in a value of its own.
 */
function storedDecisionProblems(decision: StoredDecision): string[] {
  const found: string[] = [];
  if (decision.valid !== (decision.violations.length === 0)) found.push(`코어 결정의 valid(${decision.valid})가 위반 ${decision.violations.length}건과 맞지 않습니다.`);
  if (decision.action !== 'revise' && decision.rerun_from !== null) found.push(`코어 결정이 ${decision.action}로 끝났는데 재실행 단계(rerun_from=${decision.rerun_from})가 남아 있습니다.`);
  if (decision.action === 'revise' && decision.rerun_from === null) found.push('코어 결정이 revise인데 재실행 단계가 없습니다.');
  if (decision.next_revision_count === undefined) found.push('코어 결정에 next_revision_count가 없습니다. 웹은 값을 채우지 않고 revision_count만 표시합니다.');
  else if (decision.next_revision_count !== decision.revision_count + (decision.action === 'revise' ? 1 : 0)) found.push('코어 결정의 next_revision_count가 실제 수정 여부와 맞지 않습니다.');
  return found;
}

const VIOLATION_LABELS: Record<string, string> = {
  SOURCE_SCOPE_MISMATCH: '다른 모델·문서 버전의 원문이 섞였습니다',
  FEATURE_SCOPE_MISMATCH: '기능의 제품 모델·문서 버전 또는 합성/실자료 범위가 현재 대상과 다릅니다',
  SOURCE_KIND_MISMATCH: '합성 자료와 실제 자료가 섞였습니다',
  REQUEST_PRODUCT_MISMATCH: '요청 범위 밖의 제품입니다',
  REVIEW_CONFLICT: '리뷰가 서로 상충합니다',
  REVIEW_UNCERTAIN: '불편인지 불확실한 리뷰를 근거로 썼습니다',
  NO_REVIEW_EVIDENCE: '불편을 뒷받침하는 리뷰가 없습니다',
  // The flag means the run's own review assessment did not call the cited review a complaint/conflict (record 034:
  // real 8B runs labelled explicit complaints "positive"), so the label credits that mismatch instead of asserting it.
  NON_COMPLAINT_AS_NEED: '불편 근거로 인용한 리뷰를 같은 실행의 리뷰 판단에서 불편·상충으로 분류하지 않았습니다(리뷰 판단과 불편 근거 불일치)',
  DUPLICATE_CONCEPT: '후보가 기존 기능과 중복됩니다',
  UNCERTAIN_DUPLICATION: '후보의 기존 기능 중복 여부가 불확실합니다',
  MISSING_EVIDENCE: '인용한 근거 ID가 현재 입력 자료에 없습니다',
  OUTPUT_SCOPE_MISMATCH: '출력의 모델·문서 버전이 입력과 다릅니다',
  STALE_INPUT: '이전 입력(바뀌기 전 명세)의 결과입니다',
  UNSUPPORTED_WITHOUT_MANUAL: '설명서 근거 없이 미지원으로 판단했습니다',
  SUPPORT_UNKNOWN: '설명서에서 지원 여부를 확인할 수 없습니다',
  CONCEPT_LIMIT: '후보가 3개를 넘습니다',
  HOLD_WITHOUT_QUESTIONS: '보류했지만 확인할 질문이 없습니다',
  HUMAN_DECISION_REQUIRED: '기획자가 내려야 할 선택을 Agent가 정했습니다',
  VALIDATION_FAILED: '모델 응답이 단계 규격에 맞지 않습니다',
  INVALID_EVIDENCE_ID: '없는 근거 ID를 인용했습니다',
  // PR #60 (CORE002 semantic review, draft): a model-written review of each candidate against exclusions and quality.
  EXCLUSION_VIOLATION: '의미 검토: 후보가 제외 조건을 어겼습니다',
  EXCLUSION_UNCERTAIN: '의미 검토: 제외 조건 준수 여부가 불확실합니다',
  QUALITY_VIOLATION: '의미 검토: 기획 품질 기준을 어겼습니다',
  QUALITY_UNCERTAIN: '의미 검토: 기획 품질 기준 충족이 불확실합니다',
  SEMANTIC_QUESTION: '의미 검토에서 추가 확인이 필요한 질문이 남았습니다',
  INVALID_SEMANTIC_REVIEW: '의미 검토 응답이 규격에 맞지 않습니다',
  INVALID_NO_CANDIDATE_REVIEW: '후보 없음 판단을 검토한 응답이 원문·범위·완전성 확인을 통과하지 못했습니다(후보 없음 자체의 오류가 아님)',
  // Remaining review_judgement codes (packages/core judgement_contract.py), first seen raw in a live run (record 020).
  DUPLICATE_ID: '같은 ID가 중복됩니다',
  SOURCE_FEATURE_MISSING: '근거가 없는 기능을 가리킵니다',
  SOURCE_FEATURE_LINK_MISMATCH: '설명서 근거와 기능의 연결이 서로 맞지 않습니다',
  FEATURE_MANUAL_MISSING: '기능을 뒷받침하는 유효한 설명서 근거 또는 연결 관계가 없습니다',
  FEATURE_SOURCE_LINK_MISMATCH: '기능과 설명서 근거의 연결이 서로 맞지 않습니다',
  CHANGED_EVIDENCE_MISSING: '변경된 근거로 지정한 자료가 입력에 없습니다',
  REVISION_COUNT_MISMATCH: '출력의 수정 회차가 입력과 다릅니다',
  DESIRED_OUTCOME_COVERAGE: '불편마다 바라는 결과가 정리되지 않았습니다',
  ASSESSMENT_COVERAGE: '평가 목록이 실제 평가 대상과 일치하지 않습니다',
  NEED_MODEL_MISMATCH: '불편이 요청과 다른 모델로 기록되었습니다',
  NEED_REVIEW_REQUIRED: '불편의 근거가 리뷰가 아닙니다',
  COMPLAINT_NOT_EXTRACTED: '불편으로 정리되지 않은 불편 리뷰가 있습니다',
  NEED_COMPARISON_MISSING: '기존 기능과 대조하지 않은 불편이 있습니다',
  GAP_NEED_MISMATCH: '대조 항목이 없는 불편이나 다른 모델을 가리킵니다',
  GAP_REVIEW_MISSING: '대조 항목에 불편의 리뷰 근거가 빠졌습니다',
  GAP_FEATURE_MISSING: '대조 항목이 없는 기능을 가리킵니다',
  GAP_MANUAL_MISSING: '대조 항목에 연결 기능의 설명서 근거가 빠졌습니다',
  SUPPORT_BASIS_MISMATCH: '설명서 근거 유형과 지원 판단이 맞지 않습니다',
  SUPPORTED_WITHOUT_FEATURE: '지원한다고 판단했지만 연결된 기능이 없습니다',
  RESOLUTION_PAIN_MISMATCH: '해결 여부와 남은 불편 내용이 맞지 않습니다',
  CONCEPT_GAP_MISSING: '후보가 없는 대조 항목을 근거로 듭니다',
  CONCEPT_WITHOUT_CONFIRMED_GAP: '불편이 남았다고 확인되지 않은 항목으로 후보를 만들었습니다',
  CONCEPT_GROUNDING_MISSING: '후보가 대조 항목의 근거를 인용하지 않았습니다',
  DUPLICATION_COMPARISON_INCOMPLETE: '후보를 모든 기존 기능과 비교하지 않았습니다',
  ZERO_CANDIDATES_WITHOUT_REASON: '후보가 없는데 사유가 없습니다',
  COMPLETED_WITH_UNRESOLVED: '보류·미해결 사유가 남았는데 완료로 끝냈습니다',
  INVALID_REVISION_TERMINATION: '수정 횟수를 다 쓰지 않았거나 사유 없이 실패로 끝냈습니다',
  // PR #159 (CORE manual quality R1) codes; wording confirmed by 황대겸 (record 027).
  COMPARE_CITATION_OMISSION: '입력에 제공된 연결 기능의 설명서 근거가 기능 대조 결과의 인용에서 빠졌습니다',
  // no_candidate_review.py builds "NO_CANDIDATE_" + verdict; "consistent" is not fed back, so only these two occur.
  NO_CANDIDATE_VIOLATION: '후보 없음 판단이 원자료와 맞지 않습니다',
  NO_CANDIDATE_UNCERTAIN: '후보 없음 판단을 확인할 자료가 부족합니다',
};

const BARE_CODE = /^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/;

/**
 * The core copies violation codes into hold_reasons / unresolved / no_candidate_reasons when it stops (planning_agent
 * terminal output). Shown as-is, "REVIEW_CONFLICT" means nothing to a planner, so a reason that is exactly a code gets
 * its label with the code kept; free-text reasons pass through unchanged. Display only — stored data is not rewritten.
 */
export function reasonText(item: string): string {
  const label = Object.hasOwn(VIOLATION_LABELS, item) ? VIOLATION_LABELS[item] : undefined;
  if (label) return `${label} (${item})`;
  if (BARE_CODE.test(item)) return `${item} (설명이 등록되지 않은 검사 코드)`;
  // The core also writes codes inside generated sentences ("판단 근거의 REVIEW_UNCERTAIN 조건을 … 있나요?"). Known codes
  // get their label in place, keeping the code; unknown tokens and everything else stay exactly as stored.
  return item.replace(INLINE_CODE, code => Object.hasOwn(VIOLATION_LABELS, code) ? `'${VIOLATION_LABELS[code]}'(${code})` : code);
}

// A code already written as "(CODE" (a label we produced, or violationText) is left alone so labels never stack.
const INLINE_CODE = /(?<!\()\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g;

const QUALITY_LABELS: Record<string, string> = {
  mechanism: '작동 방식', difference_from_current_features: '현재 기능과 차이', unverified_assumptions: '미검증 가정', unsupported_claims: '근거 없는 단정', unsupported_factual_claims: '근거 없는 단정',
};
const VERDICT_LABELS: Record<string, string> = { compliant: '준수', satisfied: '충족', violation: '위반', uncertain: '불확실' };

/** One line for the details the core attached to a violation; unknown shapes are shown as compact JSON, never dropped. */
export function violationDetail(details: unknown): string | null {
  if (details === undefined || details === null) return null;
  if (isObject(details)) {
    if (typeof details.verdict === 'string' && typeof details.concept_id === 'string') {
      const target = typeof details.condition === 'string' ? `제외 조건 '${details.condition}'` : `기준 ${QUALITY_LABELS[details.criterion as string] ?? String(details.criterion)}`;
      const quote = typeof details.candidate_quote === 'string' && details.candidate_quote ? ` · 후보 인용 '${details.candidate_quote}'` : '';
      return `후보 ${details.concept_id} × ${target}: ${VERDICT_LABELS[details.verdict] ?? details.verdict}${quote}${typeof details.reason === 'string' ? ` — ${details.reason}` : ''}`;
    }
    if (Array.isArray(details.questions)) return `질문: ${details.questions.join(' / ')}`;
    if (Object.keys(details).length === 1 && typeof details.reason === 'string') return `사유: ${details.reason}`;
  }
  const text = JSON.stringify(details);
  return text.length > 200 ? `${text.slice(0, 200)}…` : text;
}

export function violationText(item: { code: string; stage: string; details?: unknown }): string {
  const detail = violationDetail(item.details);
  return `${Object.hasOwn(VIOLATION_LABELS, item.code) ? VIOLATION_LABELS[item.code] : item.code} (${item.code} · ${item.stage} 단계)${detail ? ` · ${detail}` : ''}`;
}

const SEMANTIC = /^(EXCLUSION|QUALITY|SEMANTIC|INVALID_SEMANTIC)_/;
/**
 * Codes that make the core hold instead of revising (packages/core judgement_contract.py `finish`, "grounding"). Any
 * other violation in a held decision was found too but not revised, because the hold ends the run first.
 */
const GROUNDING = new Set(['REVIEW_CONFLICT', 'REVIEW_UNCERTAIN', 'NO_REVIEW_EVIDENCE', 'SUPPORT_UNKNOWN', 'SOURCE_KIND_MISMATCH', 'UNSUPPORTED_WITHOUT_MANUAL', 'UNCERTAIN_DUPLICATION']);

/** What an accept does and does not establish (PM semantic review 2026-10-05: an excluded candidate passed accept). */
export const ACCEPT_DETAIL = '판단 계약의 형식·인용·관계 검사를 통과했습니다. 제외 조건을 의미상 지켰는지, 후보가 실현 가능하거나 효과가 있는지는 이 검사가 판정하지 않으므로 기획자가 원문과 함께 검토해야 합니다.';

export interface JudgementView {
  action: JudgementDecision['action']; label: string; detail: string; tone: 'done' | 'notice' | 'error';
  /** Candidates may be offered for the planner's keep/focus/exclude choice only after the core accepted them. */
  candidates_selectable: boolean;
  /** The declared status differs from the decision (e.g. a completed declaration that the core held back). */
  declared_status_overridden: boolean;
  violations: string[]; questions: string[]; hold_reasons: string[]; unresolved: string[]; no_candidate_reasons: string[];
  out_of_scope_sources: string[];
  /** For a hold: the violations that caused it, and the other judgement errors left unrevised because the run stopped. */
  hold_causes: string[]; unrevised_errors: string[];
}

/** What the planner should read first: the core's decision, not the status the judgement declared about itself. */
export function judgementView(input: JudgementInput, output: JudgementOutput, decision: JudgementDecision | StoredDecision): JudgementView {
  const scope = `${input.product.model_id}@${input.product.document_version}`;
  const base = {
    action: decision.action, candidates_selectable: decision.action === 'accept',
    declared_status_overridden: !({ accept: ['completed'], hold: ['held'], unresolved: ['failed'], revise: [] } as Record<string, string[]>)[decision.action].includes(output.status),
    violations: decision.violations.map(violationText), questions: [...output.questions, ...output.gaps.flatMap(gap => gap.questions)],
    hold_reasons: output.hold_reasons, unresolved: output.unresolved, no_candidate_reasons: output.no_candidate_reasons,
    out_of_scope_sources: input.sources.filter(item => `${item.model_id}@${item.document_version}` !== scope).map(item => `${item.id} (${item.model_id} · 문서 ${item.document_version})`),
    hold_causes: decision.action === 'hold' ? decision.violations.filter(item => GROUNDING.has(item.code)).map(violationText) : [],
    unrevised_errors: decision.action === 'hold' ? decision.violations.filter(item => !GROUNDING.has(item.code) && !SEMANTIC.test(item.code)).map(violationText) : [],
  };
  switch (decision.action) {
    case 'accept': return { ...base, label: '계약 검사 통과 · 의미 미검증', tone: 'done', detail: ACCEPT_DETAIL };
    case 'hold': return { ...base, label: '보류', tone: 'notice', detail: decision.violations.some(item => SEMANTIC.test(item.code))
      ? '의미 검토에서 제외 조건·기획 기준 준수가 불확실하거나 확인할 질문이 남아 후보를 보류했습니다. 아래 질문에 답하거나 조건을 고쳐 새로 실행해야 하며, 이 결과의 후보는 선택할 수 없습니다.'
      : base.unrevised_errors.length && base.hold_causes.length
        ? `근거 확인이 필요한 문제 ${base.hold_causes.length}건으로 코어가 보류했습니다. 함께 발견된 판단 오류 ${base.unrevised_errors.length}건은 보류로 실행이 끝나 내부 수정을 시도하지 않았습니다(자료 부족만의 문제가 아님). 근거와 판단을 확인한 뒤 새 입력으로 다시 실행해야 하며, 이 결과의 후보는 선택할 수 없습니다.`
        : '자료 범위나 근거를 확인한 뒤 새 입력으로 다시 실행해야 합니다. 이 결과의 후보는 선택할 수 없습니다.' };
    case 'revise': return { ...base, label: `수정 필요 · ${decision.rerun_from} 단계부터 재실행`, tone: 'notice', detail: `내부 수정 ${decision.next_revision_count ?? '?'}/2회차로 다시 실행할 중간 결과입니다. 저장·선택 대상이 아닙니다.` };
    default: return { ...base, label: '미해결 종료', tone: 'error', detail: '두 번 수정한 뒤에도 문제가 남았거나 판단에 실패했습니다. 추가 모델 호출을 멈추고 사유를 남깁니다.' };
  }
}

export interface JudgementRunMeta { run_id: string; project_id: string; created_at: string; dataset_sha256: string; actor_id: string }

/**
 * Stored-run view of a terminal decision, following docs/core/judgement-contract.md: accept→completed,
 * hold→held, unresolved→failed with the reasons in Run.unresolved. A revise decision is an in-flight internal
 * revision, so it yields null instead of a run. Candidates are kept only when accepted, so a held judgement can't be
 * picked in the keep/focus/exclude flow. Assessments stay in the core log and are not added to canonical objects.
 */
export function judgementRunSnapshot(input: JudgementInput, output: JudgementOutput, decision: JudgementDecision, meta: JudgementRunMeta): RunSnapshot | null {
  if (decision.action === 'revise') return null;
  const status = ({ accept: 'completed', hold: 'held', unresolved: 'failed' } as const)[decision.action];
  const reasons = [...decision.violations.map(violationText), ...output.hold_reasons, ...output.unresolved, ...output.no_candidate_reasons];
  const concepts = decision.action === 'accept' ? structuredClone(output.concepts) : [];
  const evidenceIds = [...new Set([...output.needs, ...output.gaps, ...concepts].flatMap(item => item.evidence_ids))];
  return {
    run: {
      id: meta.run_id, project_id: meta.project_id, dataset_version: input.request.dataset_version, contract_version: '0.1.0',
      status, stage: 'finished', revision_count: output.revision_count, max_revisions: 2, concepts,
      unresolved: decision.action === 'accept' ? [...output.unresolved] : reasons, evidence_ids: evidenceIds, events: [],
    },
    request: structuredClone(input.request), previous_run_id: null, request_revision: 0, actor_id: meta.actor_id, client: 'skill',
    created_at: meta.created_at, document_versions: { [output.model_id]: output.document_version }, dataset_sha256: meta.dataset_sha256,
    unconfirmed: [...output.questions], output: {
      needs: structuredClone(output.needs), gaps: structuredClone(output.gaps),
      no_candidate_reasons: [...output.no_candidate_reasons],
    },
  };
}

// ---- Stored workspace runs (docs/pm/workspace-planning.md): output = {needs, gaps, no_candidate_reasons, planning_execution}.

export interface ModelCallRecord {
  stage: string; skill_id: string; execution_kind: string; revision_count: number; model_id: string; model_digest: string;
  metadata?: { adapter?: string; elapsed_ms?: number; generation_settings?: Record<string, unknown> };
}
export interface TraceStep { stage: string; operation: string; elapsed_ms?: number }
export interface SemanticAssessment {
  concept_id: string; verdict: string; reason: string; candidate_quote: string;
  source_quotes?: { evidence_id: string; quote: string }[]; condition_index?: number; condition?: string; criterion?: string;
}
/** PR #60 (draft): one model-written semantic review and the core's decision on it. */
export interface SemanticReview {
  report: { exclusion_assessments: SemanticAssessment[]; quality_assessments: SemanticAssessment[]; questions: string[] };
  decision: StoredDecision;
  /** Exact immutable originals of this review attempt, when retained by the core. */
  reviewed_input?: JudgementInput; reviewed_output?: JudgementOutput;
}
export interface PlanningExecution {
  execution_kind: 'fixture' | 'live_model'; status: 'completed' | 'held' | 'failed';
  original_input: JudgementInput; input: JudgementInput; output: JudgementOutput | null; decision: StoredDecision | null;
  trace: TraceStep[]; model_calls: ModelCallRecord[]; errors: { code: string; message: string }[];
  /** The checked output the core turned down; the terminal output keeps no candidates. */
  rejected_output?: JudgementOutput;
  semantic_reviews?: SemanticReview[];
  rejected_execution?: unknown; rejected_execution_omitted?: string;
  /** Shared revision budget (packages/core correction_budget.py); terminal_reason says why the run stopped. */
  correction_budget?: { revision_count: number; max_revisions: number; closed: boolean; terminal_reason: string | null; attempts?: unknown[] };
}

/** packages/core feature_support.py SUPPORT: the support_status a gap's manual basis allows. */
export const SUPPORT_FROM_BASIS: Record<string, string> = { explicit_supported: 'supported', explicit_unsupported: 'unsupported', unmentioned: 'insufficient_evidence', conflicting: 'insufficient_evidence' };

/**
 * Stored judgement facts shown next to each comparison row (record 034 audit U2). "supported" only means the current
 * feature is documented — the core prompt says so even when the desired outcome is not met — so the resolution, the
 * desired outcome and the review polarity are read from the same run's record. Display only; nothing is re-judged.
 */
export interface JudgedNotes {
  accepted: boolean; status: PlanningExecution['status'];
  resolution: Map<string, string>; basis: Map<string, string>; desired: Map<string, string>; polarity: Map<string, string>;
}

export function judgedNotes(snapshot: RunSnapshot): JudgedNotes | null {
  const view = planningExecutionView(snapshot);
  if (view.kind !== 'ok' || !view.execution.output) return null;
  const output = view.execution.output;
  return {
    accepted: view.execution.status === 'completed' && view.execution.decision?.action === 'accept', status: view.execution.status,
    resolution: new Map(output.gap_assessments.map(item => [item.gap_id, item.resolution])),
    basis: new Map(output.gap_assessments.map(item => [item.gap_id, item.support_basis])),
    desired: new Map(output.desired_outcomes.map(item => [item.need_id, item.desired_outcome])),
    polarity: new Map(output.review_assessments.map(item => [item.evidence_id, item.polarity])),
  };
}

/** How many candidates the model produced that the core turned down (rejected_output); never selectable. */
export function rejectedCandidateCount(snapshot: RunSnapshot): number {
  const execution = (snapshot.output as { planning_execution?: { rejected_output?: { concepts?: unknown } } } | null)?.planning_execution;
  const concepts = execution?.rejected_output?.concepts;
  return Array.isArray(concepts) ? concepts.length : 0;
}

/** Why a stored run stopped, read from its core record without re-judging; null when not recorded. */
export function terminalReason(snapshot: RunSnapshot): string | null {
  const execution = (snapshot.output as { planning_execution?: { correction_budget?: { terminal_reason?: unknown } } } | null)?.planning_execution;
  const reason = execution?.correction_budget?.terminal_reason;
  return typeof reason === 'string' ? reason : null;
}
export type ExecutionView =
  | { kind: 'none' }
  | { kind: 'invalid'; errors: string[] }
  | { kind: 'ok'; execution: PlanningExecution; problems: string[]; models: string[]; model_calls: number; elapsed_ms: number | null };


function inputErrors(label: string, value: unknown): string[] {
  return errors(validateInput, value).map(item => `/${label}${item}`);
}

// The workspace output envelope permits additional JSON. Check every field the UI reads before typed projection,
// so malformed nested records become an alert rather than an exception during source lookup or React rendering.
const text = { type: 'string', minLength: 1, pattern: '\\S' };
const recordArrays = {
  trace: ajv.compile({ type: 'array', items: { type: 'object', required: ['stage', 'operation'], properties: { stage: text, operation: text, elapsed_ms: { type: 'number', minimum: 0 } } } }),
  model_calls: ajv.compile({ type: 'array', items: { type: 'object', required: ['stage', 'skill_id', 'execution_kind', 'revision_count', 'model_id', 'model_digest'], properties: {
    stage: text, skill_id: text, execution_kind: { enum: ['fixture', 'live_model'] }, revision_count: { type: 'integer', minimum: 0, maximum: 2 }, model_id: text, model_digest: text,
  } } }),
  errors: ajv.compile({ type: 'array', items: { type: 'object', required: ['code', 'message'], properties: { code: text, message: { type: 'string' } } } }),
};
const assessmentProperties = {
  concept_id: text, reason: text, candidate_quote: { type: 'string' },
  source_quotes: { type: 'array', items: { type: 'object', required: ['evidence_id', 'quote'], properties: { evidence_id: text, quote: text } } },
};
const assessmentValidators = {
  exclusion_assessments: ajv.compile({ type: 'object', required: [...Object.keys(assessmentProperties), 'verdict', 'condition_index', 'condition'], properties: {
    ...assessmentProperties, verdict: { enum: ['compliant', 'violation', 'uncertain'] }, condition_index: { type: 'integer', minimum: 0 }, condition: { type: 'string' },
  } }),
  quality_assessments: ajv.compile({ type: 'object', required: [...Object.keys(assessmentProperties), 'verdict', 'criterion'], properties: {
    ...assessmentProperties, verdict: { enum: ['satisfied', 'violation', 'uncertain'] }, criterion: text,
  } }),
};
const validateQuestions = ajv.compile({ type: 'array', items: { type: 'string' } });

function semanticReviewErrors(value: unknown): string[] {
  if (!Array.isArray(value)) return ['/semantic_reviews must be an array'];
  return value.flatMap((item, index) => {
    const at = `/semantic_reviews/${index}`;
    if (!isObject(item) || !isObject(item.report)) return [`${at} has no report`];
    const report = item.report;
    const rows = (Object.keys(assessmentValidators) as (keyof typeof assessmentValidators)[]).flatMap(key => Array.isArray(report[key])
      ? (report[key] as unknown[]).flatMap((row, n) => errors(assessmentValidators[key], row).map(error => `${at}/report/${key}/${n}${error}`))
      : [`${at}/report/${key} must be an array`]);
    rows.push(...errors(validateQuestions, report.questions).map(error => `${at}/report/questions${error}`));
    if (item.reviewed_input !== undefined || item.reviewed_output !== undefined) {
      rows.push(...inputErrors(`${at.slice(1)}/reviewed_input`, item.reviewed_input));
      rows.push(...judgementOutputErrors(item.reviewed_output).map(error => `${at}/reviewed_output${error}`));
    }
    return [...rows, ...errors(validateStoredDecision, item.decision).map(error => `${at}/decision${error}`)];
  });
}

/**
 * Reads the core's own record of a stored run. It never re-judges: malformed records are reported as invalid, and
 * records that disagree with the stored run (status, request, scope, candidates) are shown as problems, not hidden.
 */
export function planningExecutionView(snapshot: RunSnapshot): ExecutionView {
  const raw = (snapshot.output as Record<string, unknown> | null)?.planning_execution;
  if (raw === undefined || raw === null) return { kind: 'none' };
  if (!isObject(raw)) return { kind: 'invalid', errors: ['/planning_execution is not an object'] };
  const found: string[] = [];
  if (raw.execution_kind !== 'fixture' && raw.execution_kind !== 'live_model') found.push('/execution_kind must be fixture or live_model');
  if (!['completed', 'held', 'failed'].includes(raw.status as string)) found.push('/status must be completed, held or failed');
  for (const key of Object.keys(recordArrays) as (keyof typeof recordArrays)[]) found.push(...errors(recordArrays[key], raw[key]).map(item => `/${key}${item}`));
  found.push(...inputErrors('original_input', raw.original_input), ...inputErrors('input', raw.input));
  if (raw.output !== null) found.push(...judgementOutputErrors(raw.output).map(item => `/output${item}`));
  if (raw.decision !== null) found.push(...errors(validateStoredDecision, raw.decision).map(item => `/decision${item}`));
  if (raw.rejected_output !== undefined) found.push(...judgementOutputErrors(raw.rejected_output).map(item => `/rejected_output${item}`));
  if (raw.semantic_reviews !== undefined) found.push(...semanticReviewErrors(raw.semantic_reviews));
  if (found.length) return { kind: 'invalid', errors: found };

  const execution = raw as unknown as PlanningExecution;
  const problems: string[] = execution.decision ? storedDecisionProblems(execution.decision) : [];
  if (execution.status !== snapshot.run.status) problems.push(`저장된 실행 상태(${snapshot.run.status})와 판단 기록 상태(${execution.status})가 다릅니다.`);
  if (execution.status === 'completed' && execution.decision?.action !== 'accept') problems.push('완료로 기록됐지만 코어 검사 결정이 accept가 아닙니다.');
  if (canonical(execution.original_input.request) !== canonical(snapshot.request)) problems.push('판단에 들어간 원 요청이 이 실행의 요청과 다릅니다.');
  if (canonical(execution.input.request) !== canonical(execution.original_input.request)) problems.push('판단의 최종 요청이 이 실행의 원 요청과 다릅니다.');
  const product = execution.input.product;
  if (snapshot.document_versions[product.model_id] !== product.document_version) problems.push(`판단한 모델·문서 버전(${product.model_id} ${product.document_version})이 이 실행의 고정 범위와 다릅니다.`);
  if (execution.output && (execution.output.model_id !== product.model_id || execution.output.document_version !== product.document_version)) problems.push('판단 출력의 모델·문서 버전이 입력과 다릅니다.');
  if (execution.status === 'completed' && execution.output && canonical(execution.output.concepts) !== canonical(snapshot.run.concepts)) problems.push('실행에 저장된 후보가 판단 출력의 후보와 다릅니다.');
  if (execution.status !== 'completed' && snapshot.run.concepts.length) problems.push('보류·실패한 판단인데 실행에 후보가 남아 있습니다.');
  if (execution.rejected_execution !== undefined || execution.rejected_execution_omitted) problems.push('규격에 맞지 않아 거절된 판단 기록이 있습니다. 완료 결과로 쓰지 않았습니다.');
  const models = [...new Set(execution.model_calls.map(call => `${call.model_id} · ${call.model_digest.slice(0, 12)}`))];
  const times = execution.trace.map(step => step.elapsed_ms).filter((value): value is number => typeof value === 'number');
  return { kind: 'ok', execution, problems, models, model_calls: execution.model_calls.length, elapsed_ms: times.length ? Math.max(...times) : null };
}

/**
 * The run's own sources and features (the exact input the core judged) come first, so the comparison table, candidate
 * review and exports quote what the judgement saw, even when the bootstrap dataset differs.
 */
export function runSources(snapshot: RunSnapshot | undefined, features: Feature[], evidence: Evidence[]): { features: Feature[]; evidence: Evidence[] } {
  const view = snapshot ? planningExecutionView(snapshot) : { kind: 'none' as const };
  if (view.kind !== 'ok') return { features, evidence };
  const own = view.execution.input;
  const sourceIds = new Set(own.sources.map(item => item.id));
  const featureIds = new Set(own.features.map(item => item.id));
  return {
    features: [...structuredClone(own.features), ...features.filter(item => !featureIds.has(item.id))],
    evidence: [...structuredClone(own.sources), ...evidence.filter(item => !sourceIds.has(item.id))],
  };
}

/**
 * Candidates the planner may keep/focus/exclude for the next run. A run whose stored core record is malformed, or did
 * not end in an accepted decision, offers none even if candidates were stored with it. Runs without a core record
 * (fixtures, request-only drafts) keep the stored candidates as before.
 */
function acceptedStoredExecution(snapshot: RunSnapshot, view: ExecutionView): boolean {
  return view.kind === 'ok' && snapshot.run.status === 'completed' && view.execution.status === 'completed'
    && view.execution.output !== null && view.execution.decision?.valid === true
    && view.execution.decision.action === 'accept' && view.problems.length === 0;
}

export function selectableConcepts(snapshot: RunSnapshot): RunSnapshot['run']['concepts'] {
  const view = planningExecutionView(snapshot);
  if (view.kind === 'none') return snapshot.run.status === 'completed' ? snapshot.run.concepts : [];
  return acceptedStoredExecution(snapshot, view) ? snapshot.run.concepts : [];
}

/** Why a rerun from this run starts without a usable judgement, or null when the base run was accepted. */
export function rerunBaseNotice(snapshot: RunSnapshot): string | null {
  const view = planningExecutionView(snapshot);
  if (view.kind === 'none') return snapshot.run.status === 'completed' ? null : '이 실행에는 채택된 판단 결과가 없어 후보를 고를 수 없습니다. 조건을 고쳐 새로 요청할 수 있습니다.';
  if (view.kind === 'invalid') return '이 실행의 판단 기록 형식이 맞지 않아 후보를 고를 수 없습니다. 조건만 고쳐 새로 요청할 수 있으며, 이전 판단을 이어받지 않습니다.';
  const { status, decision } = view.execution;
  if (acceptedStoredExecution(snapshot, view)) return snapshot.run.concepts.length ? null : '이 실행은 후보 없이 끝났습니다. 조건을 고쳐 새로 요청할 수 있습니다.';
  if (status === 'completed' && view.problems.length) return '저장된 판단 기록이 실행 상태·입력·범위·후보와 일치하지 않아 후보를 고를 수 없습니다. 불일치를 확인하고 조건을 고쳐 새로 요청할 수 있습니다.';
  if (status === 'completed') return '완료로 기록됐지만 최종 출력과 채택 결정을 함께 확인할 수 없어 후보를 고를 수 없습니다. 조건을 고쳐 새로 요청할 수 있습니다.';
  const reason = status === 'held' ? '보류' : '실패';
  return `이 실행은 ${reason}로 끝나 채택된 후보가 없습니다${decision ? '' : '(코어 결정 없음)'}. 조건을 고쳐 새로 요청할 수 있으며 실제 판단 여부는 새 실행 결과로 확인합니다. 이 실행의 결과를 성공으로 이어받지 않습니다.`;
}

/** What kind of record this is; a live run that stopped before any model call is not presented as model output. */
export function executionKindText(kind: string, modelCalls: number): string {
  if (kind === 'fixture') return 'fixture 실행 기록(모델 호출 아님)';
  return modelCalls > 0 ? '실제 모델 실행 기록(저장된 결과)' : '실제 모델 경로 · 모델 호출 전에 중단';
}

export interface ExportSemanticRow { round: number; concept_id: string; target: string; verdict: string; candidate_quote: string; reason: string }
/** The core record of a run as it goes into JSON/Markdown exports: decision, terminal reasons and semantic review. */
export type ExportJudgement =
  | { record_valid: false; record_errors: string[] }
  | {
    record_valid: true; execution_kind: PlanningExecution['execution_kind']; status: PlanningExecution['status'];
    decision: StoredDecision['action'] | null; violations: string[]; record_problems: string[]; errors: { code: string; message: string }[];
    /** Hold only: violations that caused the hold, and judgement errors the hold left unrevised (screen lists the same). */
    hold_causes: string[]; unrevised_errors: string[]; terminal_reason: string | null;
    questions: string[]; hold_reasons: string[]; unresolved: string[]; no_candidate_reasons: string[];
    rejected_candidates: { id: string; title: string }[]; semantic_reviews: { round: number; action: string; violations: string[] }[];
    semantic_rows: ExportSemanticRow[]; models: string[]; model_calls: number;
  };

export function exportJudgement(snapshot: RunSnapshot): ExportJudgement | null {
  const view = planningExecutionView(snapshot);
  if (view.kind === 'none') return null;
  if (view.kind === 'invalid') return { record_valid: false, record_errors: [...view.errors] };
  const { execution } = view;
  const output = execution.output;
  const reviews = execution.semantic_reviews ?? [];
  const unique = (items: string[]) => [...new Set(items)];
  return {
    record_valid: true, execution_kind: execution.execution_kind, status: execution.status, decision: execution.decision?.action ?? null,
    violations: (execution.decision?.violations ?? []).map(violationText), record_problems: [...view.problems],
    errors: execution.errors.map(item => ({ code: item.code, message: item.message })),
    ...(output && execution.decision ? (({ hold_causes, unrevised_errors }) => ({ hold_causes, unrevised_errors }))(judgementView(execution.input, output, execution.decision)) : { hold_causes: [], unrevised_errors: [] }),
    terminal_reason: terminalReason(snapshot),
    questions: unique([...(output?.questions ?? []), ...(output?.gaps ?? []).flatMap(gap => gap.questions), ...reviews.flatMap(review => review.report.questions)]),
    hold_reasons: [...(output?.hold_reasons ?? [])], unresolved: [...(output?.unresolved ?? [])], no_candidate_reasons: [...(output?.no_candidate_reasons ?? [])],
    rejected_candidates: (execution.rejected_output?.concepts ?? []).map(concept => ({ id: concept.id, title: concept.title })),
    semantic_reviews: reviews.map((review, index) => ({ round: index + 1, action: review.decision.action, violations: review.decision.violations.map(violationText) })),
    semantic_rows: reviews.flatMap((review, index) => [...review.report.exclusion_assessments, ...review.report.quality_assessments].map(row => ({
      round: index + 1, concept_id: row.concept_id, target: row.condition !== undefined ? `제외 조건: ${row.condition}` : `기준: ${row.criterion ?? ''}`,
      verdict: row.verdict, candidate_quote: row.candidate_quote, reason: row.reason,
    }))),
    models: [...view.models], model_calls: view.model_calls,
  };
}
