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
  REVIEW_SCOPE_MISMATCH: '리뷰 판단의 근거 ID가 현재 입력 리뷰 범위에 없습니다',
  REVIEW_REASON_MISSING: '리뷰의 불편 여부를 판단한 사유가 없습니다',
  REVIEW_ASSESSMENT_COVERAGE: '현재 입력 리뷰별 판단이 누락되었거나 중복되었습니다',
  UNCERTAINTY_CONTEXT_MISSING: '불확실하거나 상충하는 리뷰에서 확인할 정보와 질문이 빠졌습니다',
  UNCERTAINTY_SCOPE_MISMATCH: '미확인 정보가 해당 리뷰 판단과 연결되지 않거나 중복되었습니다',
  UNCERTAINTY_FIELD_MISSING: '미확인 사유, 필요한 정보, 확인 질문 중 필수 항목이 없거나 비어 있습니다',
  EMPTY_NEEDS_WITHOUT_JUDGEMENT: '불편 목록이 비어 있지만 리뷰별 판단 사유나 확인할 정보가 없습니다',
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

/** violationText plus the gap/concept IDs the stored check named for that code (none when not recorded). */
export function targetedViolationText(item: { code: string; stage: string; details?: unknown }, targets: string[]): string {
  return `${violationText(item)}${targets.length ? ` · 대상 ${targets.join(', ')}` : ''}`;
}

/**
 * Read-only facts from a run's stored trace (record 034 audit U3), so the screen and the export can say what each
 * violation targets, how each candidate's lineage was judged and what every check round decided. Shapes that do not
 * match are skipped, never guessed; the core's decision stays the source of truth.
 */
export interface TraceFacts {
  /** code → gap/concept IDs from the last quality_context (feature_support / residual_matrix / concept_lineage). */
  targets: Map<string, string[]>;
  /** concept_id → lineage valid (linked to a confirmed remaining-pain gap) and its own violation codes. */
  lineage: Map<string, { valid: boolean; codes: string[] }>;
  /** Each review_decision in order: the Agent's internal revision rounds, not the planner's request revisions. */
  /**
   * details: the failed stage step stored right before this decision ({ok: false, error}), read with errorDetails/
   * errorNotes — e.g. VALIDATION_FAILED from need_extract carries UNCERTAINTY_CONTEXT_MISSING (record 049).
   */
  rounds: { round: number; revision_count: number; action: string; codes: string[]; details: string[]; repeated: boolean }[];
}

export function traceFacts(trace: TraceStep[]): TraceFacts {
  const targets = new Map<string, string[]>();
  const lineage = new Map<string, { valid: boolean; codes: string[] }>();
  const quality = [...trace].reverse().find(step => step.operation === 'quality_context' && isObject(step.outputs));
  const outputs = quality && isObject(quality.outputs) ? quality.outputs : {};
  for (const part of ['feature_support', 'residual_matrix', 'concept_lineage']) {
    const section = outputs[part];
    const violations = isObject(section) && Array.isArray(section.violations) ? section.violations : [];
    for (const item of violations) {
      if (!isObject(item) || typeof item.code !== 'string') continue;
      const target = typeof item.gap_id === 'string' ? item.gap_id : typeof item.concept_id === 'string' ? item.concept_id : null;
      if (target && !(targets.get(item.code) ?? []).includes(target)) targets.set(item.code, [...(targets.get(item.code) ?? []), target]);
      if (typeof item.concept_id === 'string') {
        const entry = lineage.get(item.concept_id) ?? { valid: true, codes: [] };
        lineage.set(item.concept_id, { ...entry, codes: [...new Set([...entry.codes, item.code])] });
      }
    }
  }
  const candidates = isObject(outputs.concept_lineage) && Array.isArray(outputs.concept_lineage.candidates) ? outputs.concept_lineage.candidates : [];
  for (const item of candidates) {
    if (isObject(item) && typeof item.concept_id === 'string' && typeof item.valid === 'boolean') {
      lineage.set(item.concept_id, { valid: item.valid, codes: lineage.get(item.concept_id)?.codes ?? [] });
    }
  }
  const rounds: TraceFacts['rounds'] = [];
  let failed: string[] = [];
  for (const step of trace) {
    if (step.operation !== 'review_decision') {
      if (isObject(step.outputs) && step.outputs.ok === false && isObject(step.outputs.error)) {
        const error = step.outputs.error as { code?: string; details?: unknown };
        failed = [...errorDetails(error).map(errorDetailText), ...errorNotes(error)];
      }
      continue;
    }
    const out = isObject(step.outputs) ? step.outputs : null;
    if (!out || typeof out.action !== 'string' || typeof out.revision_count !== 'number' || !Array.isArray(out.violations)) continue;
    const codes = out.violations.flatMap(item => isObject(item) && typeof item.code === 'string' ? [item.code] : []);
    const previous = rounds[rounds.length - 1];
    const key = (item: { codes: string[]; details: string[] }) => [...item.codes, ...item.details].join('|');
    rounds.push({ round: rounds.length + 1, revision_count: out.revision_count, action: out.action, codes, details: failed,
      repeated: Boolean(previous && codes.length && key(previous) === key({ codes, details: failed })) });
    failed = [];
  }
  return { targets, lineage, rounds };
}

/** A stored question that names a check code gets the IDs that code targeted, so the planner knows what to answer about. */
export function questionWithTargets(question: string, facts: TraceFacts | null): string {
  if (!facts) return question;
  const ids = [...new Set((question.match(INLINE_CODE) ?? []).flatMap(code => facts.targets.get(code) ?? []))];
  return ids.length ? `${question} (대상: ${ids.join(', ')})` : question;
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
export function judgementView(input: JudgementInput, output: JudgementOutput, decision: JudgementDecision | StoredDecision, facts: TraceFacts | null = null): JudgementView {
  const scope = `${input.product.model_id}@${input.product.document_version}`;
  const text = (item: JudgementViolation | StoredDecision['violations'][number]) => targetedViolationText(item, facts?.targets.get(item.code) ?? []);
  const base = {
    action: decision.action, candidates_selectable: decision.action === 'accept',
    declared_status_overridden: !({ accept: ['completed'], hold: ['held'], unresolved: ['failed'], revise: [] } as Record<string, string[]>)[decision.action].includes(output.status),
    violations: decision.violations.map(text), questions: [...output.questions, ...output.gaps.flatMap(gap => gap.questions)].map(item => questionWithTargets(item, facts)),
    hold_reasons: output.hold_reasons, unresolved: output.unresolved, no_candidate_reasons: output.no_candidate_reasons,
    out_of_scope_sources: input.sources.filter(item => `${item.model_id}@${item.document_version}` !== scope).map(item => `${item.id} (${item.model_id} · 문서 ${item.document_version})`),
    hold_causes: decision.action === 'hold' ? decision.violations.filter(item => GROUNDING.has(item.code)).map(text) : [],
    unrevised_errors: decision.action === 'hold' ? decision.violations.filter(item => !GROUNDING.has(item.code) && !SEMANTIC.test(item.code)).map(text) : [],
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
  /** prompt_eval_count/eval_count: input/output tokens as the model server reported them (Ollama metadata). */
  metadata?: { adapter?: string; elapsed_ms?: number; generation_settings?: Record<string, unknown>; prompt_eval_count?: number; eval_count?: number };
  /** Exact prompt sent and response received, when the core kept them. */
  formatted_prompt?: string; raw_response?: string;
}
export interface TraceStep { stage: string; operation: string; elapsed_ms?: number; outputs?: unknown }
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
/** One check the core reported inside an error's details: the specific code, and which review/field it points at. */
export interface ErrorDetail { code: string; evidence_id: string | null; path: string | null }

export interface GroundingDetail {
  concept_id: string | null;
  missing_links: { gap_id: string; need_id: string; required_evidence_ids: string[]; missing_evidence_ids: string[] }[];
}

/** Reads only the R5 ID fields. API authorization of those IDs remains the server's responsibility. */
export function groundingDetails(error: { details?: unknown }): GroundingDetail[] {
  if (!isObject(error.details)) return [];
  const details = error.details;
  const id = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9._:-]{1,160}$/.test(value);
  const ids = (value: unknown): value is string[] => Array.isArray(value) && value.length <= 64 && value.every(id);
  const rows = [...(Array.isArray(details.violations) ? details.violations : []),
    ...(Array.isArray(details.grounding_violations) ? details.grounding_violations : []), details];
  const found: GroundingDetail[] = [];
  for (const row of rows.slice(0, 201)) {
    if (!isObject(row) || row.code !== 'CONCEPT_GROUNDING_MISSING' || (row.concept_id !== undefined && !id(row.concept_id))
      || !Array.isArray(row.missing_links) || row.missing_links.length > 32) continue;
    const missing_links = row.missing_links.flatMap(link => {
      if (!isObject(link) || !id(link.gap_id) || !id(link.need_id) || !ids(link.required_evidence_ids)
        || !ids(link.missing_evidence_ids) || !link.missing_evidence_ids.length) return [];
      const required = link.required_evidence_ids;
      const missing = link.missing_evidence_ids;
      if (!missing.every(evidence => required.includes(evidence))) return [];
      return [{ gap_id: link.gap_id, need_id: link.need_id, required_evidence_ids: [...required], missing_evidence_ids: [...missing] }];
    });
    if (missing_links.length) found.push({ concept_id: id(row.concept_id) ? row.concept_id : null, missing_links });
  }
  return found.filter((row, index) => found.findIndex(other => JSON.stringify(other) === JSON.stringify(row)) === index);
}

/**
 * The specific check codes inside an error (R4, PR #190): need_extract puts REVIEW_ and UNCERTAINTY_ codes in
 * details.violations and EMPTY_NEEDS_WITHOUT_JUDGEMENT in details.code, while the error itself is only VALIDATION_FAILED.
 * Read as stored; malformed entries are skipped, never guessed.
 */
export function errorDetails(error: { code?: string; details?: unknown }): ErrorDetail[] {
  const details = error.details;
  if (!details || typeof details !== 'object') return [];
  const text = (value: unknown) => typeof value === 'string' && value ? value : null;
  const entry = (item: unknown): ErrorDetail[] => {
    if (!item || typeof item !== 'object') return [];
    const record = item as Record<string, unknown>;
    const code = text(record.code);
    // A detail repeating the error's own code (PR #190 metadata conflict: violations [{code: VALIDATION_FAILED}]) adds nothing.
    return code && BARE_CODE.test(code) && code !== error.code ? [{ code, evidence_id: text(record.evidence_id), path: text(record.path) }] : [];
  };
  const record = details as Record<string, unknown>;
  return [...(Array.isArray(record.violations) ? record.violations.flatMap(entry) : []), ...entry({ code: record.code })];
}

/**
 * Other stored facts of an error that say where to look (record 049, real PR #190 core records): the two conflicting
 * declaration paths, the stated reason (e.g. schema_mismatch) and a review named at the top of the details.
 */
export function errorNotes(error: { details?: unknown }): string[] {
  const details = error.details;
  if (!details || typeof details !== 'object') return [];
  const record = details as Record<string, unknown>;
  const notes: string[] = [];
  const paths = Array.isArray(record.conflicting_paths) ? record.conflicting_paths.filter((item): item is string => typeof item === 'string') : [];
  if (paths.length) notes.push(`서로 다른 두 선언: ${paths.join(' ↔ ')}`);
  if (typeof record.reason === 'string' && record.reason) notes.push(`사유: ${record.reason}`);
  if (typeof record.evidence_id === 'string' && record.evidence_id) notes.push(`리뷰 ${record.evidence_id}${typeof record.declared_polarity === 'string' ? `(선언 극성 ${record.declared_polarity})` : ''}`);
  for (const row of groundingDetails(error)) for (const link of row.missing_links) {
    notes.push(`후보 ${row.concept_id ?? 'ID 미공개'} · 대조 ${link.gap_id} → 불편 ${link.need_id} · 필요한 인용 ${link.required_evidence_ids.join(', ')} · 누락 인용 ${link.missing_evidence_ids.join(', ')}`);
  }
  return notes;
}

export function errorDetailText(item: ErrorDetail): string {
  return [reasonText(item.code), item.evidence_id ? `리뷰 ${item.evidence_id}` : '', item.path ? `위치 ${item.path}` : ''].filter(Boolean).join(' · ');
}

export interface PlanningExecution {
  execution_kind: 'fixture' | 'live_model'; status: 'completed' | 'held' | 'failed';
  original_input: JudgementInput; input: JudgementInput; output: JudgementOutput | null; decision: StoredDecision | null;
  /** details: the core's structured error details (e.g. need_extract VALIDATION_FAILED → details.violations, PR #190). */
  trace: TraceStep[]; model_calls: ModelCallRecord[]; errors: { code: string; message: string; details?: unknown }[];
  /** The checked output the core turned down; the terminal output keeps no candidates. */
  rejected_output?: JudgementOutput;
  semantic_reviews?: SemanticReview[];
  rejected_execution?: unknown; rejected_execution_omitted?: string;
  /** Shared revision budget (packages/core correction_budget.py); terminal_reason says why the run stopped. */
  correction_budget?: { revision_count: number; max_revisions: number; closed: boolean; terminal_reason: string | null; attempts?: unknown[] };
  no_candidate_reviews?: unknown[];
  /** Skill execution record; trusted_collector_verified=false means no trusted PM collector checked this run. */
  skill_trace?: { trusted_collector_verified?: unknown };
}

/** One model call's usage as the model server reported it (record 034 audit U5). A missing value stays null, never 0. */
export interface CallMetrics { stage: string; skill_id: string; revision_count: number; prompt_tokens: number | null; output_tokens: number | null; elapsed_ms: number | null }
export interface ExecutionMetrics {
  calls: CallMetrics[];
  /** Totals over every call; null when any call lacks the value, so a partial sum never reads as the whole usage. */
  prompt_tokens: number | null; output_tokens: number | null; model_elapsed_ms: number | null;
  /** Calls whose token counts were not recorded. */
  unrecorded_token_calls: number;
  /** Last trace offset: time since the run started, including retrieval and checks — not model time. */
  run_elapsed_ms: number | null;
  /** Distinct generation settings across calls, e.g. "temperature 0 · seed 42". */
  settings: string[];
}

const reported = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
const totalOf = (values: (number | null)[]): number | null => values.length && values.every(value => value !== null) ? values.reduce<number>((sum, value) => sum + (value ?? 0), 0) : null;
const SETTING_LABEL: [string, string][] = [['temperature', 'temperature'], ['seed', 'seed'], ['num_ctx', '문맥'], ['num_predict', '최대 출력']];

function settingsText(settings: unknown): string | null {
  if (!settings || typeof settings !== 'object') return null;
  const parts = SETTING_LABEL.flatMap(([key, label]) => {
    const value = (settings as Record<string, unknown>)[key];
    return typeof value === 'number' || typeof value === 'string' ? [`${label} ${value}`] : [];
  });
  return parts.length ? parts.join(' · ') : null;
}

export function executionMetrics(execution: PlanningExecution): ExecutionMetrics {
  const calls = execution.model_calls.map(call => ({ stage: call.stage, skill_id: call.skill_id, revision_count: call.revision_count,
    prompt_tokens: reported(call.metadata?.prompt_eval_count), output_tokens: reported(call.metadata?.eval_count), elapsed_ms: reported(call.metadata?.elapsed_ms) }));
  const times = execution.trace.map(step => reported(step.elapsed_ms)).filter((value): value is number => value !== null);
  return {
    calls, prompt_tokens: totalOf(calls.map(call => call.prompt_tokens)), output_tokens: totalOf(calls.map(call => call.output_tokens)),
    model_elapsed_ms: totalOf(calls.map(call => call.elapsed_ms)),
    unrecorded_token_calls: calls.filter(call => call.prompt_tokens === null || call.output_tokens === null).length,
    run_elapsed_ms: times.length ? Math.max(...times) : null,
    settings: [...new Set(execution.model_calls.map(call => settingsText(call.metadata?.generation_settings)).filter((item): item is string => item !== null))],
  };
}

/** What this run did and did not verify (record 034 audit U5). Read from the record; nothing is inferred. */
export interface VerificationScope {
  semantic_reviews: number; no_candidate_reviews: number;
  /** A judgement output was stored, so its declarations are on screen and need the scope note. */
  has_output: boolean;
  /** null when the record does not say. */
  trusted_collector_verified: boolean | null;
  /** Last quality_context rule check per module; empty when the trace has none. */
  rule_modules: { module: string; violations: number; semantic_accuracy_verified: boolean | null }[];
  source_kinds: string[];
}
export const RULE_MODULE_LABEL: Record<string, string> = { feature_support: '기능 지원', residual_matrix: '잔여 불편 행렬', concept_lineage: '콘셉트 계보' };

export const grouped = (value: number) => value.toLocaleString('en-US');
/** null = the record did not report it; shown as 미기록, never as 0. */
export const seconds = (ms: number | null) => ms === null ? '미기록' : `${(ms / 1000).toFixed(1)}초`;
export function tokenText(metrics: ExecutionMetrics): string {
  if (!metrics.calls.length) return '호출 없음';
  if (metrics.prompt_tokens === null || metrics.output_tokens === null) return `미기록(${metrics.calls.length}회 중 ${metrics.unrecorded_token_calls}회 기록 없음 · 합계 계산 안 함)`;
  return `입력 ${grouped(metrics.prompt_tokens)} · 출력 ${grouped(metrics.output_tokens)} · 합 ${grouped(metrics.prompt_tokens + metrics.output_tokens)}`;
}

/** The same scope sentences on screen and in the Markdown export. */
export function scopeLines(scope: VerificationScope, kind: PlanningExecution['execution_kind']): string[] {
  const items: string[] = [];
  if (!scope.semantic_reviews && !scope.no_candidate_reviews && scope.has_output) items.push(`의미 검토 0회 · 후보 없음 검토 0회: 이 실행에서는 규칙·계약 검사만 했습니다. 리뷰 판단·기능 대조·후보는 ${kind === 'fixture' ? '작성된 fixture 선언' : '판단 모델의 선언'}이며 의미 정확성은 검증되지 않았습니다.`);
  else if (scope.semantic_reviews || scope.no_candidate_reviews) items.push(`의미 검토 ${scope.semantic_reviews}회 · 후보 없음 검토 ${scope.no_candidate_reviews}회: 판단과 같은 모델의 검토 선언이며 독립 검증이 아닙니다.`);
  if (scope.rule_modules.length) {
    const unverified = scope.rule_modules.some(item => item.semantic_accuracy_verified !== true);
    items.push(`규칙 모듈 마지막 검사: ${scope.rule_modules.map(item => `${RULE_MODULE_LABEL[item.module]} 위반 ${item.violations}건`).join(' · ')}${unverified ? ' · 의미 정확성 미검증(semantic_accuracy_verified=false)' : ''}. 규칙 통과는 불편·간극·남은 불편의 내용이 맞다는 뜻이 아니며 최종 결정은 위 코어 결정을 따릅니다.`);
  }
  if (scope.trusted_collector_verified === false) items.push('신뢰 수집기 검증 안 됨(trusted_collector_verified=false): 이 기록은 PM의 신뢰 수집기가 검증한 제품 증거가 아닙니다.');
  if (scope.source_kinds.includes('synthetic')) items.push('입력 자료에 합성자료가 있습니다. 동작 확인용이며 실제 고객 수요·제품 성능의 근거가 아닙니다.');
  return items;
}

export function verificationScope(execution: PlanningExecution): VerificationScope {
  const step = [...execution.trace].reverse().find(item => item.operation === 'quality_context');
  const outputs = step?.outputs && typeof step.outputs === 'object' ? step.outputs as Record<string, unknown> : {};
  const rule_modules = Object.keys(RULE_MODULE_LABEL).flatMap(module => {
    const value = outputs[module] as { violations?: unknown; semantic_accuracy_verified?: unknown } | undefined;
    if (!value || typeof value !== 'object' || !Array.isArray(value.violations)) return [];
    return [{ module, violations: value.violations.length, semantic_accuracy_verified: typeof value.semantic_accuracy_verified === 'boolean' ? value.semantic_accuracy_verified : null }];
  });
  const verified = execution.skill_trace?.trusted_collector_verified;
  return {
    semantic_reviews: (execution.semantic_reviews ?? []).length, has_output: execution.output !== null,
    no_candidate_reviews: Array.isArray(execution.no_candidate_reviews) ? execution.no_candidate_reviews.length : 0,
    trusted_collector_verified: typeof verified === 'boolean' ? verified : null, rule_modules,
    source_kinds: [...new Set([execution.input.product.source_kind, ...execution.input.sources.map(item => item.source_kind)].filter((item): item is string => typeof item === 'string'))],
  };
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
    accepted: acceptedStoredExecution(snapshot, view), status: view.execution.status,
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
  /** elapsed_ms is the last trace offset (whole run, cumulative), not model time; per-call usage is in metrics. */
  | { kind: 'ok'; execution: PlanningExecution; problems: string[]; models: string[]; model_calls: number; elapsed_ms: number | null; metrics: ExecutionMetrics };


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
  const metrics = executionMetrics(execution);
  return { kind: 'ok', execution, problems, models, model_calls: execution.model_calls.length, elapsed_ms: metrics.run_elapsed_ms, metrics };
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
    decision: StoredDecision['action'] | null; violations: string[]; record_problems: string[]; errors: { code: string; message: string; details: ErrorDetail[]; notes: string[] }[];
    /** Hold only: violations that caused the hold, and judgement errors the hold left unrevised (screen lists the same). */
    hold_causes: string[]; unrevised_errors: string[]; terminal_reason: string | null;
    questions: string[]; hold_reasons: string[]; unresolved: string[]; no_candidate_reasons: string[];
    /** Turned-down candidates with their gaps, stored lineage verdict and own violation codes (record 034 audit U3). */
    rejected_candidates: { id: string; title: string; gap_ids: string[]; lineage_valid: boolean | null; codes: string[] }[]; semantic_reviews: { round: number; action: string; violations: string[] }[];
    semantic_rows: ExportSemanticRow[]; models: string[]; model_calls: number;
    /** Reported model usage (null = not recorded, never 0) and what the run did not verify (record 034 audit U5). */
    metrics: ExecutionMetrics; scope: VerificationScope;
    /** Agent-internal revisions within this request (max 2); the planner's request revision is meta.request_revision. */
    internal_revisions: { used: number; max: number };
    /**
     * The judging model's own declarations (record 034 audit U4): review polarity, gap support/resolution and candidate
     * duplication, including duplication rows left without a candidate. Declarations, not an independent check.
     */
    review_assessments: { evidence_id: string; polarity: string; reason: string }[];
    gap_assessments: { gap_id: string; support_basis: string; resolution: string; reason: string }[];
    concept_assessments: { concept_id: string; duplication: string; reason: string; from: 'output' | 'rejected_output'; has_candidate: boolean }[];
    /** Assessed reviews no need or gap cites; a complaint among them was dropped by the judgement. */
    unused_review_ids: string[];
    /** How many no-candidate reviews checked the stated no-candidate reasons (0 = not reviewed). */
    no_candidate_reviews: number;
    /** Agent-internal check rounds from the trace (not the planner's request revisions); repeated = same codes as the round before. */
    check_rounds: TraceFacts['rounds'];
  };

/** Reviews the run assessed but no need or gap cites (display only). */
export function unusedReviewIds(output: JudgementOutput): string[] {
  const cited = new Set([...output.needs.flatMap(need => need.evidence_ids), ...output.gaps.flatMap(gap => gap.evidence_ids)]);
  return output.review_assessments.map(item => item.evidence_id).filter(id => !cited.has(id));
}

function conceptAssessments(output: JudgementOutput | null | undefined, from: 'output' | 'rejected_output') {
  return (output?.concept_assessments ?? []).map(item => ({
    concept_id: item.concept_id, duplication: item.duplication, reason: item.reason, from,
    has_candidate: (output?.concepts ?? []).some(concept => concept.id === item.concept_id),
  }));
}

export function exportJudgement(snapshot: RunSnapshot): ExportJudgement | null {
  const view = planningExecutionView(snapshot);
  if (view.kind === 'none') return null;
  if (view.kind === 'invalid') return { record_valid: false, record_errors: [...view.errors] };
  const { execution } = view;
  const output = execution.output;
  const reviews = execution.semantic_reviews ?? [];
  const unique = (items: string[]) => [...new Set(items)];
  const facts = traceFacts(execution.trace);
  return {
    record_valid: true, execution_kind: execution.execution_kind, status: execution.status, decision: execution.decision?.action ?? null,
    violations: (execution.decision?.violations ?? []).map(item => targetedViolationText(item, facts.targets.get(item.code) ?? [])), record_problems: [...view.problems],
    errors: execution.errors.map(item => ({ code: item.code, message: item.message, details: errorDetails(item), notes: errorNotes(item) })),
    ...(output && execution.decision ? (({ hold_causes, unrevised_errors }) => ({ hold_causes, unrevised_errors }))(judgementView(execution.input, output, execution.decision, facts)) : { hold_causes: [], unrevised_errors: [] }),
    terminal_reason: terminalReason(snapshot),
    questions: unique([...(output?.questions ?? []), ...(output?.gaps ?? []).flatMap(gap => gap.questions), ...reviews.flatMap(review => review.report.questions)]).map(item => questionWithTargets(item, facts)),
    hold_reasons: [...(output?.hold_reasons ?? [])], unresolved: [...(output?.unresolved ?? [])], no_candidate_reasons: [...(output?.no_candidate_reasons ?? [])],
    rejected_candidates: (execution.rejected_output?.concepts ?? []).map(concept => ({ id: concept.id, title: concept.title, gap_ids: [...concept.gap_ids],
      lineage_valid: facts.lineage.get(concept.id)?.valid ?? null, codes: [...(facts.lineage.get(concept.id)?.codes ?? [])] })),
    semantic_reviews: reviews.map((review, index) => ({ round: index + 1, action: review.decision.action, violations: review.decision.violations.map(violationText) })),
    semantic_rows: reviews.flatMap((review, index) => [...review.report.exclusion_assessments, ...review.report.quality_assessments].map(row => ({
      round: index + 1, concept_id: row.concept_id, target: row.condition !== undefined ? `제외 조건: ${row.condition}` : `기준: ${row.criterion ?? ''}`,
      verdict: row.verdict, candidate_quote: row.candidate_quote, reason: row.reason,
    }))),
    models: [...view.models], model_calls: view.model_calls,
    metrics: structuredClone(view.metrics), scope: verificationScope(execution),
    internal_revisions: { used: execution.correction_budget?.revision_count ?? execution.input.revision_count, max: execution.correction_budget?.max_revisions ?? 2 },
    review_assessments: (output?.review_assessments ?? []).map(item => ({ evidence_id: item.evidence_id, polarity: item.polarity, reason: item.reason })),
    gap_assessments: (output?.gap_assessments ?? []).map(item => ({ gap_id: item.gap_id, support_basis: item.support_basis, resolution: item.resolution, reason: item.reason })),
    concept_assessments: [...conceptAssessments(output, 'output'), ...conceptAssessments(execution.rejected_output, 'rejected_output')],
    unused_review_ids: output ? unusedReviewIds(output) : [],
    no_candidate_reviews: Array.isArray(execution.no_candidate_reviews) ? execution.no_candidate_reviews.length : 0,
    check_rounds: facts.rounds,
  };
}
