import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError } from './api';
import { evidenceLocation } from './domain';
import type { Evidence } from './domain';
import { ExecutionPanel } from './JudgementViews';
import { reasonText, rerunBaseNotice, selectableConcepts } from './judgement';
import { runStatusView } from './liveWorkspace';
import { editSummary, END_RULE, START_RULE } from './measurement';
import type { EditSummary, ModificationMeasurement } from './measurement';
import type { ErrorView, EvidenceSearch, LiveWorkspace } from './liveWorkspace';
import {
  buildComparison, buildExport, buildRerunRequest, candidateChoicesFor, conceptDetailChanges, exportMarkdown, FIXTURE_NOTICE, heldItems,
  nextRequestRevision, requestChanges, scopeWarnings, scopeWarningText, splitConditions, statusLabel,
} from './planning';
import type { CandidateChoice, Concept, ConceptTextChange, DataMode, Feature, MissingQuestion, PlanningRequest, RequestChange, RunSnapshot } from './planning';
import { ArrowIcon, SearchIcon } from './icons';
import './planning.css';

export function ErrorBox({ error, onClose }: { error: ErrorView; onClose?: () => void }) {
  return <div className={`inline-message ${error.tone}`} role={error.tone === 'error' ? 'alert' : 'status'}>
    <strong>{error.title}</strong><p>{error.action}</p><code>{error.code}</code>
    {onClose ? <button type="button" className="text-button" onClick={onClose}>닫기</button> : null}
  </div>;
}

/** Live-mode connection bar: token input (memory only), connection state and project choice. */
export function WorkspaceBar({ workspace, onScopeChange }: { workspace: LiveWorkspace; onScopeChange: () => void }) {
  const [token, setToken] = useState('');
  const connected = workspace.connection === 'connected';
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await workspace.connect(token);
    setToken('');
    onScopeChange();
  }
  async function choose(id: string) {
    await workspace.selectProject(id);
    onScopeChange();
  }
  return <section className="panel workspace-bar" aria-label="작업실 서버 연결">
    <div className="workspace-bar-row">
      <div className="workspace-state"><span className={`status-dot ${connected ? 'ready' : workspace.connection === 'error' ? 'error' : 'loading'}`} /><div><strong>작업실 서버</strong><small>{connected ? `연결됨 · 프로젝트 ${workspace.projects.length}개` : workspace.connection === 'connecting' ? '연결 중…' : workspace.connection === 'error' ? '연결 오류' : '미연결 · 요청 저장과 실행 기록에는 연결이 필요합니다'}</small></div></div>
      {connected ? <div className="workspace-actions">
        <label className="run-picker">프로젝트<select value={workspace.project?.project.id ?? ''} disabled={workspace.busy || !workspace.projects.length} onChange={event => choose(event.target.value)}>
          {workspace.projects.length ? workspace.projects.map(item => <option key={item.project.id} value={item.project.id}>{item.project.name}</option>) : <option value="">저장된 프로젝트 없음</option>}
        </select></label>
        <button type="button" className="secondary-button" onClick={() => { workspace.disconnect(); onScopeChange(); }}>연결 해제</button>
      </div> : <form className="workspace-actions" onSubmit={submit}>
        <label className="sr-only" htmlFor="workspace-token">작업실 토큰</label>
        <input id="workspace-token" type="password" autoComplete="off" spellCheck={false} placeholder="작업실 토큰 (메모리에만 보관)" value={token} onChange={event => setToken(event.target.value)} />
        <button className="primary-button" type="submit" disabled={!token.trim() || workspace.busy}>연결<ArrowIcon /></button>
      </form>}
    </div>
    {workspace.project ? <dl className="run-meta project-meta">
      <div><dt>고정 문서 버전</dt><dd>{Object.entries(workspace.project.document_versions).map(([model, version]) => `${model} ${version}`).join(', ')}</dd></div>
      <div><dt>자료 버전</dt><dd>{workspace.project.project.dataset_version} · <span className="mono" title={workspace.project.dataset_sha256}>{workspace.project.dataset_sha256.slice(0, 12)}…</span></dd></div>
      <div><dt>소유자</dt><dd>{workspace.project.owner_id}</dd></div>
      <div><dt>생성</dt><dd>{workspace.project.created_at}</dd></div>
    </dl> : null}
    {workspace.error ? <ErrorBox error={workspace.error} onClose={workspace.clearError} /> : null}
  </section>;
}

/** Server-side search within the project's fixed document versions; an empty result is not an error. */
export function ServerEvidenceSearch({ workspace, modelId }: { workspace: LiveWorkspace; modelId: string }) {
  const project = workspace.project;
  const scope = JSON.stringify([workspace.scopeVersion, project?.owner_id, project?.project.id,
    project?.dataset_sha256, modelId, project?.document_versions[modelId]]);
  return <ScopedEvidenceSearch key={scope} workspace={workspace} modelId={modelId} />;
}

function ScopedEvidenceSearch({ workspace, modelId }: { workspace: LiveWorkspace; modelId: string }) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<EvidenceSearch | null>(null);
  const mounted = useRef(false);
  const searchSequence = useRef(0);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; searchSequence.current += 1; };
  }, []);
  const project = workspace.project;
  const inScope = !!project && modelId in project.document_versions;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const sequence = ++searchSequence.current;
    setResult(null);
    const found = await workspace.search(query.trim(), modelId);
    if (mounted.current && sequence === searchSequence.current) setResult(found);
  }
  return <section className="panel planning-panel server-search" aria-label="프로젝트 범위 서버 검색">
    <div className="planning-head"><div><p className="eyebrow">PROJECT SCOPE</p><h3>프로젝트 고정 범위 서버 검색</h3></div>
      <form className="condition-row" onSubmit={submit}><label className="search-field"><SearchIcon /><span className="sr-only">서버 근거 검색</span><input type="search" placeholder="예: 청소" value={query} onChange={event => setQuery(event.target.value)} /></label><button className="secondary-button" type="submit" disabled={!inScope || !query.trim() || workspace.busy}>서버 검색</button></form>
    </div>
    {!project ? <p className="muted">작업실에 연결하고 프로젝트를 선택하면 고정된 문서 버전 안에서만 검색합니다.</p>
      : !inScope ? <p className="muted">{modelId} 모델은 선택한 프로젝트의 검토 범위({Object.keys(project.document_versions).join(', ')})가 아닙니다.</p>
      : !result ? <p className="muted">{modelId} · 문서 {project.document_versions[modelId]}로 고정해 검색합니다.</p>
      : <>
        <p className="hint">“{result.query}” · {result.modelId} · 문서 {result.documentVersion ?? '전체'} · {result.total}건 · 방식 {result.method}</p>
        {result.items.length ? <ul className="server-results">{result.items.map(item => <li key={item.id}><span className="id">{item.id} · {sourceKindLabel(item.source_kind)} · {item.source_type === 'review' ? '고객 리뷰' : '제품 설명서'} ·{item.locator.row ? `${item.locator.row}행` : item.locator.page ? `${item.locator.page}쪽` : item.locator.section}</span>{item.text}</li>)}</ul>
          : <p className="muted">검색 결과가 없습니다. 서버는 정상 응답했으며, 이 문서 버전에 일치하는 원문이 없습니다.</p>}
      </>}
  </section>;
}

export function ModeSwitch({ mode, onChange }: { mode: DataMode; onChange: (mode: DataMode) => void }) {
  return <div className="mode-switch" role="group" aria-label="데이터 출처">
    {([['live', '실제 서버'], ['fixture', '계약 fixture']] as const).map(([value, label]) => <button key={value} className={mode === value ? 'active' : ''} aria-pressed={mode === value} onClick={() => onChange(value)}>{label}</button>)}
  </div>;
}

export function FixtureBanner() {
  return <div className="fixture-banner" role="note"><strong>모의 데이터 모드</strong><p>{FIXTURE_NOTICE} 서버에 아무것도 저장하거나 전송하지 않습니다.</p></div>;
}

const SOURCE_KINDS: Record<string, string> = { synthetic: '합성자료', public: '공개자료', licensed: '이용허락 자료', private: '비공개 자료' };

/** Real vs synthetic origin stays visible wherever a source is quoted. */
export function sourceKindLabel(kind: string): string {
  return SOURCE_KINDS[kind] ?? kind;
}

/** Inline citation: shows the original text, location and version without leaving the current view. */
function EvidenceRef({ id, evidence }: { id: string; evidence: Map<string, Evidence> }) {
  const [open, setOpen] = useState(false);
  const item = evidence.get(id);
  if (!item) return <span className="evidence-ref missing" title="원문을 찾을 수 없습니다">{id} · 자료 누락</span>;
  return <span className="evidence-ref-wrap">
    <button type="button" className={`evidence-ref ${item.source_type}`} aria-expanded={open} onClick={() => setOpen(value => !value)}>{id}</button>
    {open ? <span className="evidence-pop" role="note"><q>{item.text}</q><small>{sourceKindLabel(item.source_kind)} · {item.model_id} · 문서 {item.document_version} · {evidenceLocation(item)} · {item.source_id}</small></span> : null}
  </span>;
}

function Refs({ ids, evidence }: { ids: string[]; evidence: Map<string, Evidence> }) {
  return ids.length ? <span className="refs">{ids.map(id => <EvidenceRef key={id} id={id} evidence={evidence} />)}</span> : <span className="muted">없음</span>;
}

export function RequestInsights({ questions, changes, revision, mode }: { questions: MissingQuestion[]; changes: RequestChange[]; revision: number; mode: DataMode }) {
  return <div className="request-insights">
    <section aria-label="부족한 정보">
      <h4>Agent가 확인할 질문 <span>{questions.length}</span></h4>
      {questions.length ? <ul className="question-list">{questions.map(item => <li key={item.field}><strong>{item.label}</strong>{item.question}</li>)}</ul> : <p className="muted">필수 정보가 모두 입력되었습니다.</p>}
    </section>
    <section aria-label="변경 요청">
      <h4>원 요청 대비 변경 <span>요청 회차 {revision}</span></h4>
      {changes.length ? <table className="change-table"><thead><tr><th>항목</th><th>원 요청</th><th>변경</th></tr></thead><tbody>{changes.map(item => <tr key={item.field}><th>{item.label}</th><td>{item.before}</td><td>{item.after}</td></tr>)}</tbody></table> : <p className="muted">원 요청과 같습니다. 변경하면 새 회차로 기록됩니다.</p>}
      {mode === 'fixture' ? <p className="hint">fixture 모드에서는 회차 계산만 보여 주며 서버에 저장하지 않습니다.</p> : null}
    </section>
  </div>;
}

function ComparisonTable({ snapshot, features, evidence }: { snapshot: RunSnapshot; features: Feature[]; evidence: Map<string, Evidence> }) {
  if (!snapshot.output) return <p className="muted pad">이 실행에는 대조 결과가 없습니다. {runStatusView(snapshot.run.status).detail}</p>;
  const rows = buildComparison(snapshot.output, features, [...evidence.values()]);
  return <div className="table-scroll"><table className="comparison-table">
    <thead><tr><th>모델</th><th>고객 불편</th><th>연결된 기존 기능</th><th>기능 조건</th><th>판단</th><th>남은 불편</th><th>근거</th><th>확인할 질문</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.need.id}>
      <td className="model-cell">{row.need.model_id}</td>
      <td><span className="id">{row.need.id}</span><strong>{row.need.pain}</strong><small>{row.need.situation}</small></td>
      <td>{row.features.length ? row.features.map(item => <span key={item.id} className="feature-chip" title={item.description}>{item.name}<small>{item.id} · 문서 {item.document_version}</small></span>) : <span className="muted">없음</span>}</td>
      <td>{row.conditions.length ? row.conditions.join(', ') : <span className="muted">없음</span>}</td>
      <td><span className={`status-pill ${row.gap?.support_status ?? 'none'}`}>{statusLabel(row.gap?.support_status ?? null)}</span></td>
      <td>{row.gap?.remaining_pain || <span className="muted">-</span>}</td>
      <td><Refs ids={row.evidence.map(item => item.id)} evidence={evidence} />{row.missingIds.length ? <span className="missing-note">누락: {row.missingIds.join(', ')}</span> : null}</td>
      <td>{[...row.need.uncertainties, ...(row.gap?.questions ?? [])].map(text => <p key={text} className="question">{text}</p>)}</td>
    </tr>)}</tbody>
  </table></div>;
}

export function download(name: string, type: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = name; link.click();
  URL.revokeObjectURL(url);
}

function ExportActions({ mode, snapshot, features, evidence, runs }: { mode: DataMode; snapshot: RunSnapshot; features: Feature[]; evidence: Evidence[]; runs: RunSnapshot[] }) {
  // The completeness check runs on the same document that will be downloaded, so the badge and the file always agree.
  const check = buildExport(mode, snapshot, features, evidence, '', runs).completeness;
  const missingCount = Object.values(check).filter(Array.isArray).reduce((sum: number, list) => sum + (list as string[]).length, 0);
  function exportAs(format: 'json' | 'md') {
    const doc = buildExport(mode, snapshot, features, evidence, new Date().toISOString(), runs);
    const base = `${snapshot.run.id}${mode === 'fixture' ? '-fixture' : ''}`;
    if (format === 'json') download(`${base}.json`, 'application/json', `${JSON.stringify(doc, null, 2)}\n`);
    else download(`${base}.md`, 'text/markdown', exportMarkdown(doc));
  }
  return <div className="export-actions"><span className={`export-check ${check.complete ? 'ok' : 'missing'}`} title="선택 실행의 요청·후보·근거 원문·요구사항·가정·보류·계보와 내보내기 내용의 일치 여부">{check.complete ? '내보내기 점검: 누락 없음' : `내보내기 점검: 누락·불일치 ${missingCount}건`}</span><span>회의용 내보내기</span><button type="button" className="secondary-button" onClick={() => exportAs('json')}>JSON</button><button type="button" className="secondary-button" onClick={() => exportAs('md')}>문서(Markdown)</button></div>;
}

function RunPicker({ runs, selected, onSelect }: { runs: RunSnapshot[]; selected: RunSnapshot; onSelect: (id: string) => void }) {
  return <label className="run-picker">실행 기록<select value={selected.run.id} onChange={event => onSelect(event.target.value)}>{runs.map(item => <option key={item.run.id} value={item.run.id}>{item.run.id} · 요청 회차 {item.request_revision} · {item.run.status}</option>)}</select></label>;
}

interface PlanningProps { mode: DataMode; runs: RunSnapshot[]; selected: RunSnapshot; onSelect: (id: string) => void; features: Feature[]; evidence: Evidence[] }

function RunStatus({ snapshot, mode }: { snapshot: RunSnapshot; mode: DataMode }) {
  const view = runStatusView(snapshot.run.status);
  // Fixture runs are hand-written examples, so their status must not read as an Agent result.
  const fixture = mode === 'fixture' && snapshot.actor_id !== 'local-draft';
  return <span className={`run-status ${fixture ? 'fixture' : view.tone}`} title={fixture ? FIXTURE_NOTICE : view.detail}>{fixture ? `fixture 예시 · ${snapshot.run.status}` : view.label}<small>{snapshot.run.status} · {snapshot.run.stage}</small></span>;
}

/** Candidates side by side on the attributes a planner compares before choosing. */
function CandidateMatrix({ snapshot }: { snapshot: RunSnapshot }) {
  const concepts = snapshot.run.concepts;
  const rows: [string, (concept: Concept) => string][] = [
    ['상태', concept => statusLabel(concept.status)],
    ['유형', concept => ({ product: '제품', feature: '기능', service: '서비스' })[concept.kind]],
    ['대응 간극', concept => concept.gap_ids.join(', ')],
    ['근거 수', concept => `${concept.evidence_ids.length}건`],
    ['요구사항 수', concept => `${concept.requirements.length}개`],
    ['확인할 가정', concept => `${concept.assumptions.length}개`],
  ];
  return <div className="table-scroll"><table className="candidate-matrix">
    <thead><tr><th>비교 항목</th>{concepts.map(concept => <th key={concept.id}><span className="id">{concept.id}</span>{concept.title}</th>)}</tr></thead>
    <tbody>{rows.map(([label, value]) => <tr key={label}><th>{label}</th>{concepts.map(concept => <td key={concept.id}>{value(concept)}</td>)}</tr>)}</tbody>
  </table></div>;
}

/** One place to read a candidate's sources, the judgments behind it, its assumptions and what was held back. */
function CandidateReview({ snapshot, concept, features, evidence }: { snapshot: RunSnapshot; concept: Concept; features: Feature[]; evidence: Map<string, Evidence> }) {
  const gaps = (snapshot.output?.gaps ?? []).filter(gap => concept.gap_ids.includes(gap.id));
  const held = heldItems(snapshot);
  const outOfScope = new Set(scopeWarnings(snapshot, features, [...evidence.values()]).filter(item => item.kind === 'evidence').map(item => item.id));
  return <div className="candidate-review">
    <div className="review-col">
      <h4>판단 근거</h4>
      {gaps.length ? gaps.map(gap => {
        const need = snapshot.output!.needs.find(item => item.id === gap.need_id);
        return <div key={gap.id} className="judgment">
          <div className="judgment-top"><span className="id">{gap.id} · {gap.model_id}</span><span className={`status-pill ${gap.support_status}`}>{statusLabel(gap.support_status)}</span></div>
          {need ? <p><strong>{need.pain}</strong><small>{need.situation}</small></p> : null}
          <dl>
            <dt>기존 기능</dt><dd>{gap.feature_ids.length ? gap.feature_ids.map(id => features.find(item => item.id === id)?.name ?? id).join(', ') : '연결된 기능 없음'}</dd>
            <dt>남은 불편</dt><dd>{gap.remaining_pain || '-'}</dd>
            {need?.uncertainties.length ? <><dt>상충·불확실</dt><dd>{need.uncertainties.join(' / ')}</dd></> : null}
            {gap.questions.length ? <><dt>확인할 질문</dt><dd>{gap.questions.join(' / ')}</dd></> : null}
          </dl>
        </div>;
      }) : <p className="muted">이 실행에는 후보와 연결된 판단 기록이 없습니다.</p>}
      <h4>확인할 가정</h4>
      {concept.assumptions.length ? <ul>{concept.assumptions.map(item => <li key={item}>{item}</li>)}</ul> : <p className="muted">없음</p>}
    </div>
    <div className="review-col">
      <h4>근거 원문 <span className="count">{concept.evidence_ids.length}건</span></h4>
      <ul className="quote-list">{concept.evidence_ids.map(id => {
        const item = evidence.get(id);
        return <li key={id}>{item ? <><q>{item.text}</q><small>{id} · {sourceKindLabel(item.source_kind)} · {item.source_type === 'review' ? '고객 리뷰' : '제품 설명서'} · {item.model_id} · 문서 {item.document_version} · {evidenceLocation(item)}{outOfScope.has(id) ? <span className="scope-flag"> · 검토 범위 밖 문서 버전</span> : null}</small></> : <span className="missing-note">{id} · 원문을 찾을 수 없습니다(자료 누락)</span>}</li>;
      })}</ul>
      <h4>보류·미해결 <span className="count">{held.length}건</span></h4>
      {held.length ? <ul className="held-list">{held.map(item => <li key={`${item.kind}-${item.text}`}><span className={`status-pill ${item.kind}`}>{item.kind === 'insufficient_evidence' ? '근거 부족·보류' : '미해결'}</span>{item.text}{item.questions.length ? <small>{item.questions.join(' / ')}</small> : null}</li>)}</ul> : <p className="muted">보류된 항목이 없습니다.</p>}
    </div>
  </div>;
}

/** Citations from a document version the run is not pinned to (document-update case) stay visible, never merged silently. */
function ScopeNotice({ snapshot, features, evidence }: { snapshot: RunSnapshot; features: Feature[]; evidence: Evidence[] }) {
  const warnings = scopeWarnings(snapshot, features, evidence);
  if (!warnings.length) return null;
  return <div className="scope-notice" role="note"><strong>검토 범위 밖 문서 버전 {warnings.length}건</strong><span>이 실행의 고정 문서 버전({Object.entries(snapshot.document_versions).map(([model, version]) => `${model} ${version}`).join(', ')})과 다른 자료입니다. 문서 범위를 바꾸려면 기획자가 결정해야 합니다.</span><ul>{warnings.map(item => <li key={`${item.kind}-${item.id}`}>{scopeWarningText(item)}</li>)}</ul></div>;
}

export function ConceptsView({ mode, runs, selected, onSelect, features, evidence }: PlanningProps) {
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  const [reviewId, setReviewId] = useState('');
  const reviewed = selected.run.concepts.find(item => item.id === reviewId) ?? selected.run.concepts[0];
  return <div className="planning-stack">
    <section className="panel planning-panel">
      <div className="planning-head"><div><p className="eyebrow">COMPARISON</p><h3>불편·기존 기능 대조표</h3></div><div className="head-tools"><RunStatus snapshot={selected} mode={mode} /><RunPicker runs={runs} selected={selected} onSelect={onSelect} /></div></div>
      <ComparisonTable snapshot={selected} features={features} evidence={evidenceById} />
      <ScopeNotice snapshot={selected} features={features} evidence={evidence} />
    </section>
    <ExecutionPanel snapshot={selected} />
    <section className="panel planning-panel">
      <div className="planning-head"><div><p className="eyebrow">CANDIDATES</p><h3>콘셉트 후보 <span className="count">{selected.run.concepts.length} / 3</span></h3></div><ExportActions mode={mode} snapshot={selected} features={features} evidence={evidence} runs={runs} /></div>
      {selected.run.concepts.length && !selectableConcepts(selected).length ? <p className="scope-flag" role="alert">저장된 판단 기록이 이 후보들을 채택하지 않았습니다(보류·실패·기록 오류). 원문 검토용으로만 표시하며 선택·재실행 대상이 아닙니다.</p> : null}
      {selected.run.concepts.length ? <div className="concept-grid">{selected.run.concepts.map(concept => <article key={concept.id} className={`concept-card ${concept.status}`}>
        <div className="concept-top"><span className="id">{concept.id} · {concept.kind}</span><span className={`status-pill ${concept.status}`}>{statusLabel(concept.status)}</span></div>
        <h4>{concept.title}</h4>
        <p className="differentiation">{concept.differentiation}</p>
        <dl>
          <dt>대응 간극</dt><dd>{concept.gap_ids.join(', ')}</dd>
          <dt>요구사항</dt><dd><ul>{concept.requirements.map(item => <li key={item}>{item}</li>)}</ul></dd>
          <dt>확인할 가정</dt><dd>{concept.assumptions.length ? <ul>{concept.assumptions.map(item => <li key={item}>{item}</li>)}</ul> : <span className="muted">없음</span>}</dd>
          <dt>근거 원문</dt><dd><Refs ids={concept.evidence_ids} evidence={evidenceById} /></dd>
        </dl>
        <button type="button" className={`review-button ${reviewed?.id === concept.id ? 'active' : ''}`} aria-pressed={reviewed?.id === concept.id} onClick={() => setReviewId(concept.id)}>원문·판단 함께 보기</button>
      </article>)}</div> : <p className="muted pad">{selected.run.status === 'not_implemented' ? '이 실행은 요청만 기록된 초안입니다. Agent가 연결되지 않아 후보를 만들지 않았습니다.' : '생성된 후보가 없습니다.'}</p>}
      {selected.run.unresolved.length ? <div className="unresolved"><strong>보류·미해결</strong><ul>{selected.run.unresolved.map(item => <li key={item}>{reasonText(item)}</li>)}</ul></div> : null}
    </section>
    {selected.run.concepts.length > 1 ? <section className="panel planning-panel"><div className="planning-head"><div><p className="eyebrow">SIDE BY SIDE</p><h3>후보 비교표</h3></div></div><CandidateMatrix snapshot={selected} /></section> : null}
    {reviewed ? <section className="panel planning-panel" aria-label="후보 상세 검토"><div className="planning-head"><div><p className="eyebrow">REVIEW</p><h3>{reviewed.title} <span className="count">원문·판단·가정·보류</span></h3></div><span className={`status-pill ${reviewed.status}`}>{statusLabel(reviewed.status)}</span></div><CandidateReview snapshot={selected} concept={reviewed} features={features} evidence={evidenceById} /></section> : null}
  </div>;
}

export interface MeasureControls {
  records: ModificationMeasurement[];
  start: (goal: string, baseRunId: string) => void;
  cancel: () => void;
  exportRecords: () => void;
  error: string;
}

function elapsed(since: string, now: number): string {
  const seconds = Math.max(0, Math.floor((now - Date.parse(since)) / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

/** E03: explicit goal and start; the clock stops when the rerun is saved. Nothing is measured implicitly. */
function MeasureBar({ measure, baseRunId }: { measure: MeasureControls; baseRunId: string }) {
  const running = measure.records.find(item => item.status === 'running');
  const [goal, setGoal] = useState('');
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  if (running) {
    return <div className="measure-bar running" role="status">
      <span className="measure-clock" aria-label="경과 시간">{elapsed(running.started_at, now)}</span>
      <span><strong>수정 시간 측정 중</strong><small>목표: {running.goal} · 기준 실행 {running.base_run_id} · 다시 실행 요청이 저장되면 멈춥니다</small></span>
      <button type="button" className="text-button" onClick={measure.cancel}>측정 취소</button>
    </div>;
  }
  return <div className="measure-bar">
    <label className="sr-only" htmlFor="measure-goal">수정 목표</label>
    <input id="measure-goal" value={goal} onChange={event => setGoal(event.target.value)} placeholder="수정 목표 (예: 중복 후보를 빼고 1인 가구 조건 추가)" />
    <button type="button" className="secondary-button" onClick={() => { measure.start(goal, baseRunId); setGoal(''); }}>수정 시간 측정 시작</button>
    {measure.error ? <p className="form-error" role="alert">{measure.error}</p> : null}
  </div>;
}

function MeasurementLog({ measure }: { measure: MeasureControls }) {
  if (!measure.records.length) return <p className="hint">수정 시간 측정 기록이 없습니다. 측정은 "다시 실행" 패널에서 시작합니다.</p>;
  return <div className="measurement-log">
    <h4 className="sub">수정 시간 기록 <small>{START_RULE} → {END_RULE}</small></h4>
    <ul>{measure.records.map(item => <li key={item.measurement_id}><strong>{item.modification_seconds === null ? (item.status === 'running' ? '측정 중' : '미측정(취소)') : `${item.modification_seconds}초`}</strong><span>{item.goal}</span><small>{item.base_run_id} → {item.result_run_id ?? '-'}{item.edits ? ` · 후보 ${item.edits.candidates_changed} · 조건 +${item.edits.conditions_added}/−${item.edits.conditions_removed}` : ''}</small></li>)}</ul>
    <button type="button" className="secondary-button" onClick={measure.exportRecords}>수정 시간 기록 내보내기(JSON)</button>
  </div>;
}

/** Planner picks a role per candidate and corrects conditions; the preview shows the exact next request before rerun. */
function RerunPanel({ mode, selected, original, onRerun, busy, measure }: { mode: DataMode; selected: RunSnapshot; original: PlanningRequest; onRerun: (request: PlanningRequest, edits: EditSummary) => Promise<void>; busy: boolean; measure: MeasureControls }) {
  // Only an accepted core judgement offers candidates; a held, failed or malformed record starts from conditions alone.
  const concepts = selectableConcepts(selected);
  const baseNotice = rerunBaseNotice(selected);
  const { conditions: startConditions } = splitConditions(selected.request, concepts);
  const [initialChoices] = useState(() => candidateChoicesFor(selected.request, concepts));
  const [choices, setChoices] = useState<Record<string, CandidateChoice>>(initialChoices);
  const nextConditionId = useRef(startConditions.length);
  const [conditions, setConditions] = useState(() => startConditions.map((text, id) => ({ id, text })));
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');

  let preview: PlanningRequest | null = null;
  let previewError = '';
  try { preview = buildRerunRequest(selected.request, concepts, choices, conditions.map(item => item.text)); } catch (failure) { previewError = failure instanceof ApiError ? failure.message : '재실행 요청을 만들 수 없습니다.'; }
  const changes = preview ? requestChanges(selected.request, preview) : [];

  function addDraft() {
    const text = draft.trim();
    if (!text) { setError('추가할 조건을 입력해 주세요.'); return; }
    if (conditions.some(item => item.text.trim() === text)) { setError('이미 같은 조건이 있습니다.'); return; }
    const condition = { id: nextConditionId.current++, text };
    setConditions(items => [...items, condition]); setDraft(''); setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview) return;
    if (!changes.length) { setError('바뀐 조건이 없습니다. 후보 선택이나 조건을 수정한 뒤 다시 실행해 주세요.'); return; }
    try { await onRerun(preview, editSummary(initialChoices, choices, startConditions, splitConditions(preview, concepts).conditions)); setError(''); } catch (failure) { setError(failure instanceof ApiError ? failure.message : '새 실행을 만들지 못했습니다.'); }
  }

  return <form className="panel planning-panel condition-form" onSubmit={submit} aria-label="후보·조건 선택 후 재실행">
    <p className="eyebrow">RERUN</p><h3>후보와 조건을 고르고 다시 실행</h3>
    <MeasureBar measure={measure} baseRunId={selected.run.id} />
    <p className="hint">{selected.run.id}의 요청을 바탕으로 새 실행을 연결합니다. {mode === 'fixture' ? '현재는 브라우저 안의 초안이며 결과는 not_implemented로 남습니다.' : '작업실 서버에 새 실행으로 저장합니다. 기존 실행은 유지됩니다.'}</p>
    {baseNotice ? <p className="scope-flag" role="note">{baseNotice}</p> : null}
    <h4 className="sub">후보 선택</h4>
    {concepts.length ? <ul className="choice-list">{concepts.map(concept => <li key={concept.id}>
      <span><span className="id">{concept.id} · {statusLabel(concept.status)}</span>{concept.title}</span>
      <span className="choice-group" role="radiogroup" aria-label={`${concept.title} 처리`}>{([['keep', '유지'], ['focus', '집중'], ['exclude', '제외']] as const).map(([value, label]) => <label key={value} className={choices[concept.id] === value ? `on ${value}` : ''}><input type="radio" name={`choice-${concept.id}`} checked={choices[concept.id] === value} onChange={() => setChoices(items => ({ ...items, [concept.id]: value }))} />{label}</label>)}</span>
    </li>)}</ul> : <p className="muted">이 실행에는 고를 후보가 없습니다. 조건만 교정해 다시 실행할 수 있습니다.</p>}
    <h4 className="sub">조건 교정 <small>제외·제약 조건</small></h4>
    <ul className="condition-list">{conditions.map((item, index) => <li key={item.id}>
      <label className="sr-only" htmlFor={`condition-${item.id}`}>조건 {index + 1}</label>
      <input id={`condition-${item.id}`} value={item.text} onChange={event => { const text = event.target.value; setConditions(items => items.map(value => value.id === item.id ? { ...value, text } : value)); }} />
      <button type="button" className="text-button" onClick={() => setConditions(items => items.filter(value => value.id !== item.id))} aria-label={`조건 ${index + 1} 삭제`}>삭제</button>
    </li>)}</ul>
    <div className="condition-row"><label className="sr-only" htmlFor="extra-condition">추가 조건</label><input id="extra-condition" value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); addDraft(); } }} placeholder="예: 1인 가구 소형 모델만 검토" /><button type="button" className="secondary-button" onClick={addDraft}>조건 추가</button></div>
    <h4 className="sub">다음 요청 미리보기 <small>요청 회차 {preview ? nextRequestRevision(original, selected, preview) : '-'}</small></h4>
    {previewError ? <p className="form-error" role="alert">{previewError}</p> : changes.length ? <table className="change-table"><thead><tr><th>항목</th><th>지금</th><th>다음 실행</th></tr></thead><tbody>{changes.map(item => <tr key={item.field}><th>{item.label}</th><td>{item.before}</td><td>{item.after}</td></tr>)}</tbody></table> : <p className="muted">아직 바뀐 내용이 없습니다.</p>}
    <div className="form-footer"><p>후보 선택은 공통 요청 규격 안에서 제외 조건("후보 제외: …")과 기획 요청 끝의 "[집중 검토: …]"로 전달됩니다.</p><button className="primary-button" type="submit" disabled={busy || !preview}>{mode === 'fixture' ? '새 실행 초안' : busy ? '저장 중…' : '다시 실행 요청'}<ArrowIcon /></button></div>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </form>;
}

function DetailChanges({ previous, selected }: { previous: RunSnapshot | undefined; selected: RunSnapshot }) {
  // A draft without Agent output has no result to compare; showing "removed" candidates would misstate the history.
  if (selected.run.status === 'not_implemented') return <p className="muted">Agent가 연결되지 않아 결과 변화가 없습니다.</p>;
  const changes = conceptDetailChanges(previous, selected);
  if (!changes.length) return <p className="muted">후보 변화가 없습니다.</p>;
  const list = (label: string, items: string[], sign: '+' | '−') => items.length ? <li className={sign === '+' ? 'added' : 'removed'}><strong>{sign} {label}</strong>{items.join(' / ')}</li> : null;
  // Plain React text: line breaks are preserved by CSS only, no HTML or markdown is interpreted. An empty value gets a label in a separate element.
  const textStyle = { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', margin: 0 } as const;
  const side = (role: 'before' | 'after', label: string, text: string) => <div className={role === 'before' ? 'removed' : 'added'} style={{ display: 'grid', gap: 2 }}>
    <strong>{label}</strong>
    {text === '' ? <em data-empty="true">(비어 있음)</em> : <span data-role={role} style={textStyle}>{text}</span>}
  </div>;
  const textDiff = (field: 'title' | 'differentiation', label: string, change: ConceptTextChange | null) => change ? <li data-text-change={field} style={{ display: 'grid', gap: 4, alignItems: 'start' }}>
    <strong>{label} 변경</strong>
    {side('before', '변경 전', change.before)}
    {side('after', '변경 후', change.after)}
  </li> : null;
  return <ul className="status-changes">{changes.map(item => <li key={item.id} className="detail-change">
    <div className="detail-change-top"><span><span className="id">{item.id}</span>{item.title}</span><span className="status-flow"><span className={`status-pill ${item.status[0] ?? 'none'}`}>{statusLabel(item.status[0])}</span><ArrowIcon /><span className={`status-pill ${item.status[1] ?? 'none'}`}>{statusLabel(item.status[1])}</span></span></div>
    <ul className="field-diff">
      {textDiff('title', '제목', item.text.title)}{textDiff('differentiation', '차별점', item.text.differentiation)}
      {list('요구사항', item.added.requirements, '+')}{list('요구사항', item.removed.requirements, '−')}
      {list('가정', item.added.assumptions, '+')}{list('가정', item.removed.assumptions, '−')}
      {list('근거', item.added.evidence_ids, '+')}{list('근거', item.removed.evidence_ids, '−')}
    </ul>
  </li>)}</ul>;
}

export function HistoryView({ mode, runs, selected, onSelect, features, evidence, original, onRerun, busy = false, measure }: PlanningProps & { original: PlanningRequest; onRerun: (request: PlanningRequest, edits: EditSummary) => Promise<void>; busy?: boolean; measure: MeasureControls }) {
  const previous = runs.find(item => item.run.id === selected.previous_run_id);
  const changes = requestChanges(previous?.request ?? original, selected.request);

  return <div className="history-layout">
    <section className="panel planning-panel timeline-panel" aria-label="실행 기록">
      <p className="eyebrow">RUNS</p><h3>실행 기록</h3>
      <ol className="timeline">{runs.map(item => <li key={item.run.id}><button type="button" className={item.run.id === selected.run.id ? 'active' : ''} aria-current={item.run.id === selected.run.id ? 'true' : undefined} onClick={() => onSelect(item.run.id)}>
        <span className="id">{item.run.id}</span><strong>요청 회차 {item.request_revision}</strong>
        <small>{item.previous_run_id ? `← ${item.previous_run_id}` : '첫 실행'} · {mode === 'fixture' && item.actor_id !== 'local-draft' ? `fixture 예시(${item.run.status})` : runStatusView(item.run.status).label}{item.actor_id === 'local-draft' ? ' · 브라우저 초안' : ` · ${item.client}/${item.actor_id}`}</small>
      </button></li>)}</ol>
      <p className="hint">{mode === 'fixture' ? 'RUN-FX는 계약 fixture 예시이고, 추가한 초안은 새로고침하면 사라집니다.' : '작업실 서버에 저장된 실행 기록입니다. 기록은 수정되지 않고 새 실행으로만 이어집니다.'}</p>
      <MeasurementLog measure={measure} />
    </section>
    <div className="planning-stack">
      <section className="panel planning-panel">
        <div className="planning-head"><div><p className="eyebrow">BEFORE / AFTER</p><h3>{selected.run.id} 변경 전후</h3></div><ExportActions mode={mode} snapshot={selected} features={features} evidence={evidence} runs={runs} /></div>
        <dl className="run-meta">
          <div><dt>이전 실행</dt><dd>{selected.previous_run_id ?? '없음(원 요청 기준)'}</dd></div>
          <div><dt>상태 / 단계</dt><dd>{selected.run.status} / {selected.run.stage}</dd></div>
          <div><dt>Agent 내부 수정</dt><dd>{selected.run.revision_count} / {selected.run.max_revisions}회</dd></div>
          <div><dt>문서 버전</dt><dd>{Object.entries(selected.document_versions).map(([model, version]) => `${model} ${version}`).join(', ')}</dd></div>
          <div><dt>기록 시각</dt><dd>{selected.created_at}</dd></div>
        </dl>
        <h4 className="sub">요청 변경</h4>
        {changes.length ? <table className="change-table"><thead><tr><th>항목</th><th>변경 전</th><th>변경 후</th></tr></thead><tbody>{changes.map(item => <tr key={item.field}><th>{item.label}</th><td>{item.before}</td><td>{item.after}</td></tr>)}</tbody></table> : <p className="muted">이전 기준과 요청이 같습니다.</p>}
        <h4 className="sub">후보 변화 <small>제목·차별점·상태·요구사항·가정·근거</small></h4>
        <DetailChanges previous={previous} selected={selected} />
        {selected.run.events.length ? <><h4 className="sub">판단 순서와 사용한 Skill</h4><ol className="events">{selected.run.events.map((item, index) => <li key={`${item.stage}-${index}`}><span className="stage">{item.stage}</span><span>{item.summary}</span>{item.tool ? <code>{item.tool}</code> : null}</li>)}</ol></> : null}
        {selected.unconfirmed.length ? <div className="unresolved"><strong>미확인 사항</strong><ul>{selected.unconfirmed.map(item => <li key={item}>{item}</li>)}</ul></div> : null}
      </section>
      <ExecutionPanel snapshot={selected} />
      <RerunPanel key={selected.run.id} mode={mode} selected={selected} original={original} onRerun={onRerun} busy={busy} measure={measure} />
    </div>
  </div>;
}
