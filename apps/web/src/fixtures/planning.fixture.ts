/**
 * Contract fixture for UI development before the planning Agent exists (P2-WEB-001).
 * Hand-written examples shaped by packages/contracts; NOT Agent output and NOT a server response.
 * Evidence/feature IDs refer to bootstrap.fixture.json, which copies kitchen-demo 0.1.0 entries verbatim.
 */
import bootstrap from './bootstrap.fixture.json';
import type { BootstrapData } from '../domain';
import type { Concept, Gap, Need, PlanningRequest, RunSnapshot } from '../planning';

export const FIXTURE_BOOTSTRAP = bootstrap as unknown as BootstrapData;

// Canonical DemoDataset hash of data/demo/dataset.json (same rule as lgax_core.workspace); verified in planning.test.ts.
export const FIXTURE_DATASET_SHA256 = '8cbc9a492bd41f1112907a166744972501095aca49325630afbabe27b43b2c03';
export const FIXTURE_PROJECT_ID = 'PROJECT-FX-001';

export const FIXTURE_ORIGINAL_REQUEST: PlanningRequest = {
  product_group: 'fridge',
  target_customer: '키친 상품기획자',
  use_situation: '음료를 쏟은 뒤 선반과 식품을 옮겨 청소하는 상황',
  improvement_task: '청소 불편과 기존 기능을 대조하고 기회 후보를 검토',
  exclusions: ['실기기 제어', '제조용 CAD', '물리 시뮬레이션'],
  model_ids: ['FRIDGE-A'],
  dataset_version: '0.1.0',
};

const needs: Need[] = [
  {
    id: 'NEED-FX-001', model_id: 'FRIDGE-A',
    situation: '음료나 우유를 쏟은 뒤 선반을 청소하는 상황',
    pain: '선반 위 식품을 모두 옮겨야 해서 청소가 번거롭고 미루게 된다',
    evidence_ids: ['REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-008', 'REVIEW-EVIDENCE-009'],
    uncertainties: ['REVIEW-EVIDENCE-006은 선반 청소가 크게 불편하지 않다고 답해 상충 근거가 있음'],
  },
  {
    id: 'NEED-FX-002', model_id: 'FRIDGE-A',
    situation: '청소하거나 선반 높이를 바꾸는 동안 식품을 잠시 꺼내 두는 상황',
    pain: '꺼낸 식품을 둘 임시 보관 공간이 부족하다',
    evidence_ids: ['REVIEW-EVIDENCE-002', 'REVIEW-EVIDENCE-010'],
    uncertainties: [],
  },
];

const gaps: Gap[] = [
  {
    id: 'GAP-FX-001', need_id: 'NEED-FX-001', model_id: 'FRIDGE-A', feature_ids: ['FEATURE-001'],
    support_status: 'unsupported',
    remaining_pain: '선반 분리는 가능하지만 "선반 위 식품을 모두 이동" 조건 때문에 전체 이동 부담이 남는다',
    evidence_ids: ['MANUAL-001', 'REVIEW-EVIDENCE-001'],
    questions: ['문서 2.0의 부분 분리 트레이(FEATURE-006)가 검토 범위(문서 1.0)에 포함되어야 하는지 확인 필요'],
  },
  {
    id: 'GAP-FX-002', need_id: 'NEED-FX-002', model_id: 'FRIDGE-A', feature_ids: [],
    support_status: 'insufficient_evidence',
    remaining_pain: '',
    evidence_ids: ['REVIEW-EVIDENCE-002', 'REVIEW-EVIDENCE-010'],
    questions: ['임시 보관과 연결된 기능이 설명서에서 확인되지 않음 — 다른 모델·문서 확인 필요'],
  },
];

const trayConcept: Concept = {
  id: 'CONCEPT-FX-001', title: '오염 구획만 꺼내는 분리 청소 트레이', kind: 'feature', gap_ids: ['GAP-FX-001'],
  evidence_ids: ['REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-008', 'MANUAL-001'],
  differentiation: '기존 선반 분리(FEATURE-001)는 식품 전체 이동이 조건이지만, 오염된 구획만 단독으로 꺼내 세척한다',
  requirements: ['오염된 구획만 단독으로 분리할 수 있어야 한다', '분리하지 않은 구획의 식품은 옮기지 않아도 된다'],
  assumptions: ['구획 분리 구조가 냉장 성능에 영향을 주지 않는지 미확인', '문서 2.0의 부분 분리 트레이(FEATURE-006)와 중복 여부 미확인'],
  status: 'needs_review',
};

const guideConcept: Concept = {
  id: 'CONCEPT-FX-002', title: '청소 전 식품 이동 범위 안내', kind: 'service', gap_ids: ['GAP-FX-001'],
  evidence_ids: ['REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-004', 'REVIEW-EVIDENCE-009'],
  differentiation: '설명서에서 분리 방법을 찾기 어렵다는 리뷰와 청소를 미룬다는 리뷰에 대응해 필요한 이동 범위만 단계별로 안내한다',
  requirements: ['선반 분리 순서를 단계별로 보여준다', '청소할 구역에 따라 옮겨야 할 식품 범위를 안내한다'],
  assumptions: ['안내만으로 식품 이동 부담이 줄어드는지 미확인'],
  status: 'proposed',
};

const first: RunSnapshot = {
  run: {
    id: 'RUN-FX-001', project_id: FIXTURE_PROJECT_ID, dataset_version: '0.1.0', contract_version: '0.1.0',
    status: 'completed', stage: 'finished', revision_count: 1, max_revisions: 2,
    concepts: [trayConcept, guideConcept],
    unresolved: ['GAP-FX-002: 임시 보관 불편은 연결 기능 근거가 부족해 콘셉트 생성을 보류'],
    evidence_ids: ['MANUAL-001', 'REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-002', 'REVIEW-EVIDENCE-004', 'REVIEW-EVIDENCE-006', 'REVIEW-EVIDENCE-008', 'REVIEW-EVIDENCE-009', 'REVIEW-EVIDENCE-010'],
    events: [
      { stage: 'plan', summary: '요청 검증 후 검토 범위를 FRIDGE-A 문서 1.0으로 고정', tool: null, evidence_ids: [] },
      { stage: 'retrieve', summary: '청소·보관 관련 리뷰와 설명서 원문 조회', tool: 'evidence_lookup', evidence_ids: ['MANUAL-001', 'REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-002', 'REVIEW-EVIDENCE-006'] },
      { stage: 'needs', summary: '불편 2건 구조화, 상충 리뷰 1건을 불확실성으로 기록', tool: 'need_extract', evidence_ids: ['REVIEW-EVIDENCE-001', 'REVIEW-EVIDENCE-006'] },
      { stage: 'compare', summary: '선반 분리 기능과 대조, 임시 보관은 근거 부족', tool: 'product_compare', evidence_ids: ['MANUAL-001'] },
      { stage: 'concepts', summary: '근거가 있는 간극에 대해 콘셉트 2개 작성', tool: 'concept_draft', evidence_ids: ['REVIEW-EVIDENCE-008'] },
      { stage: 'review', summary: '인용 누락 1건을 발견해 1회 수정', tool: 'review_revision', evidence_ids: ['REVIEW-EVIDENCE-004'] },
    ],
  },
  request: FIXTURE_ORIGINAL_REQUEST, previous_run_id: null, request_revision: 0,
  actor_id: 'fixture-planner', client: 'web', created_at: '2026-10-04T08:00:00.000000Z',
  document_versions: { 'FRIDGE-A': '1.0' }, dataset_sha256: FIXTURE_DATASET_SHA256,
  unconfirmed: [], output: { needs, gaps },
};

const duplicateCondition = '문서 2.0 부분 분리 트레이와 같은 기능 제외';

const second: RunSnapshot = {
  run: {
    ...first.run, id: 'RUN-FX-002', revision_count: 0,
    concepts: [{ ...trayConcept, status: 'rejected', assumptions: [...trayConcept.assumptions, '추가 조건에 따라 문서 2.0 FEATURE-006과 중복 가능성이 있어 제외'] }, guideConcept],
    unresolved: [...first.run.unresolved, 'FEATURE-006은 문서 2.0에만 있어 현재 고정 범위(1.0)에서는 원문 대조가 불가 — 문서 범위 확대 여부 결정 필요'],
    events: [
      ...first.run.events.slice(0, 4),
      { stage: 'concepts', summary: `추가 조건 "${duplicateCondition}"을 반영해 기존 후보를 재검토`, tool: 'concept_draft', evidence_ids: ['MANUAL-001'] },
    ],
  },
  request: { ...FIXTURE_ORIGINAL_REQUEST, exclusions: [...FIXTURE_ORIGINAL_REQUEST.exclusions, duplicateCondition] },
  previous_run_id: 'RUN-FX-001', request_revision: 1,
  actor_id: 'fixture-planner', client: 'web', created_at: '2026-10-04T08:10:00.000000Z',
  document_versions: { 'FRIDGE-A': '1.0' }, dataset_sha256: FIXTURE_DATASET_SHA256,
  unconfirmed: ['문서 범위를 2.0으로 확대할지 기획자 결정 필요'], output: { needs, gaps },
};

export const FIXTURE_RUNS: RunSnapshot[] = [first, second];
