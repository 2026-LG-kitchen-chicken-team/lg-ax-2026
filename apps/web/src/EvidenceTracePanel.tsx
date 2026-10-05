/**
 * P2-WEB-003 evidence trace: for one judgement (a gap and the features it compared), lists every cited review/manual
 * source with its original text, page/row, product model, document version and real/synthetic kind, and says why a
 * citation cannot be relied on. It never re-judges anything; it only compares the ids a judgement cited with the
 * sources actually available. Nothing here is fetched, so it says nothing about live data being connected.
 */
import { evidenceLocation } from './domain';
import type { Evidence } from './domain';
import type { Feature, Gap } from './planning';

/** `usable` is the only status that may count as support; every other status is shown with its reason. */
export type TraceStatus = 'usable' | 'other_model' | 'other_version' | 'changed' | 'deleted' | 'not_found';
export type TraceRole = 'review' | 'manual' | 'unknown';

export interface TraceScope { model_id: string; document_version: string }
export interface TraceSubject { label: string; evidenceIds: string[]; featureIds: string[] }

export interface TraceRow {
  id: string; status: TraceStatus; role: TraceRole;
  /** The source that is shown: the current one, or the copy the judgement saw when the current one is gone. */
  source: Evidence | null;
  /** Current source when it exists and differs from what the judgement saw (changed text or version). */
  current: Evidence | null;
  note: string;
}

export interface EvidenceTrace {
  label: string; scope: TraceScope; rows: TraceRow[];
  counts: Record<TraceStatus, number>;
  /** Reasons the cited evidence does not establish the judgement; empty only when review and manual support are both usable. */
  insufficiency: string[];
  sufficient: boolean;
}

const STATUS_LABEL: Record<TraceStatus, string> = {
  usable: '범위 일치', other_model: '다른 제품 모델', other_version: '다른 문서 버전', changed: '판단 뒤 변경됨', deleted: '삭제된 자료', not_found: '찾을 수 없음',
};
const ROLE_LABEL: Record<TraceRole, string> = { review: '고객 리뷰', manual: '제품 설명서', unknown: '유형 미상' };
const KIND_LABEL: Record<string, string> = { synthetic: '합성 자료', public: '공개 실제 자료', licensed: '라이선스 실제 자료', private: '비공개 실제 자료' };

export function traceStatusLabel(status: TraceStatus): string {
  return STATUS_LABEL[status];
}

/** Subject of a stored gap: the citations it carries plus the existing features it compared against. */
export function subjectFromGap(gap: Gap, label: string): TraceSubject {
  return { label, evidenceIds: [...gap.evidence_ids], featureIds: [...gap.feature_ids] };
}

const sameSource = (a: Evidence, b: Evidence) => a.text === b.text && a.model_id === b.model_id && a.document_version === b.document_version && a.source_kind === b.source_kind
  && JSON.stringify(a.locator) === JSON.stringify(b.locator);

function classify(scope: TraceScope, current: Evidence | undefined, judged: Evidence | undefined): { status: TraceStatus; note: string } {
  if (!current) {
    return judged
      ? { status: 'deleted', note: '판단 당시 입력에는 있었지만 현재 자료에는 없습니다. 마지막으로 판단에 쓰인 원문을 보여 주며 근거로 인정하지 않습니다.' }
      : { status: 'not_found', note: '현재 자료와 판단 입력 어디에도 이 ID가 없습니다. 인용만 남은 상태이므로 근거로 인정하지 않습니다.' };
  }
  if (current.model_id !== scope.model_id) return { status: 'other_model', note: `검토 대상 모델(${scope.model_id})이 아닌 ${current.model_id}의 자료입니다. 다른 모델의 근거로 대신하지 않습니다.` };
  if (current.document_version !== scope.document_version) return { status: 'other_version', note: `검토 대상 문서 버전(${scope.document_version})이 아닌 ${current.document_version}의 자료입니다.` };
  if (judged && !sameSource(current, judged)) return { status: 'changed', note: '판단 당시 입력의 원문·위치·자료 유형과 현재 자료가 다릅니다. 다시 판단하기 전에는 같은 근거로 보지 않습니다.' };
  return { status: 'usable', note: '' };
}

/**
 * `evidence` is the current dataset; `judged` (optional) is the exact sources the judgement was given, which is what
 * lets a vanished source be told apart from an id that never existed.
 */
export function buildEvidenceTrace(options: { subject: TraceSubject; scope: TraceScope; features: Feature[]; evidence: Evidence[]; judged?: Evidence[] }): EvidenceTrace {
  const { subject, scope } = options;
  const current = new Map(options.evidence.map(item => [item.id, item]));
  const judged = new Map((options.judged ?? []).map(item => [item.id, item]));
  const featureById = new Map(options.features.map(item => [item.id, item]));
  const linked = subject.featureIds.map(id => featureById.get(id));
  const manualExpected = new Set(linked.flatMap(item => item?.evidence_ids ?? []));
  const ids = [...new Set([...subject.evidenceIds, ...manualExpected])];

  const rows: TraceRow[] = ids.map(id => {
    const now = current.get(id);
    const then = judged.get(id);
    const { status, note } = classify(scope, now, then);
    // Preserve the exact quoted input when the current source changed; show the new copy separately.
    const shown = status === 'changed' ? then ?? now ?? null : now ?? then ?? null;
    const role: TraceRole = shown ? shown.source_type === 'manual' ? 'manual' : shown.source_type === 'review' ? 'review' : 'unknown' : manualExpected.has(id) ? 'manual' : 'unknown';
    return { id, status, role, source: shown, current: status === 'changed' ? now ?? null : null, note };
  });

  const counts: Record<TraceStatus, number> = { usable: 0, other_model: 0, other_version: 0, changed: 0, deleted: 0, not_found: 0 };
  for (const row of rows) counts[row.status] += 1;

  const usable = (row: TraceRow, role: TraceRole) => row.status === 'usable' && row.role === role;
  const insufficiency: string[] = [];
  if (!ids.length) insufficiency.push('이 판단에 인용된 근거가 없습니다.');
  else if (!rows.some(row => usable(row, 'review'))) insufficiency.push('범위 안에서 확인되는 고객 리뷰 원문이 없어 불편을 뒷받침하지 못합니다.');
  if (ids.length && !rows.some(row => usable(row, 'manual'))) insufficiency.push('검토 범위 안의 제품 설명서 원문이 없어 기능 지원 여부를 뒷받침하지 못합니다.');
  subject.featureIds.forEach((id, index) => {
    const feature = linked[index];
    if (!feature) { insufficiency.push(`비교 대상 기능 ${id}의 자료가 없습니다.`); return; }
    if (!feature.evidence_ids.some(evidenceId => rows.some(row => row.id === evidenceId && usable(row, 'manual')))) {
      insufficiency.push(`기능 '${feature.name}'(${id})의 설명서 원문이 범위 안에서 확인되지 않아 지원 여부를 판단할 수 없습니다.`);
    }
  });
  const problems = counts.other_model + counts.other_version + counts.changed + counts.deleted + counts.not_found;
  if (problems) insufficiency.push(`범위 일치가 아닌 인용이 ${problems}건 있습니다. 근거 수에 포함하지 않았습니다.`);
  return { label: subject.label, scope, rows, counts, insufficiency, sufficient: insufficiency.length === 0 };
}

function SourceLine({ row }: { row: TraceRow }) {
  const source = row.source;
  if (!source) return <span className="missing-note">{row.id} · 원문을 찾을 수 없습니다(자료 누락)</span>;
  return <>
    <q>{source.text}</q>
    <small>{row.id} · {ROLE_LABEL[row.role]} · {KIND_LABEL[source.source_kind] ?? source.source_kind} · {source.model_id} · 문서 {source.document_version} · {evidenceLocation(source)}</small>
  </>;
}

export function EvidenceTracePanel({ trace, currentAvailable = true }: { trace: EvidenceTrace; currentAvailable?: boolean }) {
  return <section className="evidence-trace" aria-label="근거 추적">
    <h4>근거 추적 <span className="count">{trace.rows.length}건</span> <small>{trace.label} · 검토 범위 {trace.scope.model_id} · 문서 {trace.scope.document_version}</small></h4>
    {!currentAvailable ? <p className="hint" role="note">현재 자료를 조회하지 못해 저장된 판단 입력의 원문을 표시합니다. 이후 자료의 변경·삭제 여부는 확인되지 않았습니다.</p> : null}
    {trace.sufficient
      ? <p className="muted" data-trace="sufficient">{currentAvailable ? '조회한 자료의' : '판단에 사용된'} 리뷰와 설명서 원문이 모두 검토 범위 안에서 확인되었습니다. 의미가 맞는지는 원문을 읽고 기획자가 판단합니다.</p>
      : <div className="unresolved" role="alert" data-trace="insufficient"><strong>근거 부족</strong><ul>{trace.insufficiency.map(item => <li key={item}>{item}</li>)}</ul></div>}
    <ul className="quote-list">{trace.rows.map(row => <li key={row.id} data-status={row.status}>
      <span className={`status-pill ${row.status}`}>{traceStatusLabel(row.status)}</span>
      <SourceLine row={row} />
      {row.note ? <small className="scope-flag">{row.note}</small> : null}
      {row.current ? <small className="scope-flag">현재 자료: {row.current.model_id} · 문서 {row.current.document_version} · {evidenceLocation(row.current)} — {row.current.text}</small> : null}
    </li>)}</ul>
  </section>;
}
