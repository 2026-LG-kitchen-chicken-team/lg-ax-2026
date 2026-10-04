import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, loadBootstrap, parseBootstrap, requestPlanning } from './api';
import { evidenceLocation, filterEvidence, friendlyError, productName, SCENARIOS } from './domain';
import type { BootstrapData, Evidence, ProductGroup, View } from './domain';
import { FIXTURE_BOOTSTRAP, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import { ApplianceIcon, ArrowIcon, SearchIcon } from './icons';
import { contractErrors, missingRequestQuestions, nextRequestRevision, requestChanges } from './planning';
import type { DataMode, Feature, PlanningRequest, RunSnapshot } from './planning';
import { ConceptsView, FixtureBanner, HistoryView, ModeSwitch, RequestInsights } from './PlanningViews';

const NAV: { id: View; label: string; number: string }[] = [
  { id: 'request', label: '기획 요청', number: '01' },
  { id: 'evidence', label: '근거 대조', number: '02' },
  { id: 'concepts', label: '콘셉트 검토', number: '03' },
  { id: 'history', label: '수정 이력', number: '04' },
];

type DataState = { status: 'loading' } | { status: 'error'; message: string; code: string } | { status: 'ready'; data: BootstrapData };

function SourceBadge({ type }: { type: string }) {
  return <span className={`source-badge ${type === 'review' ? 'review' : 'manual'}`}>{type === 'review' ? '고객 리뷰' : type === 'manual' ? '제품 설명서' : type}</span>;
}

function EmptyState({ title, text, type = 'plain' }: { title: string; text: string; type?: 'plain' | 'future' }) {
  return <div className={`empty-state ${type}`}><div className="empty-icon" aria-hidden="true">{type === 'future' ? '↗' : '⌕'}</div><h3>{title}</h3><p>{text}</p></div>;
}

function EvidenceDetail({ selected, features }: { selected: Evidence | undefined; features: BootstrapData['features'] }) {
  if (!selected) return <aside className="detail-panel"><EmptyState title="검토할 근거를 선택하세요" text="리뷰나 제품 기능의 원문과 위치를 여기서 확인할 수 있습니다." /></aside>;
  return <aside className="detail-panel" aria-label="선택한 근거 상세">
    <div className="detail-top"><p className="eyebrow">SOURCE DETAIL</p><span className="sample-label">{selected.source_kind === 'synthetic' ? '합성자료' : selected.source_kind}</span></div>
    <SourceBadge type={selected.source_type} />
    <h3>{selected.source_type === 'review' ? '고객의 사용 경험' : '문서에 있는 제품 기능'}</h3>
    <blockquote>{selected.text}</blockquote>
    <dl className="evidence-meta">
      <div><dt>제품 모델</dt><dd>{selected.model_id}</dd></div>
      <div><dt>문서 버전</dt><dd>{selected.document_version}</dd></div>
      <div><dt>원문 위치</dt><dd>{evidenceLocation(selected)}</dd></div>
      <div><dt>근거 ID</dt><dd className="mono">{selected.id}</dd></div>
      <div><dt>출처 자료</dt><dd className="mono">{selected.source_id}</dd></div>
    </dl>
    <div className="linked-section"><h4>연결된 기능</h4>{selected.feature_ids.length ? <div className="feature-tags">{selected.feature_ids.map(id => <span key={id} title={id}>{features.find(feature => feature.id === id)?.name ?? id}</span>)}</div> : <p>등록된 기능 연결이 없습니다.</p>}</div>
    <div className="detail-note"><span aria-hidden="true">↳</span><p>이 화면은 등록된 원문을 조회합니다. 불편과 기능의 자동 대조·판단은 아직 연결되지 않았습니다.</p></div>
  </aside>;
}

function RequestView({ data, group, modelId, mode }: { data: BootstrapData | undefined; group: ProductGroup; modelId: string; mode: DataMode }) {
  const scenario = SCENARIOS.find(item => item.group === group)!;
  const [prompt, setPrompt] = useState(scenario.prompt as string);
  const [situation, setSituation] = useState(scenario.situation as string);
  const [customer, setCustomer] = useState('일상에서 키친 가전을 사용하는 고객');
  const [excluded, setExcluded] = useState('이미 있는 기능을 다시 제안하지 않기');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ code: string; message: string } | null>(null);

  const datasetVersion = typeof data?.manifest.version === 'string' ? data.manifest.version : '';
  const request: PlanningRequest = { product_group: group, target_customer: customer.trim(), use_situation: situation.trim(), improvement_task: prompt.trim(), exclusions: excluded.trim() ? [excluded.trim()] : [], model_ids: modelId ? [modelId] : [], dataset_version: datasetVersion };
  // The first complete request in this form is the original; later edits are change requests with a new revision.
  const [original] = useState<PlanningRequest>(() => request);
  const baseline = { ...original, model_ids: request.model_ids, dataset_version: request.dataset_version };
  const questions = missingRequestQuestions(request);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      if (mode === 'fixture') {
        const errors = contractErrors('PlanningRequest', request);
        setResult(errors.length || questions.length
          ? { code: 'INVALID_ARGUMENT', message: `요청을 보완해 주세요. ${questions.map(item => item.label).join(', ')} ${errors.join('; ')}`.trim() }
          : { code: 'FIXTURE_ONLY', message: `공통 요청 규격 검사를 통과했습니다(요청 회차 ${nextRequestRevision(baseline, null, request)}). fixture 모드라 서버에 전송하지 않았습니다.` });
        return;
      }
      await requestPlanning(request as unknown as Record<string, unknown>);
    } catch (error) {
      setResult({ code: error instanceof ApiError ? error.code : 'UNKNOWN_ERROR', message: friendlyError(error) });
    } finally { setBusy(false); }
  }

  return <div className="request-layout"><form className="request-form panel" onSubmit={submit}>
    <div className="panel-header"><div><p className="eyebrow">PLANNING BRIEF</p><h2>어떤 불편을 개선할까요?</h2></div><span className="state-badge future">Agent 연결 예정</span></div>
    <p className="section-description">고객과 사용 상황을 구체적으로 입력해 기획의 출발점을 정하세요.</p>
    <label className="field-label" htmlFor="planning-prompt">기획 요청</label><textarea id="planning-prompt" rows={4} required value={prompt} onChange={event => setPrompt(event.target.value)} />
    <div className="form-row"><div><label className="field-label" htmlFor="planning-customer">대상 고객</label><input id="planning-customer" required value={customer} onChange={event => setCustomer(event.target.value)} /></div><div><span className="field-label">검토 모델</span><div className="readonly-field">{modelId || '자료가 연결되면 모델을 선택할 수 있습니다'}</div></div></div>
    <label className="field-label" htmlFor="planning-situation">사용 상황</label><textarea id="planning-situation" rows={2} required value={situation} onChange={event => setSituation(event.target.value)} />
    <label className="field-label" htmlFor="planning-excluded">제외 조건</label><input id="planning-excluded" value={excluded} onChange={event => setExcluded(event.target.value)} />
    <div className="form-footer"><p>현재 요청은 Agent 분석 결과를 생성하지 않습니다.</p><button className="primary-button" type="submit" disabled={!data || !modelId || busy}>{busy ? '서버 확인 중…' : mode === 'fixture' ? '요청 규격 검사' : '요청 연결 확인'}<ArrowIcon /></button></div>
    {result ? <div className={`inline-message ${['NOT_IMPLEMENTED', 'FIXTURE_ONLY'].includes(result.code) ? 'notice' : 'error'}`} role="status"><strong>{result.code === 'NOT_IMPLEMENTED' ? '기획 실행 연결이 준비 중입니다' : result.code === 'FIXTURE_ONLY' ? '요청 규격 확인 완료(전송 안 함)' : '요청을 처리하지 못했습니다'}</strong><p>{result.message}</p><code>{result.code}</code></div> : null}
    <RequestInsights questions={questions} changes={requestChanges(baseline, request)} revision={nextRequestRevision(baseline, null, request)} mode={mode} />
  </form><aside className="request-guide panel"><p className="eyebrow">WORKFLOW</p><h3>요청에서 기획안까지</h3><ol>{['자료 조회', '니즈 구조화', '기능 대조', '콘셉트 작성', '검토·수정'].map((title, index) => <li key={title}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{title}</strong><small>{index === 0 ? '원문 조회 구현' : '실행 연결 예정'}</small></div></li>)}</ol><p className="guide-note">최대 3개 후보와 확인할 가정을 제시하고, 근거가 부족하면 보류하는 흐름으로 개발합니다.</p></aside></div>;
}

export default function App() {
  const [view, setView] = useState<View>('evidence');
  const [group, setGroup] = useState<ProductGroup>('fridge');
  const [modelChoice, setModelChoice] = useState('');
  const [type, setType] = useState('all');
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [state, setState] = useState<DataState>({ status: 'loading' });
  const [reload, setReload] = useState(0);
  const [mode, setMode] = useState<DataMode>('live');
  const [drafts, setDrafts] = useState<RunSnapshot[]>([]);
  const [runChoice, setRunChoice] = useState('');
  // The fixture goes through the same contract parser as live responses, so a broken fixture fails loudly.
  const fixtureState = useMemo<DataState>(() => {
    try { return { status: 'ready', data: parseBootstrap({ ok: true, data: FIXTURE_BOOTSTRAP }) }; } catch (error) {
      return { status: 'error', message: friendlyError(error), code: error instanceof ApiError ? error.code : 'UNKNOWN_ERROR' };
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    loadBootstrap(controller.signal).then(data => setState({ status: 'ready', data })).catch(error => {
      if (error instanceof Error && error.name === 'AbortError') return;
      setState({ status: 'error', message: friendlyError(error), code: error instanceof ApiError ? error.code : 'UNKNOWN_ERROR' });
    });
    return () => controller.abort();
  }, [reload]);

  const active = mode === 'fixture' ? fixtureState : state;
  const data = active.status === 'ready' ? active.data : undefined;
  const runs = [...FIXTURE_RUNS, ...drafts];
  const selectedRun = runs.find(item => item.run.id === runChoice) ?? runs[runs.length - 1];
  const planningProps = { mode, runs, selected: selectedRun, onSelect: setRunChoice, features: (data?.features ?? []) as unknown as Feature[], evidence: data?.evidence ?? [] };
  const products = data?.products.filter(product => product.product_group === group) ?? [];
  const modelId = products.some(product => product.model_id === modelChoice) ? modelChoice : products[0]?.model_id ?? '';
  const allModelEvidence = data?.evidence.filter(item => item.model_id === modelId) ?? [];
  const visibleEvidence = filterEvidence(data?.evidence ?? [], { modelId, query, type });
  const selected = visibleEvidence.find(item => item.id === selectedId) ?? visibleEvidence[0];
  const currentNav = NAV.find(item => item.id === view)!;

  function selectGroup(next: ProductGroup) {
    setGroup(next); setModelChoice(''); setSelectedId(''); setQuery(''); setType('all');
  }

  return <div className="workspace">
    <a href="#main-content" className="skip-link">본문으로 이동</a>
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark" aria-hidden="true"><span /><span /><span /></div><div><strong>KITCHEN</strong><span>PLANNING WORKSPACE</span></div></div>
      <div className="sidebar-project"><span className="eyebrow">LG AX HACKATHON</span><strong>키친 상품기획 Agent</strong><span>키친에서치킨먹기</span></div>
      <nav aria-label="기획 작업 영역">{NAV.map(item => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} aria-current={view === item.id ? 'page' : undefined} onClick={() => setView(item.id)}><span className="nav-number">{item.number}</span>{item.label}{view === item.id ? <ArrowIcon /> : null}</button>)}</nav>
      <div className="sidebar-lower"><p>고객의 말에서<br /><strong>새로운 기회의 근거로.</strong></p><div className="sidebar-stage"><span className="status-dot" />개발 프레임워크 · v0.1</div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">상품기획 작업실<span>/</span><strong>{currentNav.label}</strong></div><div className="topbar-right"><ModeSwitch mode={mode} onChange={next => { setMode(next); if (next === 'fixture') selectGroup('fridge'); else setSelectedId(''); }} /><div className="connection-status">{mode === 'fixture' ? <><span className="status-dot loading" />fixture 사용 · 서버 미사용</> : <><span className={`status-dot ${state.status}`} />{state.status === 'ready' ? '공통 API 연결됨' : state.status === 'loading' ? 'API 연결 확인 중' : 'API 연결 오류'}</>}</div></div></header>
      <main id="main-content">
        <section className="hero"><div><p className="eyebrow">EVIDENCE-LED KITCHEN PLANNING</p><h1>근거에서 시작하는<br />키친 기획.</h1><p>고객의 불편과 제품의 기능을 함께 살펴보고,<br className="desktop-break" /> 아직 해결되지 않은 기회를 검토하는 작업실입니다.</p></div><div className="hero-stats"><div><strong>{data?.products.length ?? '—'}</strong><span>등록된 모델</span></div><div><strong>{data?.evidence.length ?? '—'}</strong><span>조회 가능한 근거</span></div><p>{mode === 'fixture' ? `계약 fixture · FRIDGE-A 예시만 포함` : data ? `공통 계약 ${data.contract_version} · 시연용 합성자료` : '공통 API에서 자료를 불러옵니다'}</p></div></section>
        {mode === 'fixture' ? <FixtureBanner /> : null}
        <section className="scenario-grid" aria-label="제품군 선택">{SCENARIOS.map(scenario => <button key={scenario.group} onClick={() => selectGroup(scenario.group)} className={`scenario-card ${group === scenario.group ? 'selected' : ''}`} aria-pressed={group === scenario.group}><ApplianceIcon kind={scenario.group} /><span className="scenario-copy"><strong>{scenario.title}</strong><span>{scenario.subtitle}</span></span><span className="scenario-count">{data ? `${data.products.filter(product => product.product_group === scenario.group).length}개 모델` : '연결 대기'}</span></button>)}</section>
        {active.status === 'error' ? <div className="api-error" role="alert"><div><strong>자료를 불러오지 못했습니다</strong><p>{active.message}</p><code>{active.code}</code></div><button className="secondary-button" onClick={() => setReload(value => value + 1)}>다시 연결</button></div> : null}
        <div className="section-top"><div><p className="eyebrow">{currentNav.number} / WORKSPACE</p><h2>{currentNav.label}</h2></div><div className="model-select"><label htmlFor="product-model">검토 모델</label><select id="product-model" value={modelId} disabled={!products.length} onChange={event => { setModelChoice(event.target.value); setSelectedId(''); }}>{products.length ? products.map(product => <option key={product.model_id} value={product.model_id}>{product.model_id} · {productName(product)}</option>) : <option value="">자료 연결 대기</option>}</select></div></div>
        {view === 'evidence' ? <section className="evidence-workspace panel">
          <div className="evidence-toolbar"><div className="evidence-types" aria-label="근거 유형 필터">{[{ value: 'all', label: '전체' }, { value: 'review', label: '고객 리뷰' }, { value: 'manual', label: '제품 설명서' }].map(option => <button key={option.value} className={type === option.value ? 'active' : ''} aria-pressed={type === option.value} onClick={() => { setType(option.value); setSelectedId(''); }}>{option.label}<span>{option.value === 'all' ? allModelEvidence.length : allModelEvidence.filter(item => item.source_type === option.value).length}</span></button>)}</div><label className="search-field"><SearchIcon /><span className="sr-only">근거 검색</span><input type="search" placeholder="근거에서 검색" value={query} onChange={event => { setQuery(event.target.value); setSelectedId(''); }} /></label></div>
          <div className="evidence-columns"><div className="evidence-list"><div className="list-caption"><span>원문과 제품 기능</span><span>{visibleEvidence.length}개 근거</span></div>
            {active.status === 'loading' ? <div className="loading-state" role="status"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /><p>공통 API에서 근거를 불러오는 중입니다…</p></div> : !data ? <EmptyState title="API 연결이 필요합니다" text="서버가 연결되면 실제 자료와 근거를 확인할 수 있습니다." /> : !visibleEvidence.length ? <EmptyState title={allModelEvidence.length ? '검색 결과가 없습니다' : '등록된 근거가 없습니다'} text={allModelEvidence.length ? '검색어 또는 자료 유형을 바꿔 보세요.' : '이 모델에 리뷰와 제품 문서를 등록하면 여기에 표시됩니다.'} /> : <ul>{visibleEvidence.map(item => <li key={item.id}><button className={`evidence-card ${selected?.id === item.id ? 'selected' : ''}`} aria-pressed={selected?.id === item.id} onClick={() => setSelectedId(item.id)}><div className="evidence-card-top"><SourceBadge type={item.source_type} /><span>{evidenceLocation(item)}</span></div><p>{item.text}</p><div className="evidence-card-bottom"><span>{item.model_id} · {item.document_version}</span><ArrowIcon /></div></button></li>)}</ul>}
          </div><EvidenceDetail selected={selected} features={data?.features ?? []} /></div>
          <footer className="evidence-footer"><span className={`status-dot ${active.status}`} /><p>{data ? '원문 조회와 모델별 필터가 연결되어 있습니다. 자동 대조·판단은 구현 예정입니다.' : '공통 API가 연결되면 원문을 조회할 수 있습니다. 자동 대조·판단은 구현 예정입니다.'}</p></footer>
        </section> : view === 'request' ? <RequestView key={`${group}-${mode}`} data={data} group={group} modelId={modelId} mode={mode} /> : mode === 'fixture' && view === 'concepts' ? <ConceptsView {...planningProps} /> : mode === 'fixture' ? <HistoryView {...planningProps} original={FIXTURE_ORIGINAL_REQUEST} onDraft={draft => { setDrafts(items => [...items, draft]); setRunChoice(draft.run.id); }} /> : view === 'concepts' ? <section className="panel future-panel"><EmptyState type="future" title="근거를 갖춘 콘셉트를 이곳에서 검토합니다" text="콘셉트 생성과 중복·인용 검사는 아직 연결되지 않았습니다. 생성된 결과가 있을 때 후보별 차별점, 요구사항, 확인할 가정을 함께 표시할 예정입니다." /><div className="future-columns"><div><strong>콘셉트 비교</strong><span>최대 3개 타당한 후보 · 근거 부족 시 보류</span></div><div><strong>요구사항 확인</strong><span>연결된 원문 · 남은 불편 · 검토할 조건</span></div><div><strong>기획자 검토</strong><span>선택 · 수정 요청 · 추가 조건</span></div></div></section> : <section className="panel future-panel"><EmptyState type="future" title="아직 실행·수정 이력이 없습니다" text="Agent 실행과 기록 저장이 연결되면 동일 기획의 변경 전후, 사용한 자료 버전, 재검토 이유를 확인할 수 있습니다." /><div className="history-plan"><span>기획 요청</span><ArrowIcon /><span>근거·판단 기록</span><ArrowIcon /><span>새 자료로 재검토</span><ArrowIcon /><span>변경 전후 비교</span></div></section>}
        <footer className="page-footer"><span>키친에서치킨먹기 · LG AX 2026</span><span>반복 가능한 상품기획을 위한 첫 작업 공간</span></footer>
      </main>
    </div>
  </div>;
}
