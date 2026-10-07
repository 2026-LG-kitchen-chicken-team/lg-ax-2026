import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, loadBootstrap, parseBootstrap, requestPlanning } from './api';
import { bootstrapSourceSummary, evidenceLocation, filterEvidence, friendlyError, productName, SCENARIOS } from './domain';
import type { BootstrapData, Evidence, ProductGroup, View } from './domain';
import { FIXTURE_BOOTSTRAP, FIXTURE_ORIGINAL_REQUEST, FIXTURE_PROJECT_ID, FIXTURE_RUNS } from './fixtures/planning.fixture';
import { ApplianceIcon, ArrowIcon, SearchIcon } from './icons';
import { runStatusView, sameProjectScope, useLiveWorkspace } from './liveWorkspace';
import type { WorkspaceProject } from './workspace';
import { runSources } from './judgement';
import { contractErrors, draftRunFromRequest, missingRequestQuestions, nextRequestRevision, requestChanges } from './planning';
import type { DataMode, Feature, PlanningRequest, RunSnapshot } from './planning';
import { PendingJudgement } from './PendingJudgement';
import { ReviewTrendsPanel } from './ReviewTrendsPanel';
import { ConceptsView, download, FixtureBanner, HistoryView, ModeSwitch, RequestInsights, ServerEvidenceSearch, WorkspaceBar } from './PlanningViews';
import { currentEvidenceForSnapshot } from './EvidenceTracePanel';
import type { MeasureControls } from './PlanningViews';
import { cancelMeasurement, exportMeasurements, finishMeasurement, startMeasurement } from './measurement';
import type { EditSummary, MeasurementScope, ModificationMeasurement } from './measurement';

const NAV: { id: View; label: string; number: string }[] = [
  { id: 'request', label: '기획 요청', number: '01' },
  { id: 'evidence', label: '근거 대조', number: '02' },
  { id: 'concepts', label: '콘셉트 검토', number: '03' },
  { id: 'history', label: '수정 이력', number: '04' },
  { id: 'trends', label: '리뷰 동향', number: '05' },
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
    <div className="detail-note"><span aria-hidden="true">↳</span><p>현재 등록된 원문입니다. 저장된 실행이 사용한 원문과 판단은 콘셉트 검토에서 함께 확인하세요.</p></div>
  </aside>;
}

// busy is the workspace's own in-flight state: it survives this form being re-mounted while a save is still running.
interface LiveRequestTarget { project: WorkspaceProject | null; latest: RunSnapshot | null; busy?: boolean; save: (request: PlanningRequest, continueProject: boolean) => Promise<RunSnapshot | null> }

function lines(value: string): string[] {
  return [...new Set(value.split('\n').map(item => item.trim()).filter(Boolean))];
}

function RequestView({ data, group, modelId, mode, live, trendNote = '' }: { data: BootstrapData | undefined; group: ProductGroup; modelId: string; mode: DataMode; live?: LiveRequestTarget; trendNote?: string }) {
  const scenario = SCENARIOS.find(item => item.group === group)!;
  // A connected project in this product group seeds the form, so edits become change requests on that project.
  const projectRequest = live?.project?.project.request as PlanningRequest | undefined;
  const seed = projectRequest?.product_group === group ? live?.latest?.request ?? projectRequest : undefined;
  const groupModels = (data?.products ?? []).filter(product => product.product_group === group).map(product => product.model_id);
  // A bucket carried over from the review-trend panel is appended once, visibly, so the planner can edit or remove it.
  const [prompt, setPrompt] = useState(() => { const base = seed?.improvement_task ?? scenario.prompt as string; return trendNote && !base.includes(trendNote) ? `${base}
${trendNote}` : base; });
  const [situation, setSituation] = useState(seed?.use_situation ?? scenario.situation as string);
  const [customer, setCustomer] = useState(seed?.target_customer ?? '일상에서 키친 가전을 사용하는 고객');
  const [excluded, setExcluded] = useState((seed?.exclusions ?? ['이미 있는 기능을 다시 제안하지 않기']).join('\n'));
  const [models, setModels] = useState<string[]>(seed?.model_ids ?? (modelId ? [modelId] : []));
  const [busy, setBusy] = useState(false);
  // Synchronous lock: two clicks delivered before React re-renders the disabled button must not save twice.
  const inFlight = useRef(false);
  const [result, setResult] = useState<{ code: string; message: string } | null>(null);
  const saving = busy || Boolean(live?.busy);

  const selectedModels = groupModels.length ? groupModels.filter(id => models.includes(id)) : models;
  const datasetVersion = typeof data?.manifest.version === 'string' ? data.manifest.version : '';
  const request: PlanningRequest = { product_group: group, target_customer: customer.trim(), use_situation: situation.trim(), improvement_task: prompt.trim(), exclusions: lines(excluded), model_ids: selectedModels, dataset_version: datasetVersion };
  // Without a project, the first request in this form is the original; later edits are change requests with a new revision.
  const [firstRequest] = useState<PlanningRequest>(() => request);
  const continueProject = !!(live && projectRequest && sameProjectScope(projectRequest, request));
  const datasetChanged = !!(live && projectRequest && datasetVersion && projectRequest.dataset_version !== datasetVersion);
  const original = continueProject ? projectRequest! : { ...firstRequest, model_ids: request.model_ids, dataset_version: request.dataset_version };
  const parent = continueProject ? live!.latest : null;
  // A live save that starts a new project is that project's original request: the server records revision 0.
  const newLiveProject = !!live && !continueProject;
  const revision = newLiveProject ? 0 : nextRequestRevision(original, parent, request);
  const questions = missingRequestQuestions(request);
  const changes = newLiveProject ? [] : requestChanges(parent?.request ?? original, request);
  const unchanged = continueProject && !changes.length;

  function toggleModel(id: string) {
    setModels(items => items.includes(id) ? items.filter(item => item !== id) : [...items, id]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || live?.busy) return;
    inFlight.current = true;
    setBusy(true);
    setResult(null);
    try {
      if (questions.length) {
        setResult({ code: 'NEEDS_INFO', message: questions.map(item => `${item.label}: ${item.question}`).join(' ') });
        return;
      }
      if (mode === 'fixture') {
        const errors = contractErrors('PlanningRequest', request);
        setResult(errors.length
          ? { code: 'INVALID_ARGUMENT', message: `요청을 보완해 주세요. ${errors.join('; ')}` }
          : { code: 'FIXTURE_ONLY', message: `공통 요청 규격 검사를 통과했습니다(요청 회차 ${revision}). fixture 모드라 서버에 전송하지 않았습니다.` });
        return;
      }
      if (live) {
        // Saving succeeds as a record; it is reported separately from analysis. A server without the planning runner
        // marks the run not_implemented; with it, the heading names the judgement's terminal state instead.
        const saved = await live.save(request, continueProject);
        if (saved) {
          const status = runStatusView(saved.run.status);
          const where = continueProject ? `기존 프로젝트의 변경 요청으로 저장했습니다(이전 실행 ${saved.previous_run_id ?? '없음'})` : '새 프로젝트로 저장했습니다';
          setResult({ code: SAVED_CODE[saved.run.status] ?? 'SAVED', message: `${where}. 실행 ${saved.run.id} · 요청 회차 ${saved.request_revision} · ${status.label}: ${status.detail}` });
        }
        return;
      }
      await requestPlanning(request as unknown as Record<string, unknown>);
    } catch (error) {
      setResult({ code: error instanceof ApiError ? error.code : 'UNKNOWN_ERROR', message: friendlyError(error) });
    } finally { inFlight.current = false; setBusy(false); }
  }

  const footer = live
    ? unchanged ? `이전 실행과 같은 요청입니다. 저장하면 같은 요청 회차(${revision})로 다시 기록됩니다.` : continueProject ? `“${live.project!.project.name}” 프로젝트에 변경 요청(요청 회차 ${revision})으로 저장합니다. 서버의 실행 결과는 저장 후 확인하세요.` : '새 프로젝트와 첫 실행으로 저장합니다. 제품군·검토 모델·자료 버전이 바뀌면 새 프로젝트가 됩니다.'
    : mode === 'live' ? '작업실에 연결하면 요청을 저장할 수 있습니다. 지금은 연결 확인만 합니다.' : '현재 요청은 Agent 분석 결과를 생성하지 않습니다.';

  return <div className="request-layout"><form className="request-form panel" onSubmit={submit}>
    <div className="panel-header"><div><p className="eyebrow">PLANNING BRIEF</p><h2>어떤 불편을 개선할까요?</h2></div><span className="state-badge">{mode === 'fixture' ? '화면 확인용 예시' : live ? '작업실 연결됨' : '작업실 연결 필요'}</span></div>
    <p className="section-description">고객과 사용 상황을 구체적으로 입력해 기획의 출발점을 정하세요.</p>
    {datasetChanged ? <p className="scope-notice" role="note" data-dataset-change>자료 버전이 {projectRequest!.dataset_version}에서 {datasetVersion}로 바뀌었습니다. 현재 자료로 새 프로젝트를 만들며, 이전 프로젝트와 실행 기록은 원 버전 그대로 보존합니다.</p> : null}
    <label className="field-label" htmlFor="planning-prompt">기획 요청</label><textarea id="planning-prompt" rows={4} value={prompt} onChange={event => setPrompt(event.target.value)} />
    <label className="field-label" htmlFor="planning-customer">대상 고객</label><input id="planning-customer" value={customer} onChange={event => setCustomer(event.target.value)} />
    <fieldset className="model-picker"><legend className="field-label">검토 모델 <small>기존 기능을 대조할 모델을 하나 이상 고르세요</small></legend>
      {groupModels.length ? groupModels.map(id => <label key={id} className={models.includes(id) ? 'checked' : ''}><input type="checkbox" checked={models.includes(id)} onChange={() => toggleModel(id)} />{id}<small>{productName(data!.products.find(product => product.model_id === id)!)}</small></label>) : <div className="readonly-field">자료가 연결되면 모델을 선택할 수 있습니다</div>}
    </fieldset>
    <label className="field-label" htmlFor="planning-situation">사용 상황</label><textarea id="planning-situation" rows={2} value={situation} onChange={event => setSituation(event.target.value)} />
    <label className="field-label" htmlFor="planning-excluded">제외 조건 <small>한 줄에 하나씩</small></label><textarea id="planning-excluded" rows={2} value={excluded} onChange={event => setExcluded(event.target.value)} />
    <div className="form-footer"><p>{footer}</p><button className="primary-button" type="submit" disabled={!data || saving}>{saving ? '서버 확인 중…' : mode === 'fixture' ? '요청 규격 검사' : live ? unchanged ? '같은 요청 다시 기록' : continueProject ? '변경 요청 저장' : '새 프로젝트로 저장' : '요청 연결 확인'}<ArrowIcon /></button></div>
    <PendingJudgement active={saving && mode === 'live' && Boolean(live)} action="요청 저장과 판단 실행" />
    {result ? <div className={`inline-message ${NOTICE_CODES.includes(result.code) ? 'notice' : 'error'}`} role="status" data-code={result.code}><strong>{result.code === 'NOT_IMPLEMENTED' ? '기획 실행 연결이 준비 중입니다' : result.code === 'FIXTURE_ONLY' ? '요청 규격 확인 완료(전송 안 함)' : result.code.startsWith('SAVED') ? SAVED_TITLE[result.code] ?? '요청 저장 완료' : result.code === 'NEEDS_INFO' ? '확인이 필요한 정보가 있습니다 · 저장하지 않음' : '요청을 처리하지 못했습니다'}</strong><p>{result.message}</p>{NOTICE_CODES.includes(result.code) ? null : <code>{result.code}</code>}</div> : null}
    <RequestInsights questions={questions} changes={changes} revision={revision} mode={mode} />
  </form><aside className="request-guide panel"><p className="eyebrow">WORKFLOW</p><h3>요청에서 기획안까지</h3><ol>{['자료 조회', '니즈 구조화', '기능 대조', '콘셉트 작성', '검토·수정'].map((title, index) => <li key={title}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{title}</strong><small>{index === 0 ? '원문과 자료 범위 확인' : '저장된 실행 기록에서 확인'}</small></div></li>)}</ol><p className="guide-note">분석이 연결된 서버는 최대 3개 후보를 생성하고 근거가 부족하면 보류합니다. 요청만 저장된 경우에는 분석 결과로 표시하지 않습니다.</p></aside></div>;
}

// Outcome codes that are not errors: the heading already says what happened, so the raw code chip is shown only for errors.
const NOTICE_CODES = ['NOT_IMPLEMENTED', 'FIXTURE_ONLY', 'SAVED', 'SAVED_NOT_IMPLEMENTED', 'SAVED_COMPLETED', 'SAVED_HELD', 'NEEDS_INFO'];

// The save heading says what the server actually did: stored a request only, or ran the judgement to a terminal state.
const SAVED_CODE: Record<string, string> = { not_implemented: 'SAVED_NOT_IMPLEMENTED', completed: 'SAVED_COMPLETED', held: 'SAVED_HELD', failed: 'SAVED_FAILED' };
const SAVED_TITLE: Record<string, string> = {
  SAVED_NOT_IMPLEMENTED: '요청 저장 완료 · 분석 결과 아님',
  SAVED_COMPLETED: '요청 저장 · 판단 완료(계약 검사 통과 · 의미 미검증)',
  SAVED_HELD: '요청 저장 · 판단 보류(후보 없음)',
  SAVED_FAILED: '요청 저장 · 판단 실패',
};

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
  // Bumped only when the user connects or switches project, so the request form reseeds without losing a save result.
  const [formSeed, setFormSeed] = useState(0);
  const [trendNote, setTrendNote] = useState('');
  // The fixture goes through the same contract parser as live responses, so a broken fixture fails loudly.
  const fixtureState = useMemo<DataState>(() => {
    try { return { status: 'ready', data: parseBootstrap({ ok: true, data: FIXTURE_BOOTSTRAP }) }; } catch (error) {
      return { status: 'error', message: friendlyError(error), code: error instanceof ApiError ? error.code : 'UNKNOWN_ERROR' };
    }
  }, []);

  useEffect(() => {
    if (mode !== 'live') return;
    const controller = new AbortController();
    let current = true;
    setState({ status: 'loading' });
    loadBootstrap(controller.signal).then(data => {
      if (current) setState({ status: 'ready', data });
    }).catch(error => {
      if (!current || error instanceof Error && error.name === 'AbortError') return;
      setState({ status: 'error', message: friendlyError(error), code: error instanceof ApiError ? error.code : 'UNKNOWN_ERROR' });
    });
    return () => { current = false; controller.abort(); };
  }, [mode, reload]);

  const workspace = useLiveWorkspace();
  // Authenticated sources belong to this login. A missing/private bootstrap is never replaced by the public demo.
  const active: DataState = mode === 'fixture' ? fixtureState
    : workspace.connection === 'connected' && workspace.bootstrap ? { status: 'ready', data: workspace.bootstrap }
    : workspace.connection === 'connecting' ? { status: 'loading' }
    : workspace.connection === 'error' ? { status: 'error', message: workspace.error?.action ?? '작업실 자료 연결을 다시 확인해 주세요.', code: workspace.error?.code ?? 'CONNECTION_FAILED' }
    : state;
  const data = active.status === 'ready' ? active.data : undefined;
  const visibleQuery = mode === 'live' && (workspace.connection === 'connecting' || workspace.connection === 'error') ? '' : query;
  const visibleTrendNote = mode === 'live' && workspace.connection === 'connected' ? trendNote : '';
  useEffect(() => {
    if (mode === 'live' && workspace.connection !== 'connected') {
      setTrendNote(''); setQuery(''); setSelectedId(''); setModelChoice('');
    }
  }, [mode, workspace.connection]);
  const runs = mode === 'fixture' ? [...FIXTURE_RUNS, ...drafts] : workspace.runs;
  const selectedRun = runs.find(item => item.run.id === runChoice) ?? runs[runs.length - 1];
  // A stored planning run quotes the sources and features its judgement actually received, ahead of the bootstrap data.
  const runScope = runSources(selectedRun, (data?.features ?? []) as unknown as Feature[], data?.evidence ?? []);
  const planningProps = { mode, runs, selected: selectedRun, onSelect: selectRun, features: runScope.features, evidence: runScope.evidence,
    currentEvidence: mode === 'fixture' ? data?.evidence : currentEvidenceForSnapshot(data, selectedRun) };
  const originalRequest = mode === 'fixture' ? FIXTURE_ORIGINAL_REQUEST : workspace.project?.project.request as PlanningRequest | undefined;
  // R4 (record 041): a selected live project fixes the product scope. The group/model used to stay at the default
  // fridge/FRIDGE-A for a microwave project, so the evidence, trend and request views showed another product's scope
  // and a "continue this project" request could carry it. Sync once per project; the planner can still change it after.
  const projectScope = mode === 'live' && originalRequest ? `${workspace.project?.project.id}|${originalRequest.product_group}|${originalRequest.model_ids.join(',')}` : '';
  useEffect(() => {
    if (!projectScope || !originalRequest) return;
    setGroup(originalRequest.product_group as ProductGroup);
    setModelChoice(originalRequest.model_ids[0] ?? '');
    setSelectedId('');
  }, [projectScope]);
  // Expiry/reconnect must discard private form state. Connected project creation also changes scopeVersion,
  // but must keep its in-flight form mounted so the successful save result and entered request remain visible.
  const requestConnectionKey = mode === 'live' && workspace.connection !== 'connected' ? `${workspace.connection}-${workspace.scopeVersion}` : 'connected';

  const [measurements, setMeasurements] = useState<ModificationMeasurement[]>([]);
  const [measureError, setMeasureError] = useState('');
  const measurementSequence = useRef(0);
  const measurementGeneration = useRef(0);
  useEffect(() => () => { measurementGeneration.current += 1; }, []);
  const projectId = mode === 'fixture' ? FIXTURE_PROJECT_ID : workspace.project?.project.id ?? '';
  const projectOwner = mode === 'fixture' ? null : workspace.project?.owner_id ?? null;
  // scopeVersion changes on reconnect as well as project changes. Project owner is not an authenticated participant identity.
  const scopeId = JSON.stringify([mode, mode === 'fixture' ? 0 : workspace.scopeVersion, projectId, projectOwner,
    mode === 'fixture' ? null : workspace.project?.dataset_sha256, mode === 'fixture' ? null : workspace.project?.document_versions]);
  const measurementScope = useMemo<MeasurementScope>(() => ({ scope_id: scopeId, project_id: projectId, project_owner_id: projectOwner }), [scopeId, projectId, projectOwner]);
  const currentMeasurementScope = useRef(measurementScope);
  const currentMeasurements = measurements.filter(item => item.mode === mode && item.scope?.scope_id === scopeId);
  useEffect(() => {
    if (currentMeasurementScope.current.scope_id !== scopeId) invalidateMeasurements();
    currentMeasurementScope.current = measurementScope;
  }, [scopeId, measurementScope]);
  useEffect(() => {
    // Account reconnect, expiry and disconnect must not retain private goals from the previous connection.
    if (mode === 'live' && workspace.connection !== 'connected') setMeasurements([]);
    setMeasureError('');
  }, [mode, workspace.connection]);
  useEffect(() => {
    const now = new Date();
    setMeasurements(items => items.map(item => item.status === 'running' && (item.scope?.scope_id !== scopeId || item.base_run_id !== selectedRun?.run.id)
      ? cancelMeasurement(item, now) : item));
  }, [scopeId, selectedRun?.run.id]);

  function invalidateMeasurements(clear = false) {
    measurementGeneration.current += 1;
    const now = new Date();
    setMeasurements(items => clear ? [] : items.map(item => item.status === 'running' ? cancelMeasurement(item, now) : item));
    setMeasureError('');
  }

  function selectRun(id: string) {
    if (id !== selectedRun?.run.id) invalidateMeasurements();
    setRunChoice(id);
  }

  // Invalidate before waiting for the hook's asynchronous operations, rather than after their response arrives.
  const scopedWorkspace = {
    ...workspace,
    async connect(token: string) { invalidateMeasurements(true); setRunChoice(''); setTrendNote(''); await workspace.connect(token); },
    disconnect() { invalidateMeasurements(true); setRunChoice(''); setTrendNote(''); workspace.disconnect(); },
    async selectProject(id: string) { invalidateMeasurements(); setRunChoice(''); setTrendNote(''); await workspace.selectProject(id); },
  };

  const measure: MeasureControls = {
    records: currentMeasurements, error: measureError,
    start(goal, baseRunId) {
      try {
        if (!projectId || baseRunId !== selectedRun?.run.id || mode === 'live' && workspace.connection !== 'connected') {
          throw new ApiError('INVALID_ARGUMENT', '현재 프로젝트의 기준 실행을 선택해 주세요.');
        }
        if (currentMeasurements.some(item => item.status === 'running')) throw new ApiError('INVALID_ARGUMENT', '진행 중인 측정을 먼저 취소해 주세요.');
        const started = startMeasurement(goal, baseRunId, mode, `MEASURE-${++measurementSequence.current}`, new Date(), measurementScope);
        setMeasurements(items => [...items, started]); setMeasureError('');
      } catch (failure) { setMeasureError(friendlyError(failure)); }
    },
    cancel() { setMeasurements(items => items.map(item => item.status === 'running' && item.scope?.scope_id === scopeId ? cancelMeasurement(item, new Date()) : item)); },
    exportRecords() { download(`modification-time-${new Date().toISOString().slice(0, 10)}.json`, 'application/json', `${JSON.stringify(exportMeasurements(currentMeasurements, new Date().toISOString()), null, 2)}\n`); },
  };

  async function rerun(request: PlanningRequest, edits: EditSummary) {
    if (!selectedRun) return;
    const base = selectedRun;
    const generation = measurementGeneration.current;
    const completion = { mode, base_run_id: base.run.id, scope: measurementScope };
    const current = () => generation === measurementGeneration.current && completion.scope.scope_id === currentMeasurementScope.current.scope_id;
    // Keep the captured base selected while the hook appends a saved run; its implicit latest-run fallback must not switch mid-request.
    setRunChoice(base.run.id);
    let resultId: string;
    if (mode === 'fixture') {
      const draft = draftRunFromRequest(base, FIXTURE_ORIGINAL_REQUEST, request, `RUN-DRAFT-${runs.length + 1}`, new Date().toISOString());
      setDrafts(items => [...items, draft]);
      resultId = draft.run.id;
    } else {
      const saved = await workspace.addRun(request, base.run.id);
      if (!current()) return;
      if (!saved) throw new ApiError('REQUEST_FAILED', '새 실행을 저장하지 못했습니다. 위쪽 작업실 안내를 확인해 주세요.');
      if (saved.run.project_id !== completion.scope.project_id || saved.previous_run_id !== base.run.id) {
        throw new ApiError('CONTRACT_MISMATCH', '새 실행과 측정의 프로젝트·기준 실행이 다릅니다.');
      }
      resultId = saved.run.id;
    }
    if (!current()) return;
    // The measurement stops only after the rerun is actually saved; a failed save leaves it running.
    const ended = new Date();
    const completed = new Map<string, ModificationMeasurement>();
    for (const item of currentMeasurements) {
      if (item.status !== 'running' || item.base_run_id !== base.run.id) continue;
      try { completed.set(item.measurement_id, finishMeasurement(item, resultId, edits, ended, completion)); }
      catch (failure) { completed.set(item.measurement_id, cancelMeasurement(item, ended)); setMeasureError(friendlyError(failure)); }
    }
    setMeasurements(items => items.map(item => item.status === 'running' ? completed.get(item.measurement_id) ?? item : item));
    setRunChoice(resultId);
  }
  const products = data?.products.filter(product => product.product_group === group) ?? [];
  const modelId = products.some(product => product.model_id === modelChoice) ? modelChoice : products[0]?.model_id ?? '';
  const allModelEvidence = data?.evidence.filter(item => item.model_id === modelId) ?? [];
  const visibleEvidence = modelId ? filterEvidence(data?.evidence ?? [], { modelId, query: visibleQuery, type }) : [];
  const selected = visibleEvidence.find(item => item.id === selectedId) ?? visibleEvidence[0];
  const currentNav = NAV.find(item => item.id === view)!;

  function selectGroup(next: ProductGroup) {
    if (mode === 'fixture' && next !== FIXTURE_ORIGINAL_REQUEST.product_group) return;
    setGroup(next); setModelChoice(''); setSelectedId(''); setQuery(''); setType('all');
  }

  function changeMode(next: DataMode) {
    if (next === mode) return;
    // Invalidate pending live chains before fixture actions become available.
    // A request already sent to the server cannot be rolled back by a mode switch.
    invalidateMeasurements(true);
    if (next === 'fixture') workspace.disconnect();
    setMode(next);
    setGroup(next === 'fixture' ? FIXTURE_ORIGINAL_REQUEST.product_group : 'fridge');
    setModelChoice(next === 'fixture' ? FIXTURE_ORIGINAL_REQUEST.model_ids[0] : '');
    setSelectedId(''); setQuery(''); setType('all'); setRunChoice('');
    setTrendNote('');
    setFormSeed(value => value + 1);
    // Cached live data is not displayed as the result of a fresh connection check.
    if (next === 'live') setState({ status: 'loading' });
  }

  return <div className="workspace">
    <a href="#main-content" className="skip-link">본문으로 이동</a>
    <aside className="sidebar">
      <div className="brand"><img className="brand-icon" src="/kitchen-evidence-icon.png" alt="" width="44" height="44" decoding="async" aria-hidden="true" /><div><strong>KITCHEN</strong><span>PLANNING WORKSPACE</span></div></div>
      <div className="sidebar-project"><span className="eyebrow">LG AX HACKATHON</span><strong>키친 상품기획 Agent</strong><span>키친에서치킨먹기</span></div>
      <nav aria-label="기획 작업 영역">{NAV.map(item => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} aria-current={view === item.id ? 'page' : undefined} onClick={() => setView(item.id)}><span className="nav-number">{item.number}</span>{item.label}{view === item.id ? <ArrowIcon /> : null}</button>)}</nav>
      <div className="sidebar-lower"><p>고객의 말에서<br /><strong>새로운 기회의 근거로.</strong></p><div className="sidebar-stage"><span className="status-dot" />개발 프레임워크 · v0.1</div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">상품기획 작업실<span>/</span><strong>{currentNav.label}</strong></div><div className="topbar-right"><ModeSwitch mode={mode} onChange={changeMode} /><div className="connection-status">{mode === 'fixture' ? <><span className="status-dot loading" />fixture 사용 · 공통 API 요청 안 함</> : <><span className={`status-dot ${active.status}`} />{active.status === 'ready' ? workspace.connection === 'connected' ? '인증된 작업실 자료 연결됨' : '공통 API 연결됨' : active.status === 'loading' ? '자료 API 연결 확인 중' : '자료 API 연결 오류'}</>}</div></div></header>
      <main id="main-content">
        <section className="hero"><div><p className="eyebrow">EVIDENCE-LED KITCHEN PLANNING</p><h1>근거에서 시작하는<br />키친 기획.</h1><p>고객의 불편과 제품의 기능을 함께 살펴보고,<br className="desktop-break" /> 아직 해결되지 않은 기회를 검토하는 작업실입니다.</p></div><div className="hero-stats"><div><strong>{data?.products.length ?? '—'}</strong><span>등록된 모델</span></div><div><strong>{data?.evidence.length ?? '—'}</strong><span>조회 가능한 근거</span></div><p>{mode === 'fixture' ? `계약 fixture · FRIDGE-A 예시만 포함` : data ? `공통 계약 ${data.contract_version} · ${bootstrapSourceSummary(data)}` : '공통 API에서 자료를 불러옵니다'}</p></div></section>
        {mode === 'fixture' ? <FixtureBanner /> : <WorkspaceBar workspace={scopedWorkspace} onScopeChange={() => setFormSeed(value => value + 1)} />}
        <section className="scenario-grid" aria-label="제품군 선택">{SCENARIOS.map(scenario => {
          const unavailable = mode === 'fixture' && scenario.group !== FIXTURE_ORIGINAL_REQUEST.product_group;
          return <button key={scenario.group} disabled={unavailable} onClick={() => selectGroup(scenario.group)} className={`scenario-card ${group === scenario.group ? 'selected' : ''}`} aria-pressed={group === scenario.group}><ApplianceIcon kind={scenario.group} /><span className="scenario-copy"><strong>{scenario.title}</strong><span>{scenario.subtitle}</span></span><span className="scenario-count">{unavailable ? 'fixture 미제공' : data ? `${data.products.filter(product => product.product_group === scenario.group).length}개 모델` : '연결 대기'}</span></button>;
        })}</section>
        {active.status === 'error' ? <div className="api-error" role="alert"><div><strong>자료를 불러오지 못했습니다</strong><p>{active.message}</p><code>{active.code}</code></div><button className="secondary-button" onClick={() => setReload(value => value + 1)}>다시 연결</button></div> : null}
        <div className="section-top"><div><p className="eyebrow">{currentNav.number} / WORKSPACE</p><h2>{currentNav.label}</h2></div><div className="model-select"><label htmlFor="product-model">검토 모델</label><select id="product-model" value={modelId} disabled={!products.length} onChange={event => { setModelChoice(event.target.value); setSelectedId(''); }}>{products.length ? products.map(product => <option key={product.model_id} value={product.model_id}>{product.model_id} · {productName(product)}</option>) : <option value="">자료 연결 대기</option>}</select></div></div>
        {view === 'evidence' ? <section className="evidence-workspace panel">
          <div className="evidence-toolbar"><div className="evidence-types" aria-label="근거 유형 필터">{[{ value: 'all', label: '전체' }, { value: 'review', label: '고객 리뷰' }, { value: 'manual', label: '제품 설명서' }].map(option => <button key={option.value} className={type === option.value ? 'active' : ''} aria-pressed={type === option.value} onClick={() => { setType(option.value); setSelectedId(''); }}>{option.label}<span>{option.value === 'all' ? allModelEvidence.length : allModelEvidence.filter(item => item.source_type === option.value).length}</span></button>)}</div><label className="search-field"><SearchIcon /><span className="sr-only">근거 검색</span><input type="search" placeholder="근거에서 검색" value={visibleQuery} onChange={event => { setQuery(event.target.value); setSelectedId(''); }} /></label></div>
          <div className="evidence-columns"><div className="evidence-list"><div className="list-caption"><span>원문과 제품 기능</span><span>{visibleEvidence.length}개 근거</span></div>
            {active.status === 'loading' ? <div className="loading-state" role="status"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /><p>공통 API에서 근거를 불러오는 중입니다…</p></div> : !data ? <EmptyState title="API 연결이 필요합니다" text="서버가 연결되면 실제 자료와 근거를 확인할 수 있습니다." /> : !visibleEvidence.length ? <EmptyState title={allModelEvidence.length ? '검색 결과가 없습니다' : '등록된 근거가 없습니다'} text={allModelEvidence.length ? '검색어 또는 자료 유형을 바꿔 보세요.' : '이 모델에 리뷰와 제품 문서를 등록하면 여기에 표시됩니다.'} /> : <ul>{visibleEvidence.map(item => <li key={item.id}><button className={`evidence-card ${selected?.id === item.id ? 'selected' : ''}`} aria-pressed={selected?.id === item.id} onClick={() => setSelectedId(item.id)}><div className="evidence-card-top"><SourceBadge type={item.source_type} /><span>{evidenceLocation(item)}</span></div><p>{item.text}</p><div className="evidence-card-bottom"><span>{item.model_id} · {item.document_version}</span><ArrowIcon /></div></button></li>)}</ul>}
          </div><EvidenceDetail selected={selected} features={data?.features ?? []} /></div>
          <footer className="evidence-footer"><span className={`status-dot ${active.status}`} /><p>{data ? '원문과 모델별 필터를 조회합니다. 판단에 사용된 근거는 각 저장된 실행에서 확인하세요.' : '자료 API가 연결되면 원문을 조회할 수 있습니다.'}</p></footer>
        </section> : view === 'trends' ? <ReviewTrendsPanel mode={mode} workspace={workspace} data={data} modelId={modelId} productGroup={group} onUseInPlanning={(note, model) => {
          const product = data?.products.find(item => item.model_id === model);
          if (product && product.product_group !== group) { setGroup(product.product_group as ProductGroup); setModelChoice(model); }
          setTrendNote(note); setFormSeed(value => value + 1); setView('request');
        }} /> : view === 'request' ? <RequestView key={`${group}-${mode}-${formSeed}-${requestConnectionKey}`} data={data} group={group} modelId={modelId} mode={mode} trendNote={mode === 'fixture' ? trendNote : visibleTrendNote} live={mode === 'live' && workspace.connection === 'connected' ? { project: workspace.project, latest: workspace.runs[workspace.runs.length - 1] ?? null, busy: workspace.busy, save: (request, continueProject) => {
          invalidateMeasurements(); setRunChoice('');
          return continueProject ? workspace.addRun(request, workspace.runs[workspace.runs.length - 1]?.run.id ?? null) : workspace.saveRequest(request, data?.products ?? []);
        } } : undefined} /> : selectedRun && originalRequest && view === 'concepts' ? <ConceptsView {...planningProps} selected={selectedRun} /> : selectedRun && originalRequest ? <HistoryView {...planningProps} selected={selectedRun} original={originalRequest} onRerun={rerun} busy={workspace.busy} measure={measure} /> : view === 'concepts' ? <section className="panel future-panel"><EmptyState type="future" title="근거를 갖춘 콘셉트를 이곳에서 검토합니다" text="작업실에 연결하고 기획 요청을 저장하면 실행 결과를 확인할 수 있습니다. 요청만 저장됐거나 분석이 보류된 경우에는 후보를 표시하지 않습니다." /><div className="future-columns"><div><strong>콘셉트 비교</strong><span>최대 3개 타당한 후보 · 근거 부족 시 보류</span></div><div><strong>요구사항 확인</strong><span>연결된 원문 · 남은 불편 · 검토할 조건</span></div><div><strong>기획자 검토</strong><span>선택 · 수정 요청 · 추가 조건</span></div></div></section> : <section className="panel future-panel"><EmptyState type="future" title="아직 실행·수정 이력이 없습니다" text="작업실에 연결하면 동일 기획의 저장된 실행과 변경 전후, 사용한 자료 버전을 확인할 수 있습니다." /><div className="history-plan"><span>기획 요청</span><ArrowIcon /><span>근거·판단 기록</span><ArrowIcon /><span>새 자료로 재검토</span><ArrowIcon /><span>변경 전후 비교</span></div></section>}
        {mode === 'live' && view === 'evidence' && workspace.connection === 'connected' ? <ServerEvidenceSearch workspace={workspace} modelId={modelId} /> : null}
        {mode === 'live' && (view === 'concepts' || view === 'history') && !selectedRun ? <p className="hint">{workspace.connection === 'connected' ? '저장된 실행 기록이 없습니다. 기획 요청에서 작업실에 저장하면 여기에 표시됩니다.' : '작업실 서버에 연결하면 저장된 실제 실행 기록을 불러옵니다. 화면 예시는 상단의 계약 fixture에서 볼 수 있습니다.'}</p> : null}
        <footer className="page-footer"><span>키친에서치킨먹기 · LG AX 2026</span><span>반복 가능한 상품기획을 위한 첫 작업 공간</span></footer>
      </main>
    </div>
  </div>;
}
