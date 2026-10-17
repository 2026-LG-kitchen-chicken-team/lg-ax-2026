import test from 'node:test';
import assert from 'node:assert/strict';
import {
  NODE_DEFS, parseCSV, normalizeModels, normalizeReviews, runStage, getClarification,
} from '../src/engine.js';
import { SAMPLE_REQUEST, SAMPLE_MODELS, SAMPLE_REVIEWS } from '../src/sample-data.js';

const copy = value => JSON.parse(JSON.stringify(value));
const oneModel = () => [{ id: 'M-A', name: '가상 냉장고 A', source: '제품 설명서', version: '1.0', synthetic: true, features: [
  { id: 'M-A:F1', name: '분리형 선반', evidence: '선반을 분리해 세척할 수 있다. 분리 전 식품을 모두 옮긴다.', page: 4, condition: '식품을 옮긴 후 분리' },
  { id: 'M-A:F2', name: '높이 조절 선반', evidence: '선반 높이를 세 단계로 조절할 수 있다.', page: 5 },
  { id: 'M-A:F3', name: '투명 서랍', evidence: '투명 전면을 통해 내부 식품을 확인할 수 있다.', page: 6 },
] }];
const painReview = (text = '선반 청소를 하려면 식품을 전부 옮겨야 해서 번거로워요.') => ({ id: 'R-1', model: 'M-A', text, source: '고객 원문 CSV', version: '1', location: '행 2', synthetic: true });
function execute(overrides = {}) {
  const context = { request: '냉장고 수납·정리·청소 개선', reviews: [painReview()], models: oneModel(), conditions: {}, decisions: {}, results: {}, ...overrides };
  for (const node of NODE_DEFS) context.results[node.id] = runStage(node.id, context);
  return context;
}

test('normal workflow creates source-linked requirements using current model/version', () => {
  const { results } = execute();
  assert.equal(results.retrieve.matchedReviews.length, 1);
  assert.equal(results.structure.needs[0].category, 'cleaning_transport');
  assert.equal(results.compare.comparisons[0].classification, 'residual');
  assert.equal(results.concept.concepts.length, 1);
  assert.equal(results.validate.needsRepair, false);
  const candidate = results.validate.acceptedConcepts[0];
  assert.ok(candidate.requirementEvidence.every(row => row.reviewIds.includes('R-1') && row.featureIds.includes('M-A:F1')));
  const ref = candidate.sources.find(source => source.id === 'M-A:F1');
  assert.equal(ref.version, '1.0');
  assert.equal(ref.condition, '식품을 옮긴 후 분리');
  assert.equal(ref.page, 4);
});

test('CSV parser preserves BOM, multiline quoted content and escaped quotes', () => {
  const rows = parseCSV('\uFEFFid,model,text\r\nR-1,M-A,"청소, 수납\n그는 ""어려움""이라고 적음"');
  assert.equal(rows[0].text, '청소, 수납\n그는 "어려움"이라고 적음');
  assert.throws(() => parseCSV('id,id\n1,2'), /중복/);
  assert.throws(() => parseCSV('id,text\n1,"닫히지 않음'), /따옴표/);
});

test('duplicate review IDs are retained and block ambiguous citation rather than substituted', () => {
  const context = execute({ reviews: [painReview(), painReview('같은 ID의 다른 청소 원문')] });
  assert.equal(context.results.retrieve.reviews.length, 2);
  assert.equal(context.results.retrieve.unresolvedReviews.length, 2);
  assert.ok(context.results.retrieve.validation.issues.some(issue => issue.code === 'duplicate_id'));
  assert.equal(context.results.concept.concepts.length, 0);
  assert.equal(context.results.validate.needsRepair, true);
});

test('missing review/model identifiers remain held issues and never become valid synthetic IDs', () => {
  const context = execute({ reviews: [{ text: painReview().text, model: 'M-A' }, { ...painReview(), id: 'R-2', model: 'UNKNOWN' }, { ...painReview(), id: 'R-3', model: '' }] });
  assert.equal(context.results.retrieve.reviews.length, 3);
  assert.equal(context.results.retrieve.matchedReviews.length, 0);
  assert.equal(context.results.retrieve.unresolvedReviews.length, 3);
  assert.ok(context.results.retrieve.validation.issues.some(issue => issue.code === 'missing_review_id'));
  assert.ok(context.results.retrieve.validation.issues.some(issue => issue.code === 'unknown_model'));
  assert.ok(context.results.retrieve.validation.issues.some(issue => issue.code === 'missing_model'));
  assert.equal(context.results.concept.concepts.length, 0);
  assert.equal(normalizeModels([{ name: '식별자 없는 모델' }])[0].missingId, true);
});

test('feature already solving proposed mechanism excludes duplicate concept', () => {
  const models = oneModel();
  models[0].features.push({ id: 'M-A:F4', name: '칸별 탈착 트레이', evidence: '오염된 칸의 탈착 트레이만 내용물을 담은 채 분리하여 청소한다.', page: 8 });
  const context = execute({ models });
  assert.equal(context.results.compare.comparisons[0].classification, 'duplicate');
  assert.equal(context.results.concept.concepts.length, 0);
  assert.ok(context.results.compare.excludedCandidates.some(row => row.title === '구획별 탈착 트레이'));
});

test('other model feature cannot fill missing feature evidence', () => {
  const models = oneModel();
  models[0].features = [];
  models.push({ ...oneModel()[0], id: 'M-B', features: oneModel()[0].features.map(feature => ({ ...feature, id: feature.id.replace('M-A', 'M-B') })) });
  const context = execute({ models });
  assert.equal(context.results.compare.comparisons[0].classification, 'unknown');
  assert.equal(context.results.compare.comparisons[0].featureIds.length, 0);
  assert.equal(context.results.concept.concepts.length, 0);
});

test('validation detects injected review and feature cross-model contamination', () => {
  const context = execute();
  context.results.structure.needs[0].modelId = 'M-B';
  const checked = runStage('validate', context);
  assert.equal(checked.needsRepair, true);
  assert.ok(checked.issues.some(issue => issue.code === 'model_mismatch'));
  assert.equal(checked.acceptedConcepts.length, 0);
});

test('positive-only review excluded, mixed review retained, conflicting experiences kept separately', () => {
  const reviews = [
    painReview('높이 조절은 편하지만 큰 냄비와 작은 통의 수납 배치를 정하기 어려워요.'),
    { ...painReview('높이 조절과 선반 덕분에 큰 용기 수납이 편해요.'), id: 'R-2' },
    { ...painReview('투명 서랍은 좋지만 뒤쪽 식재료가 안 보여서 자주 잊어요.'), id: 'R-3' },
  ];
  const context = execute({ reviews });
  assert.equal(context.results.structure.positiveReviews.length, 1);
  assert.equal(context.results.structure.mixedReviews.length, 2);
  assert.ok(context.results.structure.needs.every(need => !need.reviewIds.includes('R-2')));
  assert.ok(context.results.structure.needs.some(need => need.reviewIds.includes('R-1')));
  assert.ok(context.results.structure.needs.some(need => need.reviewIds.includes('R-3')));
  assert.equal(context.results.structure.positiveReviews[0].text, reviews[1].text);
});

test('no evidence produces unknown/held instead of asserting function absent', () => {
  const models = oneModel();
  models[0].features = [{ id: 'M-A:F1', name: '분리형 선반', evidence: '', page: 4 }];
  const context = execute({ models });
  assert.equal(context.results.concept.concepts.length, 0);
  assert.equal(context.results.compare.comparisons[0].classification, 'unknown');
  assert.match(context.results.compare.comparisons[0].reason, /기능이 없다고 단정하지/);
  assert.ok(context.results.retrieve.validation.issues.some(issue => issue.code === 'missing_evidence'));
});

test('ambiguous cleaning waits for human include/hold and preserves decision without inventing cause', () => {
  const context = execute({ reviews: [painReview('선반 청소가 어려운데 정확히 왜 그런지는 모르겠어요.')] });
  const question = getClarification(context);
  assert.equal(question.stage, 'compare');
  assert.equal(question.evidence[0].id, 'R-1');
  for (const decision of ['include', 'hold']) {
    const decided = { ...context, decisions: { [question.id]: decision } };
    const compared = runStage('compare', decided);
    assert.equal(compared.comparisons[0].userDecision, decision);
    assert.equal(compared.comparisons[0].eligible, false);
    assert.equal(getClarification(decided), null);
    assert.equal(compared.comparisons[0].classification, decision === 'include' ? 'assumption' : 'held');
  }
});

test('changed model spec and document version invalidate old results including unchanged excerpts', () => {
  const context = execute();
  context.models = copy(context.models);
  context.models[0].version = '2.0';
  const checked = runStage('validate', context);
  assert.equal(checked.needsRepair, true);
  assert.ok(checked.issues.some(issue => issue.code === 'stale_inputs'));
  assert.ok(checked.issues.some(issue => issue.code === 'citation_mismatch'));
  const rerun = execute({ models: context.models });
  assert.equal(rerun.results.validate.needsRepair, false);
  assert.equal(rerun.results.concept.concepts[0].sources.find(ref => ref.type === 'feature').version, '2.0');
});

test('tampered original quote or page is rejected during validation', () => {
  const context = execute();
  context.results.concept.concepts[0].sources[0].page = 999;
  const checked = runStage('validate', context);
  assert.ok(checked.issues.some(issue => issue.code === 'citation_mismatch'));
  const second = execute();
  second.results.structure.needs[0].quotes[0].text = '만들어진 인용';
  assert.ok(runStage('validate', second).issues.some(issue => issue.code === 'quote_mismatch'));
});

test('excluded hardware and proposal text constraints both apply at generation and validation', () => {
  assert.equal(execute({ conditions: { text: '제품 구조 변경 제외' } }).results.concept.concepts.length, 0);
  assert.equal(execute({ conditions: { excludedTerms: ['허용 하중'] } }).results.concept.concepts.length, 0);
  const context = execute();
  context.conditions = { excludedTerms: ['탈착 트레이'] };
  const checked = runStage('validate', context);
  assert.equal(checked.acceptedConcepts.length, 0);
  assert.ok(checked.issues.some(issue => issue.code === 'invalid_concept'));
});

test('sample counts within specified scope and concepts capped at three without padding', () => {
  assert.ok(SAMPLE_MODELS.length >= 3 && SAMPLE_MODELS.length <= 5);
  assert.ok(SAMPLE_REVIEWS.length >= 30 && SAMPLE_REVIEWS.length <= 50);
  const context = execute({ reviews: SAMPLE_REVIEWS, models: SAMPLE_MODELS, request: SAMPLE_REQUEST });
  assert.equal(context.results.concept.concepts.length, 3);
  assert.equal(context.results.validate.needsRepair, false);
  assert.equal(execute({ reviews: [] }).results.concept.concepts.length, 0);
});

test('explicit category conditions change computed output rather than replaying sample outcome', () => {
  const context = execute({ reviews: SAMPLE_REVIEWS, models: SAMPLE_MODELS, conditions: { categories: ['organization_visibility'] } });
  assert.ok(context.results.structure.needs.every(need => need.category === 'organization_visibility'));
  assert.equal(context.results.concept.concepts.length, 1);
  assert.equal(context.results.concept.concepts[0].category, 'organization_visibility');
});

test('normalization retains source version, page and synthetic provenance across repeated normalization', () => {
  const reviews = normalizeReviews([{ 리뷰ID: 'R-5', 모델ID: 'M-A', 원문: '고객 원문', 출처: '원문 파일', 문서버전: 'r3', 페이지: 8, 합성여부: '예' }]);
  assert.deepEqual(normalizeReviews(reviews), reviews);
  assert.equal(reviews[0].version, 'r3');
  assert.equal(reviews[0].page, 8);
  assert.equal(reviews[0].synthetic, true);
  const models = normalizeModels(oneModel());
  assert.deepEqual(normalizeModels(models), models);
});
