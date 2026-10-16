import { NODE_DEFS } from './engine.js';

// Presentation reads completed outputs and explicit controller state. It never
// advances work, estimates elapsed progress, or manufactures item-level events.
const labels = Object.freeze({
  idle: '대기', running: '실행 중', paused: '일시정지', awaiting: '확인 필요',
  stopped: '중지됨', completed: '완료', failed: '실패', review: '검토 필요',
});
const rows = value => Array.isArray(value) ? value : [];
const text = value => typeof value === 'string' ? value.trim() : '';
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : null;
const metric = (label, value, unit = '개') => ({ label, value, unit });
const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const modelKey = value => value == null ? '' : String(value).trim().toLowerCase().replace(/[\s_\-.:()\[\]]/g, '');
const nodeFor = id => NODE_DEFS.find(node => node.id === id);
const knownStatus = status => Object.hasOwn(labels, status) ? status : 'idle';

function inputs(state) {
  const result = state.results || {};
  const product = text(state.brief?.product) || '선택 제품';
  const customer = text(state.brief?.customer);
  const scope = text(state.brief?.scope);
  return {
    result, product, customer, scope,
    reviews: rows(state.reviews).length,
    models: rows(state.models).length,
    connected: Array.isArray(result.retrieve?.matchedReviews) ? result.retrieve.matchedReviews.length : null,
    needs: Array.isArray(result.structure?.needs) ? result.structure.needs.length : null,
    opportunities: Array.isArray(result.compare?.comparisons) ? result.compare.comparisons.filter(row => row.eligible === true).length : null,
    concepts: Array.isArray(result.concept?.concepts) ? result.concept.concepts.length : null,
  };
}

function taskFor(state, id) {
  const { product, customer, scope, reviews, models, needs, opportunities, concepts } = inputs(state);
  const target = models ? `${models}개 모델의` : '모델 명세가 필요한';
  const situation = [customer, scope].filter(Boolean).join(' · ');
  switch (id) {
    case 'retrieve': return `${product} 리뷰 ${reviews}개와 모델 ${models}개의 원문·ID·출처를 확인하고 같은 모델끼리 연결합니다.`;
    case 'structure': return `${product} ${target} 리뷰에서 ${situation ? `${situation} 상황의 ` : ''}불편을 묶고 긍정 경험과 미분류 원문을 구분합니다.`;
    case 'compare': return `${product} ${target} ${needs === null ? '고객 불편' : `불편 ${needs}묶음`}을 기존 기능·사용 조건과 대조해 남은 불편과 확인할 가정을 구분합니다.`;
    case 'concept': return opportunities === 0
      ? `${product}의 확인된 기획 기회가 없어 근거 부족·중복·제외 조건과 보류 사유를 정리합니다.`
      : `${product} ${target} ${opportunities === null ? '근거가 확인된 잔여 불편' : `검토 기회 ${opportunities}개`}에서 동작 방식·요구사항·확인할 가정을 작성합니다.`;
    case 'validate': return `${product} ${target} ${concepts === null ? '기획 결과' : `콘셉트 ${concepts}개`}와 보류 항목의 모델·원문·중복·요구사항 연결을 검사합니다.`;
    default: return `${product}의 기획 요청과 원문 자료를 확인합니다.`;
  }
}

function resultPresentation(id, result, state) {
  switch (id) {
    case 'retrieve': {
      const reviews = rows(result.reviews).length, models = rows(result.models).length;
      const matched = rows(result.matchedReviews).length, held = rows(result.unresolvedReviews).length;
      const registeredIds = new Set(rows(result.models).map(model => modelKey(model.id) || modelKey(model.modelId)).filter(Boolean));
      const connectedModels = new Set(rows(result.matchedReviews).map(review => modelKey(review.model) || modelKey(review.modelId)).filter(id => registeredIds.has(id))).size;
      return {
        completionText: `리뷰 ${reviews}개 확인 · 모델 ${connectedModels}개 연결 · 등록 모델 ${models}개 · 모델 일치 리뷰 ${matched}개${held ? ` · 연결 보류 ${held}개` : ''}`,
        metrics: [metric('확인 리뷰', reviews), metric('모델 연결 리뷰', matched), metric('연결 모델', connectedModels), metric('제품 모델', models), metric('연결 보류', held)],
      };
    }
    case 'structure': {
      const needs = rows(result.needs).length, positive = rows(result.positiveReviews).length;
      const mixed = rows(result.mixedReviews).length, unknown = rows(result.unclassifiedReviews).length;
      const outside = rows(result.outOfScopeReviews).length;
      return {
        completionText: `불편 ${needs}묶음 정리 · 긍정 경험 ${positive}개 분리${unknown ? ` · 미분류 ${unknown}개` : ''}${outside ? ` · 범위 밖 ${outside}개` : ''}`,
        metrics: [metric('불편 묶음', needs, '묶음'), metric('긍정 경험', positive), metric('혼합 리뷰', mixed), metric('미분류', unknown), metric('범위 밖', outside)],
      };
    }
    case 'compare': {
      const comparisons = rows(result.comparisons), eligible = comparisons.filter(row => row.eligible === true).length;
      const held = rows(result.withheld).length, excluded = rows(result.excludedCandidates).length;
      return {
        completionText: `불편 ${comparisons.length}개 대조 · 검토 기회 ${eligible}개 · 보류 ${held}개`,
        metrics: [metric('대조한 불편', comparisons.length), metric('검토 기회', eligible), metric('보류 항목', held), metric('제외 후보', excluded)],
      };
    }
    case 'concept': {
      const concepts = rows(result.concepts), requirements = concepts.reduce((sum, item) => sum + rows(item.requirements).length, 0);
      return {
        completionText: `콘셉트 ${concepts.length}개 작성 · 요구사항 ${requirements}개${rows(result.withheld).length ? ` · 보류 ${result.withheld.length}개` : ''}`,
        metrics: [metric('작성 콘셉트', concepts.length), metric('연결 요구사항', requirements), metric('보류 항목', rows(result.withheld).length)],
      };
    }
    case 'validate': {
      const checks = rows(result.checks), passed = checks.filter(check => check.passed === true).length;
      const failed = checks.filter(check => check.passed === false).length;
      const issues = rows(result.issues), accepted = Array.isArray(result.acceptedConcepts) ? result.acceptedConcepts : rows(state.results?.concept?.concepts);
      return {
        completionText: `검사 ${checks.length}항목 중 ${passed}항목 통과 · 확인 필요 ${failed}항목 · 문제 ${issues.length}건 · 검토 가능 콘셉트 ${accepted.length}개`,
        metrics: [metric('검사 항목', checks.length, '항목'), metric('통과 항목', passed, '항목'), metric('확인 필요 항목', failed, '항목'), metric('검사 문제', issues.length, '건'), metric('검토 가능 콘셉트', accepted.length)],
      };
    }
    default: return { completionText: text(result.summary), metrics: [] };
  }
}

function inboundMetrics(state, id) {
  const input = inputs(state);
  switch (id) {
    case 'retrieve': return [metric('입력 리뷰', input.reviews), metric('등록 모델', input.models)];
    case 'structure': return input.connected === null ? [] : [metric('연결된 입력 리뷰', input.connected)];
    case 'compare': return input.needs === null ? [] : [metric('입력 불편 묶음', input.needs, '묶음')];
    case 'concept': return input.opportunities === null ? [] : [metric('입력 검토 기회', input.opportunities)];
    case 'validate': return input.concepts === null ? [] : [metric('입력 콘셉트', input.concepts)];
    default: return [];
  }
}

function nextFor(status, id, state) {
  if (status === 'awaiting') return '연결 원문을 확인한 뒤 ‘가정으로 포함’ 또는 ‘보류’를 선택하세요.';
  if (status === 'paused') return '‘계속’을 선택하면 같은 실행을 이어갑니다.';
  if (status === 'stopped') return '보존된 결과를 확인하고 필요한 단계부터 다시 실행하세요.';
  if (status === 'failed') return '오류와 입력 자료를 확인한 뒤 이 단계부터 다시 실행하세요.';
  if (status === 'review') return '검사 문제와 수정 이력을 확인한 뒤 요청·자료를 보완하고 필요한 단계부터 다시 실행하세요.';
  if (status === 'running') return '현재 작업과 연결 근거를 확인하세요. 필요하면 일시정지할 수 있습니다.';
  if (status === 'completed') {
    if (id === 'validate') return '원문과 최종 결과를 검토하고 JSON 또는 CSV로 내보내세요.';
    const next = NODE_DEFS[NODE_DEFS.findIndex(node => node.id === id) + 1];
    return next ? `완료 결과의 원문을 확인하고 ${next.label} 단계의 작업을 확인하세요.` : '결과와 연결 원문을 확인하세요.';
  }
  return state.status === 'idle' ? '기획 요청과 자료를 확인한 뒤 전체 실행을 시작하세요.' : '이전 단계 결과를 확인하고 필요한 단계부터 실행하세요.';
}

export function getStagePresentation(state = {}, id) {
  const node = nodeFor(id), step = object(state.steps?.[id]) || {};
  const result = object(state.results?.[id]);
  const current = state.active === id;
  const isActive = current && ['running', 'paused', 'awaiting'].includes(state.status);
  let status = knownStatus(step.status || (result ? 'completed' : 'idle'));
  if (current && ['paused', 'awaiting', 'stopped', 'failed'].includes(state.status)) status = state.status;
  if (id === 'validate' && result?.needsRepair && status === 'completed') status = 'review';
  const hasCompletedResult = result && (status === 'completed' || status === 'review');
  const output = hasCompletedResult ? resultPresentation(id, result, state) : { completionText: '', metrics: inboundMetrics(state, id) };
  let task = taskFor(state, id);
  if (status === 'awaiting' && text(state.question?.text)) task = state.question.text;
  if (status === 'failed') task = text(state.error) || text(step.task) || '단계 실행에 실패했습니다. 오류 기록을 확인하세요.';
  let progressText = labels[status];
  if (hasCompletedResult) progressText = output.completionText;
  else if (status === 'running') {
    const [subject, unit, action] = {
      retrieve: ['리뷰', '개', '확인'], structure: ['리뷰', '개', '분류'],
      compare: ['불편', '묶음', '대조'], concept: ['콘셉트', '개', '작성'],
      validate: ['검사', '항목', '확인'],
    }[id] || ['작업', '개', '처리'];
    progressText = number(step.processed) && number(step.total)
      ? `${subject} ${step.total}${unit} 중 ${step.processed}${unit} ${action}`
      : '처리 중 · 진행 수 집계 전';
  } else if (status === 'paused') progressText = '일시정지 · 완료한 결과 보존';
  else if (status === 'awaiting') progressText = '기획자 응답 대기';
  else if (status === 'stopped') progressText = '중지됨 · 완료한 결과 보존';
  return {
    label: node?.label || '전체 현황', status, statusLabel: labels[status], isActive,
    task, progressText, completionText: output.completionText, metrics: output.metrics,
    nextAction: nextFor(status, id, state),
  };
}

export function getOverallPresentation(state = {}) {
  const status = knownStatus(state.status), stageId = nodeFor(state.active)?.id || null;
  const stageCount = NODE_DEFS.length;
  const completedCount = NODE_DEFS.filter(node => object(state.results?.[node.id]) && (state.steps?.[node.id]?.status === 'completed' || !state.steps?.[node.id]?.status)).length;
  const stage = stageId ? getStagePresentation(state, stageId) : null;
  let title, summary, nextAction;
  switch (status) {
    case 'running':
      title = `${stage?.label || '상품기획'}를 진행하고 있습니다`;
      summary = stage?.task || taskFor(state, 'retrieve');
      nextAction = nextFor(status, stageId, state);
      break;
    case 'awaiting':
      title = '기획자 확인이 필요합니다';
      summary = text(state.question?.text) || '확인할 항목의 연결 원문과 판단 조건을 검토해 주세요.';
      nextAction = nextFor(status, stageId, state);
      break;
    case 'paused':
      title = `${stage?.label || '실행'}에서 일시정지했습니다`;
      summary = `완료한 ${completedCount}개 단계의 결과를 보존하고 다음 작업 경계에서 대기합니다.`;
      nextAction = nextFor(status, stageId, state);
      break;
    case 'stopped':
      title = '실행을 중지했습니다';
      summary = `완료한 ${completedCount}개 단계의 결과와 실행 기록을 보존했습니다.`;
      nextAction = nextFor(status, stageId, state);
      break;
    case 'failed':
      title = `${stage?.label || '실행'}에서 오류가 발생했습니다`;
      summary = text(state.error) || stage?.task || '오류 기록과 입력 자료를 확인해 주세요.';
      nextAction = nextFor(status, stageId, state);
      break;
    case 'review': {
      const issues = rows(state.results?.validate?.issues);
      title = '미해결 항목을 검토해 주세요';
      summary = issues.length ? `검사 문제 ${issues.length}건이 남아 있습니다. ${issues.map(issue => text(issue.message)).filter(Boolean).slice(0, 2).join(' / ')}` : '검사 결과와 보류 사유를 확인해 주세요.';
      nextAction = nextFor(status, stageId, state);
      break;
    }
    case 'completed': {
      const accepted = state.results?.validate?.acceptedConcepts;
      const concepts = Array.isArray(accepted) ? accepted : rows(state.results?.concept?.concepts);
      const requirements = concepts.reduce((sum, concept) => sum + rows(concept.requirements).length, 0);
      title = '기획 결과를 검토할 수 있습니다';
      summary = concepts.length
        ? `검토 가능한 콘셉트 ${concepts.length}개와 요구사항 ${requirements}개를 원문 근거와 함께 확인하세요.`
        : '검토 가능한 콘셉트가 없습니다. 근거 부족·중복·제외 조건과 보류 사유를 확인하세요.';
      nextAction = '최종 결과와 원문을 검토하고 실행 기록을 포함해 JSON 또는 CSV로 내보내세요.';
      break;
    }
    default:
      title = `${inputs(state).product} 상품기획을 준비합니다`;
      summary = `입력 리뷰 ${inputs(state).reviews}개 · 제품 모델 ${inputs(state).models}개. 요청 조건과 원문 자료를 먼저 확인하세요.`;
      nextAction = nextFor('idle', stageId, state);
  }
  return { statusLabel: labels[status], title, summary, nextAction, stageId, completedCount, stageCount };
}
