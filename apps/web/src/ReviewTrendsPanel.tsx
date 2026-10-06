import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from './api';
import type { BootstrapData, Evidence } from './domain';
import { evidenceLocation } from './domain';
import { FIXTURE_TREND_NOTICE, FIXTURE_TRENDS, fixtureTrendEvidence } from './fixtures/reviewTrends.fixture';
import type { LiveWorkspace } from './liveWorkspace';
import type { DataMode, PlanningRequest } from './planning';
import { download } from './PlanningViews';
import {
  aggregateProblems, buildTrendFilters, percentText, planningTrendNote, SMALL_SAMPLE, topicLabel, topicsOf, trendCells,
  trendSnapshotExport, trendSnapshotMarkdown,
} from './reviewTrends';
import type { TrendAggregate, TrendCell } from './reviewTrends';
import type { ReviewTrendFilters, TrendEvidenceData } from './workspace';

type Source = 'fixture' | 'live';
type Granularity = ReviewTrendFilters['granularity'];
const GRANULARITY_LABEL: Record<Granularity, string> = { month: '월별', season: '계절별', year: '연도별' };
const NOT_CONNECTED = '승인된 리뷰 동향 집계기가 아직 서버에 연결되지 않았습니다(501). 숫자나 그래프를 대신 만들지 않습니다. 화면 흐름은 합성 fixture로 확인할 수 있습니다.';

/** One drill-down target. A page is shown, extended or sent to planning only while it still matches this key. */
const drillKey = (aggregateId: string, bucketId: string, topicId: string) => JSON.stringify([aggregateId, bucketId, topicId]);

interface Props {
  mode: DataMode; workspace: LiveWorkspace; data: BootstrapData | undefined; modelId: string;
  onUseInPlanning: (note: string, modelId: string) => void;
}

/**
 * Issue #149: monthly/seasonal complaint ratios with their denominators, empty-period and small-sample marks, the review
 * texts behind a bar, and a hand-off of the chosen bucket to a planning request. Numbers come only from a fixed aggregate
 * (server or labelled synthetic fixture); the panel checks them before drawing and never recomputes them.
 */
export function ReviewTrendsPanel({ mode, workspace, data, modelId, onUseInPlanning }: Props) {
  const liveReady = mode === 'live' && workspace.connection === 'connected' && Boolean(workspace.project);
  const [source, setSource] = useState<Source>('fixture');
  const [granularity, setGranularity] = useState<Granularity>('month');
  const [start, setStart] = useState('2026-01-01');
  const [end, setEnd] = useState('2026-07-01');
  const [liveAggregate, setLiveAggregate] = useState<TrendAggregate | null>(null);
  const [liveError, setLiveError] = useState<{ code: string; message: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [topic, setTopic] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState<{ key: string; data: TrendEvidenceData } | null>(null);
  const [pageError, setPageError] = useState('');
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  // Every drill-down request and every live query gets a generation; only the latest one may change the screen.
  const drillGeneration = useRef(0);
  const queryGeneration = useRef(0);

  const aggregate = source === 'fixture' ? FIXTURE_TRENDS[granularity] : liveAggregate;
  const problems = useMemo(() => aggregate ? aggregateProblems(aggregate) : [], [aggregate]);
  const topics = aggregate ? topicsOf(aggregate) : [];
  const activeTopic = topics.includes(topic) ? topic : topics[0] ?? '';
  const cells = aggregate && activeTopic ? trendCells(aggregate, activeTopic) : [];
  const cell = cells.find(item => item.bucket.bucket_id === selected) ?? null;
  const cellKey = (target: TrendCell) => aggregate ? drillKey(aggregate.aggregate_id, target.bucket.bucket_id, target.topic?.topic_id ?? activeTopic) : '';
  const currentKey = cell ? cellKey(cell) : null;
  const shownPage = page && page.key === currentKey ? page.data : null;
  const maxRatio = Math.max(0.0001, ...cells.map(item => item.ratio ?? 0));

  // PM review of #158: a new query, topic, aggregate, source or login/project scope drops the old drill-down and makes
  // any in-flight evidence response stale, so a January page can never sit under (or be sent as) a May bucket.
  const projectId = workspace.project?.project.id ?? null;
  const loginScope = JSON.stringify([mode, workspace.connection, workspace.scopeVersion, projectId]);
  useEffect(() => {
    drillGeneration.current += 1;
    setSelected(null); setPage(null); setPageError(''); setPendingKey(null);
  }, [aggregate?.aggregate_id, activeTopic, source, granularity, loginScope]);
  // A live aggregate belongs to one login/project scope; a later scope never shows it or accepts its slow reply.
  useEffect(() => {
    queryGeneration.current += 1;
    setLiveAggregate(null); setLiveError(null); setLoading(false);
  }, [loginScope]);
  useEffect(() => { if (!liveReady && source === 'live') setSource('fixture'); }, [liveReady, source]);

  async function queryLive() {
    const project = workspace.project;
    if (!project || !data) return;
    const request = project.project.request as unknown as PlanningRequest;
    const model = request.model_ids.includes(modelId) ? modelId : request.model_ids[0];
    const sourceIds = [...new Set(data.evidence.filter(item => item.model_id === model && item.source_type === 'review').map(item => item.source_id))];
    const kind = (data.evidence.find(item => item.model_id === model)?.source_kind ?? 'synthetic') as ReviewTrendFilters['source_kind'];
    const built = buildTrendFilters({ projectId: project.project.id, modelId: model, sourceIds, datasetVersion: request.dataset_version, start, end, granularity, topicIds: [], sourceKind: kind });
    const generation = ++queryGeneration.current;
    setLiveAggregate(null); setLiveError(null);
    if ('error' in built) { setLiveError({ code: 'INVALID_INPUT', message: built.error }); return; }
    setLoading(true);
    try {
      const result = await workspace.reviewTrends(built.filters);
      if (generation !== queryGeneration.current) return;
      if (result) setLiveAggregate(result.aggregate as unknown as TrendAggregate);
    } catch (failure) {
      if (generation !== queryGeneration.current) return;
      const code = failure instanceof ApiError ? failure.code : 'UNKNOWN_ERROR';
      setLiveError({ code, message: code === 'NOT_IMPLEMENTED' ? NOT_CONNECTED : failure instanceof Error ? failure.message : '동향을 조회하지 못했습니다.' });
    } finally { if (generation === queryGeneration.current) setLoading(false); }
  }

  async function openCell(target: TrendCell, offset = 0) {
    const generation = ++drillGeneration.current;
    const key = cellKey(target);
    setSelected(target.bucket.bucket_id); setPageError('');
    if (!offset) setPage(null);
    if (!aggregate || !target.topic || target.state !== 'value') { setPendingKey(null); return; }
    const topicId = target.topic.topic_id;
    setPendingKey(key);
    try {
      const next = source === 'fixture'
        ? fixtureTrendEvidence(aggregate, target.bucket.bucket_id, topicId, offset)
        : await workspace.trendEvidence(aggregate.aggregate_id, target.bucket.bucket_id, topicId, offset);
      if (generation !== drillGeneration.current || !next) return;
      if (drillKey(next.aggregate_id, next.bucket_id, next.topic_id) !== key) throw new Error('원문 조회 결과의 집계·구간·주제가 요청과 다릅니다.');
      // "More" only extends the page of the same key; anything else starts over from this response.
      setPage(previous => offset && previous?.key === key ? { key, data: { ...next, evidence: [...previous.data.evidence, ...next.evidence] } } : { key, data: next });
    } catch (failure) {
      if (generation !== drillGeneration.current) return;
      setPageError(failure instanceof Error ? failure.message : '원문을 불러오지 못했습니다.');
    } finally { if (generation === drillGeneration.current) setPendingKey(null); }
  }

  function exportSnapshot(format: 'json' | 'md') {
    if (!aggregate) return;
    // Only a finished page of exactly the selected aggregate/bucket/topic is recorded as viewed evidence.
    const viewed = shownPage && cell && pendingKey === null
      ? { bucket_id: shownPage.bucket_id, topic_id: shownPage.topic_id, total: shownPage.total, evidence_ids: shownPage.evidence.map(item => String(item.id)) }
      : null;
    const doc = trendSnapshotExport(aggregate, { fixture: source === 'fixture', exportedAt: new Date().toISOString(), viewed });
    const base = `review-trend-${aggregate.filters.model_id}-${aggregate.aggregate_id.slice(0, 18)}`;
    if (format === 'json') download(`${base}.json`, 'application/json', `${JSON.stringify(doc, null, 2)}
`);
    else download(`${base}.md`, 'text/markdown', trendSnapshotMarkdown(doc));
  }

  const counts = aggregate?.counts;
  return <section className="panel trends-panel" aria-label="리뷰 동향">
    <div className="trends-head">
      <img src="/kitchen-evidence-icon.png" width={32} height={32} alt="" className="trends-icon" />
      <div><p className="eyebrow">REVIEW TRENDS</p><h3>월·계절별 불편 리뷰 동향</h3>
        <p className="hint">해당 기간의 유효한 고유 리뷰 전체를 분모로 한 비율입니다. 한 리뷰가 여러 주제에 해당할 수 있어 주제별 합은 분모보다 클 수 있습니다. 리뷰 수는 판매량이나 수요 증가를 뜻하지 않습니다.</p></div>
    </div>

    <div className="trends-controls">
      <fieldset className="segmented"><legend className="sr-only">자료 출처</legend>
        <label><input type="radio" name="trend-source" checked={source === 'fixture'} onChange={() => setSource('fixture')} />합성 fixture</label>
        <label><input type="radio" name="trend-source" checked={source === 'live'} disabled={!liveReady} onChange={() => setSource('live')} />실제 서버{liveReady ? '' : ' (작업실 연결·프로젝트 필요)'}</label>
      </fieldset>
      <fieldset className="segmented"><legend className="sr-only">구간 단위</legend>
        {(['month', 'season'] as Granularity[]).map(value => <label key={value}><input type="radio" name="trend-granularity" checked={granularity === value} onChange={() => setGranularity(value)} />{GRANULARITY_LABEL[value]}</label>)}
      </fieldset>
      {topics.length ? <label className="trends-field">주제<select value={activeTopic} onChange={event => setTopic(event.target.value)}>{topics.map(id => <option key={id} value={id}>{topicLabel(id)}</option>)}</select></label> : null}
      {source === 'live' ? <form className="trends-period" onSubmit={event => { event.preventDefault(); void queryLive(); }}>
        <label className="trends-field">시작일<input type="date" value={start} onChange={event => setStart(event.target.value)} /></label>
        <label className="trends-field">종료일(미포함)<input type="date" value={end} onChange={event => setEnd(event.target.value)} /></label>
        <button className="secondary-button" type="submit" disabled={loading}>{loading ? '조회 중…' : '동향 조회'}</button>
      </form> : null}
    </div>

    {source === 'fixture' ? <p className="fixture-note" role="note">{FIXTURE_TREND_NOTICE} 기간: {aggregate?.filters.start_date} ~ {aggregate?.filters.end_date_exclusive}(미포함), 시간대 Asia/Seoul.</p> : null}
    {liveError ? <div className={`inline-message ${liveError.code === 'NOT_IMPLEMENTED' ? 'notice' : 'error'}`} role="status" data-code={liveError.code}><strong>{liveError.code === 'NOT_IMPLEMENTED' ? '실제 동향 집계 미연결' : '동향을 조회하지 못했습니다'}</strong><p>{liveError.message}</p><code>{liveError.code}</code></div> : null}
    {source === 'fixture' && granularity === 'year' ? <p className="muted">연도별 fixture는 준비하지 않았습니다.</p> : null}
    {source === 'live' && !aggregate && !liveError ? <p className="muted">기간을 고르고 동향 조회를 누르면 서버의 고정 집계를 불러옵니다.</p> : null}

    {aggregate && problems.length ? <div className="inline-message error" role="alert"><strong>집계 숫자가 서로 맞지 않아 그래프를 그리지 않습니다</strong><ul>{problems.map(item => <li key={item}>{item}</li>)}</ul></div> : null}

    {aggregate && !problems.length ? <>
      <dl className="trend-counts">
        <div><dt>분모(유효 고유 리뷰)</dt><dd>{counts!.eligible_unique_review_count}건</dd></div>
        <div><dt>날짜 없음 제외</dt><dd>{counts!.excluded_undated_count}건</dd></div>
        <div><dt>기간 밖 제외</dt><dd>{counts!.excluded_outside_period_count}건</dd></div>
        <div><dt>중복 제외</dt><dd>{counts!.duplicate_count}건</dd></div>
        <div><dt>범위 밖(다른 모델·자료)</dt><dd>{counts!.excluded_out_of_scope_count}건</dd></div>
        <div><dt>미분류(분모에 포함)</dt><dd>{counts!.unclassified_review_count}건</dd></div>
      </dl>
      {counts!.eligible_unique_review_count === 0 ? <p className="inline-message notice" role="status" data-denominator="zero">이 기간·범위에는 비율을 계산할 유효 리뷰가 없습니다(분모 0건). 모든 구간을 "자료 없음"으로 표시하며 0%가 아닙니다. 제외된 리뷰 수를 확인해 기간이나 자료를 바꿔 보세요.</p> : null}
      {aggregate.warnings.length ? <ul className="trend-warnings">{aggregate.warnings.map(item => <li key={item}>{item}</li>)}</ul> : null}

      <div className="trend-chart" role="group" aria-label={`${topicLabel(activeTopic)} ${GRANULARITY_LABEL[aggregate.filters.granularity]} 비율`}>
        {cells.map(item => <button key={item.bucket.bucket_id} type="button" className={`trend-bar ${item.state}${selected === item.bucket.bucket_id ? ' selected' : ''}`}
          aria-pressed={selected === item.bucket.bucket_id}
          aria-label={`${item.bucket.label}${item.bucket.partial_period ? ' 부분 구간' : ''}: ${item.state === 'empty' ? '리뷰 없음' : `${item.count}/${item.total}건 ${percentText(item.ratio)}`}${item.small ? ' 작은 표본' : ''}`}
          onClick={() => void openCell(item)}>
          <span className="trend-value">{item.state === 'empty' ? '자료 없음' : percentText(item.ratio)}</span>
          <span className="trend-track" aria-hidden="true"><span className="trend-fill" style={{ height: item.state === 'value' ? `${Math.max(4, ((item.ratio ?? 0) / maxRatio) * 100)}%` : '0%' }} /></span>
          <span className="trend-label">{item.bucket.label}{item.bucket.partial_period ? <small>부분 구간</small> : null}</span>
          <span className="trend-n">{item.count}/{item.total}건{item.small ? <small>작은 표본</small> : null}</span>
        </button>)}
      </div>
      <div className="export-actions trend-export" aria-label="집계 스냅샷 내보내기">
        <span className="hint">집계 스냅샷 내보내기{source === 'fixture' ? ' (합성 fixture로 표시됨)' : ''}</span>
        <button type="button" className="secondary-button" onClick={() => exportSnapshot('json')}>JSON</button>
        <button type="button" className="secondary-button" onClick={() => exportSnapshot('md')}>문서(Markdown)</button>
      </div>
      <p className="hint">막대는 비율, 아래 숫자는 주제 리뷰 수/분모입니다. "자료 없음"은 그 기간 리뷰가 없다는 뜻이고 0%와 다릅니다. 표본 {SMALL_SAMPLE}건 미만은 작은 표본으로 표시하며, 통계적 유의성 판정이 아닙니다. 집계 ID {aggregate.aggregate_id}</p>

      {cell ? <div className="trend-drilldown" aria-live="polite">
        <h4>{cell.bucket.label} · {topicLabel(activeTopic)} 원문</h4>
        {cell.state === 'empty' ? <p className="muted">이 기간에는 유효한 리뷰가 없습니다.</p> : cell.state === 'zero' ? <p className="muted">이 기간 리뷰 {cell.total}건 중 이 주제에 해당하는 리뷰가 없습니다(0%).</p> : null}
        {pageError ? <p className="form-error" role="alert">{pageError}</p> : null}
        {pendingKey && pendingKey === currentKey && !shownPage ? <p className="muted" role="status">원문을 불러오는 중입니다…</p> : null}
        {shownPage ? <>
          <p className="hint">{shownPage.total}건 중 {shownPage.evidence.length}건 · 집계 {shownPage.aggregate_id}에 실제 포함된 원문만 보여 줍니다.</p>
          <ul className="trend-evidence">{(shownPage.evidence as unknown as Evidence[]).map(item => <li key={item.id}><span className="id">{item.id}</span><blockquote>{item.text}</blockquote><small>{item.source_kind === 'synthetic' ? '합성자료' : item.source_kind} · {item.model_id} · 문서 {item.document_version} · {evidenceLocation(item)}</small></li>)}</ul>
          {shownPage.next_offset !== null ? <button type="button" className="text-button" disabled={pendingKey !== null} onClick={() => void openCell(cell, shownPage.next_offset!)}>{pendingKey ? '원문 불러오는 중…' : '원문 더 보기'}</button> : null}
          {/* Locked until the evidence of exactly this aggregate/bucket/topic has finished loading. */}
          <button type="button" className="primary-button" disabled={pendingKey !== null}
            onClick={() => onUseInPlanning(planningTrendNote(aggregate, cell, (shownPage.evidence as unknown as Evidence[]).map(item => item.id), source === 'fixture'), aggregate.filters.model_id)}>이 구간을 기획 요청에 추가</button>
        </> : null}
      </div> : null}
    </> : null}
  </section>;
}
