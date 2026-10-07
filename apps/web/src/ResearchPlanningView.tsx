import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { download } from './PlanningViews';
import { ResearchClient } from './researchClient';
import { ResearchRelationsGraph } from './ResearchRelationsGraph';
import { ResearchSourcesPanel } from './ResearchSourcesPanel';
import { ResearchSourceLinks as SourceLinks } from './ResearchSourceLinks';
import { exportResearchPlan, researchGroupLabel, researchScopeLabel } from './research';
import { buildConceptStoryboard, exportConceptStoryboard } from './conceptStoryboard';
import { coverageText, summaryCoverageView } from './researchCoverage';
import { planningInputScopeLabel } from './researchSelection';
import type { PlanningBrief, ResearchBundle, ResearchBundleSummary, ResearchProblem } from './research';
import './research.css';

const GOALS = ['고객 자료에서 아직 남은 사용 부담을 찾아 개선안을 제안하기', '설치·첫 사용 과정의 경험 개선하기', '기존 기능과 고객 기대의 차이를 비교하기', '경쟁 제품과 차별화할 기회 탐색하기'];
const CONSTRAINTS = ['하드웨어 변경 없이 개선', '기존 기능을 새로운 발명으로 제안하지 않기', '추가 구매 비용 최소화'];
const STATUS = { complete: '기획 초안 생성 완료', partial: '일부 근거 확인 필요', needs_sources: '추가 자료 필요' };
const CONCEPT_STATUS = { draft: '제안 초안', supported: '근거 연결됨', needs_sources: '근거 보강 필요' };
function errorMessage(error: unknown): string { return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.'; }
/** V1 first stage: export one concept as a 30–45 s future-concept storyboard (no image/voice/video model is called). */
function StoryboardActions({ brief, bundle, conceptId, title }: { brief: PlanningBrief; bundle: ResearchBundle; conceptId: string; title: string }) {
  const [error, setError] = useState('');
  const save = (format: 'json' | 'markdown') => {
    try {
      const result = exportConceptStoryboard(buildConceptStoryboard(bundle, brief, conceptId));
      const name = `storyboard-${brief.run_id}-r${brief.revision}-${conceptId}`.replace(/[^A-Za-z0-9_.-]/g, '_');
      download(`${name}.${format === 'json' ? 'json' : 'md'}`, format === 'json' ? 'application/json' : 'text/markdown', result[format]);
      setError('');
    } catch (failure) { setError(errorMessage(failure)); }
  };
  return <div className="research-storyboard" aria-label={`${title} 콘셉트 스토리보드`}><span>콘셉트 영상 스토리보드 · 미래 콘셉트 시안이며 실제 성능 증거가 아닙니다</span><div className="research-actions"><button type="button" className="secondary-button" onClick={() => save('markdown')}>스토리보드 Markdown</button><button type="button" className="secondary-button" onClick={() => save('json')}>스토리보드 JSON</button></div>{error ? <p role="alert" className="research-note">{error}</p> : null}</div>;
}
function BriefResult({ brief, bundle, onInspect, onReuseProblem }: { brief: PlanningBrief; bundle: ResearchBundle; onInspect: (id: string) => void; onReuseProblem: (problem: ResearchProblem) => void }) {
  const [exportError, setExportError] = useState('');
  const exportPlan = (format: 'json' | 'markdown') => {
    try {
      const result = exportResearchPlan(bundle, brief);
      const name = `kitchen-plan-${brief.run_id.replace(/[^A-Za-z0-9_.-]/g, '_')}-r${brief.revision}`;
      download(`${name}.${format === 'json' ? 'json' : 'md'}`, format === 'json' ? 'application/json' : 'text/markdown', result[format]);
      setExportError('');
    } catch (failure) { setExportError(errorMessage(failure)); }
  };
  const coverage = summaryCoverageView(brief);
  return <section className="research-result" aria-label="실제 자료 기획 결과">
    <header className="research-result-header"><div><p className="eyebrow">RESEARCH → PLAN</p><h2>{STATUS[brief.status]}</h2><p>수정 {brief.revision} · {brief.run_id} · {researchScopeLabel(brief.analysis_scope)}</p></div><div className="research-actions"><button type="button" className="secondary-button" onClick={() => exportPlan('json')}>JSON 내보내기</button><button type="button" className="secondary-button" onClick={() => exportPlan('markdown')}>기획안 Markdown</button></div></header>
    {exportError ? <p className="research-error" role="alert">파일을 내보내지 못했습니다: {exportError}</p> : null}
    <p className="research-note" data-planning-input-scope>{planningInputScopeLabel(brief)}. 아래 원문 선택을 바꿔도 저장된 결과의 입력 범위는 바뀌지 않습니다.</p>
    <p className="research-note">개선 후 장면은 제안 시나리오입니다. 실제 제품의 성능이나 검증된 효과로 단정하지 않습니다.</p>
    <div className="research-summary-grid">{([['positive', '좋았던 경험'], ['negative', '불편·부정 경험'], ['mixed', '혼합·조건부 경험']] as const).map(([key, title]) => <section className={`research-card summary-${key}`} key={key}><h3>{title}</h3>{coverage.state === 'ok' ? <p className="research-muted" data-summary-polarity-coverage={key}>고객 원문 {coverage.value.polaritySources[key]}건 인용 · 요약 {coverage.value.summaryItems[key]}개</p> : null}{brief.summaries[key].length ? brief.summaries[key].map((item, index) => <div key={index}><p>{item.text}</p><SourceLinks ids={item.source_ids} bundle={bundle} onInspect={onInspect} /></div>) : <p className="research-muted">이 실행에서 확인된 요약 없음</p>}</section>)}</div>
    <p className={coverage.state === 'malformed' ? 'research-note research-coverage-malformed' : 'research-note'} data-summary-coverage={coverage.state}>{coverageText(coverage)}</p>
    <section aria-label="문제와 반대 근거"><h3 className="research-section-heading">어떤 부담이 남아 있나요?</h3>{brief.problems.length ? <div className="research-card-grid">{brief.problems.map(problem => <article className="research-card" key={problem.id}><h4>{problem.title}</h4><p>{problem.description}</p><SourceLinks ids={problem.source_ids} bundle={bundle} onInspect={onInspect} /><div className="research-counter"><strong>반대 근거도 확인</strong><SourceLinks ids={problem.counter_source_ids} bundle={bundle} onInspect={onInspect} /></div><p className="research-muted">분석 범위: {problem.scope_caveat || '별도 기재 없음'}</p></article>)}</div> : <p className="research-note">현재 자료에서 제안으로 연결할 문제를 확인하지 못했습니다. 원문과 미확인 사항을 확인해 주세요.</p>}</section>
    <section aria-label="기존 및 경쟁 제품 대조"><h3 className="research-section-heading">기존 대응과 남은 부담</h3>{brief.comparisons.length ? <div className="research-comparisons">{brief.comparisons.map(item => <article className="research-card" key={item.id}><h4>{item.product}</h4><div className="research-before-after"><div><strong>기존 대응</strong><p>{item.existing_response}</p></div><div><strong>남은 부담</strong><p>{item.remaining_burden}</p></div></div><SourceLinks ids={item.source_ids} bundle={bundle} onInspect={onInspect} />{item.comparison_limits.length ? <ul className="research-muted">{item.comparison_limits.map((limit, index) => <li key={index}>{limit}</li>)}</ul> : null}</article>)}</div> : <p className="research-note">대조에 사용할 제품 근거가 없습니다. 경쟁 자료가 부족하면 경쟁 우위를 단정하지 않습니다.</p>}</section>
    <section aria-label="개선 시나리오"><h3 className="research-section-heading">기획을 경험과 장면으로</h3>{brief.concepts.map(concept => <article className="research-card research-concept" key={concept.id}><div className="research-card-title"><h4>{concept.title}</h4><span className="research-chip">{CONCEPT_STATUS[concept.status]}</span></div><p><strong>{concept.target_user}</strong> · {concept.use_context}</p><p>{concept.mechanism}</p><SourceLinks ids={concept.source_ids} bundle={bundle} onInspect={onInspect} /><div className="research-before-after"><div><h5>지금의 사용 과정</h5><ol>{concept.before_steps.map((step, index) => <li key={index}>{step}</li>)}</ol></div><div><h5>제안하는 사용 과정</h5><ol>{concept.after_steps.map((step, index) => <li key={index}>{step}</li>)}</ol></div></div>{concept.proposed_changes.length ? <p>변경 제안: {concept.proposed_changes.join(' · ')}</p> : null}<div className="research-scenes" aria-label={`${concept.title} 장면 구성`}>{concept.visual_scenes.map((scene, index) => <section key={index}><span className="research-scene-number">SCENE {index + 1}</span><h5>{scene.title}</h5><div><strong>이전</strong><p>{scene.before}</p></div><div className="research-scene-after"><strong>제안</strong><p>{scene.after}</p></div></section>)}</div><div className="research-before-after"><div><h5>검증 전 가정</h5>{concept.assumptions.length ? <ul>{concept.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="research-muted">별도 기재 없음</p>}</div><div><h5>다음에 확인할 질문</h5><ul>{concept.validation_questions.map((question, index) => <li key={index}>{question}</li>)}</ul></div></div><StoryboardActions brief={brief} bundle={bundle} conceptId={concept.id} title={concept.title} /></article>)}{!brief.concepts.length ? <p className="research-note">근거를 갖춘 개선안이 아직 없습니다. 추가 자료와 조건을 검토해 주세요.</p> : null}</section>
    {brief.uncertainties.length ? <section className="research-card research-uncertainties" aria-label="미확인 사항"><h3>아직 확인해야 할 것</h3><ul>{brief.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul></section> : null}
    <ResearchRelationsGraph key={brief.run_id} bundle={bundle} brief={brief} onInspect={onInspect} onReuseProblem={onReuseProblem} />
  </section>;
}

export function ResearchPlanningView() {
  const [tokenInput, setTokenInput] = useState('');
  const client = useRef<ResearchClient | null>(null);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [bundles, setBundles] = useState<ResearchBundleSummary[]>([]);
  const [bundle, setBundle] = useState<ResearchBundle | null>(null);
  const [bundleChoice, setBundleChoice] = useState('');
  const [goal, setGoal] = useState(GOALS[0]);
  const [constraints, setConstraints] = useState<string[]>([CONSTRAINTS[1]]);
  const [extraConstraints, setExtraConstraints] = useState('');
  const [history, setHistory] = useState<PlanningBrief[]>([]);
  const [runChoice, setRunChoice] = useState('');
  const [restoreId, setRestoreId] = useState('');
  const [inspectId, setInspectId] = useState('');
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const sourcePanel = useRef<HTMLElement | null>(null);
  const selected = history.find(item => item.run_id === runChoice && item.bundle_id === bundle?.bundle_id) ?? null;
  useEffect(() => () => { generation.current++; controller.current?.abort(); client.current = null; }, []);

  function begin() { controller.current?.abort(); const current = ++generation.current; const abort = new AbortController(); controller.current = abort; busyRef.current = true; setBusy(true); setError(''); return { current, signal: abort.signal }; }
  function resetResults() { setBundle(null); setBundleChoice(''); setHistory([]); setRunChoice(''); setInspectId(''); setRestoreId(''); setSelectedSourceIds([]); }
  async function connect(event: FormEvent) {
    event.preventDefault(); if (busyRef.current) return;
    const operation = begin(); resetResults(); setConnected(false); setBundles([]);
    const token = tokenInput.trim(); const next = new ResearchClient(() => token); client.current = next; setTokenInput('');
    try { const listed = await next.listBundles(operation.signal); if (operation.current !== generation.current) return; setBundles(listed); setConnected(true); }
    catch (failure) { if (operation.current === generation.current) { setError(errorMessage(failure)); client.current = null; } }
    finally { if (operation.current === generation.current) { busyRef.current = false; setBusy(false); } }
  }
  function disconnect() {
    generation.current++; controller.current?.abort(); client.current = null; busyRef.current = false;
    setBusy(false); setConnected(false); setBundles([]); setTokenInput(''); resetResults(); setError('');
    setGoal(GOALS[0]); setConstraints([CONSTRAINTS[1]]); setExtraConstraints('');
  }
  async function chooseBundle(id: string) {
    if (!client.current || busyRef.current) return;
    const api = client.current; const operation = begin(); setBundle(null); setBundleChoice(id); setRunChoice(''); setInspectId(''); setSelectedSourceIds([]);
    try { const data = await api.getBundle(id, operation.signal); if (operation.current === generation.current) setBundle(data); }
    catch (failure) { if (operation.current === generation.current) setError(errorMessage(failure)); }
    finally { if (operation.current === generation.current) { busyRef.current = false; setBusy(false); } }
  }
  async function run(previous: PlanningBrief | null, useSelection = false) {
    if (!bundle || !client.current || busyRef.current) return;
    if (!goal.trim()) { setError('기획 목적을 입력해 주세요.'); return; }
    if (useSelection && !selectedSourceIds.length) { setError('기획에 사용할 실제 근거를 한 건 이상 선택해 주세요.'); return; }
    const chosenConstraints = [...new Set([...constraints, ...extraConstraints.split('\n').map(item => item.trim()).filter(Boolean)])];
    if (previous && previous.goal === goal.trim() && JSON.stringify(previous.constraints) === JSON.stringify(chosenConstraints)) {
      setError('기획 목적이나 조건을 바꾼 뒤 조건 변경을 실행해 주세요.'); return;
    }
    const api = client.current; const capturedBundle = bundle; const operation = begin();
    try {
      const brief = await api.createPlan(capturedBundle, { bundle_id: capturedBundle.bundle_id, goal: goal.trim(), constraints: chosenConstraints, previous_run_id: previous?.run_id ?? null,
        ...(!previous && useSelection ? { selected_source_ids: [...selectedSourceIds] } : {}) }, previous, operation.signal);
      if (operation.current !== generation.current) return;
      setHistory(items => [...items.filter(item => item.run_id !== brief.run_id), brief]); setRunChoice(brief.run_id);
    } catch (failure) { if (operation.current === generation.current) setError(errorMessage(failure)); }
    finally { if (operation.current === generation.current) { busyRef.current = false; setBusy(false); } }
  }
  async function restore() {
    if (!bundle || !client.current || busyRef.current || !restoreId.trim()) return;
    const api = client.current; const capturedBundle = bundle; const operation = begin();
    try { const brief = await api.getPlan(capturedBundle, restoreId.trim(), operation.signal); if (operation.current !== generation.current) return; setHistory(items => [...items.filter(item => item.run_id !== brief.run_id), brief]); selectBrief(brief); }
    catch (failure) { if (operation.current === generation.current) setError(errorMessage(failure)); }
    finally { if (operation.current === generation.current) { busyRef.current = false; setBusy(false); } }
  }
  function selectBrief(brief: PlanningBrief) { setRunChoice(brief.run_id); setGoal(brief.goal); setConstraints(brief.constraints.filter(item => CONSTRAINTS.includes(item))); setExtraConstraints(brief.constraints.filter(item => !CONSTRAINTS.includes(item)).join('\n')); }
  function inspect(id: string) { setInspectId(id); sourcePanel.current?.scrollIntoView({ behavior: 'auto', block: 'start' }); }
  function reuseProblem(problem: ResearchProblem) {
    setGoal(`선택한 문제의 반대 근거와 기존 제품 대응을 비교하고 개선안을 검토하기: ${problem.title}`);
    document.getElementById('research-goal')?.focus();
  }
  return <div className="research-workspace">
    <section className="research-intro"><p className="eyebrow">PUBLIC EVIDENCE · VISUAL PLANNING</p><h1>고객의 말에서<br />다음 제품의 경험으로.</h1><p>실제 리뷰·Q&A·제품 문서를 선택하면 AI가 문제와 반대 근거를 살펴보고,<br />개선 전후의 사용 과정과 장면을 기획합니다. 불편을 미리 적을 필요는 없습니다.</p><div className="research-flow" aria-label="기획 단계"><span>실제 자료</span><span>문제·반대 근거</span><span>기존·경쟁 대조</span><span>개선 장면</span><span>조건 변경</span></div></section>
    <section className="research-connection panel" aria-label="실제 자료 작업실 연결"><div><strong>{connected ? '실제 자료 작업실 연결됨' : '실제 자료 작업실 연결'}</strong><p>작업실 토큰은 현재 화면 메모리에만 보관됩니다. 공개 원문만 이 흐름에 사용합니다.</p></div>{connected ? <button type="button" className="secondary-button" onClick={disconnect}>연결 해제</button> : <form onSubmit={connect}><label className="sr-only" htmlFor="research-token">실제 자료 작업실 토큰</label><input id="research-token" type="password" autoComplete="off" spellCheck={false} placeholder="작업실 토큰" value={tokenInput} onChange={event => setTokenInput(event.target.value)} disabled={busy} /><button className="primary-button" type="submit" disabled={busy || !tokenInput.trim()}>{busy ? '연결 중…' : '실제 자료 연결'}</button></form>}</section>
    {error ? <div className="research-error" role="alert"><strong>요청을 완료하지 못했습니다</strong><p>{error}</p><p>기존 결과가 있다면 그대로 보존됩니다. 저장 요청은 자동 재전송하지 않습니다.</p></div> : null}
    {!connected ? <section className="research-empty panel"><h2>자료 연결을 기다리고 있습니다</h2><p>서버에 연결하면 등록된 실제 자료 묶음이 표시됩니다.<br />합성 리뷰나 미리 만들어 둔 기획 결과로 대신 표시하지 않습니다.</p></section> : <>
      <section className="research-setup panel"><div className="research-card-title"><h2>1. 실제 자료와 목적 선택</h2><span className="research-chip">공개 원문</span></div><div className="research-form-grid"><div><label htmlFor="research-bundle">자료 묶음</label><select id="research-bundle" value={bundleChoice} disabled={busy} onChange={event => { if (event.target.value) void chooseBundle(event.target.value); }}><option value="">검토할 실제 자료를 선택하세요</option>{bundles.map(item => <option key={item.bundle_id} value={item.bundle_id}>{item.title ?? researchGroupLabel(item.product_group)} · {researchScopeLabel(item.analysis_scope)} · 자료 {item.source_count ?? '미확인'} / 리뷰 {item.review_count ?? '미확인'}</option>)}</select>{!bundles.length ? <p className="research-note">등록된 실제 자료가 없습니다. 자료 수집·적재가 준비되면 다시 연결해 주세요.</p> : null}{bundle ? <p className="research-note">실제 원문 {bundle.sources.length}건 · 리뷰 {bundle.sources.filter(item => item.source_type === 'review').length}건 · {researchScopeLabel(bundle.analysis_scope)}. 구매 모델·게시일이 미확인인 자료는 그 상태로 표시합니다.</p> : null}</div><div><label htmlFor="research-goal-choice">기획 목적 선택</label><select id="research-goal-choice" value={GOALS.includes(goal) ? goal : ''} disabled={busy} onChange={event => setGoal(event.target.value)}><option value="">직접 목적 입력</option>{GOALS.map(item => <option key={item} value={item}>{item}</option>)}</select><label htmlFor="research-goal">기획 목적</label><textarea id="research-goal" rows={2} maxLength={2000} value={goal} onChange={event => setGoal(event.target.value)} disabled={busy} /></div></div><fieldset disabled={busy}><legend>기획 제약</legend><div className="research-constraint-options">{CONSTRAINTS.map(item => <label key={item}><input type="checkbox" checked={constraints.includes(item)} onChange={event => setConstraints(values => event.target.checked ? [...values, item] : values.filter(value => value !== item))} />{item}</label>)}</div><label htmlFor="research-extra-constraints">추가 조건 · 한 줄에 하나</label><textarea id="research-extra-constraints" rows={2} maxLength={4000} placeholder="예: 설치 기사 없이 사용자가 직접 설정 가능" value={extraConstraints} onChange={event => setExtraConstraints(event.target.value)} /></fieldset><div className="research-actions"><button type="button" className="primary-button" disabled={!bundle || busy || !goal.trim()} onClick={() => void run(null)}>{busy ? '요청 처리 중…' : '새 기획 생성'}</button><button type="button" className="secondary-button" disabled={!bundle || !selectedSourceIds.length || busy || !goal.trim()} onClick={() => void run(null, true)}>선택 근거로 새 기획 생성 ({selectedSourceIds.length}건)</button><button type="button" className="secondary-button" disabled={!bundle || !selected || busy || !goal.trim()} onClick={() => void run(selected)}>현재 결과에서 조건 변경</button></div>{busy ? <p role="status" className="research-note">실제 자료를 확인하고 요청을 처리하고 있습니다. 화면 이동·연결 해제는 서버에서 시작한 실행을 취소하지 않습니다.</p> : null}</section>
      {bundle ? <><section className="research-history panel" aria-label="실제 기획 수정 이력"><div><h2>2. 실행·수정 이력</h2><p>현재 연결에서 확인한 기록입니다. 실행 ID로 서버에 저장된 기획을 다시 불러올 수 있습니다.</p></div><div className="research-history-controls"><label className="sr-only" htmlFor="research-run-choice">기획 실행 선택</label><select id="research-run-choice" value={runChoice} disabled={busy} onChange={event => { const brief = history.find(item => item.run_id === event.target.value); if (brief) selectBrief(brief); }}><option value="">실행 결과 선택</option>{history.filter(item => item.bundle_id === bundle.bundle_id).map(item => <option key={item.run_id} value={item.run_id}>수정 {item.revision} · {STATUS[item.status]} · {item.run_id}</option>)}</select><label className="sr-only" htmlFor="research-restore-id">저장된 실행 ID</label><input id="research-restore-id" value={restoreId} onChange={event => setRestoreId(event.target.value)} placeholder="저장된 실행 ID" disabled={busy} /><button type="button" className="secondary-button" disabled={busy || !restoreId.trim()} onClick={() => void restore()}>불러오기</button></div>{selected ? <p className="research-note">기준 기획: {selected.previous_brief_id ?? '첫 기획'} · 목적: {selected.goal} · 조건: {selected.constraints.join(' / ') || '없음'}</p> : null}</section>{selected ? <BriefResult key={selected.run_id} brief={selected} bundle={bundle} onInspect={inspect} onReuseProblem={reuseProblem} /> : <section className="research-empty panel"><h2>자료에서 발견한 기획이 여기에 표시됩니다</h2><p>기획 목적과 제약을 선택하고 실행하면 문제·반대 근거·개선 장면을 확인할 수 있습니다.</p></section>}
        <ResearchSourcesPanel key={bundle.bundle_id} selectedSourceIds={selectedSourceIds} onSelectionChange={setSelectedSourceIds} planningBusy={busy} bundle={bundle} brief={selected} inspectId={inspectId} onInspect={inspect} onCloseInspect={() => setInspectId('')} panelRef={sourcePanel} sourceBundleHash={bundles.find(item => item.bundle_id === bundle.bundle_id)?.bundle_sha256 ?? null} />
      </> : null}
    </>}
  </div>;
}
