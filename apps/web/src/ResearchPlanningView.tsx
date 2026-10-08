import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { download } from './PlanningViews';
import { ResearchClient } from './researchClient';
import type { ResearchPlanProgress } from './researchClient';
import { ResearchRelationsGraph } from './ResearchRelationsGraph';
import { ResearchSourcesPanel } from './ResearchSourcesPanel';
import { ResearchSourceLinks as SourceLinks } from './ResearchSourceLinks';
import { exportResearchPlan, researchGroupLabel, researchScopeLabel } from './research';
import { buildConceptStoryboard, exportConceptStoryboard } from './conceptStoryboard';
import { coverageText, summaryCoverageView } from './researchCoverage';
import { planningInputScopeLabel } from './researchSelection';
import type { PlanningBrief, ResearchBundle, ResearchBundleSummary, ResearchProblem } from './research';
import type { SharedPrototypeSession } from './sharedSession';
import { forgetResearchJob, pendingResearchJob, retainResearchJob } from './sharedSession';
import { conversationPath, conversationThreads } from './researchConversations';
import './research.css';
import './chatPlanning.css';

const GOALS = ['고객 자료에서 아직 남은 사용 부담을 찾아 개선안을 제안하기', '설치·첫 사용 과정의 경험 개선하기', '기존 기능과 고객 기대의 차이를 비교하기', '경쟁 제품과 차별화할 기회 탐색하기'];
const CONSTRAINTS = ['하드웨어 변경 없이 개선', '기존 기능을 새로운 발명으로 제안하지 않기', '추가 구매 비용 최소화'];
const STATUS = { complete: '기획 초안 생성 완료', partial: '일부 근거 확인 필요', needs_sources: '추가 자료 필요' };
const CONCEPT_STATUS = { draft: '제안 초안', supported: '근거 연결됨', needs_sources: '근거 보강 필요' };
function jumpToSection(id: string) {
  const heading = document.getElementById(id);
  heading?.focus({ preventScroll: true });
  heading?.scrollIntoView?.({ behavior: 'auto', block: 'start' });
}
function PlanOverview({ brief }: { brief: PlanningBrief }) {
  const problem = brief.problems[0];
  const comparison = problem ? brief.comparisons.find(item => item.problem_id === problem.id) : undefined;
  const concept = problem ? brief.concepts.find(item => item.problem_ids.includes(problem.id)) : undefined;
  return <section className="research-plan-overview" aria-label="첫 문제의 기획 연결 요약">
    <div className="research-card-title"><h3>한눈에 보는 기획의 연결</h3><span className="research-chip">AI 초안 · 원문 대조 필요</span></div>
    <div className="research-plan-path">
      <article><span>고객 경험</span><h4>{problem?.title ?? '확인한 문제 없음'}</h4><p>{problem?.description ?? '자료와 미확인 사항을 먼저 살펴보세요.'}</p>{problem ? <a href="#research-problems" onClick={event => { event.preventDefault(); jumpToSection('research-problems'); }}>문제·반대 근거 보기 ↗</a> : null}</article>
      <article><span>기존 제품</span><h4>{comparison?.product ?? '연결된 제품 대조 없음'}</h4><p>{comparison?.existing_response ?? '이 문제와 명시적으로 연결된 대조 자료가 없습니다.'}</p>{comparison ? <a href="#research-comparisons" onClick={event => { event.preventDefault(); jumpToSection('research-comparisons'); }}>기존 대응·남은 부담 보기 ↗</a> : null}</article>
      <article><span>개선 제안</span><h4>{concept?.title ?? '연결된 개선안 없음'}</h4><p>{concept?.mechanism ?? '이 문제와 명시적으로 연결된 개선안이 없습니다.'}</p>{concept ? <a href="#research-concepts" onClick={event => { event.preventDefault(); jumpToSection('research-concepts'); }}>개선 전후 장면 보기 ↗</a> : null}</article>
    </div>
    <p className="research-muted">첫 문제와 명시적으로 연결된 항목만 표시합니다. 요약·기획은 검토할 초안이며 검증된 고객 경험이나 성능을 뜻하지 않습니다.</p>
  </section>;
}
function errorMessage(error: unknown): string { return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.'; }
function bundleUsageLabel(bundle: ResearchBundleSummary): string {
  if (bundle.bundle_id.includes('-public-intake-')) return '추가 수집 자료';
  if (bundle.bundle_id.includes('-manual-reference-')) return '제품 문서';
  if (bundle.bundle_id.startsWith('LGE-R8-')) return '보관 자료';
  return '리뷰·제품 문서';
}
function ChatActionCard({ title, description, onClick }: { title: string; description: string; onClick: () => void }) {
  return <button type="button" className="chat-action-card" onClick={onClick}><strong>{title}</strong><span>{description}</span></button>;
}
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
  return <div className="research-storyboard" aria-label={`${title} 콘셉트 스토리보드`}><span>콘셉트 영상 스토리보드 · 미래 콘셉트 시안이며 실제 성능 증거가 아닙니다</span><div className="research-actions"><button type="button" className="secondary-button" onClick={() => save('markdown')}>영상 구성안 (.md)</button><button type="button" className="secondary-button" onClick={() => save('json')}>영상 구성 기록 (.json)</button></div>{error ? <p role="alert" className="research-note">{error}</p> : null}</div>;
}
function BriefResult({ brief, bundle, onInspect, onReuseProblem }: { brief: PlanningBrief; bundle: ResearchBundle; onInspect: (id: string) => void; onReuseProblem: (problem: ResearchProblem) => void }) {
  const [exportError, setExportError] = useState('');
  const [tab, setTab] = useState<'insights' | 'concepts' | 'relations'>('insights');
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
    <header className="research-result-header"><div><h2 id="research-results" tabIndex={-1}>리뷰 분석과 개선 기회</h2><p><span className="research-chip">{STATUS[brief.status]}</span> · 수정 {brief.revision}</p></div><details className="chat-export"><summary>기획안 저장</summary><div className="research-actions"><button type="button" className="secondary-button" onClick={() => exportPlan('markdown')}>기획안 문서 (.md)</button><button type="button" className="secondary-button" onClick={() => exportPlan('json')}>전체 기록 (.json)</button></div><code>{brief.run_id}</code></details></header>
    <div className="chat-result-tabs" role="tablist" aria-label="기획 결과 보기" onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')];
      const index = buttons.indexOf(event.target as HTMLButtonElement);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
      event.preventDefault(); buttons[next].click(); buttons[next].focus();
    }}>{([['insights', '리뷰 분석'], ['concepts', '개선 장면'], ['relations', '관계 그래프']] as const).map(([value, label]) => <button type="button" role="tab" id={`chat-tab-${value}`} aria-controls={`chat-panel-${value}`} aria-selected={tab === value} tabIndex={tab === value ? 0 : -1} key={value} onClick={() => setTab(value)}>{label}</button>)}</div>
    {exportError ? <p className="research-error" role="alert">파일을 내보내지 못했습니다: {exportError}</p> : null}
    <p className="research-note" data-planning-input-scope>{planningInputScopeLabel(brief)}. 이 결과가 사용한 근거입니다. 원문 선택을 바꿔도 기존 결과는 유지됩니다.</p>
    <p className="research-note">개선 후 장면은 제안 시나리오입니다. 실제 제품의 성능이나 검증된 효과로 단정하지 않습니다.</p>
    <div id="chat-panel-insights" role="tabpanel" aria-labelledby="chat-tab-insights" hidden={tab !== 'insights'}><PlanOverview brief={brief} />
    <div className="research-summary-grid">{([['positive', '좋았던 경험', '01'], ['negative', '불편·부정 경험', '02'], ['mixed', '혼합·조건부 경험', '03']] as const).map(([key, title, number]) => <section className={`research-card summary-${key}`} key={key}><span className="research-summary-eyebrow">{number} · 리뷰 요약</span><h3>{title}</h3>{coverage.state === 'ok' ? <p className="research-muted" data-summary-polarity-coverage={key}>고객 원문 {coverage.value.polaritySources[key]}건 인용 · 요약 {coverage.value.summaryItems[key]}개</p> : null}{brief.summaries[key].length ? brief.summaries[key].map((item, index) => <div key={index}><p>{item.text}</p><SourceLinks ids={item.source_ids} bundle={bundle} onInspect={onInspect} /></div>) : <p className="research-muted">이 실행에서 확인된 요약 없음</p>}</section>)}</div>
    <p className={coverage.state === 'malformed' ? 'research-note research-coverage-malformed' : 'research-note'} data-summary-coverage={coverage.state}>{coverageText(coverage)}</p>
    <section aria-label="문제와 반대 근거"><h3 className="research-section-heading" id="research-problems" tabIndex={-1}>어떤 부담이 남아 있나요?</h3>{brief.problems.length ? <div className="research-card-grid">{brief.problems.map(problem => <article className="research-card" key={problem.id}><h4>{problem.title}</h4><p>{problem.description}</p><SourceLinks ids={problem.source_ids} bundle={bundle} onInspect={onInspect} /><div className="research-counter"><strong>반대 근거도 확인</strong><SourceLinks ids={problem.counter_source_ids} bundle={bundle} onInspect={onInspect} /></div><p className="research-muted">분석 범위: {problem.scope_caveat || '별도 기재 없음'}</p></article>)}</div> : <p className="research-note">현재 자료에서 제안으로 연결할 문제를 확인하지 못했습니다. 원문과 미확인 사항을 확인해 주세요.</p>}</section>
    <section aria-label="기존 및 경쟁 제품 대조"><h3 className="research-section-heading" id="research-comparisons" tabIndex={-1}>기존 대응과 남은 부담</h3>{brief.comparisons.length ? <div className="research-comparisons">{brief.comparisons.map(item => <article className="research-card" key={item.id}><h4>{item.product}</h4><div className="research-before-after"><div><strong>기존 대응</strong><p>{item.existing_response}</p></div><div><strong>남은 부담</strong><p>{item.remaining_burden}</p></div></div><SourceLinks ids={item.source_ids} bundle={bundle} onInspect={onInspect} />{item.comparison_limits.length ? <ul className="research-muted">{item.comparison_limits.map((limit, index) => <li key={index}>{limit}</li>)}</ul> : null}</article>)}</div> : <p className="research-note">대조에 사용할 제품 근거가 없습니다. 경쟁 자료가 부족하면 경쟁 우위를 단정하지 않습니다.</p>}</section>
    </div><div id="chat-panel-concepts" role="tabpanel" aria-labelledby="chat-tab-concepts" hidden={tab !== 'concepts'}><section aria-label="개선 시나리오"><h3 className="research-section-heading" id="research-concepts" tabIndex={-1}><span className="research-section-number">개선 시나리오</span>기획을 경험과 장면으로</h3>{brief.concepts.map((concept, conceptIndex) => <article className="research-card research-concept" key={concept.id}><span className="research-concept-index">개선안 {conceptIndex + 1}</span><div className="research-card-title"><h4>{concept.title}</h4><span className="research-chip">{CONCEPT_STATUS[concept.status]}</span></div><p><strong>{concept.target_user}</strong> · {concept.use_context}</p><p>{concept.mechanism}</p><SourceLinks ids={concept.source_ids} bundle={bundle} onInspect={onInspect} /><div className="research-before-after"><div><h5>지금의 사용 과정</h5><ol>{concept.before_steps.map((step, index) => <li key={index}>{step}</li>)}</ol></div><div><h5>제안하는 사용 과정</h5><ol>{concept.after_steps.map((step, index) => <li key={index}>{step}</li>)}</ol></div></div>{concept.proposed_changes.length ? <p>변경 제안: {concept.proposed_changes.join(' · ')}</p> : null}<div className="research-scenes" aria-label={`${concept.title} 장면 구성`}>{concept.visual_scenes.map((scene, index) => <section key={index}><span className="research-scene-number">장면 {index + 1}</span><h5>{scene.title}</h5><div><strong>이전</strong><p>{scene.before}</p></div><div className="research-scene-after"><strong>제안</strong><p>{scene.after}</p></div></section>)}</div><div className="research-before-after"><div><h5>검증 전 가정</h5>{concept.assumptions.length ? <ul>{concept.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="research-muted">별도 기재 없음</p>}</div><div><h5>다음에 확인할 질문</h5><ul>{concept.validation_questions.map((question, index) => <li key={index}>{question}</li>)}</ul></div></div><StoryboardActions brief={brief} bundle={bundle} conceptId={concept.id} title={concept.title} /></article>)}{!brief.concepts.length ? <p className="research-note">근거를 갖춘 개선안이 아직 없습니다. 추가 자료와 조건을 검토해 주세요.</p> : null}</section>
    </div>{brief.uncertainties.length ? <section className="research-card research-uncertainties" aria-label="미확인 사항"><h3>아직 확인해야 할 것</h3><ul>{brief.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul></section> : null}
    <div id="chat-panel-relations" role="tabpanel" aria-labelledby="chat-tab-relations" hidden={tab !== 'relations'}><ResearchRelationsGraph key={brief.run_id} bundle={bundle} brief={brief} onInspect={onInspect} onReuseProblem={onReuseProblem} /></div>
  </section>;
}

export function ResearchPlanningView({ sharedSession, sharedConnectionState }: {
  sharedSession?: SharedPrototypeSession;
  sharedConnectionState?: 'checking' | 'unavailable';
} = {}) {
  const sharedMode = Boolean(sharedSession || sharedConnectionState);
  const [tokenInput, setTokenInput] = useState('');
  const client = useRef<ResearchClient | null>(null);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [jobProgress, setJobProgress] = useState<ResearchPlanProgress | null>(null);
  const [savedJobId, setSavedJobId] = useState(pendingResearchJob);
  const [jobRecoveryNotice, setJobRecoveryNotice] = useState('');
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
  const [sourcesOpen, setSourcesOpen] = useState(() => !window.matchMedia || window.matchMedia('(min-width: 1100px)').matches);
  const [selectionMode, setSelectionMode] = useState(false);
  const [conditionsOpen, setConditionsOpen] = useState(false);
  const threads = conversationThreads(history);
  const selected = history.find(item => item.run_id === runChoice && item.bundle_id === bundle?.bundle_id) ?? null;
  useEffect(() => () => { generation.current++; controller.current?.abort(); client.current = null; }, []);
  useEffect(() => { if (runChoice) jumpToSection('research-results'); }, [runChoice]);

  function begin() { controller.current?.abort(); const current = ++generation.current; const abort = new AbortController(); controller.current = abort; busyRef.current = true; setBusy(true); setError(''); return { current, signal: abort.signal }; }
  function resetResults() { setBundle(null); setBundleChoice(''); setHistory([]); setRunChoice(''); setInspectId(''); setRestoreId(''); setSelectedSourceIds([]); }
  async function connect(event: FormEvent) {
    event.preventDefault(); if (busyRef.current) return;
    await connectToken(tokenInput.trim());
  }
  async function connectToken(token: string) {
    if (busyRef.current) return;
    const operation = begin(); resetResults(); setConnected(false); setBundles([]);
    setJobProgress(null); setJobRecoveryNotice('');
    const next = new ResearchClient(() => token); client.current = next; setTokenInput('');
    try { const listed = await next.listBundles(operation.signal); if (operation.current !== generation.current) return; setBundles(listed); setConnected(true); }
    catch (failure) { if (operation.current === generation.current) { setError(errorMessage(failure)); client.current = null; } }
    finally { if (operation.current === generation.current) { busyRef.current = false; setBusy(false); } }
  }
  useEffect(() => {
    if (!sharedSession) return;
    void connectToken(sharedSession.token);
    return () => { generation.current++; controller.current?.abort(); client.current = null; busyRef.current = false; };
  }, [sharedSession]);
  function disconnect() {
    generation.current++; controller.current?.abort(); client.current = null; busyRef.current = false;
    setBusy(false); setConnected(false); setBundles([]); setTokenInput(''); resetResults(); setError('');
    setJobProgress(null); setJobRecoveryNotice('');
    setGoal(GOALS[0]); setConstraints([CONSTRAINTS[1]]); setExtraConstraints('');
  }
  async function chooseBundle(id: string) {
    if (!client.current || busyRef.current) return;
    const api = client.current; const operation = begin(); setBundle(null); setBundleChoice(id); setRunChoice(''); setInspectId(''); setSelectedSourceIds([]); setSelectionMode(false);
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
    setJobProgress(null); setJobRecoveryNotice('');
    try {
      const brief = await api.createPlan(capturedBundle, { bundle_id: capturedBundle.bundle_id, goal: goal.trim(), constraints: chosenConstraints, previous_run_id: previous?.run_id ?? null,
        ...(!previous && useSelection ? { selected_source_ids: [...selectedSourceIds] } : {}) }, previous, operation.signal, status => {
        if (operation.current !== generation.current) return;
        setJobProgress(status);
        if (status.status === 'queued' || status.status === 'running') { retainResearchJob(status.job_id); setSavedJobId(status.job_id); }
        else { forgetResearchJob(status.job_id); setSavedJobId(value => value === status.job_id ? null : value); }
      });
      if (operation.current !== generation.current) return;
      setHistory(items => [...items.filter(item => item.run_id !== brief.run_id), brief]); setRunChoice(brief.run_id);
    } catch (failure) { if (operation.current === generation.current) setError(errorMessage(failure)); }
    finally { if (operation.current === generation.current) { busyRef.current = false; setBusy(false); } }
  }
  async function recoverJob() {
    if (!client.current || busyRef.current || !sharedMode && !savedJobId) return;
    const api = client.current; const operation = begin(); setJobRecoveryNotice('');
    try {
      const job = sharedMode ? await api.getCurrentJobStatus(operation.signal) : await api.getJobStatus(savedJobId!, operation.signal);
      if (operation.current !== generation.current) return;
      setJobProgress({ job_id: job.job_id, status: job.status, queue_position: job.queue_position });
      if (job.status === 'queued' || job.status === 'running') { retainResearchJob(job.job_id); setSavedJobId(job.job_id); }
      if (job.status === 'completed') {
        const result = job.result as Record<string, unknown>;
        if (typeof result.bundle_id !== 'string' || !/^[A-Za-z0-9_-]{1,200}$/.test(result.bundle_id)
          || typeof result.run_id !== 'string' || !/^[A-Za-z0-9_-]{1,200}$/.test(result.run_id)
          || !bundles.some(item => item.bundle_id === result.bundle_id)) throw new Error('완료된 요청의 실행 ID·자료 묶음을 현재 등록 자료에서 확인하지 못했습니다. 결과를 자동으로 복원하지 않습니다.');
        setRestoreId(result.run_id);
        setJobRecoveryNotice(`서버 처리는 완료됐습니다. 이 상태 조회만으로 자료 선택·기획 결과를 복원하지 않습니다. 자료 묶음 ${result.bundle_id}를 선택한 뒤 실행 ID ${result.run_id}로 ‘불러오기’를 눌러 주세요. 결과는 기존 자료 버전·원문 범위 검사 후 표시됩니다.`);
      }
      if (job.status === 'failed') { forgetResearchJob(job.job_id); setSavedJobId(null); setError(job.error!.message); }
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
  function inspect(id: string) { setSourcesOpen(true); setInspectId(id); sourcePanel.current?.scrollIntoView({ behavior: 'auto', block: 'start' }); }
  function reuseProblem(problem: ResearchProblem) {
    setGoal(`선택한 문제의 반대 근거와 기존 제품 대응을 비교하고 개선안을 검토하기: ${problem.title}`);
    document.getElementById('research-goal')?.focus();
  }
  async function openConversation(brief: PlanningBrief) {
    if (!client.current || busyRef.current) return;
    if (brief.bundle_id !== bundle?.bundle_id) {
      const operation = begin();
      try {
        const data = await client.current.getBundle(brief.bundle_id, operation.signal);
        if (operation.current !== generation.current) return;
        setBundle(data); setBundleChoice(data.bundle_id); setSelectedSourceIds([]); setInspectId(''); selectBrief(brief);
      } catch (failure) { if (operation.current === generation.current) setError(errorMessage(failure)); }
      finally { if (operation.current === generation.current) { busyRef.current = false; setBusy(false); } }
    } else selectBrief(brief);
  }
  function newConversation() {
    if (busyRef.current) return;
    setRunChoice(''); setGoal(GOALS[0]); setConstraints([CONSTRAINTS[1]]); setExtraConstraints('');
    setSelectionMode(false); setJobProgress(null); setError(''); setConditionsOpen(false);
    document.getElementById('research-goal')?.focus();
  }
  return <div className={`research-workspace chat-workspace${sourcesOpen ? ' sources-open' : ''}`} onKeyDown={event => {
    if (event.key === 'Escape') { setSourcesOpen(false); setConditionsOpen(false); }
  }}>
    <aside className="chat-sidebar" aria-label="기획 대화 목록">
      <div className="chat-brand"><strong>KITCHEN</strong><span>상품기획 작업실</span></div>
      <button type="button" className="chat-new" disabled={busy} onClick={newConversation}>+ 새 기획</button>
      <p className="chat-list-label">기획 대화</p>
      <nav aria-label="저장된 기획 대화">{threads.length ? threads.map(item => <button type="button" key={item.run_id} disabled={busy} aria-current={selected && conversationPath(history, item).some(turn => turn.brief_id === selected.brief_id) ? 'page' : undefined} onClick={() => void openConversation(item)}><span>{item.goal}</span><small>{researchGroupLabel(item.product_group)} · 수정 {item.revision}</small></button>) : <p>기획을 시작하면 대화가<br />여기에 모입니다.</p>}</nav>
      <details className="chat-recovery"><summary>이전 기획 불러오기</summary><p>현재 연결에서 저장한 기획을 확인합니다.</p><div className="research-history-controls"><label className="sr-only" htmlFor="research-run-choice">기획 실행 선택</label><select id="research-run-choice" value={runChoice} disabled={busy} onChange={event => { const brief = history.find(item => item.run_id === event.target.value); if (brief) void openConversation(brief); }}><option value="">저장된 기획 선택</option>{history.map(item => <option key={item.run_id} value={item.run_id}>수정 {item.revision} · {item.goal}</option>)}</select><label className="sr-only" htmlFor="research-restore-id">저장된 실행 ID</label><input id="research-restore-id" value={restoreId} onChange={event => setRestoreId(event.target.value)} placeholder="저장된 기록 ID" disabled={busy} /><button type="button" className="secondary-button" disabled={busy || !bundle || !restoreId.trim()} onClick={() => void restore()}>불러오기</button></div>{(savedJobId || sharedMode) && connected ? <div aria-label="접수한 요청 상태 복구"><button type="button" className="secondary-button" disabled={busy} onClick={() => void recoverJob()}>접수한 요청 상태 확인</button>{jobRecoveryNotice ? <p>{jobRecoveryNotice}</p> : null}</div> : null}</details>
      <div className="chat-team">키친에서치킨먹기<span>LG AX 2026</span></div>
    </aside>
    <section className="chat-main" aria-label="기획 대화">
      <header className="chat-header"><div><strong>{selected ? researchGroupLabel(selected.product_group) + ' 기획' : '새 기획'}</strong><span>{bundle ? `공개 원문 ${bundle.sources.length}건` : '고객 경험에서 시작하는 기획'}</span></div><button type="button" className="chat-tool" aria-expanded={sourcesOpen} aria-controls="chat-evidence" onClick={() => setSourcesOpen(value => !value)}>{sourcesOpen ? '자료 패널 닫기' : '자료 패널 열기'}</button></header>
      <div className="chat-transcript" aria-live="polite">
        {!connected ? <section className="chat-welcome"><h1>자료 연결을 기다리고 있습니다</h1><p>{sharedConnectionState === 'unavailable' ? '잠시 후 링크를 다시 열어 주세요.' : '서버에 연결하면 실제 제품 자료를 선택할 수 있습니다.'}</p></section> : !selected ? <section className="chat-welcome"><p className="chat-kicker">고객의 말에서, 다음 제품의 경험으로</p><h1>어떤 제품 경험을 바꿔볼까요?</h1><p>실제 리뷰·질문·제품 문서로 고객의 불편을 찾고,<br />기존 기능과 비교해 개선안을 함께 다듬습니다.</p><div className="chat-starters"><ChatActionCard title="고객의 불편 찾기" description="좋았던 경험과 불편을 함께 살펴보고 아직 남은 사용 부담을 찾습니다." onClick={() => { setGoal(GOALS[0]); document.getElementById('research-goal')?.focus(); }} /><ChatActionCard title="제품 경험 개선하기" description="설치부터 첫 사용까지, 개선 전후의 장면으로 기획합니다." onClick={() => { setGoal(GOALS[1]); document.getElementById('research-goal')?.focus(); }} /></div></section> : bundle ? <>{conversationPath(history, selected).map(turn => <div className="chat-turn" key={turn.run_id}><article className="chat-user-message" aria-label={`기획 요청 ${turn.revision + 1}`}><span>나</span><p>{turn.goal}</p>{turn.constraints.length ? <small>{turn.constraints.join(' · ')}</small> : null}</article><div className="chat-assistant-message"><p className="chat-assistant-name"><span>K</span> KITCHEN <small>기획 초안</small></p>{turn.run_id === selected.run_id ? <BriefResult key={turn.run_id} brief={turn} bundle={bundle} onInspect={inspect} onReuseProblem={reuseProblem} /> : <details className="chat-previous"><summary>이전 답변 · {STATUS[turn.status]} · 개선안 {turn.concepts.length}개</summary><p>{turn.problems[0]?.description ?? '추가 자료와 미확인 사항을 확인해 주세요.'}</p><button type="button" className="chat-tool" disabled={busy} onClick={() => selectBrief(turn)}>이 버전 열기</button></details>}</div></div>)}</> : null}
        {jobProgress ? <section className="chat-progress" aria-label="접수한 기획 요청 상태" role="status"><span className={jobProgress.status === 'queued' || jobProgress.status === 'running' ? 'chat-spinner' : 'chat-progress-dot'} /><div><strong>{error && (jobProgress.status === 'queued' || jobProgress.status === 'running') ? '요청 상태 확인 중단' : jobProgress.status === 'queued' ? `요청 접수 · 대기 순서 ${jobProgress.queue_position ?? '확인 중'}` : jobProgress.status === 'running' ? '기획 생성 실행 중' : jobProgress.status === 'completed' ? '기획 요청 처리 완료' : '기획 생성 실패'}</strong><p>{jobProgress.status === 'queued' || jobProgress.status === 'running' ? '고객 원문과 기존 제품의 대응을 살펴보고 있습니다. 기다리는 동안 자료를 탐색할 수 있습니다.' : '결과와 연결된 원문을 함께 확인해 주세요.'}</p></div></section> : null}
        {error ? <div className="research-error" role="alert"><strong>요청을 완료하지 못했습니다</strong><p>{error}</p><button type="button" className="chat-tool" onClick={() => setError('')}>알림 닫기</button></div> : null}
      </div>
      <div className="chat-compose-area">
        <section className="chat-composer" aria-label="기획 요청 입력"><label className="sr-only" htmlFor="research-goal">기획 목적</label><textarea id="research-goal" rows={2} maxLength={2000} placeholder="원하는 기획이나 바꾸고 싶은 조건을 적어 주세요." value={goal} onChange={event => setGoal(event.target.value)} disabled={busy} />
          <div className="chat-compose-tools"><div><button type="button" className="chat-tool" aria-expanded={sourcesOpen} aria-controls="chat-evidence" onClick={() => setSourcesOpen(true)}>{bundle ? researchGroupLabel(bundle.product_group) + ' · 자료' : '자료 선택'}</button><button type="button" className="chat-tool" aria-expanded={conditionsOpen} aria-controls="chat-conditions" onClick={() => setConditionsOpen(value => !value)}>기획 조건{constraints.length + extraConstraints.split('\n').filter(item => item.trim()).length ? ` · ${constraints.length + extraConstraints.split('\n').filter(item => item.trim()).length}` : ''}</button></div><button type="button" className="primary-button chat-send" aria-label={busy ? '기획 중' : selected ? '조건 반영' : '기획 시작'} disabled={!connected || !bundle || busy || !goal.trim() || (!selected && selectionMode && !selectedSourceIds.length)} onClick={() => void run(selected, !selected && selectionMode)}>{busy ? '기획 중…' : selected ? '조건 반영' : '기획 시작'}<span aria-hidden="true">↑</span></button></div>
          <div className="chat-conditions" id="chat-conditions" hidden={!conditionsOpen}><label htmlFor="research-goal-choice">추천 기획 목적</label><select id="research-goal-choice" value={GOALS.includes(goal) ? goal : ''} disabled={busy} onChange={event => { if (event.target.value) setGoal(event.target.value); }}><option value="">직접 입력</option>{GOALS.map(item => <option key={item} value={item}>{item}</option>)}</select><fieldset disabled={busy}><legend>기획 제약</legend>{CONSTRAINTS.map(item => <label key={item}><input type="checkbox" checked={constraints.includes(item)} onChange={event => setConstraints(values => event.target.checked ? [...values, item] : values.filter(value => value !== item))} />{item}</label>)}<label htmlFor="research-extra-constraints">추가 조건 · 한 줄에 하나</label><textarea id="research-extra-constraints" rows={2} maxLength={4000} placeholder="예: 사용자가 직접 설정 가능" value={extraConstraints} onChange={event => setExtraConstraints(event.target.value)} /></fieldset></div>
        </section>
        <p className="chat-compose-note">{selected ? `기존 기획의 근거 범위를 유지해 조건을 반영합니다. 수정 ${selected.revision + 1}로 저장합니다.` : selectionMode ? `선택한 원문 ${selectedSourceIds.length}건으로 기획합니다.` : bundle ? `선택한 자료 묶음 전체 ${bundle.sources.length}건으로 기획합니다.` : '오른쪽에서 기획에 사용할 제품 자료를 먼저 선택해 주세요.'}</p><p className="chat-ai-note">AI가 작성한 초안입니다. 중요한 판단은 연결된 원문과 함께 확인하세요.</p>
      </div>
    </section>
    <aside id="chat-evidence" className="chat-evidence" aria-label="기획에 사용할 자료" hidden={!sourcesOpen}><header><div><h2>기획에 사용할 자료</h2><p>리뷰와 제품 문서를 살펴보세요.</p></div><button type="button" className="chat-tool" aria-label="자료 패널 닫기" onClick={() => { setSourcesOpen(false); document.getElementById('research-goal')?.focus(); }}>×</button></header>
      <div className="chat-evidence-body"><section className="chat-bundle-picker"><label htmlFor="research-bundle">제품 자료 선택</label><select id="research-bundle" value={bundleChoice} disabled={busy || !connected} onChange={event => { if (event.target.value) void chooseBundle(event.target.value); }}><option value="">제품 자료를 선택하세요</option>{bundles.map(item => <option key={item.bundle_id} value={item.bundle_id}>{item.title ?? researchGroupLabel(item.product_group)} · {bundleUsageLabel(item)} · {item.source_count ?? '—'}건</option>)}</select>{bundle ? <><p>{researchScopeLabel(bundle.analysis_scope)} · 리뷰 {bundle.sources.filter(item => item.source_type === 'review').length}건</p><label className="chat-selection-mode"><input type="checkbox" checked={selectionMode} disabled={busy || Boolean(selected)} onChange={event => setSelectionMode(event.target.checked)} />선택 원문만 사용 ({selectedSourceIds.length}건)</label>{selected ? <p>조건 변경은 기존 기획의 입력 범위를 유지합니다.</p> : null}</> : <p>냉장고 · 식기세척기 · 전자레인지<br />추가 제품군은 등록된 자료에서 선택할 수 있습니다.</p>}</section>
      {!sharedMode ? <section className="chat-auth" aria-label="실제 자료 작업실 연결">{connected ? <button type="button" className="chat-tool" onClick={disconnect}>연결 해제</button> : <form onSubmit={connect}><label htmlFor="research-token">작업실 연결</label><input id="research-token" type="password" autoComplete="off" spellCheck={false} placeholder="작업실 토큰" value={tokenInput} onChange={event => setTokenInput(event.target.value)} disabled={busy} /><button className="primary-button" type="submit" disabled={busy || !tokenInput.trim()}>{busy ? '연결 중…' : '실제 자료 연결'}</button></form>}</section> : !connected ? <div className="chat-auth" role="status">{busy || sharedConnectionState === 'checking' ? '자료 연결 중…' : <>{'연결 대기'}{sharedSession ? <button type="button" className="chat-tool" onClick={() => void connectToken(sharedSession.token)}>다시 연결</button> : null}</>}</div> : null}
      {bundle ? <ResearchSourcesPanel key={bundle.bundle_id} guideClient={client.current ?? undefined} selectedSourceIds={selectedSourceIds} onSelectionChange={setSelectedSourceIds} planningBusy={busy} bundle={bundle} brief={selected} inspectId={inspectId} onInspect={inspect} onCloseInspect={() => setInspectId('')} panelRef={sourcePanel} sourceBundleHash={bundles.find(item => item.bundle_id === bundle.bundle_id)?.bundle_sha256 ?? null} /> : <div className="chat-evidence-empty"><article><h3>원문 탐색</h3><p>자료를 선택하면 키워드로 찾고, 기획에 사용할 원문을 고를 수 있습니다.</p></article><article><h3>결과와 근거 연결</h3><p>AI 답변의 근거를 누르면 원문과 출처가 이곳에 열립니다.</p></article><p>관계 그래프와 개선 장면은 기획 결과에서 확인할 수 있습니다.</p></div>}</div>
    </aside>
  </div>;
}
