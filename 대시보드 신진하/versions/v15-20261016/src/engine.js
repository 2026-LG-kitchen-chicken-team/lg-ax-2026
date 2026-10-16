/**
 * Browser-local, deterministic evidence workflow.
 * Uploaded text is data, never an instruction. No model API or network is used.
 */
export const NODE_DEFS = Object.freeze([
  { id: 'retrieve', label: '자료 조회', skill: 'source_retrieve', agent: '메인 기획자 · 자료 조회 역할', description: '요청과 원문을 읽고 리뷰 ID와 제품 모델을 연결합니다.' },
  { id: 'structure', label: '니즈 구조화', skill: 'needs_structure', agent: '메인 기획자 · 니즈 분석 역할', description: '원문에 나타난 청소·정리·수납 상황을 모델별로 묶습니다.' },
  { id: 'compare', label: '기능 대조', skill: 'feature_compare', agent: '메인 기획자 · 모델 대조 역할', description: '근거가 있는 기존 기능과 여전히 남은 사용 불편을 나눕니다.' },
  { id: 'concept', label: '콘셉트 작성', skill: 'concept_draft', agent: '메인 기획자 · 콘셉트 작성 역할', description: '근거가 충분한 기회에서 최대 세 개의 콘셉트와 요구사항을 만듭니다.' },
  { id: 'validate', label: '검토 및 수정', skill: 'validate_revise', agent: '메인 기획자 · 근거 검토 역할', description: '모델 연결, 원문 인용, 기능 중복, 요구사항 근거를 검사합니다.' },
]);

const asText = value => value == null ? '' : String(value).trim();
const keyOf = value => asText(value).toLowerCase().replace(/[\s_\-.:()\[\]]/g, '');
const list = value => Array.isArray(value) ? value : value == null ? [] : [value];
const unique = values => [...new Set(values)];
const syntheticValue = value => value === true || /^(true|1|yes|y|예|합성|샘플|가상)$/i.test(asText(value));
const ALIASES = {
  id: ['id', 'review_id', 'reviewid', '리뷰id', '리뷰번호', '리뷰식별자', '번호'],
  model: ['model', 'model_id', 'modelid', 'product_id', 'productid', '모델', '모델id', '모델명', '제품', '제품id', '제품모델', '제품식별자', '제품명'],
  text: ['text', 'review', 'review_text', 'content', 'body', 'comment', '원문', '리뷰', '리뷰원문', '리뷰내용', '내용', '불편', '고객리뷰'],
  source: ['source', 'url', 'origin', '출처', '출처url', '원문위치', '자료명'],
  synthetic: ['synthetic', 'is_synthetic', '합성', '합성여부', '샘플여부', '가상'],
  version: ['version', 'documentVersion', 'document_version', 'specVersion', '버전', '문서버전'],
  page: ['page', '페이지', '쪽'],
  location: ['location', 'position', '원문위치', '위치'],
};

function readField(row, aliases) {
  if (!row || typeof row !== 'object') return undefined;
  const entries = Object.entries(row);
  for (const alias of aliases) {
    const found = entries.find(([key]) => keyOf(key) === keyOf(alias));
    if (found && found[1] != null && found[1] !== '') return found[1];
  }
  return undefined;
}

/** RFC-4180 style CSV: BOM, escaped quotes, commas and newlines in quotes. */
export function parseCSV(text) {
  const input = String(text ?? '').replace(/^\uFEFF/, '');
  if (!input.trim()) return [];
  const records = [];
  let record = [], field = '', quoted = false, started = false;
  for (let i = 0; i < input.length; i++) {
    const char = input[i];
    if (quoted) {
      if (char === '"' && input[i + 1] === '"') { field += '"'; i++; }
      else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"' && !started) { quoted = true; started = true; }
    else if (char === ',') { record.push(field); field = ''; started = false; }
    else if (char === '\n' || char === '\r') {
      if (char === '\r' && input[i + 1] === '\n') i++;
      record.push(field);
      if (record.some(cell => cell.trim() !== '')) records.push(record);
      record = []; field = ''; started = false;
    } else { field += char; started = true; }
  }
  if (quoted) throw new Error('CSV의 따옴표가 닫히지 않았습니다. 원문을 확인해 주세요.');
  record.push(field);
  if (record.some(cell => cell.trim() !== '')) records.push(record);
  if (!records.length) return [];
  const headers = records.shift().map((header, i) => asText(header) || `column_${i + 1}`);
  if (new Set(headers.map(keyOf)).size !== headers.length) throw new Error('CSV 열 이름이 중복됩니다. 열 이름을 고유하게 바꿔 주세요.');
  return records.map((cells, rowIndex) => {
    if (cells.length > headers.length) throw new Error(`CSV ${rowIndex + 2}행의 열 수가 머리글보다 많습니다. 쉼표가 있는 원문은 따옴표로 감싸 주세요.`);
    const row = Object.create(null);
    headers.forEach((header, i) => { row[header] = cells[i] ?? ''; });
    return row;
  });
}

export function normalizeReviews(rows) {
  const data = typeof rows === 'string' ? parseCSV(rows) : Array.isArray(rows) ? rows : list(rows?.reviews);
  return data.map((row, i) => ({
    id: asText(readField(row, ALIASES.id)) || `UNIDENTIFIED-REVIEW-${i + 1}`,
    missingId: Boolean(row?.missingId || !asText(readField(row, ALIASES.id))),
    model: asText(readField(row, ALIASES.model)),
    text: asText(readField(row, ALIASES.text)),
    source: asText(readField(row, ALIASES.source)) || `업로드 리뷰 · 행 ${i + 2}`,
    synthetic: syntheticValue(readField(row, ALIASES.synthetic)),
    version: asText(readField(row, ALIASES.version)),
    page: readField(row, ALIASES.page),
    location: asText(readField(row, ALIASES.location)) || `행 ${i + 2}`,
  }));
}

export function normalizeModels(data) {
  let input = data;
  if (typeof input === 'string') {
    try { input = JSON.parse(input); }
    catch { throw new Error('제품 명세는 모델과 기능 근거가 있는 JSON 형식이어야 합니다.'); }
  }
  const models = Array.isArray(input) ? input : Array.isArray(input?.models) ? input.models : input && typeof input === 'object' ? [input] : [];
  return models.map((row, i) => {
    const rawId = asText(readField(row, ['id', 'model_id', 'modelid', '모델id', '제품id', '모델', 'model']));
    const id = rawId || `UNIDENTIFIED-MODEL-${i + 1}`;
    const source = asText(readField(row, ALIASES.source)) || '업로드 제품 명세';
    const raw = readField(row, ['features', '기능', '기능목록', '명세', 'specifications']);
    const features = (typeof raw === 'string' ? raw.split(/[;\n]/).filter(Boolean) : list(raw)).map((feature, index) => {
      const plain = typeof feature === 'string';
      const name = plain ? asText(feature) : asText(readField(feature, ['name', 'feature', 'title', '기능', '기능명', '이름']));
      const evidence = plain ? asText(feature) : asText(readField(feature, ['evidence', 'excerpt', 'quote', 'text', '원문', '근거', '인용', '설명']));
      const page = plain ? undefined : readField(feature, ['page', '페이지', '쪽']);
      const featureSource = plain ? '' : asText(readField(feature, ALIASES.source));
      const version = plain ? '' : asText(readField(feature, ALIASES.version));
      const condition = plain ? '' : asText(readField(feature, ['condition', 'conditions', 'usage', '사용조건', '조건']));
      const location = plain ? '' : asText(readField(feature, ALIASES.location));
      return { id: plain ? `${id}:F${index + 1}` : asText(feature.id) || `${id}:F${index + 1}`, name, evidence, condition, version: version || asText(readField(row, ALIASES.version)), ...(location ? { location } : {}), ...(featureSource ? { source: featureSource } : {}), ...(page != null && page !== '' ? { page } : {}) };
    });
    return {
      id,
      missingId: Boolean(row?.missingId || !rawId),
      name: asText(readField(row, ['name', 'model_name', 'modelname', '제품명', '모델명', '이름'])) || id,
      features,
      source,
      synthetic: syntheticValue(readField(row, ALIASES.synthetic)),
      version: asText(readField(row, ALIASES.version)),
    };
  });
}

export function validateData(reviews, models) {
  const issues = [];
  const add = (code, severity, message) => issues.push({ code, severity, message });
  if (!reviews.length) add('empty_reviews', 'error', '분석할 리뷰가 없습니다.');
  if (!models.length) add('empty_models', 'error', '대조할 제품 모델이 없습니다.');
  for (const [kind, rows] of [['리뷰', reviews], ['모델', models]]) {
    const seen = new Set();
    for (const row of rows) {
      if (seen.has(keyOf(row.id))) add('duplicate_id', 'error', `${kind} ID ${row.id}가 중복됩니다.`);
      seen.add(keyOf(row.id));
    }
  }
  for (const review of reviews) {
    if (review.missingId) add('missing_review_id', 'warning', `${review.id}: 원본 리뷰 ID가 없어 분석을 보류합니다. 이 표시는 원본 ID를 대신하지 않습니다.`);
    if (!review.text) add('empty_text', 'warning', `${review.id}: 리뷰 원문이 비어 있어 니즈 추출에서 제외합니다.`);
    if (!review.model) add('missing_model', 'warning', `${review.id}: 모델 식별자가 없어 연결을 보류합니다.`);
    else if (!lookupModel(review, models)) add('unknown_model', 'warning', `${review.id}: ${review.model}와 정확히 일치하는 모델 명세가 없습니다.`);
  }
  for (const model of models) {
    if (model.missingId) add('missing_model_id', 'warning', `${model.id}: 원본 모델 ID가 없어 리뷰 연결을 보류합니다.`);
    if (!model.version) add('missing_document_version', 'warning', `${model.id}: 문서 버전이 지정되지 않았습니다. 현재 원문 스냅샷으로 대조하고 실제 연결 전 버전을 확인합니다.`);
    for (const feature of model.features) {
      if (!feature.name || !feature.evidence) add('missing_evidence', 'warning', `${model.id} / ${feature.name || '이름 없는 기능'}: 기능 원문 근거가 없어 판단에 사용하지 않습니다.`);
    }
  }
  const featureIds = models.flatMap(model => model.features.map(feature => feature.id));
  if (unique(featureIds.map(keyOf)).length !== featureIds.length) add('duplicate_feature_id', 'error', '제품 기능의 근거 ID가 중복됩니다. 모델별로 고유한 ID를 사용해 주세요.');
  return { valid: !issues.some(issue => issue.severity === 'error'), issues };
}

function sourceForReview(review) {
  return { id: review.id, type: 'review', label: `${review.id} · ${review.model}`, model: review.model, modelId: review.model, text: review.text, excerpt: review.text, source: review.source, location: review.location || review.source, page: review.page, version: review.version || '', synthetic: review.synthetic };
}
function sourceForFeature(model, feature) {
  return { id: feature.id, type: 'feature', label: `${model.id} · ${feature.name}`, model: model.id, modelId: model.id, text: feature.evidence, excerpt: feature.evidence, condition: feature.condition || '', source: feature.source || model.source, location: feature.location || feature.source || model.source, page: feature.page, version: feature.version || model.version || '', synthetic: model.synthetic };
}
function common(summary, activity, extra = {}) {
  return { summary, activity, items: [], sources: [], warnings: [], assumptions: [], ...extra };
}
function lookupModel(review, models) {
  const exact = models.filter(model => keyOf(model.id) === keyOf(review.model));
  if (exact.length === 1) return exact[0];
  const byName = models.filter(model => keyOf(model.name) === keyOf(review.model));
  return byName.length === 1 ? byName[0] : null;
}
export function source_retrieve(context) {
  const reviews = normalizeReviews(context.reviews || []), models = normalizeModels(context.models || []);
  const validation = validateData(reviews, models);
  const matchedReviews = [], unresolvedReviews = [];
  for (const review of reviews) {
    const model = lookupModel(review, models);
    if (model && !model.missingId && !review.missingId && review.text && validation.valid) matchedReviews.push({ ...review, model: model.id });
    else unresolvedReviews.push({ ...review, reason: !validation.valid ? '입력 ID 또는 자료 구성을 먼저 수정해야 합니다.' : review.missingId ? '원본 리뷰 ID 없음 · 임시 행 표시는 근거 ID로 사용하지 않음' : !review.text ? '리뷰 원문 없음' : model?.missingId ? '원본 모델 ID 없음' : '정확히 일치하는 모델 ID·이름 없음' });
  }
  const sources = [...matchedReviews.map(sourceForReview), ...models.flatMap(model => model.features.filter(f => f.name && f.evidence).map(feature => sourceForFeature(model, feature)))];
  return common(`리뷰 ${reviews.length}개와 제품 ${models.length}개를 조회하고, ${matchedReviews.length}개 리뷰를 모델에 연결했습니다.`, '리뷰 원문과 제품 명세의 ID·출처를 연결했습니다.', {
    reviews, models, matchedReviews, unresolvedReviews, sources, validation, inputSignature: inputSignature(context),
    request: asText(context.request),
    plan: ['제품군·목표 고객·기획 조건 확인', '같은 모델의 리뷰와 기능 근거 연결', '불편 묶기 → 기존 기능 대조 → 후보 생성 → 근거 검사'],
    items: models.map(model => ({ title: model.name, detail: `${model.id} · 연결 리뷰 ${matchedReviews.filter(review => review.model === model.id).length}개 · 기능 근거 ${model.features.filter(feature => feature.evidence).length}개`, modelId: model.id })),
    warnings: [...validation.issues.map(issue => issue.message), ...unresolvedReviews.filter(review => review.text).map(review => `${review.id}: ${review.reason}. 다른 모델의 명세로 대신 판단하지 않습니다.`)],
    assumptions: [asText(context.request) ? `기획 요청: ${asText(context.request)}` : '기획 요청이 비어 있어 입력된 리뷰의 사용 상황을 기준으로 분석합니다.', '분석은 브라우저에서 실행하는 키워드·근거 검사 규칙입니다. LLM 의미 해석이나 외부 자료 조회는 연결되어 있지 않습니다.', ...(reviews.some(review => review.synthetic) || models.some(model => model.synthetic) ? ['합성 자료는 흐름 검증용이며 빈도를 시장 수요 비율로 해석하지 않습니다.'] : [])],
  });
}

/** Deterministic snapshot used to reject results from an older document version. */
export function inputSignature(context = {}) {
  return JSON.stringify({ reviews: normalizeReviews(context.reviews || []), models: normalizeModels(context.models || []) });
}

const NEED_RULES = [
  { category: 'cleaning_transport', label: '청소할 때 식품 이동 부담', test: text => /청소|세척|닦|흘|국물|얼룩/.test(text) && /모두|전부|다 꺼|다꺼|꺼내|옮겨|이동|비워|비우|무겁|쏟/.test(text), pain: '일부 오염을 청소하기 위해 식품을 꺼내거나 옮기는 부담', situation: '식품이 들어 있는 상태에서 선반 일부를 청소할 때', feature: /분리|탈착|탈부착|세척|청소|트레이/ },
  { category: 'cleaning_guidance', label: '선반 탈착 방법이 어려움', test: text => /분리|탈착|뺄|빼|끼우/.test(text) && /모르|몰라|방법|어떻게|헤매|설명|안내|요령/.test(text), pain: '선반의 탈착·청소 방법을 이해하거나 찾기 어려움', situation: '선반을 분리하거나 청소 절차를 확인할 때', feature: /분리|탈착|탈부착/ },
  { category: 'organization_visibility', label: '식재료 찾기·보관 관리', test: text => /안 보|안보|보이지|못 찾|못찾|찾기|찾느|뒤쪽|깊숙|기한|잊|까먹|깜빡|중복|정리/.test(text) && !/설명서|탈착.*방법/.test(text), pain: '보관 위치나 사용 시점을 놓쳐 식재료 확인·정리에 어려움', situation: '보관한 식재료를 찾고 사용할 순서를 정할 때', feature: /투명|내부.*확인|내부.*카메라|카메라|보기|재고|보관.*목록|확인.*창/ },
  { category: 'storage_flex', label: '큰 용기·다양한 크기 수납', test: text => /높|큰|냄비|병|용기|밀폐통|수납|공간|끼워|자리/.test(text) && !/청소|세척|닦|얼룩|탈착.*방법/.test(text), pain: '용기의 크기와 선반 간격을 맞추고 배치하기 어려움', situation: '큰 용기나 크기가 다른 식품을 함께 수납할 때', feature: /높이|조절|접이|가변|접는|폴딩|수납.*배치/ },
  { category: 'cleaning_unspecified', label: '청소 불편의 조건 확인', test: text => /청소|세척|닦|오염|얼룩/.test(text), pain: '청소가 어렵다는 표현만으로는 구체적인 원인·상황이 부족함', situation: '청소 불편의 실제 원인을 확인해야 하는 상황', feature: /분리|탈착|선반|트레이/ },
];

const PAIN_PATTERN = /불편|어렵|어려|힘들|번거|모르|몰라|헷갈|헤매|문제|안\s*되|부족|좁|못|안\s*보|잊|까먹|깜빡|놓쳐|필요|미루|쏟|고민|전부|모두|비워|비우|이동|옮겨|옮기|다\s*꺼|시간이\s*걸|여러\s*번|안\s*나|되지\s*않|쉽지|불가|안내가\s*없|없어서/;
const POSITIVE_PATTERN = /편리|편해|편하|편한|쉽고|쉬워|쉽게|좋|만족|잘\s*보|잘\s*찾|문제\s*없|어렵지\s*않|불편하지\s*않|수납이\s*잘/;
function classifyReview(text) {
  // Keep the complete original quote; use sentiment only as a conservative gate.
  const clauses = text.split(/(?<=[.!?。\n])|하지만|그런데|반면|다만|지만|(?<=편한데)|(?<=좋은데)|(?<=좋지만)/).map(asText).filter(Boolean);
  const pain = clauses.filter(clause => PAIN_PATTERN.test(clause.replace(/어렵지\s*않\S*|불편하지\s*않\S*|문제\s*없\S*/g, '')));
  const positive = clauses.filter(clause => POSITIVE_PATTERN.test(clause));
  if (!positive.length && POSITIVE_PATTERN.test(text)) positive.push(text);
  return { sentiment: pain.length ? positive.length ? 'mixed' : 'pain' : positive.length ? 'positive' : 'unclassified', painText: pain.join(' '), positiveText: positive.join(' ') };
}

function inputResult(context) { return context.results?.retrieve || source_retrieve(context); }
export function needs_structure(context) {
  const data = inputResult(context), buckets = new Map();
  const unclassifiedReviews = [], outOfScopeReviews = [], positiveReviews = [], mixedReviews = [];
  const requestedCategories = Array.isArray(context.conditions?.categories) ? unique(context.conditions.categories.map(asText).filter(Boolean)) : [];
  const validCategoryIds = ['cleaning_transport', 'cleaning_guidance', 'organization_visibility', 'storage_flex'];
  const categories = requestedCategories.length ? requestedCategories.filter(category => validCategoryIds.includes(category)) : null;
  const invalidCategories = requestedCategories.filter(category => !validCategoryIds.includes(category));
  for (const review of data.matchedReviews) {
    const sentiment = classifyReview(review.text);
    if (sentiment.sentiment === 'positive') { positiveReviews.push({ ...review, reason: '긍정 경험이며 구체적인 잔여 불편을 찾지 못했습니다.' }); continue; }
    if (sentiment.sentiment === 'mixed') mixedReviews.push({ ...review, ...sentiment });
    const matched = sentiment.painText ? NEED_RULES.filter(rule => rule.test(review.text)) : [];
    const applicable = matched.filter(rule => rule.category !== 'cleaning_unspecified' || matched.length === 1);
    const selected = categories ? applicable.filter(rule => categories.includes(rule.category)) : applicable;
    if (!selected.length) {
      if (applicable.length && categories) outOfScopeReviews.push(review);
      else unclassifiedReviews.push(review);
      continue;
    }
    for (const rule of selected) {
      const key = `${review.model}|${rule.category}`;
      if (!buckets.has(key)) buckets.set(key, { rule, modelId: review.model, reviews: [] });
      buckets.get(key).reviews.push(review);
    }
  }
  const needs = [...buckets.values()].map(({ rule, modelId, reviews }) => ({
    id: `N-${modelId}-${rule.category}`, modelId, modelName: data.models.find(model => model.id === modelId)?.name || modelId,
    category: rule.category, label: rule.label, title: rule.label, pain: rule.pain, situation: rule.situation,
    count: reviews.length, reviewIds: reviews.map(review => review.id),
    quotes: reviews.map(review => ({ reviewId: review.id, text: review.text, source: review.source, synthetic: review.synthetic })),
    method: '한국어 키워드 규칙으로 묶음 · 원문 확인 필요',
  }));
  const categoryLabels = categories?.map(category => NEED_RULES.find(rule => rule.category === category).label) || [];
  const scopeSummary = categories ? ` 선택 범위: ${categoryLabels.join(' · ') || '유효한 범주 없음'}. 범위 밖 리뷰 ${outOfScopeReviews.length}개를 제외했습니다.` : '';
  return common(`${data.models.length}개 모델에서 ${needs.length}개의 불편 묶음을 만들었습니다.${scopeSummary}`, '원문에 나타난 사용 상황을 모델별로 묶고 인용을 연결했습니다.', {
    needs, unclassifiedReviews, outOfScopeReviews, positiveReviews, mixedReviews, categoryFilter: categories, invalidCategories,
    items: needs.map(need => ({ title: `${need.modelId} · ${need.label}`, detail: `${need.count}개 원문 · ${need.situation}`, id: need.id })),
    sources: data.sources.filter(source => source.type === 'review' && needs.some(need => need.reviewIds.includes(source.id))),
    warnings: [...(data.unresolvedReviews.length ? [`모델 미연결·빈 원문 ${data.unresolvedReviews.length}개는 불편 묶기에서 보류했습니다.`] : []), ...(unclassifiedReviews.length ? [`${unclassifiedReviews.length}개 리뷰는 현재 키워드 규칙에 해당하지 않습니다. 원문을 검토하고 분류 규칙을 확장해야 합니다.`] : []), ...(positiveReviews.length ? [`긍정 경험 ${positiveReviews.length}개를 불편 묶음에서 제외했습니다. 혼합 리뷰의 불편은 유지합니다.`] : []), ...(invalidCategories.length ? [`지원하지 않는 사용 상황 범주 ${invalidCategories.join(', ')}는 적용하지 않았습니다.`] : [])],
    assumptions: ['같은 표현을 자동으로 같은 원인으로 단정하지 않습니다. 묶음은 기획자가 원문으로 확인할 초안입니다.', ...(categories ? [`기획 조건의 명시적 categories 필터를 적용했습니다: ${categoryLabels.join(' · ') || '유효한 범주 없음'}. 다른 사용 상황은 이번 콘셉트 범위에서 제외합니다.`] : [])],
  });
}

function getStructure(context) { return context.results?.structure || needs_structure(context); }

function questionForNeed(need, data) {
  return {
    id: `clarify-${need.id}`, stage: 'compare', needId: need.id,
    text: `${need.modelId}의 “${need.label}”은 구체적인 원인이 부족합니다. 선반 탈착, 식품 이동, 오염 위치 등 실제 어려운 지점을 확인할 수 있나요? 확인 전 가정으로 기록할지 이번 기획에서 보류할지 선택해 주세요.`,
    evidence: data.sources.filter(source => need.reviewIds.includes(source.id)),
  };
}

/** The UI owns waiting/resuming; this pure helper never invents a user decision. */
export function getClarification(context = {}) {
  const data = inputResult(context), grouped = getStructure(context);
  const need = grouped.needs.find(entry => entry.category === 'cleaning_unspecified' && !['include', 'hold'].includes(context.decisions?.[`clarify-${entry.id}`]));
  return need ? questionForNeed(need, data) : null;
}
function conceptTemplate(need, features) {
  const reviews = need.quotes.map(quote => quote.text).join(' ');
  const base = { needId: need.id, modelId: need.modelId, reviewIds: [...need.reviewIds], featureIds: features.map(feature => feature.id), residual: need.pain };
  if (need.category === 'cleaning_transport') return {
    ...base, title: '구획별 탈착 트레이', kind: '제품 구조',
    mechanism: '내용물을 담은 채 오염된 구획의 트레이만 꺼내 세척하는 구조를 검토합니다.',
    differentiation: '기존 선반의 분리 가능 여부와 식품을 전부 옮겨야 하는 청소 부담을 구분합니다.',
    requirements: ['선반 전체 식품을 옮기지 않고 오염된 구획만 분리하는 사용 흐름을 설계한다.', '대상 모델의 기존 선반과 결합 방식·간섭을 검토한다.', '수납 용량, 허용 하중, 탈착 편의, 누수와 세척성은 실물 검증 항목으로 남긴다.'],
    duplicatePattern: /구획.*(탈착|분리).*트레이|칸별.*트레이|부분.*탈착.*트레이/,
  };
  if (need.category === 'cleaning_guidance') return {
    ...base, title: '상황별 선반 탈착 안내', kind: '안내 서비스',
    mechanism: '모델을 선택하고 탈착의 어려운 지점을 고르면 해당 명세 원문과 확인된 절차로 안내하는 서비스를 검토합니다.',
    differentiation: '분리 기능을 다시 제안하지 않고, 기능 인지와 사용 과정의 어려움을 대상으로 합니다.',
    requirements: ['모델 ID와 설명서의 근거 위치를 각 안내 화면에 연결한다.', '탈착 방법의 어려움과 식품 이동 부담을 별도 질문으로 구분한다.', '문서에 없는 조작 절차는 생성하지 않고 추가 확인 대상으로 표시한다.'],
    duplicatePattern: /상황별.*탈착.*안내|맞춤.*탈착.*안내/,
  };
  if (need.category === 'organization_visibility') return {
    ...base, title: '보관 위치·사용 순서 가이드', kind: '안내 서비스',
    mechanism: '사용자가 지정한 보관 구획과 식재료를 연결해 위치 확인과 사용 순서 결정을 돕는 서비스를 검토합니다.',
    differentiation: '기존 내부 확인 기능이 있어도 위치를 잊거나 식재료를 놓치는 불편은 별도로 검토합니다.',
    requirements: ['사용자가 식재료와 보관 구획을 등록·수정할 수 있어야 한다.', /기한|잊|까먹|깜빡/.test(reviews) ? '보관 날짜와 사용자 입력 소비기한을 바탕으로 확인할 식재료를 안내한다.' : '보관 구획별 찾기 안내를 제공하고 실제 탐색 시간을 검증한다.', '자동 인식 정확도나 식품 안전을 보장하지 않으며 사용자가 기록을 확인하도록 한다.'],
    duplicatePattern: /보관.*위치.*(가이드|안내)|식재료.*위치.*(가이드|안내)|사용.*순서.*가이드/,
  };
  if (need.category === 'storage_flex') return {
    ...base, title: '용기 조건별 수납 배치 도우미', kind: '안내 서비스',
    mechanism: '용기 크기와 모델의 확인된 선반 조절 조건을 받아 배치 순서와 확인할 간섭을 안내하는 서비스를 검토합니다.',
    differentiation: '높이 조절 선반을 다시 제안하지 않고, 실제 용기를 맞추는 배치 과정에 집중합니다.',
    requirements: ['사용자가 용기의 높이·너비·수량을 입력할 수 있어야 한다.', '모델 명세에서 확인된 조절 기능만 배치 안내에 사용한다.', '치수 근거가 없는 조합은 적합하다고 단정하지 않고 실제 간섭 확인을 요청한다.'],
    duplicatePattern: /용기.*(수납|배치).*(도우미|가이드)|수납.*배치.*(도우미|가이드)/,
  };
  return null;
}

export function feature_compare(context) {
  const data = inputResult(context), grouped = getStructure(context);
  const comparisons = [], excludedCandidates = [], withheld = [];
  for (const need of grouped.needs) {
    const model = data.models.find(entry => entry.id === need.modelId);
    const rule = NEED_RULES.find(entry => entry.category === need.category);
    const relevant = (model?.features || []).filter(feature => feature.name && feature.evidence && rule?.feature.test(`${feature.name} ${feature.evidence}`));
    const template = conceptTemplate(need, relevant);
    const duplicate = template && relevant.some(feature => template.duplicatePattern.test(`${feature.name} ${feature.evidence}`));
    const sufficient = relevant.length > 0 && need.category !== 'cleaning_unspecified';
    const userDecision = need.category === 'cleaning_unspecified' ? context.decisions?.[`clarify-${need.id}`] || null : null;
    const status = userDecision === 'hold' ? '기획자 보류' : userDecision === 'include' ? '가정 포함 · 확인 필요' : duplicate ? '기존 기능 중복' : sufficient ? '잔여 불편' : '확인 필요';
    const reason = userDecision === 'hold' ? '기획자가 구체적 원인 확인 전 보류하기로 선택했습니다. 근거·결정 기록을 유지합니다.' : userDecision === 'include' ? '기획자가 원인이 미확인된 불편을 가정으로 포함했습니다. 기능 부재 또는 설계 요구로 확정하지 않으며 추가 확인 전 콘셉트는 보류합니다.' : duplicate ? '동일한 작동 방식이 제품 기능 근거에 이미 있습니다. 차별점 없는 재제안은 제외하고 실제 어려운 지점을 추가 확인합니다.' : sufficient ? '기존 기능이 확인되지만 원문에 남은 사용 과정의 불편이 있습니다.' : relevant.length ? '불편의 실제 상황·원인이 부족해 개선 방향을 보류합니다.' : '관련 기능의 원문 근거를 찾지 못했습니다. 기능이 없다고 단정하지 않고 자료 확인을 요청합니다.';
    const comparison = {
      id: `CMP-${need.id}`, needId: need.id, modelId: need.modelId, label: need.label, title: `${need.modelId} · ${need.label}`,
      status, userDecision, classification: userDecision === 'hold' ? 'held' : userDecision === 'include' ? 'assumption' : duplicate ? 'duplicate' : sufficient ? 'residual' : 'unknown', existing: relevant.length ? relevant.map(feature => feature.name).join(' · ') : '관련 기능 확인 필요',
      existingFeatures: relevant, residual: need.pain, reason, reviewIds: [...need.reviewIds], featureIds: relevant.map(feature => feature.id), eligible: Boolean(sufficient && !duplicate),
      model: need.modelId, need: need.label, existingFeature: relevant.length ? relevant.map(feature => feature.name).join(' · ') : '관련 기능 확인 필요', remainingPain: need.pain,
      sources: data.sources.filter(source => [...need.reviewIds, ...relevant.map(feature => feature.id)].includes(source.id)),
    };
    comparisons.push(comparison);
    if (duplicate) excludedCandidates.push({ title: template.title, modelId: need.modelId, needId: need.id, reason, featureIds: comparison.featureIds });
    if (!sufficient || duplicate) withheld.push({ title: `${need.modelId} · ${need.label}`, needId: need.id, modelId: need.modelId, reason });
    const oldFeature = relevant.find(feature => /분리|탈착|높이.*조절/.test(feature.name));
    if (oldFeature && !duplicate) excludedCandidates.push({ title: `${oldFeature.name}을 신규 기능으로 재제안`, modelId: need.modelId, needId: need.id, reason: `${oldFeature.id}의 원문에 기존 기능으로 명시되어 있어 차별점 없는 후보를 제외합니다.`, featureIds: [oldFeature.id] });
  }
  return common(`${comparisons.length}개 불편을 대조해 ${comparisons.filter(row => row.eligible).length}개 기회와 ${withheld.length}개 보류 항목을 나눴습니다.`, '같은 모델의 기능 원문과 리뷰를 대조하고 기존 기능 중복을 걸러냈습니다.', {
    comparisons, excludedCandidates, withheld,
    clarificationQuestions: grouped.needs.filter(need => need.category === 'cleaning_unspecified').map(need => ({ ...questionForNeed(need, data), decision: context.decisions?.[`clarify-${need.id}`] || null })),
    items: comparisons.map(row => ({ title: row.title, detail: `${row.status} · 기존: ${row.existing} · 남은 불편: ${row.residual}`, id: row.id })),
    sources: data.sources.filter(source => comparisons.some(row => [...row.reviewIds, ...row.featureIds].includes(source.id))),
    warnings: withheld.map(item => `${item.title}: ${item.reason}`),
    assumptions: ['설명서의 언급이 없다는 이유만으로 기능이 없다고 단정하지 않습니다.', '기능이 있다는 사실과 고객의 불편이 해결됐다는 판단은 따로 검토합니다.', ...comparisons.filter(row => row.userDecision === 'include').map(row => `${row.needId}: 사용자가 원인 미확인 불편을 가정으로 포함했습니다. 추가 확인 전 설계·효과를 확정하지 않습니다.`)],
  });
}

function exclusions(context) {
  const value = context.conditions;
  const terms = typeof value === 'object' && value ? list(value.excludedTerms ?? value.exclude ?? value.exclusions).map(asText).filter(Boolean) : [];
  const text = [context.request, typeof value === 'string' ? value : value?.text || '', ...terms].map(asText).join(' ');
  return { terms, hardwareExcluded: /서비스만|서비스\s*중심|(?:구조|하드웨어|실기기)[^\n]{0,18}(?:제외|금지)|(?:제외|금지)[^\n]{0,18}(?:구조|하드웨어)/.test(text) };
}
export function concept_draft(context) {
  const data = inputResult(context), grouped = getStructure(context), compared = context.results?.compare || feature_compare(context);
  const constraints = exclusions(context), candidates = [], withheld = [...compared.withheld];
  const priority = { cleaning_transport: 0, organization_visibility: 1, storage_flex: 2, cleaning_guidance: 3 };
  const sorted = compared.comparisons.filter(row => row.eligible).sort((a, b) => (priority[grouped.needs.find(need => need.id === a.needId)?.category] ?? 9) - (priority[grouped.needs.find(need => need.id === b.needId)?.category] ?? 9));
  const usedTypes = new Set();
  for (const comparison of sorted) {
    const need = grouped.needs.find(entry => entry.id === comparison.needId);
    if (!need) continue;
    const template = conceptTemplate(need, comparison.existingFeatures);
    if (!template) continue;
    const proposalText = [template.title, template.kind, template.mechanism, template.differentiation, ...template.requirements].join(' ').toLocaleLowerCase();
    const forbidden = constraints.terms.find(term => proposalText.includes(term.toLocaleLowerCase()));
    if ((constraints.hardwareExcluded && template.kind === '제품 구조') || forbidden) {
      withheld.push({ title: template.title, modelId: need.modelId, needId: need.id, reason: forbidden ? `기획 제외 조건 "${forbidden}"에 해당합니다.` : '기획 조건에서 제품 구조 변경을 제외했습니다.' });
      continue;
    }
    if (usedTypes.has(need.category)) {
      const prior = candidates.find(candidate => candidate.category === need.category);
      prior.additionalModelIds.push(need.modelId);
      prior.relatedNeeds.push(need.id);
      continue;
    }
    if (candidates.length >= 3) {
      withheld.push({ title: template.title, modelId: need.modelId, needId: need.id, reason: '기획 결과는 최대 3개입니다. 추가 기회는 후속 검토로 남겼습니다.' });
      continue;
    }
    usedTypes.add(need.category);
    const { duplicatePattern, ...details } = template;
    const id = `C-${String(candidates.length + 1).padStart(2, '0')}`;
    candidates.push({
      ...details, id, category: need.category, model: need.modelId, label: template.title, description: template.mechanism, evidence: need.quotes.slice(0, 3), additionalModelIds: [], relatedNeeds: [need.id],
      sources: data.sources.filter(source => [...need.reviewIds, ...template.featureIds].includes(source.id)),
      requirements: [...template.requirements],
      requirementEvidence: template.requirements.map((text, i) => ({ id: `${id}:REQ${i + 1}`, text, reviewIds: [...need.reviewIds], featureIds: [...template.featureIds], type: i === 2 ? '검증 조건' : '기획 요구사항' })),
      assumptions: ['사용 편의·제조 가능성·치수 적합성은 아직 검증하지 않았습니다.', '대표 모델의 원문을 기준으로 작성했으며 다른 모델에는 별도 대조가 필요합니다.'],
    });
  }
  return common(`근거가 연결된 콘셉트 ${candidates.length}개를 작성했습니다.${candidates.length ? '' : ' 근거가 부족한 후보는 보류했습니다.'}`, '잔여 불편에서 콘셉트·동작 방식·요구사항과 검증할 가정을 작성했습니다.', {
    concepts: candidates, withheld, excludedCandidates: compared.excludedCandidates,
    items: candidates.map(candidate => ({ title: candidate.title, detail: `${candidate.modelId} · ${candidate.kind} · 요구사항 ${candidate.requirements.length}개`, id: candidate.id })),
    sources: data.sources.filter(source => candidates.some(candidate => [...candidate.reviewIds, ...candidate.featureIds].includes(source.id))),
    warnings: withheld.map(item => `${item.title}: ${item.reason}`),
    assumptions: ['최대 3개는 우선순위 상한이며 억지로 3개를 채우지 않습니다.', '요구사항은 제안·검증 조건입니다. 물리 성능이나 시장 수요가 확인됐다는 의미가 아닙니다.'],
  });
}

export function validate_revise(context) {
  // Validation always rebuilds authoritative records, including document versions.
  const data = source_retrieve(context), grouped = getStructure(context);
  const compared = context.results?.compare || feature_compare(context), created = context.results?.concept || concept_draft(context);
  const checks = [], issues = [], rejectedConcepts = [], acceptedConcepts = [];
  const reviewMap = new Map(data.matchedReviews.map(review => [review.id, review]));
  const modelMap = new Map(data.models.map(model => [model.id, model]));
  const featureMap = new Map(data.models.flatMap(model => model.features.map(feature => [feature.id, { ...feature, modelId: model.id }])));
  // Rebuild authoritative citation values from records, rather than trust result citations.
  const sourceMap = new Map([
    ...data.matchedReviews.map(sourceForReview),
    ...data.models.flatMap(model => model.features.filter(feature => feature.name && feature.evidence).map(feature => sourceForFeature(model, feature))),
  ].map(source => [source.id, source]));
  const addCheck = (id, label, passed, detail, warning = false) => checks.push({ id, label, passed, status: passed ? warning ? '주의' : '통과' : '실패', detail });
  const staleInput = context.results?.retrieve?.inputSignature && context.results.retrieve.inputSignature !== data.inputSignature;
  if (staleInput) issues.push({ code: 'stale_inputs', severity: 'error', message: '자료·모델 명세 또는 문서 버전이 바뀌었습니다. 자료 조회부터 다시 실행해야 합니다.', repairStage: 'retrieve' });
  addCheck('document_version', '자료·문서 버전 검사', !staleInput, staleInput ? '이전 실행의 근거를 새 문서와 혼용할 수 없습니다.' : '현재 입력 자료와 근거 스냅샷의 버전을 확인했습니다.');
  for (const issue of data.validation.issues.filter(issue => issue.severity === 'error')) issues.push({ ...issue, repairStage: 'retrieve' });
  addCheck('input_ids', '입력 ID·자료 구성', data.validation.valid, data.validation.valid ? '리뷰·모델 ID가 고유하고 필수 자료가 있습니다.' : '입력 자료의 오류를 먼저 수정해야 합니다.');
  const badNeeds = grouped.needs.filter(need => !modelMap.has(need.modelId) || need.reviewIds.some(id => !reviewMap.has(id) || reviewMap.get(id).model !== need.modelId));
  if (badNeeds.length) issues.push({ code: 'model_mismatch', severity: 'error', message: '불편과 다른 모델의 리뷰가 연결되었습니다.', repairStage: 'structure' });
  addCheck('model_link', '모델 혼동 검사', !badNeeds.length, badNeeds.length ? `${badNeeds.length}개 불편의 모델 연결을 수정해야 합니다.` : `${grouped.needs.length}개 불편을 같은 모델의 리뷰에 연결했습니다.`);
  const badQuotes = grouped.needs.flatMap(need => need.quotes || []).filter(quote => !reviewMap.has(quote.reviewId) || reviewMap.get(quote.reviewId).text !== quote.text);
  if (badQuotes.length) issues.push({ code: 'quote_mismatch', severity: 'error', message: '인용이 원문과 일치하지 않거나 리뷰 ID가 없습니다.', repairStage: 'structure' });
  addCheck('raw_quotes', '원문 인용 검사', !badQuotes.length, badQuotes.length ? `${badQuotes.length}개 인용을 원문과 다시 연결해야 합니다.` : '인용문이 입력 원문과 정확히 일치합니다.');
  const allCitations = [...(compared.sources || []), ...(created.sources || []), ...compared.comparisons.flatMap(row => row.sources || []), ...created.concepts.flatMap(candidate => candidate.sources || [])];
  const badCitations = allCitations.filter(source => {
    const original = sourceMap.get(source.id);
    return !original || original.text !== source.text || original.model !== source.model || original.source !== source.source || original.page !== source.page || original.version !== source.version || original.location !== source.location || original.condition !== source.condition || original.synthetic !== source.synthetic;
  });
  if (badCitations.length) issues.push({ code: 'citation_mismatch', severity: 'error', message: '화면에 표시할 근거 원문·출처·페이지가 입력 자료와 일치하지 않습니다.', repairStage: 'compare' });
  addCheck('citation_locations', '출처·페이지 연결 검사', !badCitations.length, badCitations.length ? `${badCitations.length}개 인용 위치를 입력 자료와 다시 연결해야 합니다.` : '표시할 근거의 원문·출처·페이지가 입력 자료와 일치합니다.');
  const badCompare = compared.comparisons.filter(row => row.featureIds.some(id => !featureMap.has(id) || !featureMap.get(id).evidence || featureMap.get(id).modelId !== row.modelId));
  if (badCompare.length) issues.push({ code: 'feature_mismatch', severity: 'error', message: '기능 대조에 근거 누락 또는 다른 모델의 기능이 있습니다.', repairStage: 'compare' });
  addCheck('feature_evidence', '제품 기능 근거 검사', !badCompare.length, badCompare.length ? `${badCompare.length}개 대조의 기능 근거를 수정해야 합니다.` : '사용한 기능에 같은 모델의 원문 근거가 있습니다.');
  if (created.concepts.length > 3) issues.push({ code: 'concept_limit', severity: 'error', message: '콘셉트가 최대 3개를 초과했습니다.', repairStage: 'concept' });
  for (const candidate of created.concepts) {
    const reasons = [], model = modelMap.get(candidate.modelId), need = grouped.needs.find(entry => entry.id === candidate.needId);
    if (!model || !need || need.modelId !== candidate.modelId) reasons.push('대표 모델·불편 ID 연결 오류');
    if (!candidate.reviewIds?.length || candidate.reviewIds.some(id => !reviewMap.has(id) || reviewMap.get(id).model !== candidate.modelId)) reasons.push('리뷰 인용 누락 또는 모델 혼동');
    if (!candidate.featureIds?.length || candidate.featureIds.some(id => !featureMap.has(id) || !featureMap.get(id).evidence || featureMap.get(id).modelId !== candidate.modelId)) reasons.push('제품 기능 근거 누락 또는 모델 혼동');
    if (!candidate.sources?.length || [...(candidate.reviewIds || []), ...(candidate.featureIds || [])].some(id => !candidate.sources.some(source => source.id === id))) reasons.push('표시할 원문 근거 누락');
    if (candidate.sources?.some(source => {
      const original = sourceMap.get(source.id);
      return !original || ['text', 'model', 'source', 'page', 'version', 'location', 'condition', 'synthetic'].some(key => source[key] !== original[key]);
    })) reasons.push('콘셉트 원문·버전·위치 불일치');
    if (!candidate.evidence?.length || candidate.evidence.some(quote => !reviewMap.has(quote.reviewId) || reviewMap.get(quote.reviewId).text !== quote.text)) reasons.push('콘셉트 리뷰 인용 누락 또는 원문 불일치');
    if (!candidate.requirements?.length || candidate.requirements.some(text => !asText(text))) reasons.push('요구사항 누락');
    if (!candidate.requirementEvidence || candidate.requirementEvidence.length !== candidate.requirements?.length || candidate.requirementEvidence.some((req, i) => req.text !== candidate.requirements[i] || !req.reviewIds?.length || !req.featureIds?.length || req.reviewIds.some(id => !candidate.reviewIds?.includes(id)) || req.featureIds.some(id => !candidate.featureIds?.includes(id)))) reasons.push('요구사항 근거 연결 누락');
    const template = need && conceptTemplate(need, model?.features || []);
    if (template && model.features.some(feature => feature.evidence && template.duplicatePattern.test(`${feature.name} ${feature.evidence}`))) reasons.push('기존 기능과 동일한 콘셉트');
    if (model?.features.some(feature => feature.evidence && keyOf(feature.name) === keyOf(candidate.title))) reasons.push('기존 기능명과 동일한 재제안');
    const constraints = exclusions(context);
    if (constraints.hardwareExcluded && candidate.kind === '제품 구조') reasons.push('제품 구조 변경 제외 조건 위반');
    const proposalText = [candidate.title, candidate.kind, candidate.mechanism, candidate.differentiation, ...(candidate.requirements || [])].join(' ').toLocaleLowerCase();
    if (constraints.terms.some(term => proposalText.includes(term.toLocaleLowerCase()))) reasons.push('기획 제외 조건 위반');
    if (reasons.length) {
      rejectedConcepts.push({ ...candidate, rejectionReasons: unique(reasons) });
      issues.push({ code: 'invalid_concept', severity: 'error', message: `${candidate.id} ${candidate.title}: ${unique(reasons).join(' / ')}`, repairStage: 'concept' });
    } else if (acceptedConcepts.length < 3) acceptedConcepts.push(candidate);
  }
  addCheck('concepts', '콘셉트 중복·요구사항 검사', !rejectedConcepts.length && created.concepts.length <= 3, rejectedConcepts.length ? `${rejectedConcepts.length}개 후보를 제외하고 수정 대상으로 남겼습니다.` : `${created.concepts.length}개 콘셉트의 중복·필수 항목·근거 연결을 검사했습니다.`);
  addCheck('withheld', '불확실성·보류 기록', true, `근거 부족·중복·제외 조건 ${created.withheld.length}개 항목을 보류 또는 제외 기록으로 남겼습니다.`, created.withheld.length > 0);
  const needsRepair = issues.some(issue => issue.severity === 'error');
  return common(needsRepair ? `${issues.length}개 검사 오류가 있어 수정이 필요합니다.` : `근거 검사를 마쳤습니다. 검토 가능한 콘셉트는 ${acceptedConcepts.length}개입니다.`, '모델 ID와 원문을 확인하고 중복·누락 후보를 검사했습니다.', {
    checks, issues, needsRepair, repairTargets: unique(issues.map(issue => issue.repairStage).filter(Boolean)), acceptedConcepts, rejectedConcepts, concepts: acceptedConcepts,
    status: needsRepair ? '수정 필요' : '검토 완료',
    items: checks.map(check => ({ title: check.label, detail: `${check.status} · ${check.detail}`, id: check.id })),
    sources: created.sources,
    warnings: [...issues.map(issue => issue.message), ...data.unresolvedReviews.map(review => `${review.id}: 모델·원문 연결 보류`)],
    assumptions: ['검사는 ID·원문·기능 중복·필수 항목의 일관성을 확인합니다. 실제 제품 성능과 수요 검증은 별도입니다.', '규칙 기반 결과의 해석과 콘셉트 채택은 기획자가 원문을 확인해 판단해야 합니다.'],
  });
}

export function runStage(id, context = {}) {
  const stage = { retrieve: source_retrieve, structure: needs_structure, compare: feature_compare, concept: concept_draft, validate: validate_revise }[id];
  if (!stage) throw new Error(`알 수 없는 단계: ${id}`);
  return stage({ ...context, results: context.results || {} });
}
