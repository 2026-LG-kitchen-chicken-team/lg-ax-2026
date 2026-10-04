import { useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError } from './api';
import { evidenceLocation } from './domain';
import type { Evidence } from './domain';
import {
  buildComparison, buildExport, conceptChanges, draftRunWithCondition, exportMarkdown, FIXTURE_NOTICE, requestChanges, statusLabel,
} from './planning';
import type { DataMode, Feature, MissingQuestion, PlanningRequest, RequestChange, RunSnapshot } from './planning';
import { ArrowIcon } from './icons';
import './planning.css';

export function ModeSwitch({ mode, onChange }: { mode: DataMode; onChange: (mode: DataMode) => void }) {
  return <div className="mode-switch" role="group" aria-label="데이터 출처">
    {([['live', '실제 서버'], ['fixture', '계약 fixture']] as const).map(([value, label]) => <button key={value} className={mode === value ? 'active' : ''} aria-pressed={mode === value} onClick={() => onChange(value)}>{label}</button>)}
  </div>;
}

export function FixtureBanner() {
  return <div className="fixture-banner" role="note"><strong>모의 데이터 모드</strong><p>{FIXTURE_NOTICE} 서버에 아무것도 저장하거나 전송하지 않습니다.</p></div>;
}

/** Inline citation: shows the original text, location and version without leaving the current view. */
function EvidenceRef({ id, evidence }: { id: string; evidence: Map<string, Evidence> }) {
  const [open, setOpen] = useState(false);
  const item = evidence.get(id);
  if (!item) return <span className="evidence-ref missing" title="원문을 찾을 수 없습니다">{id} · 자료 누락</span>;
  return <span className="evidence-ref-wrap">
    <button type="button" className={`evidence-ref ${item.source_type}`} aria-expanded={open} onClick={() => setOpen(value => !value)}>{id}</button>
    {open ? <span className="evidence-pop" role="note"><q>{item.text}</q><small>{item.model_id} · 문서 {item.document_version} · {evidenceLocation(item)} · {item.source_id}</small></span> : null}
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
  if (!snapshot.output) return <p className="muted pad">이 실행에는 대조 결과가 없습니다.</p>;
  const rows = buildComparison(snapshot.output, features, [...evidence.values()]);
  return <div className="table-scroll"><table className="comparison-table">
    <thead><tr><th>고객 불편</th><th>연결된 기존 기능</th><th>기능 조건</th><th>판단</th><th>남은 불편</th><th>근거</th><th>확인할 질문</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.need.id}>
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

function download(name: string, type: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = name; link.click();
  URL.revokeObjectURL(url);
}

function ExportActions({ mode, snapshot, features, evidence }: { mode: DataMode; snapshot: RunSnapshot; features: Feature[]; evidence: Evidence[] }) {
  function exportAs(format: 'json' | 'md') {
    const doc = buildExport(mode, snapshot, features, evidence, new Date().toISOString());
    const base = `${snapshot.run.id}${mode === 'fixture' ? '-fixture' : ''}`;
    if (format === 'json') download(`${base}.json`, 'application/json', `${JSON.stringify(doc, null, 2)}\n`);
    else download(`${base}.md`, 'text/markdown', exportMarkdown(doc));
  }
  return <div className="export-actions"><span>회의용 내보내기</span><button type="button" className="secondary-button" onClick={() => exportAs('json')}>JSON</button><button type="button" className="secondary-button" onClick={() => exportAs('md')}>문서(Markdown)</button></div>;
}

function RunPicker({ runs, selected, onSelect }: { runs: RunSnapshot[]; selected: RunSnapshot; onSelect: (id: string) => void }) {
  return <label className="run-picker">실행 기록<select value={selected.run.id} onChange={event => onSelect(event.target.value)}>{runs.map(item => <option key={item.run.id} value={item.run.id}>{item.run.id} · 요청 회차 {item.request_revision} · {item.run.status}</option>)}</select></label>;
}

interface PlanningProps { mode: DataMode; runs: RunSnapshot[]; selected: RunSnapshot; onSelect: (id: string) => void; features: Feature[]; evidence: Evidence[] }

export function ConceptsView({ mode, runs, selected, onSelect, features, evidence }: PlanningProps) {
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  return <div className="planning-stack">
    <section className="panel planning-panel">
      <div className="planning-head"><div><p className="eyebrow">COMPARISON</p><h3>불편·기존 기능 대조표</h3></div><RunPicker runs={runs} selected={selected} onSelect={onSelect} /></div>
      <ComparisonTable snapshot={selected} features={features} evidence={evidenceById} />
    </section>
    <section className="panel planning-panel">
      <div className="planning-head"><div><p className="eyebrow">CANDIDATES</p><h3>콘셉트 후보 <span className="count">{selected.run.concepts.length} / 3</span></h3></div><ExportActions mode={mode} snapshot={selected} features={features} evidence={evidence} /></div>
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
      </article>)}</div> : <p className="muted pad">{selected.run.status === 'not_implemented' ? '이 실행은 요청만 기록된 초안입니다. Agent가 연결되지 않아 후보를 만들지 않았습니다.' : '생성된 후보가 없습니다.'}</p>}
      {selected.run.unresolved.length ? <div className="unresolved"><strong>보류·미해결</strong><ul>{selected.run.unresolved.map(item => <li key={item}>{item}</li>)}</ul></div> : null}
    </section>
  </div>;
}

export function HistoryView({ mode, runs, selected, onSelect, features, evidence, original, onDraft }: PlanningProps & { original: PlanningRequest; onDraft: (draft: RunSnapshot) => void }) {
  const [condition, setCondition] = useState('');
  const [error, setError] = useState('');
  const previous = runs.find(item => item.run.id === selected.previous_run_id);
  const changes = requestChanges(previous?.request ?? original, selected.request);
  // A draft without Agent output has no result to compare; showing "removed" candidates would misstate the history.
  const statusChanges = selected.run.status === 'not_implemented' ? [] : conceptChanges(previous, selected);

  function addCondition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const draft = draftRunWithCondition(selected, original, condition, `RUN-DRAFT-${runs.length + 1}`, new Date().toISOString());
      onDraft(draft);
      setCondition(''); setError('');
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : '새 실행 초안을 만들지 못했습니다.');
    }
  }

  return <div className="history-layout">
    <section className="panel planning-panel timeline-panel" aria-label="실행 기록">
      <p className="eyebrow">RUNS</p><h3>실행 기록</h3>
      <ol className="timeline">{runs.map(item => <li key={item.run.id}><button type="button" className={item.run.id === selected.run.id ? 'active' : ''} aria-current={item.run.id === selected.run.id ? 'true' : undefined} onClick={() => onSelect(item.run.id)}>
        <span className="id">{item.run.id}</span><strong>요청 회차 {item.request_revision}</strong>
        <small>{item.previous_run_id ? `← ${item.previous_run_id}` : '첫 실행'} · {item.run.status}{item.actor_id === 'local-draft' ? ' · 브라우저 초안' : ''}</small>
      </button></li>)}</ol>
      <p className="hint">{mode === 'fixture' ? 'RUN-FX는 계약 fixture 예시이고, 추가한 초안은 새로고침하면 사라집니다.' : '서버 기록을 표시합니다.'}</p>
    </section>
    <div className="planning-stack">
      <section className="panel planning-panel">
        <div className="planning-head"><div><p className="eyebrow">BEFORE / AFTER</p><h3>{selected.run.id} 변경 전후</h3></div><ExportActions mode={mode} snapshot={selected} features={features} evidence={evidence} /></div>
        <dl className="run-meta">
          <div><dt>이전 실행</dt><dd>{selected.previous_run_id ?? '없음(원 요청 기준)'}</dd></div>
          <div><dt>상태 / 단계</dt><dd>{selected.run.status} / {selected.run.stage}</dd></div>
          <div><dt>Agent 내부 수정</dt><dd>{selected.run.revision_count} / {selected.run.max_revisions}회</dd></div>
          <div><dt>문서 버전</dt><dd>{Object.entries(selected.document_versions).map(([model, version]) => `${model} ${version}`).join(', ')}</dd></div>
          <div><dt>기록 시각</dt><dd>{selected.created_at}</dd></div>
        </dl>
        <h4 className="sub">요청 변경</h4>
        {changes.length ? <table className="change-table"><thead><tr><th>항목</th><th>변경 전</th><th>변경 후</th></tr></thead><tbody>{changes.map(item => <tr key={item.field}><th>{item.label}</th><td>{item.before}</td><td>{item.after}</td></tr>)}</tbody></table> : <p className="muted">이전 기준과 요청이 같습니다.</p>}
        <h4 className="sub">후보 상태 변화</h4>
        {statusChanges.length ? <ul className="status-changes">{statusChanges.map(item => <li key={item.id}><span className="id">{item.id}</span>{item.title}<span className="status-flow"><span className={`status-pill ${item.before ?? 'none'}`}>{statusLabel(item.before)}</span><ArrowIcon /><span className={`status-pill ${item.after ?? 'none'}`}>{statusLabel(item.after)}</span></span></li>)}</ul> : <p className="muted">{selected.run.status === 'not_implemented' ? 'Agent가 연결되지 않아 결과 변화가 없습니다.' : '후보 상태 변화가 없습니다.'}</p>}
        {selected.run.events.length ? <><h4 className="sub">판단 순서와 사용한 Skill</h4><ol className="events">{selected.run.events.map((item, index) => <li key={`${item.stage}-${index}`}><span className="stage">{item.stage}</span><span>{item.summary}</span>{item.tool ? <code>{item.tool}</code> : null}</li>)}</ol></> : null}
        {selected.unconfirmed.length ? <div className="unresolved"><strong>미확인 사항</strong><ul>{selected.unconfirmed.map(item => <li key={item}>{item}</li>)}</ul></div> : null}
      </section>
      <form className="panel planning-panel condition-form" onSubmit={addCondition}>
        <p className="eyebrow">ADD CONDITION</p><h3>추가 조건으로 다시 검토</h3>
        <p className="hint">선택한 실행({selected.run.id})의 요청에 조건을 더해 새 실행을 연결합니다. {mode === 'fixture' ? '현재는 브라우저 안의 초안이며, Agent가 연결되지 않아 결과는 not_implemented로 남습니다.' : ''}</p>
        <div className="condition-row"><label className="sr-only" htmlFor="extra-condition">추가 조건</label><input id="extra-condition" value={condition} onChange={event => setCondition(event.target.value)} placeholder="예: 1인 가구 소형 모델만 검토" /><button className="primary-button" type="submit" disabled={mode !== 'fixture'}>새 실행 초안<ArrowIcon /></button></div>
        {mode !== 'fixture' ? <p className="hint">실제 서버 재실행은 #24/#25에서 작업실 API와 연결합니다.</p> : null}
        {error ? <p className="form-error" role="alert">{error}</p> : null}
      </form>
    </div>
  </div>;
}
