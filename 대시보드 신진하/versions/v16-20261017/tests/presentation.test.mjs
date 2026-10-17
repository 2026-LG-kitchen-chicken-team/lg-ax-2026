import test from 'node:test';
import assert from 'node:assert/strict';
import { NODE_DEFS, runStage } from '../src/engine.js';
import { SAMPLE_MODELS, SAMPLE_REVIEWS } from '../src/sample-data.js';
import { getStagePresentation, getOverallPresentation } from '../src/presentation.js';

function completedState() {
  const state = {
    status: 'completed', active: 'validate',
    brief: { product: '시험 냉장고', customer: '1인 가구', scope: '수납·청소' },
    request: '고객 리뷰를 같은 모델의 제품 기능과 대조해 주세요.',
    reviews: SAMPLE_REVIEWS, models: SAMPLE_MODELS,
    results: {}, steps: {}, decisions: {},
  };
  for (const node of NODE_DEFS) {
    state.results[node.id] = runStage(node.id, state);
    state.steps[node.id] = { status: 'completed', processed: 0, total: 0 };
  }
  return state;
}

test('five completed stages report actual units rather than common unlabelled counts', () => {
  const state = completedState();
  const retrieve = getStagePresentation(state, 'retrieve');
  assert.match(retrieve.completionText, /리뷰 42개 확인/);
  assert.match(retrieve.completionText, /모델 3개 연결 · 등록 모델 3개 · 모델 일치 리뷰 42개/);
  assert.equal(retrieve.metrics.find(item => item.label === '연결 모델').value, 3);
  assert.equal(retrieve.metrics.find(item => item.label === '제품 모델').value, 3);
  const structure = getStagePresentation(state, 'structure');
  assert.equal(structure.metrics.find(item => item.label === '불편 묶음').value, state.results.structure.needs.length);
  assert.equal(structure.metrics.find(item => item.label === '긍정 경험').value, state.results.structure.positiveReviews.length);
  const compare = getStagePresentation(state, 'compare');
  assert.equal(compare.metrics.find(item => item.label === '대조한 불편').value, state.results.compare.comparisons.length);
  const concept = getStagePresentation(state, 'concept');
  assert.match(concept.completionText, /콘셉트 3개 작성/);
  assert.equal(concept.metrics.find(item => item.label === '연결 요구사항').value, 9);
  const validate = getStagePresentation(state, 'validate');
  assert.equal(validate.metrics.find(item => item.label === '검사 항목').value, state.results.validate.checks.length);
  assert.equal(validate.metrics.find(item => item.label === '검토 가능 콘셉트').value, 3);
  assert.equal(validate.isActive, false, 'last completed stage is not described as executing');
});

test('running stage with unknown total never infers percent, completed units or a three-concept goal', () => {
  const state = completedState();
  state.status = 'running'; state.active = 'concept';
  delete state.results.concept; delete state.results.validate;
  state.steps.concept = { status: 'running', processed: 0, total: null };
  state.steps.validate = { status: 'idle', processed: 0, total: null };
  const view = getStagePresentation(state, 'concept');
  assert.equal(view.isActive, true);
  assert.equal(view.completionText, '');
  assert.equal(view.progressText, '처리 중 · 진행 수 집계 전');
  assert.doesNotMatch(view.progressText, /%|\d\s*\/\s*\d|콘셉트 3개 작성/);
  assert.ok(view.metrics.every(item => item.label.startsWith('입력')));
  assert.match(view.task, /시험 냉장고/);
  assert.match(view.task, /3개 모델/);
});

test('an explicitly supplied processed/total is displayed without estimating missing values', () => {
  const state = { status: 'running', active: 'compare', models: SAMPLE_MODELS, results: {}, steps: { compare: { status: 'running', processed: 2, total: 7 } } };
  assert.equal(getStagePresentation(state, 'compare').progressText, '불편 7묶음 중 2묶음 대조');
  state.steps.compare.processed = null;
  assert.equal(getStagePresentation(state, 'compare').progressText, '처리 중 · 진행 수 집계 전');
});

test('explicit running counts carry each stage unit and retain a real zero total', () => {
  const expected = {
    retrieve: '리뷰 7개 중 2개 확인', structure: '리뷰 7개 중 2개 분류',
    compare: '불편 7묶음 중 2묶음 대조', concept: '콘셉트 7개 중 2개 작성',
    validate: '검사 7항목 중 2항목 확인',
  };
  for (const node of NODE_DEFS) {
    const state = { status: 'running', active: node.id, steps: { [node.id]: { status: 'running', processed: 2, total: 7 } } };
    assert.equal(getStagePresentation(state, node.id).progressText, expected[node.id]);
    state.steps[node.id] = { status: 'running', processed: 0, total: 0 };
    const zero = getStagePresentation(state, node.id).progressText;
    assert.match(zero, /0(?:개|묶음|항목) 중 0(?:개|묶음|항목)/);
    assert.doesNotMatch(zero, /집계 전/);
    state.steps[node.id].total = null;
    assert.equal(getStagePresentation(state, node.id).progressText, '처리 중 · 진행 수 집계 전');
  }
});

test('empty completed outputs preserve zero counts in every stage without substituting input totals', () => {
  const state = completedState();
  state.results = {
    retrieve: { reviews: [], models: [], matchedReviews: [], unresolvedReviews: [] },
    structure: { needs: [], positiveReviews: [], mixedReviews: [], unclassifiedReviews: [], outOfScopeReviews: [] },
    compare: { comparisons: [], withheld: [], excludedCandidates: [] },
    concept: { concepts: [], withheld: [] },
    validate: { checks: [], issues: [], acceptedConcepts: [], needsRepair: false },
  };
  for (const node of NODE_DEFS) {
    const view = getStagePresentation(state, node.id);
    assert.ok(view.metrics.length > 0);
    assert.ok(view.metrics.every(item => item.value === 0));
    assert.match(view.completionText, /0/);
  }
  assert.equal(getStagePresentation(state, 'retrieve').completionText, '리뷰 0개 확인 · 모델 0개 연결 · 등록 모델 0개 · 모델 일치 리뷰 0개');
});

test('connected model count uses unique matched registered IDs, not all registered models', () => {
  const state = completedState();
  state.results.retrieve = {
    reviews: [{ id: 'R1' }, { id: 'R2' }, { id: 'R3' }], models: SAMPLE_MODELS,
    matchedReviews: [{ model: 'K-B02' }, { modelId: ' k_b02 ' }, { model: 'k.b02' }], unresolvedReviews: [],
  };
  const one = getStagePresentation(state, 'retrieve');
  assert.equal(one.metrics.find(item => item.label === '연결 모델').value, 1);
  assert.equal(one.metrics.find(item => item.label === '제품 모델').value, 3);
  assert.match(one.completionText, /모델 1개 연결 · 등록 모델 3개 · 모델 일치 리뷰 3개/);
  state.results.retrieve.matchedReviews = [];
  const none = getStagePresentation(state, 'retrieve');
  assert.equal(none.metrics.find(item => item.label === '연결 모델').value, 0);
  assert.match(none.completionText, /모델 0개 연결 · 등록 모델 3개/);
  state.results.retrieve.matchedReviews = [{ model: 'NOT-REGISTERED' }];
  assert.equal(getStagePresentation(state, 'retrieve').metrics.find(item => item.label === '연결 모델').value, 0);
});

test('validation counts failed checks separately from issue records and passing caution checks', () => {
  const state = completedState();
  state.status = 'review';
  state.results.validate = {
    checks: [{ passed: true, status: '통과' }, { passed: true, status: '주의' }, { passed: false, status: '실패' }],
    issues: Array.from({ length: 5 }, (_, index) => ({ message: `검사 문제 ${index + 1}` })),
    acceptedConcepts: [], needsRepair: true,
  };
  const view = getStagePresentation(state, 'validate');
  assert.equal(view.status, 'review');
  assert.equal(view.statusLabel, '검토 필요');
  assert.equal(view.completionText, '검사 3항목 중 2항목 통과 · 확인 필요 1항목 · 문제 5건 · 검토 가능 콘셉트 0개');
  assert.equal(view.metrics.find(item => item.label === '확인 필요 항목').value, 1);
  assert.equal(view.metrics.find(item => item.label === '검사 문제').value, 5);
});

test('partial rerun removes later completion descriptions while retaining valid previous-stage counts', () => {
  const state = completedState();
  const priorNeeds = state.results.structure.needs.length;
  for (const id of ['compare', 'concept', 'validate']) {
    delete state.results[id]; state.steps[id] = { status: 'idle', processed: 0, total: null };
  }
  state.status = 'running'; state.active = 'compare'; state.steps.compare.status = 'running';
  const compare = getStagePresentation(state, 'compare');
  const concept = getStagePresentation(state, 'concept');
  assert.equal(compare.completionText, '');
  assert.equal(compare.metrics.find(item => item.label === '입력 불편 묶음').value, priorNeeds);
  assert.equal(concept.completionText, '');
  assert.deepEqual(concept.metrics, []);
  const overall = getOverallPresentation(state);
  assert.equal(overall.completedCount, 2);
  assert.equal(overall.stageCount, 5);
  assert.match(overall.title, /기능 대조/);
  assert.doesNotMatch(overall.summary, /콘셉트 3개/);
});

test('completed overall uses validated accepted count including a valid empty array', () => {
  const state = completedState();
  state.results.validate.acceptedConcepts = [];
  const empty = getOverallPresentation(state);
  assert.match(empty.summary, /검토 가능한 콘셉트가 없습니다/);
  assert.doesNotMatch(empty.summary, /콘셉트 3개|요구사항 9개/);
  assert.equal(getStagePresentation(state, 'validate').metrics.find(item => item.label === '검토 가능 콘셉트').value, 0);
  delete state.results.validate.acceptedConcepts;
  assert.match(getOverallPresentation(state).summary, /콘셉트 3개/);
});

test('human question and paused state explain the actual blocking reason and next action', () => {
  const state = completedState();
  state.status = 'awaiting'; state.active = 'compare';
  state.steps.compare = { status: 'awaiting', total: null, processed: 0 };
  state.question = { id: 'q1', text: '선반을 옮기는 상황인지 원문으로 확인해 주세요.' };
  assert.equal(getStagePresentation(state, 'compare').task, state.question.text);
  assert.equal(getOverallPresentation(state).summary, state.question.text);
  assert.match(getOverallPresentation(state).nextAction, /가정으로 포함.*보류/);
  state.status = 'paused'; state.question = null; state.steps.compare.status = 'running';
  assert.equal(getStagePresentation(state, 'compare').status, 'paused');
  assert.match(getOverallPresentation(state).nextAction, /계속/);
});

test('review and failure summaries keep real issue text and do not claim successful completion', () => {
  const state = completedState();
  state.status = 'review';
  state.results.validate.needsRepair = true;
  state.results.validate.issues = [{ message: '제품 문서 버전이 바뀌었습니다.' }];
  assert.equal(getStagePresentation(state, 'validate').statusLabel, '검토 필요');
  assert.match(getOverallPresentation(state).summary, /문제 1건.*문서 버전/);
  assert.match(getOverallPresentation(state).nextAction, /자료를 보완/);
  state.status = 'failed'; state.active = 'retrieve'; state.error = 'Python 실행기에 연결할 수 없습니다.';
  assert.equal(getStagePresentation(state, 'retrieve').task, state.error);
  assert.equal(getOverallPresentation(state).summary, state.error);
  assert.match(getOverallPresentation(state).nextAction, /다시 실행/);
});

test('Python-shaped common results need no API envelope or browser-specific metadata', () => {
  const state = {
    status: 'completed', active: 'validate', mode: 'python', models: [{ id: 'M1' }],
    results: {
      retrieve: { reviews: [{ id: 'R1' }], models: [{ id: 'M1' }], matchedReviews: [{ id: 'R1' }], unresolvedReviews: [] },
      structure: { needs: [{ id: 'N1' }], positiveReviews: [], mixedReviews: [], unclassifiedReviews: [], outOfScopeReviews: [] },
      compare: { comparisons: [{ eligible: true }], withheld: [], excludedCandidates: [] },
      concept: { concepts: [{ requirements: ['원문 연결'] }], withheld: [] },
      validate: { checks: [{ passed: true }], issues: [], needsRepair: false, acceptedConcepts: [{ requirements: ['원문 연결'] }] },
    },
  };
  assert.equal(getOverallPresentation(state).completedCount, 5);
  assert.match(getOverallPresentation(state).summary, /콘셉트 1개와 요구사항 1개/);
  assert.match(getStagePresentation(state, 'compare').completionText, /불편 1개 대조/);
});

test('helpers are pure and tolerate an empty state without inventing outputs', () => {
  const state = completedState();
  const before = JSON.stringify(state);
  for (const node of NODE_DEFS) getStagePresentation(state, node.id);
  getOverallPresentation(state);
  assert.equal(JSON.stringify(state), before);
  const idle = getOverallPresentation();
  assert.equal(idle.completedCount, 0);
  assert.match(idle.summary, /입력 리뷰 0개/);
  assert.deepEqual(getStagePresentation({}, 'concept').metrics, []);
});
