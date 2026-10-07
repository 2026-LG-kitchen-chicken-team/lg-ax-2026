import { useEffect, useMemo, useRef, useState } from 'react';
import type { Dispatch, RefObject, SetStateAction } from 'react';
import { download } from './PlanningViews';
import { documentVersionView, FACT_KIND_LABEL, RESEARCH_TYPE_LABEL } from './research';
import type { PlanningBrief, ResearchBundle } from './research';
import { ResearchSourceLinks } from './ResearchSourceLinks';
import { locatorView } from './researchLocator';
import { confirmedPostingDay, DEFAULT_SOURCE_FILTERS, expandedKeywords, exportResearchSelection, koreanSourceLimitations, selectFilteredSources, sourceDateDisplay } from './researchSources';
import type { ResearchSourceFilters } from './researchSources';
import type { ResearchClient } from './researchClient';

export function ResearchSourcesPanel({ bundle, brief, inspectId, onInspect, onCloseInspect, panelRef, sourceBundleHash, selectedSourceIds, onSelectionChange, planningBusy = false, guideClient }: {
  bundle: ResearchBundle; brief: PlanningBrief | null; inspectId: string; onInspect: (id: string) => void;
  onCloseInspect: () => void; panelRef: RefObject<HTMLElement | null>; sourceBundleHash: string | null;
  selectedSourceIds?: string[]; onSelectionChange?: Dispatch<SetStateAction<string[]>>; planningBusy?: boolean;
  guideClient?: Pick<ResearchClient, 'createGuide'>;
}) {
  const [filters, setFilters] = useState<ResearchSourceFilters>(DEFAULT_SOURCE_FILTERS);
  const [localChosenIds, setLocalChosenIds] = useState<string[]>([]);
  const chosenIds = selectedSourceIds ?? localChosenIds;
  const setChosenIds = onSelectionChange ?? setLocalChosenIds;
  const [exporting, setExporting] = useState(false); const [exportError, setExportError] = useState('');
  const [guideFormat, setGuideFormat] = useState<'html' | 'markdown' | null>(null);
  const guideAbort = useRef<AbortController | null>(null);
  const exportGeneration = useRef(0); const exportBusy = useRef(false);
  useEffect(() => () => { exportGeneration.current++; guideAbort.current?.abort(); }, []);
  // The detail opens above the list: take keyboard/screen-reader focus to it, and back to the opener when it closes.
  const detailHeading = useRef<HTMLHeadingElement | null>(null); const returnFocus = useRef<HTMLElement | null>(null);
  const inspectedId = bundle.sources.some(source => source.source_id === inspectId) ? inspectId : '';
  useEffect(() => {
    if (!inspectedId) return;
    const active = document.activeElement;
    if (active instanceof HTMLElement && active !== document.body && !active.closest('.research-source-detail')) returnFocus.current = active;
    detailHeading.current?.focus();
  }, [inspectedId]);
  function closeDetail() {
    const target = returnFocus.current; returnFocus.current = null;
    onCloseInspect();
    if (target?.isConnected) target.focus();
  }
  const sources = useMemo(() => selectFilteredSources(bundle.sources, filters), [bundle, filters]);
  const chosen = new Set(chosenIds); const visibleIds = new Set(sources.map(source => source.source_id));
  const hiddenSelectionCount = chosenIds.filter(id => !visibleIds.has(id)).length;
  const inspected = bundle.sources.find(source => source.source_id === inspectId);
  const pageModels = [...new Set(bundle.sources.map(source => source.page_model).filter(model => model !== null))];
  const expansion = expandedKeywords(filters); const limits = koreanSourceLimitations(bundle);
  const knownDates = bundle.sources.filter(source => confirmedPostingDay(source) !== null).length;
  function update(patch: Partial<ResearchSourceFilters>) { setFilters(current => ({ ...current, ...patch })); }
  function toggle(id: string, checked: boolean) { setChosenIds(current => checked ? [...new Set([...current, id])] : current.filter(value => value !== id)); }
  async function exportSelected(format: 'json' | 'markdown') {
    if (exportBusy.current) return;
    const generation = exportGeneration.current; exportBusy.current = true; setExporting(true); setExportError('');
    try {
      const result = await exportResearchSelection(bundle, chosenIds, filters, sourceBundleHash);
      if (generation !== exportGeneration.current) return;
      const filename = result.bundle.bundle_id.replace(/[^A-Za-z0-9_.-]/g, '_');
      download(`${filename}.${format === 'json' ? 'json' : 'md'}`, format === 'json' ? 'application/json' : 'text/markdown', result[format]);
    } catch (error) { if (generation === exportGeneration.current) setExportError(error instanceof Error ? error.message : '선택 자료를 내보내지 못했습니다.'); }
    finally { if (generation === exportGeneration.current) { exportBusy.current = false; setExporting(false); } }
  }
  async function exportGuide(format: 'html' | 'markdown') {
    if (exportBusy.current || planningBusy) return;
    if (!guideClient) { setExportError('공식 자료 안내서 연결을 기다리고 있습니다.'); return; }
    const generation = exportGeneration.current; const abort = new AbortController(); guideAbort.current = abort;
    exportBusy.current = true; setExporting(true); setGuideFormat(format); setExportError('');
    try {
      const result = await guideClient.createGuide(bundle, [...chosenIds], abort.signal);
      if (generation !== exportGeneration.current) return;
      const filename = `official-guide-${bundle.bundle_id}`.replace(/[^A-Za-z0-9_.-]/g, '_');
      download(`${filename}.${format === 'html' ? 'html' : 'md'}`, format === 'html' ? 'text/html;charset=utf-8' : 'text/markdown;charset=utf-8', result[format]);
    } catch (error) { if (generation === exportGeneration.current) setExportError(error instanceof Error ? error.message : '공식 자료 안내서를 내보내지 못했습니다.'); }
    finally { if (generation === exportGeneration.current) { exportBusy.current = false; guideAbort.current = null; setExporting(false); setGuideFormat(null); } }
  }
  return <section className="research-sources panel" aria-label="실제 자료 원문" ref={panelRef}>
    <div className="research-card-title"><h2>3. 원문과 사실 확인</h2><span>{sources.length} / {bundle.sources.length}건</span></div>
    <div className="research-source-filter-grid">
      <label>키워드로 원문 필터<input id="research-keyword" type="search" value={filters.query} onChange={event => update({ query: event.target.value })} placeholder="예: 소음 세척" /></label>
      <label>원문 자료 유형<select id="research-source-type" value={filters.type} onChange={event => update({ type: event.target.value as ResearchSourceFilters['type'] })}><option value="all">모든 자료</option>{Object.entries(RESEARCH_TYPE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>페이지 모델<select value={filters.page_model} onChange={event => update({ page_model: event.target.value })}><option value="">모든 페이지 모델</option>{pageModels.map(model => <option key={model} value={model}>{model}</option>)}{bundle.sources.some(source => source.page_model === null) ? <option value="__unknown__">페이지 모델 미확인</option> : null}</select></label>
      <label>게시일 확인 여부<select value={filters.posting_date_mode} onChange={event => update({ posting_date_mode: event.target.value as ResearchSourceFilters['posting_date_mode'], start_date: '', end_date: '' })}><option value="all">전체 · 날짜 미상 포함</option><option value="confirmed">확인된 게시일만 · {knownDates}건</option><option value="unknown">게시일 미상만 · {bundle.sources.length - knownDates}건</option></select></label>
      <label>게시일 시작<input type="date" disabled={filters.posting_date_mode === 'unknown'} value={filters.start_date} onChange={event => update({ start_date: event.target.value, posting_date_mode: 'confirmed' })} /></label>
      <label>게시일 끝 · 해당 날짜 포함<input type="date" disabled={filters.posting_date_mode === 'unknown'} value={filters.end_date} onChange={event => update({ end_date: event.target.value, posting_date_mode: 'confirmed' })} /></label>
    </div>
    <label className="research-expand-option"><input type="checkbox" checked={filters.expand_terms} onChange={event => update({ expand_terms: event.target.checked })} />등록 어휘로 검색 범위 확장</label>
    <p className="research-muted">등록된 주제 어휘 규칙입니다. 실모델 의미 검색이 아닙니다. 예: 소음 ↔ 시끄럽·시끄러·조용 / 냄새 ↔ 악취.</p>
    {filters.expand_terms ? <p className="research-note">이번 검색의 확장 단어: {expansion.join(' · ') || '해당 규칙 없음'}. 공백으로 나눈 검색어들은 모두 포함해야 합니다.</p> : null}
    {filters.start_date && filters.end_date && filters.start_date > filters.end_date ? <p role="alert" className="research-note">시작일이 끝 날짜보다 늦습니다. 기간을 확인해 주세요.</p> : null}
    <div className="research-source-selection" aria-label="다른 기획에 재사용할 원문 선택">
      <strong>선택 {chosenIds.length}건{hiddenSelectionCount ? ` · 현재 필터 밖 선택 ${hiddenSelectionCount}건` : ''}</strong>
      <div className="research-actions"><button type="button" className="secondary-button" disabled={!sources.length || exporting || planningBusy} onClick={() => setChosenIds(current => [...new Set([...current, ...sources.map(source => source.source_id)])])}>표시 자료 모두 선택</button><button type="button" className="secondary-button" disabled={!chosenIds.length || exporting || planningBusy} onClick={() => setChosenIds([])}>전체 선택 해제</button><button type="button" className="secondary-button" disabled={!chosenIds.length || exporting} onClick={() => void exportSelected('json')}>선택 자료 JSON</button><button type="button" className="secondary-button" disabled={!chosenIds.length || exporting} onClick={() => void exportSelected('markdown')}>선택 자료 Markdown</button></div>
      <p>원문과 facts를 그대로 복사해 다른 기획의 자료로 저장합니다. {onSelectionChange ? '선택한 근거로 기획하려면 위의 ‘선택 근거로 새 기획 생성’을 누르세요. ‘새 기획 생성’은 원래 선택한 자료 묶음 전체를 사용합니다. 조건 변경은 기존 기획의 입력 범위를 유지합니다.' : '위 기획 실행은 원래 선택한 자료 묶음을 사용합니다.'}</p>
      <div className="research-actions" aria-label="선택 공식자료 안내서 내보내기"><button type="button" className="secondary-button" disabled={!chosenIds.length || !guideClient || exporting || planningBusy} onClick={() => void exportGuide('html')}>선택 공식자료 안내서 HTML</button><button type="button" className="secondary-button" disabled={!chosenIds.length || !guideClient || exporting || planningBusy} onClick={() => void exportGuide('markdown')}>선택 공식자료 안내서 Markdown</button></div>
      <p className="research-note">공식 설명서·FAQ·설치 안내·공식 답변만 명시적으로 선택하세요. 리뷰나 고객 질문이 섞이면 선택을 고쳐야 하며 자동으로 빼지 않습니다. 공식 원문 발췌를 모은 참고 안내서로, 전체 정식 설명서를 대체하거나 구매 SKU의 적용을 확정하지 않습니다.</p>
      {!guideClient ? <p className="research-muted">공식 자료 안내서 API 연결 대기</p> : null}
      {guideFormat ? <p role="status">공식 자료 원문·사실을 확인해 {guideFormat === 'html' ? 'HTML' : 'Markdown'} 안내서를 준비하고 있습니다. 모델은 호출하지 않습니다.</p> : null}
      {exportError ? <p role="alert">{exportError}</p> : null}
    </div>
    {inspected ? <article className="research-source-detail" aria-label="인용 원문 상세"><div className="research-card-title"><h3 ref={detailHeading} tabIndex={-1}>{inspected.source_id} · {inspected.title || RESEARCH_TYPE_LABEL[inspected.source_type]}</h3><button className="secondary-button" type="button" onClick={closeDetail}>상세 닫기</button></div><blockquote>{inspected.text}</blockquote><p>페이지 모델: {inspected.page_model ?? '미확인'} · 구매 모델: {inspected.purchased_model ?? '미확인'} · {sourceDateDisplay(inspected)}</p><p>자료 범위: {inspected.coverage === 'excerpt' ? '일부 발췌' : inspected.coverage === 'full' ? '전체' : '미확인'} · <span data-document-version>{documentVersionView(inspected).label}: {documentVersionView(inspected).value}</span></p>{documentVersionView(inspected).note ? <p className="research-muted" data-document-version-note>{documentVersionView(inspected).note}</p> : null}<p data-source-locator>원문 위치: {locatorView(inspected.locator).text}</p>{locatorView(inspected.locator).technical.length ? <details className="research-locator-technical"><summary>페이지 안 기술 위치</summary>{locatorView(inspected.locator).technical.map(item => <code key={item}>{item}</code>)}</details> : null}<a href={inspected.url} target="_blank" rel="noopener noreferrer">공개 원문 출처 열기 ↗</a><ul>{[...inspected.facts, ...(brief?.source_facts.find(item => item.source_id === inspected.source_id)?.facts ?? [])].filter((fact, index, all) => all.findIndex(item => item.fact_id === fact.fact_id) === index).map(fact => <li key={fact.fact_id}><strong>{FACT_KIND_LABEL[fact.kind]}</strong> · {fact.text}{fact.value == null ? '' : ` · 원기록 값 ${fact.value}${fact.unit ? ` ${fact.unit}` : ''}`}{fact.locator && Object.keys(fact.locator).length ? ` · 위치 ${locatorView(fact.locator).text}` : ''}</li>)}</ul></article> : null}
    <div className="research-source-list">{sources.map(source => <article key={source.source_id} className="research-source-row"><label className="research-source-check"><input type="checkbox" checked={chosen.has(source.source_id)} disabled={exporting || planningBusy} onChange={event => toggle(source.source_id, event.target.checked)} />자료 선택 <span>{source.source_id}</span></label><div><span className="research-chip">{RESEARCH_TYPE_LABEL[source.source_type]}</span><strong>{source.title || source.source_id}</strong><span>{sourceDateDisplay(source)}</span></div><p>{source.text}</p><p className="research-muted">페이지 {source.page_model ?? '미확인'} · 구매 모델 {source.purchased_model ?? '미확인'}{source.rating == null ? '' : ` · ${source.rating}점`} · {source.coverage === 'excerpt' ? '일부 발췌' : source.coverage === 'full' ? '전체 자료' : '범위 미확인'} · 위치 {locatorView(source.locator).text}</p><ResearchSourceLinks ids={[source.source_id]} bundle={bundle} onInspect={onInspect} /></article>)}</div>
    {!sources.length ? <p className="research-note">일치하는 원문이 없습니다. 게시일 미상 자료는 별도로 선택하거나 키워드·유형을 바꿔 주세요.</p> : null}
    {limits.length ? <section className="research-source-limitations" aria-label="자료의 핵심 한계"><h3>이 자료로 판단할 때의 한계</h3><ul>{limits.map((limit, index) => <li key={index}>{limit}</li>)}</ul></section> : null}
    <details className="research-manifest"><summary>수집 범위와 자료 한계 · 원기록</summary><pre>{JSON.stringify(bundle.collection_manifest, null, 2)}</pre></details>
  </section>;
}
