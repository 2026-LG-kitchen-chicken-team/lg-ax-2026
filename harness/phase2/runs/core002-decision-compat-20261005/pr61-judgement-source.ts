/**
 * Web side of the CORE-001 judgement contract (P2-CORE-001, PR #51): validates a core judgement output and the
 * core's review decision, and turns them into what the planner screens show. It never re-judges anything: the
 * decision (accept/hold/revise/unresolved) always comes from lgax_core.judgement_contract.review_judgement.
 * Fixture outputs from evals/core-contract are hand-written declarations, not model results.
 */
import Ajv2020 from 'ajv/dist/2020';
import outputSchema from '../../../evals/core-contract/schemas/output.json';
import type { Evidence } from './domain';
import { canonical, contractErrors } from './planning';
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
  rerun_from: JudgementStage | null; violations: { code: string; stage: JudgementStage }[];
}

const STAGES: JudgementStage[] = ['plan', 'retrieve', 'needs', 'compare', 'concepts', 'review'];
const decisionSchema = {
  type: 'object', additionalProperties: false,
  required: ['valid', 'action', 'revision_count', 'next_revision_count', 'rerun_from', 'violations'],
  properties: {
    valid: { type: 'boolean' }, action: { enum: ['accept', 'hold', 'revise', 'unresolved'] },
    revision_count: { type: 'integer', minimum: 0, maximum: 2 }, next_revision_count: { type: 'integer', minimum: 0, maximum: 2 },
    rerun_from: { enum: [...STAGES, null] },
    violations: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['code', 'stage'], properties: { code: { type: 'string', minLength: 1 }, stage: { enum: STAGES } } } },
  },
};

const ajv = new Ajv2020({ allErrors: true, strict: false });
const validateOutput = ajv.compile(outputSchema);
const validateDecision = ajv.compile(decisionSchema);

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

const VIOLATION_LABELS: Record<string, string> = {
  SOURCE_SCOPE_MISMATCH: '다른 모델·문서 버전의 원문이 섞였습니다',
  FEATURE_SCOPE_MISMATCH: '다른 모델·문서 버전의 기능이 섞였습니다',
  SOURCE_KIND_MISMATCH: '합성 자료와 실제 자료가 섞였습니다',
  REQUEST_PRODUCT_MISMATCH: '요청 범위 밖의 제품입니다',
  REVIEW_CONFLICT: '리뷰가 서로 상충합니다',
  REVIEW_UNCERTAIN: '불편인지 불확실한 리뷰를 근거로 썼습니다',
  NO_REVIEW_EVIDENCE: '불편을 뒷받침하는 리뷰가 없습니다',
  NON_COMPLAINT_AS_NEED: '불편이 아닌 리뷰를 불편 근거로 썼습니다',
  DUPLICATE_CONCEPT: '후보가 기존 기능과 중복됩니다',
  UNCERTAIN_DUPLICATION: '후보의 기존 기능 중복 여부가 불확실합니다',
  MISSING_EVIDENCE: '판단에 필요한 인용 근거가 빠졌습니다',
  OUTPUT_SCOPE_MISMATCH: '출력의 모델·문서 버전이 입력과 다릅니다',
  STALE_INPUT: '이전 입력(바뀌기 전 명세)의 결과입니다',
  UNSUPPORTED_WITHOUT_MANUAL: '설명서 근거 없이 미지원으로 판단했습니다',
  SUPPORT_UNKNOWN: '설명서에서 지원 여부를 확인할 수 없습니다',
  CONCEPT_LIMIT: '후보가 3개를 넘습니다',
  HOLD_WITHOUT_QUESTIONS: '보류했지만 확인할 질문이 없습니다',
  HUMAN_DECISION_REQUIRED: '기획자가 내려야 할 선택을 Agent가 정했습니다',
};

export function violationText(item: { code: string; stage: string }): string {
  return `${VIOLATION_LABELS[item.code] ?? item.code} (${item.code} · ${item.stage} 단계)`;
}

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
}

/** What the planner should read first: the core's decision, not the status the judgement declared about itself. */
export function judgementView(input: JudgementInput, output: JudgementOutput, decision: JudgementDecision): JudgementView {
  const scope = `${input.product.model_id}@${input.product.document_version}`;
  const base = {
    action: decision.action, candidates_selectable: decision.action === 'accept',
    declared_status_overridden: !({ accept: ['completed'], hold: ['held'], unresolved: ['failed'], revise: [] } as Record<string, string[]>)[decision.action].includes(output.status),
    violations: decision.violations.map(violationText), questions: [...output.questions, ...output.gaps.flatMap(gap => gap.questions)],
    hold_reasons: output.hold_reasons, unresolved: output.unresolved, no_candidate_reasons: output.no_candidate_reasons,
    out_of_scope_sources: input.sources.filter(item => `${item.model_id}@${item.document_version}` !== scope).map(item => `${item.id} (${item.model_id} · 문서 ${item.document_version})`),
  };
  switch (decision.action) {
    case 'accept': return { ...base, label: '계약 검사 통과 · 의미 미검증', tone: 'done', detail: ACCEPT_DETAIL };
    case 'hold': return { ...base, label: '보류', tone: 'notice', detail: '자료 범위나 근거를 확인한 뒤 새 입력으로 다시 실행해야 합니다. 이 결과의 후보는 선택할 수 없습니다.' };
    case 'revise': return { ...base, label: `수정 필요 · ${decision.rerun_from} 단계부터 재실행`, tone: 'notice', detail: `내부 수정 ${decision.next_revision_count}/2회차로 다시 실행할 중간 결과입니다. 저장·선택 대상이 아닙니다.` };
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
export interface PlanningExecution {
  execution_kind: 'fixture' | 'live_model'; status: 'completed' | 'held' | 'failed';
  original_input: JudgementInput; input: JudgementInput; output: JudgementOutput | null; decision: JudgementDecision | null;
  trace: TraceStep[]; model_calls: ModelCallRecord[]; errors: { code: string; message: string }[];
  rejected_execution?: unknown; rejected_execution_omitted?: string;
}
export type ExecutionView =
  | { kind: 'none' }
  | { kind: 'invalid'; errors: string[] }
  | { kind: 'ok'; execution: PlanningExecution; problems: string[]; models: string[]; model_calls: number; elapsed_ms: number | null };

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

function inputErrors(label: string, value: unknown): string[] {
  if (!isObject(value) || !isObject(value.product) || !Array.isArray(value.sources) || !Array.isArray(value.features)) return [`/${label} is not a judgement input`];
  return [
    ...contractErrors('PlanningRequest', value.request).map(item => `/${label}/request${item}`),
    ...value.sources.flatMap((item, index) => contractErrors('Evidence', item).map(error => `/${label}/sources/${index}${error}`)),
    ...value.features.flatMap((item, index) => contractErrors('Feature', item).map(error => `/${label}/features/${index}${error}`)),
  ];
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
  for (const key of ['trace', 'model_calls', 'errors']) if (!Array.isArray(raw[key])) found.push(`/${key} must be an array`);
  found.push(...inputErrors('original_input', raw.original_input), ...inputErrors('input', raw.input));
  if (raw.output !== null) found.push(...judgementOutputErrors(raw.output).map(item => `/output${item}`));
  if (raw.decision !== null) found.push(...judgementDecisionErrors(raw.decision).map(item => `/decision${item}`));
  if (found.length) return { kind: 'invalid', errors: found };

  const execution = raw as unknown as PlanningExecution;
  const problems: string[] = [];
  if (execution.status !== snapshot.run.status) problems.push(`저장된 실행 상태(${snapshot.run.status})와 판단 기록 상태(${execution.status})가 다릅니다.`);
  if (execution.status === 'completed' && execution.decision?.action !== 'accept') problems.push('완료로 기록됐지만 코어 검사 결정이 accept가 아닙니다.');
  if (canonical(execution.original_input.request) !== canonical(snapshot.request)) problems.push('판단에 들어간 원 요청이 이 실행의 요청과 다릅니다.');
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
