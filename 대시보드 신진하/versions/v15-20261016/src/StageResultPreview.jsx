import React, { useEffect, useId, useMemo, useState } from 'react';
import { ArrowUpRight, AlertCircle, Check, ClipboardCheck, Database, FileText, Layers, Lightbulb, Link2, Package, RotateCcw, Search } from 'lucide-react';
import './stage-preview.css';

const STAGES = {
  retrieve: { title: '조회 · 연결한 자료', tab: 'sources', action: '연결 원문 전체 보기', icon: Search },
  structure: { title: '불편을 분류한 결과', tab: 'needs', action: '불편 목록 전체 보기', icon: Layers },
  compare: { title: '기존 기능과 남은 불편', tab: 'compare', action: '근거 대조표 전체 보기', icon: Package },
  concept: { title: '이번에 만든 콘셉트', tab: 'concepts', action: '최종 검토 콘셉트 보기', icon: Lightbulb },
  validate: { title: '검사 · 수정 결과', tab: 'checks', action: '검사 결과 전체 보기', icon: ClipboardCheck },
};
const list = value => Array.isArray(value) ? value : [];
const text = value => value == null ? '' : typeof value === 'string' || typeof value === 'number' ? String(value) : '';
const sourceText = source => text(source?.text || source?.excerpt || source?.evidence);
const modelId = value => text(value?.modelId || value?.model);
const recordKey = (value, index) => text(value?.id) || String(index);
function uniqueSources(sources) {
  const seen = new Set();
  return sources.filter(source => {
    if (!source || !sourceText(source)) return false;
    const key = `${text(source.id)}:${modelId(source)}:${text(source.type)}:${sourceText(source)}`;
    if (seen.has(key)) return false;
    seen.add(key); return true;
  });
}
function Metrics({ items }) {
  return <div className="stage-preview-metrics">{items.map(([label, count, tone]) => <div key={label} className={tone || ''}><b>{count}</b><span>{label}</span></div>)}</div>;
}
function SourceLinks({ sources, onEvidence, limit = 3, empty = true }) {
  const actual = uniqueSources(list(sources));
  if (!actual.length) return empty ? <p className="stage-preview-source-empty">연결된 원문 근거가 없습니다.</p> : null;
  return <div className="stage-preview-sources">{actual.slice(0, limit).map((source, i) => <button type="button" className="stage-preview-source" key={`${recordKey(source, i)}:${modelId(source)}`} onClick={() => onEvidence?.(source)} disabled={typeof onEvidence !== 'function'} title={sourceText(source)}><Link2 size={11}/><span>{text(source.id) || '원문'}{source.page ? ` · p.${source.page}` : ''}</span><ArrowUpRight size={10}/></button>)}{actual.length > limit && <span className="stage-preview-source-more">외 {actual.length - limit}개</span>}</div>;
}
function EmptyResult({ stage, status }) {
  const state = status === 'running' ? '처리 중입니다. 결과가 도착하면 이곳에 표시합니다.' : status === 'paused' ? '실행이 일시정지되었습니다. 아직 결과는 없습니다.' : ['awaiting', 'needs_confirmation'].includes(status) ? '기획자 확인을 기다리고 있습니다. 아직 이 단계의 결과는 없습니다.' : status === 'failed' ? '실행에 실패해 표시할 결과가 없습니다. 현재 작업의 오류 사유를 확인해 주세요.' : status === 'stopped' ? '이 단계의 결과가 만들어지기 전에 실행이 중지되었습니다.' : '단계를 실행하면 실제 결과와 원문 근거가 이곳에 나타납니다.';
  return <div className="stage-preview-empty"><Database size={22}/><strong>아직 이 단계의 결과가 없습니다.</strong><p>{state}</p></div>;
}
function ReviewGroup({ title, rows, resolve, onEvidence, note }) {
  if (!list(rows).length) return null;
  return <details className="stage-preview-details"><summary>{title}<span>{rows.length}개</span></summary>{note && <p className="stage-preview-note">{note}</p>}{rows.slice(0, 3).map((review, i) => <article className="stage-preview-review" key={recordKey(review, i)}><div className="stage-preview-card-meta"><span>{text(review.id)}</span><span>{modelId(review)}</span></div><p className="stage-preview-quote">{text(review.text)}</p>{review.reason && <p className="stage-preview-note">{text(review.reason)}</p>}<SourceLinks sources={resolve([review.id])} onEvidence={onEvidence} empty={false}/></article>)}{rows.length > 3 && <p className="stage-preview-note">전체 {rows.length}개 중 원문 3개를 미리 봅니다.</p>}</details>;
}

/** Displays existing stage results only. It never runs a stage or creates evidence. */
export default function StageResultPreview({ stage, result, results = {}, revisions = [], status = 'idle', onEvidence, onResults }) {
  const config = STAGES[stage], r = result === undefined ? results[stage] : result;
  const [chosenComparison, setChosenComparison] = useState('');
  const selectId = useId();
  useEffect(() => { setChosenComparison(''); }, [stage]);
  const sourcePool = useMemo(() => uniqueSources([
    ...list(r?.sources),
    ...list(results.retrieve?.sources),
    ...Object.values(results).flatMap(value => list(value?.sources)),
  ]), [r, results]);
  const resolve = (ids, local = []) => {
    const keys = new Set(list(ids).map(text));
    return uniqueSources([...list(local), ...sourcePool.filter(source => keys.has(text(source.id)))]);
  };
  const Icon = config?.icon || FileText;
  const comparisons = list(r?.comparisons);
  const linkedReviewCounts = new Map();
  for (const review of list(r?.matchedReviews)) {
    const id = modelId(review);
    linkedReviewCounts.set(id, (linkedReviewCounts.get(id) || 0) + 1);
  }
  const previewModels = list(r?.models).map((model, index) => ({ model, index }))
    .sort((a, b) => (linkedReviewCounts.get(text(b.model.id)) || 0) - (linkedReviewCounts.get(text(a.model.id)) || 0) || a.index - b.index)
    .slice(0, 2).map(entry => entry.model);
  const rowIndex = comparisons.findIndex((row, i) => recordKey(row, i) === chosenComparison);
  const currentRowIndex = rowIndex >= 0 ? rowIndex : 0;
  const row = comparisons[currentRowIndex];
  const concepts = list(r?.concepts);
  const checks = list(r?.checks), issues = list(r?.issues), revisionList = list(revisions);
  const latestRevision = revisionList[revisionList.length - 1];
  const open = tab => onResults?.(tab);
  return <section className={`stage-preview stage-preview-${stage || 'unknown'}`} aria-label={config?.title || '단계 결과 미리보기'}>
    <div className="stage-preview-heading"><h2><Icon size={15}/>{config?.title || '단계 결과 미리보기'}</h2><span>{r ? '실제 결과' : '결과 대기'}</span></div>
    {!r ? <EmptyResult stage={stage} status={status}/> : <>
      {r.summary && <p className="stage-preview-summary">{text(r.summary)}</p>}
      {stage === 'retrieve' && <>
        <Metrics items={[
          ['조회 리뷰', list(r.reviews).length],
          ['연결 리뷰', list(r.matchedReviews).length, 'good'],
          ['연결 보류', list(r.unresolvedReviews).length, list(r.unresolvedReviews).length ? 'attention' : ''],
        ]}/>
        {previewModels.map((model, i) => {
          const reviewIds = list(r.matchedReviews).filter(review => modelId(review) === text(model.id)).map(review => review.id);
          const featureIds = list(model.features).filter(feature => feature.evidence).map(feature => feature.id);
          return <article className="stage-preview-card" key={recordKey(model, i)}><div className="stage-preview-card-meta"><span>{text(model.id)}</span><span>{model.synthetic ? '합성 제품 자료' : '제품 자료'}</span></div><h3>{text(model.name) || text(model.id)}</h3><p className="stage-preview-note">연결 리뷰 {reviewIds.length}개 · 기능 근거 {featureIds.length}개{model.version ? ` · ${text(model.version)}` : ''}</p><SourceLinks sources={resolve([...reviewIds.slice(0, 1), ...featureIds.slice(0, 1)])} onEvidence={onEvidence}/></article>;
        })}
        {!list(r.models).length && <p className="stage-preview-note">조회 결과에 제품 모델이 없습니다.</p>}
        {list(r.models).length > 2 && <p className="stage-preview-note">제품 {r.models.length}개 중 2개를 미리 봅니다. 나머지 모델의 연결 근거는 전체 원문에서 확인하세요.</p>}
        {!!list(r.unresolvedReviews).length && <details className="stage-preview-details attention"><summary>모델에 연결하지 못한 리뷰<span>{r.unresolvedReviews.length}개</span></summary>{r.unresolvedReviews.slice(0, 3).map((review, i) => <div key={recordKey(review, i)} className="stage-preview-issue"><b>{text(review.id)} · {modelId(review)}</b><p>{text(review.reason)}</p></div>)}</details>}
        {!!list(r.validation?.issues).length && <p className="stage-preview-warning"><AlertCircle size={13}/><span>{text(r.validation.issues[0].message)}{r.validation.issues.length > 1 ? ` 외 ${r.validation.issues.length - 1}개 자료 확인 항목` : ''}</span></p>}
      </>}
      {stage === 'structure' && <>
        <Metrics items={[
          ['불편 묶음', list(r.needs).length],
          ['긍정 경험 제외', list(r.positiveReviews).length, 'good'],
          ['미분류', list(r.unclassifiedReviews).length, list(r.unclassifiedReviews).length ? 'attention' : ''],
        ]}/>
        {list(r.needs).slice(0, 2).map((need, i) => <article className="stage-preview-card" key={recordKey(need, i)}><div className="stage-preview-card-meta"><span>{text(need.modelId)}</span><span>{need.count ?? list(need.reviewIds).length}개 리뷰</span></div><h3>{text(need.label || need.title)}</h3>{need.situation && <p className="stage-preview-note">{text(need.situation)}</p>}{need.pain && <p>{text(need.pain)}</p>}<SourceLinks sources={resolve(need.reviewIds)} onEvidence={onEvidence}/></article>)}
        {!list(r.needs).length && <p className="stage-preview-note">현재 규칙과 범위에서 불편 묶음을 만들지 못했습니다. 긍정 경험·미분류 원문을 확인하세요.</p>}
        {list(r.needs).length > 2 && <p className="stage-preview-note">전체 {r.needs.length}개 묶음 중 2개를 미리 봅니다.</p>}
        <ReviewGroup title="불편에서 제외한 긍정 경험" rows={r.positiveReviews} resolve={resolve} onEvidence={onEvidence}/>
        <ReviewGroup title="원문 확인이 필요한 미분류" rows={r.unclassifiedReviews} resolve={resolve} onEvidence={onEvidence} note="현재 분류 규칙에 해당하지 않은 원문입니다. 불편이 없다는 뜻은 아닙니다."/>
        <ReviewGroup title="선택한 사용 상황의 범위 밖" rows={r.outOfScopeReviews} resolve={resolve} onEvidence={onEvidence}/>
      </>}
      {stage === 'compare' && <>
        <Metrics items={[
          ['대조 항목', comparisons.length],
          ['후보 검토 기회', comparisons.filter(value => value.eligible === true).length, 'good'],
          ['보류 항목', list(r.withheld).length, list(r.withheld).length ? 'attention' : ''],
        ]}/>
        {row ? <>
          <label className="stage-preview-selector" htmlFor={selectId}>대조할 모델 · 불편<select id={selectId} value={recordKey(row, currentRowIndex)} onChange={event => setChosenComparison(event.target.value)}>{comparisons.map((value, i) => <option key={recordKey(value, i)} value={recordKey(value, i)}>{modelId(value)} · {text(value.need || value.label || value.title)}</option>)}</select></label>
          <div className="stage-preview-compare-grid"><article className="stage-preview-card"><h3><Package size={13}/>확인된 기존 기능</h3>{list(row.existingFeatures).length ? row.existingFeatures.slice(0, 2).map((feature, i) => <div className="stage-preview-feature" key={recordKey(feature, i)}><b>{text(feature.name)}</b>{feature.evidence && <p className="stage-preview-quote">{text(feature.evidence)}</p>}{feature.condition && <p className="stage-preview-note">사용 조건 · {text(feature.condition)}</p>}</div>) : <p>{text(row.existing || row.existingFeature) || '연결된 기능 근거가 없습니다. 기능이 없다고 단정할 수 없습니다.'}</p>}{list(row.existingFeatures).length > 2 && <small className="stage-preview-note">외 {row.existingFeatures.length - 2}개 기능</small>}<SourceLinks sources={resolve(row.featureIds, list(row.sources).filter(source => source.type === 'feature'))} onEvidence={onEvidence} limit={2}/></article><article className="stage-preview-card residual"><h3><FileText size={13}/>원문에 남은 불편</h3><b className="stage-preview-pain-title">{text(row.need || row.label || row.title)}</b><p>{text(row.residual || row.remainingPain || row.pain) || '기록된 잔여 불편이 없습니다.'}</p><SourceLinks sources={resolve(row.reviewIds, list(row.sources).filter(source => source.type === 'review'))} onEvidence={onEvidence} limit={2}/></article></div>
          <div className="stage-preview-judgment"><span>{text(row.status || row.classification) || '판단 기록 없음'}</span>{row.reason && <p>{text(row.reason)}</p>}</div>
        </> : <p className="stage-preview-note">대조할 항목이 없습니다. 이전 단계의 불편 목록과 원문 연결을 확인하세요.</p>}
      </>}
      {stage === 'concept' && <>
        <div className="stage-preview-countline"><span>작성된 후보 <b>{concepts.length}개</b></span><small>최대 3개 · 기획 제안</small></div>
        <p className="stage-preview-note">이 단계에서 작성한 후보이며, 최종 검토에서 제외될 수 있습니다.</p>
        {concepts.slice(0, 3).map((concept, i) => {
          const requirements = list(concept.requirements), sources = resolve([...list(concept.reviewIds), ...list(concept.featureIds)], concept.sources);
          return <article className="stage-preview-card stage-preview-concept-card" key={recordKey(concept, i)}><div className="stage-preview-card-meta"><span>{text(concept.id)}{modelId(concept) ? ` · ${modelId(concept)}` : ''}</span><span>{text(concept.kind)}</span></div><h3>{text(concept.title || concept.label)}</h3><p className="stage-preview-concept-core">{text(concept.mechanism || concept.description) || '작동 방식이 기록되지 않았습니다.'}</p>{requirements.length ? <><div className="stage-preview-requirement"><span>핵심 요구사항</span><p>{text(requirements[0])}</p></div><details className="stage-preview-details"><summary>요구사항 · 차별점<span>{requirements.length}개 요구사항</span></summary><ol>{requirements.map((requirement, j) => <li key={j}>{text(requirement)}</li>)}</ol>{concept.differentiation && <p className="stage-preview-note">차별점 · {text(concept.differentiation)}</p>}</details></> : <p className="stage-preview-warning">연결된 요구사항이 없습니다.</p>}<SourceLinks sources={sources} onEvidence={onEvidence}/></article>;
        })}
        {concepts.length > 3 && <p className="stage-preview-warning">기록된 {concepts.length}개 후보 중 3개를 미리 봅니다. 최대 3개 상한을 검토해야 합니다.</p>}
        {!concepts.length && <div className="stage-preview-empty compact"><Lightbulb size={20}/><strong>작성된 콘셉트가 없습니다.</strong><p>후보를 임의로 채우지 않습니다. 아래 보류 사유와 연결 근거를 확인하세요.</p></div>}
        {!!list(r.withheld).length && <details className="stage-preview-details attention"><summary>보류한 기회<span>{r.withheld.length}개</span></summary>{r.withheld.slice(0, 3).map((item, i) => <div className="stage-preview-issue" key={recordKey(item, i)}><b>{text(item.title || item.label || item.id)}</b><p>{text(item.reason || item.message)}</p></div>)}{r.withheld.length > 3 && <p className="stage-preview-note">나머지 사유는 콘셉트 전체 보기에서 확인하세요.</p>}</details>}
      </>}
      {stage === 'validate' && <>
        <Metrics items={[
          ['검사 통과(주의 포함)', checks.filter(check => check.passed === true).length, 'good'],
          ['주의', checks.filter(check => check.status === '주의').length, 'attention'],
          ['검사 실패', checks.filter(check => check.passed === false).length, checks.some(check => check.passed === false) ? 'danger' : ''],
        ]}/>
        <div className="stage-preview-checks">{checks.slice(0, 3).map((check, i) => <div className={`stage-preview-check ${check.passed === false ? 'failed' : check.status === '주의' ? 'attention' : 'passed'}`} key={recordKey(check, i)}>{check.passed === true && check.status !== '주의' ? <Check size={14}/> : <AlertCircle size={14}/>}<div><b>{text(check.label)}</b><span>{text(check.status)}</span><p>{text(check.detail)}</p></div></div>)}</div>
        {!checks.length && <p className="stage-preview-note">이 결과에 기록된 검사 항목이 없습니다.</p>}
        {checks.length > 3 && <p className="stage-preview-note">전체 {checks.length}개 검사 중 3개를 미리 봅니다.</p>}
        {!!issues.length && <details open className="stage-preview-details attention"><summary>해결이 필요한 검사 기록<span>{issues.length}개</span></summary>{issues.slice(0, 3).map((issue, i) => <div className="stage-preview-issue" key={recordKey(issue, i)}><b>{text(issue.message || issue.label)}</b>{issue.repairStage && <p>재검사 단계 · {STAGES[issue.repairStage]?.title || text(issue.repairStage)}</p>}</div>)}</details>}
        {Array.isArray(r.acceptedConcepts) && <p className="stage-preview-check-outcome"><ClipboardCheck size={13}/><span>근거 검사 통과 후보 <b>{r.acceptedConcepts.length}개</b>{list(r.rejectedConcepts).length ? ` · 제외 ${r.rejectedConcepts.length}개` : ''}</span></p>}
        <div className="stage-preview-revision"><RotateCcw size={14}/><div><b>기록된 자동 수정 {revisionList.length}회</b><p>{latestRevision ? text(latestRevision.reason) || '수정 사유가 기록되지 않았습니다.' : '이번 실행에 자동 수정 기록이 없습니다.'}</p>{latestRevision && <small>{latestRevision.after ? '수정 전·후 결과가 기록되었습니다.' : '수정 후 결과를 기다리고 있습니다.'}</small>}</div>{revisionList.length > 0 && <button type="button" onClick={() => open('history')} disabled={typeof onResults !== 'function'}>이력<ArrowUpRight size={11}/></button>}</div>
        <SourceLinks sources={r.sources} onEvidence={onEvidence} empty={false}/>
      </>}
      {config && <button type="button" className="stage-preview-all" onClick={() => open(config.tab)} disabled={typeof onResults !== 'function'}>{config.action}<ArrowUpRight size={13}/></button>}
    </>}
  </section>;
}
