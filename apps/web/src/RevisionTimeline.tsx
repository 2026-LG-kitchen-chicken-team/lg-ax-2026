/** Revision timeline: tells the original request, user condition changes, data changes and Agent-internal revisions apart. */
import { conceptDetailChanges, FIXTURE_NOTICE, nextRequestRevision, requestChanges } from './planning';
import type { ConceptDetailChange, DataMode, PlanningRequest, RequestChange, RunSnapshot } from './planning';
import { runStatusView, stageLabel } from './liveWorkspace';

export type RevisionCause = 'original' | 'user_condition_change' | 'data_version_change' | 'unchanged_rerun';

export interface DataVersionChange {
  dataset_version: [string, string] | null;
  dataset_sha256: [string, string] | null;
  documents: { model_id: string; before: string | null; after: string | null }[];
}

export interface RevisionEntry {
  run_id: string;
  previous_run_id: string | null;
  request_revision: number;
  status: RunSnapshot['run']['status'];
  stage: RunSnapshot['run']['stage'];
  local_draft: boolean;
  causes: RevisionCause[];
  request_changes: RequestChange[];
  /** null when there is no earlier run to compare with (first run); the baseline is then the original request only. */
  data_changes: DataVersionChange | null;
  /** Agent-internal revisions happen inside this run (max 2); they are not user changes and not separate runs. */
  internal_revision: { count: number; max: number };
  dataset_version: string;
  dataset_sha256: string;
  document_versions: Record<string, string>;
  /** null = comparison held because the link or data is not trustworthy (see link_problems) or there is no Agent output. */
  concept_changes: ConceptDetailChange[] | null;
  link_problems: string[];
  record_problems: string[];
}

export interface RevisionTimelineResult { entries: RevisionEntry[]; problems: string[] }

/** An empty in-progress snapshot is not a decision that removed the previous candidates. */
export function isIntermediateRun(snapshot: RunSnapshot): boolean {
  return snapshot.run.status === 'pending' || snapshot.run.status === 'running';
}

function dataChanges(before: RunSnapshot, after: RunSnapshot): DataVersionChange {
  const models = [...new Set([...Object.keys(before.document_versions), ...Object.keys(after.document_versions)])].sort();
  const own = (snapshot: RunSnapshot, model: string) => (Object.hasOwn(snapshot.document_versions, model) ? snapshot.document_versions[model] : null);
  return {
    dataset_version: before.run.dataset_version === after.run.dataset_version ? null : [before.run.dataset_version, after.run.dataset_version],
    dataset_sha256: before.dataset_sha256 === after.dataset_sha256 ? null : [before.dataset_sha256, after.dataset_sha256],
    documents: models.map(model_id => ({ model_id, before: own(before, model_id), after: own(after, model_id) })).filter(item => item.before !== item.after),
  };
}

function hasDataChange(change: DataVersionChange | null): boolean {
  return !!change && (!!change.dataset_version || !!change.dataset_sha256 || change.documents.length > 0);
}

function recordProblems(snapshot: RunSnapshot): string[] {
  const found: string[] = [];
  const { revision_count: count, max_revisions: max } = snapshot.run;
  if (!Number.isInteger(count) || count < 0 || count > 2) found.push(`Agent 내부 수정 횟수 ${String(count)}는 0~2 범위를 벗어납니다.`);
  if (max !== 2) found.push(`최대 수정 횟수 ${String(max)}는 공통 계약의 2와 다릅니다.`);
  if (snapshot.run.dataset_version !== snapshot.request.dataset_version) found.push(`실행의 자료 버전(${snapshot.run.dataset_version})이 요청의 자료 버전(${snapshot.request.dataset_version})과 다릅니다.`);
  return found;
}

/**
 * Walks previous_run_id from the selected run back to the first run and describes each round.
 * A run is never linked by position or by guess: a missing, cyclic, cross-project or inconsistent link stops the walk,
 * is reported, and holds the candidate comparison instead of comparing against another run's result.
 */
export function buildRevisionTimeline(runs: RunSnapshot[], selectedId: string, original: PlanningRequest): RevisionTimelineResult {
  const byId = new Map<string, RunSnapshot>();
  const duplicates = new Set<string>();
  for (const item of runs) {
    if (byId.has(item.run.id)) duplicates.add(item.run.id);
    byId.set(item.run.id, item);
  }
  const problems: string[] = [...duplicates].sort().map(id => `실행 ID ${id}가 중복되어 어느 결과가 맞는지 구분할 수 없습니다.`);
  const selected = byId.get(selectedId);
  if (!selected || duplicates.has(selectedId)) {
    return { entries: [], problems: [...problems, ...(selected ? [] : [`선택한 실행 ${selectedId}이 기록에 없습니다.`])] };
  }

  const chain: { snapshot: RunSnapshot; parent: RunSnapshot | null; linkProblems: string[] }[] = [];
  const seen = new Set<string>();
  for (let current: RunSnapshot | undefined = selected; current;) {
    seen.add(current.run.id);
    const linkProblems: string[] = [];
    let parent: RunSnapshot | null = null;
    const parentId = current.previous_run_id;
    if (parentId !== null) {
      const candidate = byId.get(parentId);
      if (parentId === current.run.id || seen.has(parentId)) linkProblems.push(`이전 실행 ${parentId}가 순환하여 연결할 수 없습니다.`);
      else if (duplicates.has(parentId)) linkProblems.push(`이전 실행 ${parentId}가 중복 기록되어 연결할 수 없습니다.`);
      else if (!candidate) linkProblems.push(`이전 실행 ${parentId}가 기록에 없어 변경 전 결과를 연결할 수 없습니다.`);
      else if (candidate.run.project_id !== current.run.project_id) linkProblems.push(`이전 실행 ${parentId}는 다른 프로젝트(${candidate.run.project_id})의 결과라 연결하지 않았습니다.`);
      else {
        const [before, after] = [Date.parse(candidate.created_at), Date.parse(current.created_at)];
        if (Number.isFinite(before) && Number.isFinite(after) && before > after) linkProblems.push(`이전 실행 ${parentId}의 기록 시각이 이후 실행보다 늦습니다.`);
        else parent = candidate;
      }
    }
    // The server rule: a first run starts at revision 0 (equal to the original) or 1; a child adds one only when the request changed.
    const expected = nextRequestRevision(original, parent, current.request);
    if (!linkProblems.length && current.request_revision !== expected) linkProblems.push(`요청 회차 ${current.request_revision}가 요청 내용에서 계산한 ${expected}와 다릅니다.`);
    chain.unshift({ snapshot: current, parent, linkProblems });
    current = linkProblems.length ? undefined : parent ?? undefined;
  }

  const entries = chain.map(({ snapshot, parent, linkProblems }): RevisionEntry => {
    const requestDiff = requestChanges(parent?.request ?? original, snapshot.request);
    const data = parent ? dataChanges(parent, snapshot) : null;
    // The first run has no earlier data to compare; only the original request's data version is a known baseline.
    const firstDataVersion = !parent && snapshot.run.dataset_version !== original.dataset_version;
    const causes: RevisionCause[] = [];
    if (!parent && !requestDiff.length) causes.push('original');
    if (requestDiff.some(change => change.field !== 'dataset_version')) causes.push('user_condition_change');
    if (hasDataChange(data) || firstDataVersion) causes.push('data_version_change');
    if (!causes.length) causes.push('unchanged_rerun');
    const currentProblems = recordProblems(snapshot);
    const comparable = !linkProblems.length && !currentProblems.length && !isIntermediateRun(snapshot) && snapshot.run.status !== 'not_implemented'
      && (parent === null || !isIntermediateRun(parent) && parent.run.status !== 'not_implemented' && !recordProblems(parent).length);
    return {
      run_id: snapshot.run.id, previous_run_id: snapshot.previous_run_id, request_revision: snapshot.request_revision, causes,
      status: snapshot.run.status, stage: snapshot.run.stage, local_draft: snapshot.actor_id === 'local-draft',
      request_changes: requestDiff, data_changes: data,
      internal_revision: { count: snapshot.run.revision_count, max: snapshot.run.max_revisions },
      dataset_version: snapshot.run.dataset_version, dataset_sha256: snapshot.dataset_sha256, document_versions: { ...snapshot.document_versions },
      concept_changes: comparable ? conceptDetailChanges(parent ?? undefined, snapshot) : null,
      link_problems: linkProblems, record_problems: currentProblems,
    };
  });
  return { entries, problems: [...problems, ...entries.flatMap(entry => entry.link_problems.map(text => `${entry.run_id}: ${text}`))] };
}

const CAUSE_LABEL: Record<RevisionCause, string> = {
  original: '원 요청', user_condition_change: '사용자 조건 변경', data_version_change: '자료 버전 변경', unchanged_rerun: '변경 없는 재실행',
};

export function RevisionTimeline({ runs, selectedId, original, mode, onSelect }: { runs: RunSnapshot[]; selectedId: string; original: PlanningRequest; mode: DataMode; onSelect?: (id: string) => void }) {
  const { entries, problems } = buildRevisionTimeline(runs, selectedId, original);
  const versions = (versionsByModel: Record<string, string>) => Object.entries(versionsByModel).map(([model, version]) => `${model} ${version}`).join(', ') || '(자료 버전 없음)';
  return <section className="panel planning-panel" aria-label="수정 이력" data-revision-timeline>
    <p className="eyebrow">REVISIONS</p><h3>수정 이력</h3>
    <p className="hint">{mode === 'fixture' ? '화면 확인용 합성 예시 · 실제 Agent 실행 결과가 아닙니다.' : '서버에 저장된 실행 기록 · 자료 성격은 각 실행의 근거 원문에서 확인하세요.'}</p>
    {problems.length ? <div className="unresolved" role="alert" data-held="true"><strong>연결 보류</strong><ul>{problems.map(item => <li key={item}>{item}</li>)}</ul></div> : null}
    <ol className="timeline">{entries.map(entry => {
      const view = runStatusView(entry.status);
      const fixture = mode === 'fixture' && !entry.local_draft;
      return <li key={entry.run_id} data-run-id={entry.run_id} data-causes={entry.causes.join(' ')} aria-current={entry.run_id === selectedId ? 'true' : undefined}>
      <button type="button" className={entry.run_id === selectedId ? 'active' : ''} aria-current={entry.run_id === selectedId ? 'true' : undefined} onClick={() => onSelect?.(entry.run_id)}>
        <span className="id">{entry.run_id}</span><strong>요청 회차 {entry.request_revision} · {entry.causes.map(cause => CAUSE_LABEL[cause]).join(' + ')}</strong>
        <small>{entry.previous_run_id ? `← ${entry.previous_run_id}` : '첫 실행(원 요청 기준)'}</small>
        <span className={`run-status ${fixture ? 'fixture' : view.tone}`} data-field="run-status" title={fixture ? FIXTURE_NOTICE : view.detail}>
          {fixture ? `fixture 예시 · ${entry.status}` : view.label}<small title={`${entry.status} · ${entry.stage}`}>{stageLabel(entry.stage)}</small>
        </span>
      </button>
      <p data-field="internal" className="muted">Agent 내부 수정 {entry.internal_revision.count} / {entry.internal_revision.max}회 (실행 내부 회차이며 사용자 변경이 아님)</p>
      <p data-field="data-version" className="muted">사용한 자료: {entry.dataset_version} · sha256 {entry.dataset_sha256} · 문서 {versions(entry.document_versions)}</p>
      {entry.request_changes.length ? <table className="change-table" data-field="request-changes"><thead><tr><th>항목</th><th>변경 전</th><th>변경 후</th></tr></thead><tbody>{entry.request_changes.map(item => <tr key={item.field}><th>{item.label}</th><td>{item.before}</td><td>{item.after}</td></tr>)}</tbody></table> : null}
      {entry.data_changes && hasDataChange(entry.data_changes) ? <ul data-field="data-changes">
        {entry.data_changes.dataset_version ? <li>자료 버전 {entry.data_changes.dataset_version[0]} → {entry.data_changes.dataset_version[1]}</li> : null}
        {entry.data_changes.dataset_sha256 ? <li>자료 sha256 {entry.data_changes.dataset_sha256[0]} → {entry.data_changes.dataset_sha256[1]}</li> : null}
        {entry.data_changes.documents.map(item => <li key={item.model_id}>{item.model_id} 문서 {item.before ?? '(범위 밖)'} → {item.after ?? '(범위 밖)'}</li>)}
      </ul> : null}
      {entry.record_problems.length ? <ul data-field="record-problems" role="alert">{entry.record_problems.map(item => <li key={item}>{item}</li>)}</ul> : null}
      {entry.concept_changes === null
        ? <p className="muted" data-field="candidates" data-held="true">{entry.link_problems.length || entry.record_problems.length ? '연결 또는 기록을 확인할 수 없어 이전 후보와의 비교를 보류했습니다.' : '비교 가능한 Agent 결과가 없는 실행이라 후보 비교가 없습니다.'}</p>
        : entry.concept_changes.length
          ? <ul data-field="candidates">{entry.concept_changes.map(change => <li key={change.id} data-concept-id={change.id}><span className="id">{change.id}</span>{change.title} · {change.status[0] ?? '없음'} → {change.status[1] ?? '없음'}{change.text.title ? ` · 제목 "${change.text.title.before}" → "${change.text.title.after}"` : ''}{change.text.differentiation ? ` · 차별점 변경` : ''}</li>)}</ul>
          : <p className="muted" data-field="candidates">{entry.previous_run_id ? '이전 실행 대비 후보 변화가 없습니다.' : '첫 실행의 후보입니다.'}</p>}
    </li>;
    })}</ol>
  </section>;
}
