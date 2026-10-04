/**
 * Six judgment cases across the three proposal products, for screen/input regression while the planning core (#8/#9)
 * is not available (assignment PM-20261004-WEB-003-CORE-INTEGRATION).
 * Hand-written in the shape of packages/contracts 0.1.0; NOT Agent output, NOT a server response, and NOT evidence that
 * the core will judge these cases this way. Every evidence/feature ID cites data/demo/dataset.json (synthetic kitchen-demo
 * 0.1.0) verbatim, so the views resolve real source text, locations and document versions.
 */
import datasetSource from '../../../../data/demo/dataset.json';
import type { BootstrapData, Evidence } from '../domain';
import type { Concept, Feature, Gap, Need, PlanningRequest, Run, RunSnapshot } from '../planning';
import { FIXTURE_DATASET_SHA256 } from './planning.fixture';

const dataset = datasetSource as unknown as BootstrapData;
export const CASE_EVIDENCE = dataset.evidence as unknown as Evidence[];
export const CASE_FEATURES = dataset.features as unknown as Feature[];

export type CaseKind = 'normal' | 'supported' | 'duplicate' | 'insufficient_evidence' | 'conflict' | 'document_update';

export interface CaseFixture {
  kind: CaseKind;
  label: string;
  /** Which of the three proposal usage examples this case stands for, if any. */
  proposal_example: string | null;
  snapshot: RunSnapshot;
  /** What the screen must show for this case; checked by caseMatrix.test.ts. */
  expect: {
    statuses: Record<string, Gap['support_status']>;
    concept_statuses: Record<string, Concept['status']>;
    held_gap_ids: string[];
    uncertain_need_ids: string[];
    out_of_scope_ids: string[];
  };
}

const BASE = { target_customer: '키친 상품기획자', dataset_version: '0.1.0' } as const;

function snapshot(id: string, request: PlanningRequest, versions: Record<string, string>, parts: {
  status?: Run['status']; needs: Need[]; gaps: Gap[]; concepts: Concept[]; unresolved?: string[]; unconfirmed?: string[];
  extraEvidence?: string[]; events: Run['events']; revisions?: number;
}): RunSnapshot {
  const cited = new Set([...parts.needs.flatMap(item => item.evidence_ids), ...parts.gaps.flatMap(item => item.evidence_ids), ...parts.concepts.flatMap(item => item.evidence_ids), ...(parts.extraEvidence ?? [])]);
  return {
    run: {
      id, project_id: `PROJECT-CASE-${request.model_ids[0]}`, dataset_version: '0.1.0', contract_version: '0.1.0',
      status: parts.status ?? 'completed', stage: 'finished', revision_count: parts.revisions ?? 0, max_revisions: 2,
      concepts: parts.concepts, unresolved: parts.unresolved ?? [], evidence_ids: [...cited].sort(), events: parts.events,
    },
    request, previous_run_id: null, request_revision: 0, actor_id: 'fixture-planner', client: 'web',
    created_at: '2026-10-04T13:00:00.000000Z', document_versions: versions, dataset_sha256: FIXTURE_DATASET_SHA256,
    unconfirmed: parts.unconfirmed ?? [], output: { needs: parts.needs, gaps: parts.gaps },
  };
}

// 식기세척기 안내 서비스 — normal: an unsupported need with evidence becomes a candidate.
const dishwasherRequest: PlanningRequest = {
  ...BASE, product_group: 'dishwasher', use_situation: '여러 종류의 식기를 함께 적재하는 상황',
  improvement_task: '서로 다른 크기의 식기를 넣을 때 남는 불편을 검토', exclusions: ['실기기 제어'], model_ids: ['DISHWASHER-A'],
};
const normal = snapshot('RUN-CASE-NORMAL', dishwasherRequest, { 'DISHWASHER-A': '1.0' }, {
  needs: [{ id: 'NEED-CASE-DW-001', model_id: 'DISHWASHER-A', situation: '큰 접시와 냄비를 함께 적재하는 상황', pain: '설명서의 기본 적재 그림과 집의 식기 조합이 달라 놓을 위치를 판단하기 어렵다', evidence_ids: ['REVIEW-EVIDENCE-031', 'REVIEW-EVIDENCE-032'], uncertainties: [] }],
  gaps: [{ id: 'GAP-CASE-DW-001', need_id: 'NEED-CASE-DW-001', model_id: 'DISHWASHER-A', feature_ids: ['FEATURE-004'], support_status: 'unsupported', remaining_pain: '기본 적재 안내는 표준 조합 그림만 제공해 다른 식기 조합의 배치 판단 부담이 남는다', evidence_ids: ['MANUAL-004', 'REVIEW-EVIDENCE-032'], questions: [] }],
  concepts: [{
    id: 'CONCEPT-CASE-DW-001', title: '보유 식기 조합별 적재 안내', kind: 'service', gap_ids: ['GAP-CASE-DW-001'],
    evidence_ids: ['REVIEW-EVIDENCE-031', 'REVIEW-EVIDENCE-032', 'MANUAL-004'],
    differentiation: '기본 적재 안내(FEATURE-004)는 표준 그림 하나지만, 사용자가 고른 식기 조합에 맞춘 배치를 안내한다',
    requirements: ['넣을 식기 종류를 고르면 배치 예시를 보여 준다', '회전 날개 간섭 확인 조건을 배치 안내에 포함한다'],
    assumptions: ['식기 조합을 고르는 부담이 배치 판단 부담보다 작은지 미확인'], status: 'proposed',
  }],
  events: [
    { stage: 'retrieve', summary: '적재 관련 리뷰와 설명서 원문 조회', tool: 'evidence_lookup', evidence_ids: ['MANUAL-004', 'REVIEW-EVIDENCE-031', 'REVIEW-EVIDENCE-032'] },
    { stage: 'compare', summary: '기본 적재 안내와 대조해 남은 불편 기록', tool: 'product_compare', evidence_ids: ['MANUAL-004'] },
  ],
});

// 전자레인지 — supported need is solved by an existing feature; its discoverability need still leaves a gap.
const microwaveRequest: PlanningRequest = {
  ...BASE, product_group: 'microwave', use_situation: '자주 사용하는 조리 설정을 다시 입력하는 상황',
  improvement_task: '조리 설정을 반복할 때의 불편이 기존 기능으로 해결되는지 검토', exclusions: ['실기기 제어'], model_ids: ['MICROWAVE-A'],
};
const microwaveNeeds: Need[] = [
  { id: 'NEED-CASE-MW-001', model_id: 'MICROWAVE-A', situation: '매일 같은 음식을 데우는 상황', pain: '시간과 출력을 매번 다시 입력한다', evidence_ids: ['REVIEW-EVIDENCE-034'], uncertainties: [] },
  { id: 'NEED-CASE-MW-002', model_id: 'MICROWAVE-A', situation: '저장한 설정을 다시 쓰려는 상황', pain: '설정 저장 기능이 있는지, 어느 버튼으로 호출하는지 알기 어렵다', evidence_ids: ['REVIEW-EVIDENCE-035', 'REVIEW-EVIDENCE-036'], uncertainties: [] },
];
const microwaveGaps: Gap[] = [
  { id: 'GAP-CASE-MW-001', need_id: 'NEED-CASE-MW-001', model_id: 'MICROWAVE-A', feature_ids: ['FEATURE-005'], support_status: 'supported', remaining_pain: '', evidence_ids: ['MANUAL-005', 'REVIEW-EVIDENCE-034'], questions: [] },
  { id: 'GAP-CASE-MW-002', need_id: 'NEED-CASE-MW-002', model_id: 'MICROWAVE-A', feature_ids: ['FEATURE-005'], support_status: 'unsupported', remaining_pain: '기능은 있지만 존재와 호출 위치를 몰라 반복 입력이 남는다', evidence_ids: ['MANUAL-005', 'REVIEW-EVIDENCE-035', 'REVIEW-EVIDENCE-036'], questions: [] },
];
const recallGuide: Concept = {
  id: 'CONCEPT-CASE-MW-002', title: '저장 설정 호출 위치 안내', kind: 'service', gap_ids: ['GAP-CASE-MW-002'],
  evidence_ids: ['REVIEW-EVIDENCE-035', 'REVIEW-EVIDENCE-036', 'MANUAL-005'],
  differentiation: '새 기능을 만들지 않고 기존 설정 저장과 호출(FEATURE-005)을 처음 쓰는 사용자에게 알려 준다',
  requirements: ['반복 입력이 감지되면 저장 기능을 안내한다', '호출 버튼 위치를 한 화면에서 보여 준다'],
  assumptions: ['반복 입력을 감지할 수 있는 정보가 있는지 미확인'], status: 'proposed',
};
const supported = snapshot('RUN-CASE-SUPPORTED', microwaveRequest, { 'MICROWAVE-A': '1.0' }, {
  needs: microwaveNeeds, gaps: microwaveGaps, concepts: [recallGuide],
  events: [{ stage: 'compare', summary: '반복 입력 불편은 설정 저장과 호출로 해결됨, 호출 위치 불편만 남음', tool: 'product_compare', evidence_ids: ['MANUAL-005'] }],
});

// 전자레인지 기능 중복 제외 — a candidate that re-creates FEATURE-005 is kept visible as rejected, not dropped.
const duplicate = snapshot('RUN-CASE-DUPLICATE', microwaveRequest, { 'MICROWAVE-A': '1.0' }, {
  needs: microwaveNeeds, gaps: microwaveGaps, revisions: 1,
  concepts: [{
    id: 'CONCEPT-CASE-MW-001', title: '자주 쓰는 설정 원터치 저장 버튼', kind: 'feature', gap_ids: ['GAP-CASE-MW-001'],
    evidence_ids: ['REVIEW-EVIDENCE-034', 'MANUAL-005'],
    differentiation: '자주 쓰는 시간과 출력을 버튼 하나로 저장하고 호출한다',
    requirements: ['시간과 출력 설정을 저장한다', '저장한 설정을 한 번에 호출한다'],
    assumptions: ['기존 설정 저장과 호출(FEATURE-005)과 같은 기능이라 중복으로 제외'], status: 'rejected',
  }, recallGuide],
  unresolved: ['CONCEPT-CASE-MW-001: 기존 FEATURE-005(설정 저장과 호출)와 기능 중복 — 후보에서 제외'],
  events: [
    { stage: 'concepts', summary: '후보 2개 작성', tool: 'concept_draft', evidence_ids: ['REVIEW-EVIDENCE-034'] },
    { stage: 'review', summary: '기존 기능 중복 1건을 발견해 제외로 수정', tool: 'review_revision', evidence_ids: ['MANUAL-005'] },
  ],
});

// 근거 부족 — FRIDGE-C's manual says shelf removal is not in this document, so the need is held without a concept.
const fridgeCRequest: PlanningRequest = {
  ...BASE, product_group: 'fridge', use_situation: '음료를 쏟은 뒤 선반과 식품을 옮겨 청소하는 상황',
  improvement_task: '청소 불편과 기존 기능을 대조하고 기회 후보를 검토', exclusions: ['실기기 제어'], model_ids: ['FRIDGE-C'],
};
const insufficient = snapshot('RUN-CASE-INSUFFICIENT', fridgeCRequest, { 'FRIDGE-C': '1.0' }, {
  status: 'held',
  needs: [{ id: 'NEED-CASE-FC-001', model_id: 'FRIDGE-C', situation: '선반을 분리해 청소하려는 상황', pain: '선반 분리 방법을 설명서에서 찾지 못한다', evidence_ids: ['REVIEW-EVIDENCE-024'], uncertainties: [] }],
  gaps: [{ id: 'GAP-CASE-FC-001', need_id: 'NEED-CASE-FC-001', model_id: 'FRIDGE-C', feature_ids: [], support_status: 'insufficient_evidence', remaining_pain: '', evidence_ids: ['MANUAL-003', 'REVIEW-EVIDENCE-024'], questions: ['FRIDGE-C 문서 1.0에는 선반 탈착 방법이 없다(MANUAL-003) — 다른 문서 확인 필요'] }],
  concepts: [],
  unresolved: ['GAP-CASE-FC-001: 선반 탈착 기능 근거가 부족해 콘셉트 생성을 보류'],
  events: [{ stage: 'compare', summary: '연결할 기존 기능 근거가 없어 보류', tool: 'product_compare', evidence_ids: ['MANUAL-003'] }],
});

// 냉장고 구조 개선 — conflict: a review saying cleaning is easy is kept as an uncertainty and its text stays cited.
const fridgeARequest: PlanningRequest = { ...fridgeCRequest, model_ids: ['FRIDGE-A'] };
const tray: Concept = {
  id: 'CONCEPT-CASE-FA-001', title: '오염 구획만 꺼내는 분리 청소 트레이', kind: 'feature', gap_ids: ['GAP-CASE-FA-001'],
  evidence_ids: ['REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-008', 'MANUAL-001'],
  differentiation: '기존 선반 분리(FEATURE-001)는 식품 전체 이동이 조건이지만, 오염된 구획만 단독으로 꺼내 세척한다',
  requirements: ['오염된 구획만 단독으로 분리할 수 있어야 한다', '분리하지 않은 구획의 식품은 옮기지 않아도 된다'],
  assumptions: ['구획 분리 구조가 냉장 성능에 영향을 주지 않는지 미확인'], status: 'needs_review',
};
const fridgeANeed = (uncertainties: string[]): Need => ({ id: 'NEED-CASE-FA-001', model_id: 'FRIDGE-A', situation: '음료나 우유를 쏟은 뒤 선반을 청소하는 상황', pain: '선반 위 식품을 모두 옮겨야 해서 청소가 번거롭다', evidence_ids: ['REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-008'], uncertainties });
const fridgeAGap: Gap = { id: 'GAP-CASE-FA-001', need_id: 'NEED-CASE-FA-001', model_id: 'FRIDGE-A', feature_ids: ['FEATURE-001'], support_status: 'unsupported', remaining_pain: '선반 분리는 가능하지만 "선반 위 식품을 모두 이동" 조건 때문에 전체 이동 부담이 남는다', evidence_ids: ['MANUAL-001', 'REVIEW-EVIDENCE-001'], questions: [] };
const conflict = snapshot('RUN-CASE-CONFLICT', fridgeARequest, { 'FRIDGE-A': '1.0' }, {
  needs: [fridgeANeed(['REVIEW-EVIDENCE-006은 선반을 쉽게 꺼내 청소해 크게 불편하지 않다고 답해 상충 근거가 있음'])],
  gaps: [fridgeAGap], concepts: [tray], extraEvidence: ['REVIEW-EVIDENCE-006'],
  events: [{ stage: 'needs', summary: '불편 1건 구조화, 상충 리뷰 1건을 불확실성으로 기록', tool: 'need_extract', evidence_ids: ['REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-006'] }],
});

// 문서갱신 — document 2.0 adds a partial tray (MANUAL-006) but the run is pinned to 1.0; the citation is flagged, not merged.
const documentUpdate = snapshot('RUN-CASE-DOCUPDATE', fridgeARequest, { 'FRIDGE-A': '1.0' }, {
  needs: [fridgeANeed([])], gaps: [fridgeAGap],
  concepts: [{ ...tray, assumptions: [...tray.assumptions, '문서 2.0의 부분 분리 트레이(FEATURE-006)와 중복 여부 미확인'] }],
  extraEvidence: ['MANUAL-006'],
  unresolved: ['MANUAL-006은 문서 2.0에만 있어 고정 범위(문서 1.0)에서는 대조에 쓰지 않음 — 문서 범위 확대 여부 결정 필요'],
  unconfirmed: ['문서 범위를 2.0으로 확대할지 기획자 결정 필요'],
  events: [{ stage: 'retrieve', summary: '같은 모델의 새 문서 버전(2.0) 원문을 발견해 범위 밖으로 기록', tool: 'evidence_lookup', evidence_ids: ['MANUAL-001', 'MANUAL-006'] }],
});

export const CASE_MATRIX: CaseFixture[] = [
  { kind: 'normal', label: '정상', proposal_example: '식기세척기 안내 서비스', snapshot: normal,
    expect: { statuses: { 'NEED-CASE-DW-001': 'unsupported' }, concept_statuses: { 'CONCEPT-CASE-DW-001': 'proposed' }, held_gap_ids: [], uncertain_need_ids: [], out_of_scope_ids: [] } },
  { kind: 'supported', label: '지원됨', proposal_example: null, snapshot: supported,
    expect: { statuses: { 'NEED-CASE-MW-001': 'supported', 'NEED-CASE-MW-002': 'unsupported' }, concept_statuses: { 'CONCEPT-CASE-MW-002': 'proposed' }, held_gap_ids: [], uncertain_need_ids: [], out_of_scope_ids: [] } },
  { kind: 'duplicate', label: '기능중복', proposal_example: '전자레인지 기능 중복 제외', snapshot: duplicate,
    expect: { statuses: { 'NEED-CASE-MW-001': 'supported', 'NEED-CASE-MW-002': 'unsupported' }, concept_statuses: { 'CONCEPT-CASE-MW-001': 'rejected', 'CONCEPT-CASE-MW-002': 'proposed' }, held_gap_ids: [], uncertain_need_ids: [], out_of_scope_ids: [] } },
  { kind: 'insufficient_evidence', label: '근거부족', proposal_example: null, snapshot: insufficient,
    expect: { statuses: { 'NEED-CASE-FC-001': 'insufficient_evidence' }, concept_statuses: {}, held_gap_ids: ['GAP-CASE-FC-001'], uncertain_need_ids: [], out_of_scope_ids: [] } },
  { kind: 'conflict', label: '상충', proposal_example: '냉장고 구조 개선', snapshot: conflict,
    expect: { statuses: { 'NEED-CASE-FA-001': 'unsupported' }, concept_statuses: { 'CONCEPT-CASE-FA-001': 'needs_review' }, held_gap_ids: [], uncertain_need_ids: ['NEED-CASE-FA-001'], out_of_scope_ids: [] } },
  { kind: 'document_update', label: '문서갱신', proposal_example: null, snapshot: documentUpdate,
    expect: { statuses: { 'NEED-CASE-FA-001': 'unsupported' }, concept_statuses: { 'CONCEPT-CASE-FA-001': 'needs_review' }, held_gap_ids: [], uncertain_need_ids: [], out_of_scope_ids: ['MANUAL-006'] } },
];
