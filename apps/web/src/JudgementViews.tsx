import type { Evidence } from './domain';
import { executionKindText, grouped, judgementView, planningExecutionView, reasonText, scopeLines, seconds, tokenText, traceFacts, unusedReviewIds, verificationScope, violationText } from './judgement';
import type { ExecutionMetrics, JudgementDecision, JudgementInput, JudgementOutput, ModelCallRecord, PlanningExecution, SemanticAssessment, StoredDecision, TraceFacts } from './judgement';
import { sourceKindLabel, TERMINAL_TEXT } from './planning';
import type { RunSnapshot } from './planning';

const POLARITY: Record<string, string> = { complaint: '불편', positive: '긍정', conflicting: '상충', irrelevant: '무관', uncertain: '불확실' };
const SUPPORT: Record<string, string> = { explicit_supported: '설명서에 지원 명시', explicit_unsupported: '설명서에 미지원 명시', unmentioned: '설명서 미언급', conflicting: '설명서 상충' };
const RESOLUTION: Record<string, string> = { resolved: '해결됨', remaining: '불편 남음', unknown: '알 수 없음' };
const DUPLICATION: Record<string, string> = { distinct: '기존 기능과 다름', duplicate: '기존 기능과 중복', uncertain: '중복 여부 불확실' };

function TextList({ title, items, empty }: { title: string; items: string[]; empty?: string }) {
  if (!items.length && !empty) return null;
  return <><h4>{title} <span className="count">{items.length}건</span></h4>{items.length ? <ul>{items.map(item => <li key={item}>{reasonText(item)}</li>)}</ul> : <p className="muted">{empty}</p>}</>;
}

/**
 * One core judgement as the planner sees it: the core's review decision first, then the declared assessments it was
 * checked against. Fixture declarations are labelled as such so they never read as model output.
 */
export function JudgementPanel({ input, output, decision, fixture, facts = null }: { input: JudgementInput; output: JudgementOutput; decision: JudgementDecision | StoredDecision; fixture: boolean; facts?: TraceFacts | null }) {
  const view = judgementView(input, output, decision, facts);
  const sources = new Map<string, Evidence>(input.sources.map(item => [item.id, item]));
  const featureName = (id: string) => input.features.find(item => item.id === id)?.name ?? id;
  // Record 034 audit U4 (r2d2): an assessed complaint no need/gap cites was silently dropped by the judgement.
  const unused = new Set(unusedReviewIds(output));
  // Record 034 audit U5 (r0d9): the polarity and support rows are what the judging model declared; only the contract was checked.
  const declared = fixture ? '작성된 fixture 선언' : '판단 모델의 선언 · 의미 미검증';
  return <section className="judgement-panel" aria-label="판단 계약 검사 결과">
    <div className="judgement-head">
      <span className={`run-status ${view.tone}`} title={view.detail}>{view.label}<small>코어 검사 결정 · {decision.action}</small></span>
      <span className="id">{output.model_id} · 문서 {output.document_version} · 내부 수정 {output.revision_count}/2 · 입력 {output.input_sha256.slice(0, 12)}</span>
    </div>
    <p className="judgement-detail">{view.detail}</p>
    {fixture ? <p className="fixture-note">사람이 작성한 판단 선언(fixture)과 코어 검사기의 실제 결정입니다. 모델이 생성한 결과가 아닙니다.</p> : null}
    {view.declared_status_overridden ? <p className="scope-flag">판단이 스스로 선언한 상태는 '{output.status}'였지만, 코어 검사 결정에 따라 '{view.label}'로 표시합니다.</p> : null}
    {view.unrevised_errors.length && view.hold_causes.length
      ? <><TextList title="보류를 일으킨 문제(근거 확인 필요)" items={view.hold_causes} /><TextList title="함께 발견된 판단 오류(보류로 내부 수정하지 않음)" items={view.unrevised_errors} /></>
      : <TextList title="검사에서 발견한 문제" items={view.violations} empty="없음" />}
    <TextList title="다른 모델·문서 버전의 원문" items={view.out_of_scope_sources} />
    <h4>리뷰 판단 <small>{declared}</small>{unused.size ? <span className="count" data-field="unused-reviews"> · 어느 불편·Gap에도 쓰이지 않은 리뷰 {unused.size}건</span> : null}</h4>
    <ul className="quote-list">{output.review_assessments.map(item => <li key={item.evidence_id}><span className={`status-pill ${item.polarity}`}>{POLARITY[item.polarity]}</span>{sources.get(item.evidence_id) ? <q>{sources.get(item.evidence_id)!.text}</q> : <span className="missing-note">{item.evidence_id} · 원문을 찾을 수 없습니다(자료 누락)</span>}<small>{item.evidence_id} · {item.reason}</small>{unused.has(item.evidence_id) ? <span className="scope-flag" data-unused-review={item.evidence_id}> · 어느 불편·Gap에도 쓰이지 않음</span> : null}</li>)}</ul>
    <h4>기능 대조 <small>{declared}</small></h4>
    <ul>{output.gap_assessments.map(item => <li key={item.gap_id}><span className="id">{item.gap_id}</span> {SUPPORT[item.support_basis]} · {RESOLUTION[item.resolution]}<small> — {item.reason}</small></li>)}</ul>
    <h4>후보 <span className="count">{output.concepts.length}개</span></h4>
    {output.concepts.length ? <ul>{output.concepts.map(concept => {
      const assessment = output.concept_assessments.find(item => item.concept_id === concept.id);
      return <li key={concept.id}><span className="id">{concept.id}</span> {concept.title}{assessment ? <small> · {DUPLICATION[assessment.duplication]}(비교 기능: {assessment.compared_feature_ids.map(featureName).join(', ') || '없음'})</small> : null}{view.candidates_selectable ? null : <span className="scope-flag"> · 검사 미통과 · 선택 불가</span>}</li>;
    })}</ul> : <p className="muted">후보가 없습니다.</p>}
    <TextList title="확인할 질문" items={view.questions} />
    <TextList title="보류 사유" items={view.hold_reasons} />
    <TextList title="미해결" items={view.unresolved} />
    <TextList title="후보 없음 사유" items={view.no_candidate_reasons} />
  </section>;
}

const DECISION_LABEL: Record<string, string> = { accept: '계약 검사 통과', hold: '보류', revise: '수정 필요', unresolved: '미해결 종료' };
const VERDICT: Record<string, string> = { compliant: '준수', satisfied: '충족', violation: '위반', uncertain: '불확실' };
const CRITERION: Record<string, string> = { mechanism: '작동 방식', difference_from_current_features: '현재 기능과 차이', unverified_assumptions: '미검증 가정', unsupported_claims: '근거 없는 단정', unsupported_factual_claims: '근거 없는 단정' };

function AssessmentRow({ row, target }: { row: SemanticAssessment; target: string }) {
  const tone = row.verdict === 'violation' ? 'error' : row.verdict === 'uncertain' ? 'notice' : 'done';
  return <li><span className={`run-status ${tone}`}>{VERDICT[row.verdict] ?? row.verdict}</span> <span className="id">{row.concept_id}</span> × {target}
    {row.candidate_quote ? <q>{row.candidate_quote}</q> : null}<small> — {row.reason}</small>
    {row.source_quotes?.length ? <ul className="quote-list">{row.source_quotes.map(item => <li key={`${item.evidence_id}-${item.quote}`}><q>{item.quote}</q><small>{item.evidence_id}</small></li>)}</ul> : null}</li>;
}

/**
 * PR #60 (draft) semantic reviews: the model's own verdict per candidate × exclusion and quality criterion. The core
 * checks only that the rows are complete and quote the originals literally, so the verdicts are declarations to read
 * against the quotes, not an independent check. Satisfied quality rows are counted rather than listed.
 */
function SemanticReviews({ execution }: { execution: PlanningExecution }) {
  const reviews = execution.semantic_reviews ?? [];
  if (!reviews.length) return null;
  return <section className="semantic-reviews" aria-label="의미 검토 기록">
    <h4 className="sub">의미 검토 <small>{reviews.length}회 · {execution.execution_kind === 'fixture' ? '작성된 fixture 응답' : '판단과 같은 모델이 작성한 검토 선언'} · 코어는 인용 일치·누락만 검사</small></h4>
    {reviews.map((review, index) => {
      const quality = review.report.quality_assessments;
      const flagged = quality.filter(row => row.verdict !== 'satisfied');
      return <div key={index} className="semantic-review">
        <p><strong>{index + 1}회차</strong> · 결정 {DECISION_LABEL[review.decision.action] ?? review.decision.action}{review.decision.violations.length ? ` · 위반 ${review.decision.violations.length}건` : ' · 위반 없음'}</p>
        {review.reviewed_input && review.reviewed_output ? <details><summary>이 회차에서 검토한 원 입력·후보</summary><p className="id">{review.reviewed_input.product.model_id} · 문서 {review.reviewed_input.product.document_version} · 내부 수정 {review.reviewed_input.revision_count}/2 · 입력 {review.reviewed_output.input_sha256.slice(0, 12)}</p><p>{review.reviewed_input.request.improvement_task}</p><TextList title="검토 당시 제외 조건" items={review.reviewed_input.request.exclusions} empty="없음" /><ul>{review.reviewed_output.concepts.map(concept => <li key={concept.id}><span className="id">{concept.id}</span> {concept.title}</li>)}</ul></details> : null}
        <ul>{review.report.exclusion_assessments.map((row, n) => <AssessmentRow key={`x-${n}`} row={row} target={`제외 조건 '${row.condition ?? row.condition_index}'`} />)}</ul>
        {review.report.exclusion_assessments.length ? null : <p className="muted">제외 조건이 없어 조건별 검토가 없습니다.</p>}
        <ul>{flagged.map((row, n) => <AssessmentRow key={`q-${n}`} row={row} target={`기준 ${CRITERION[row.criterion ?? ''] ?? row.criterion}`} />)}</ul>
        <p className="muted">기획 품질 기준 {quality.length}건 중 충족 선언 {quality.length - flagged.length}건</p>
        {review.report.questions.length ? <><h4>확인할 질문</h4><ul>{review.report.questions.map(item => <li key={item}>{item}</li>)}</ul></> : null}
      </div>;
    })}
    {execution.decision?.action === 'accept' ? <p className="scope-flag">의미 검토도 위반 없음으로 선언했지만 같은 모델의 자기 검토입니다. 독립 검토 전이므로 기획자가 인용과 함께 확인해야 합니다.</p> : null}
  </section>;
}

/** The core's decision when no judgement output was stored (a stage kept failing), so its violations are not lost. */
function DecisionOnly({ decision }: { decision: StoredDecision }) {
  return <section className="judgement-panel" aria-label="판단 계약 검사 결과">
    <div className="judgement-head"><span className="run-status error">{DECISION_LABEL[decision.action] ?? decision.action}<small>코어 검사 결정 · {decision.action}</small></span><span className="id">내부 수정 {decision.revision_count}/2</span></div>
    <h4>검사에서 발견한 문제 <span className="count">{decision.violations.length}건</span></h4>
    <ul>{decision.violations.map((item, index) => <li key={`${item.code}-${index}`}>{violationText(item)}</li>)}</ul>
  </section>;
}

/** Candidates the core produced and then turned down; kept for review, never selectable. */
function RejectedCandidates({ output, facts = null }: { output: JudgementOutput; facts?: TraceFacts | null }) {
  // Record 034 audit U3: say why each candidate was turned down. A candidate with no violation of its own is not
  // "rejected" on its merits; the whole run stopped. Duplication rows whose candidate body was never stored are listed too.
  const orphans = output.concept_assessments.filter(item => !output.concepts.some(concept => concept.id === item.concept_id));
  if (!output.concepts.length && !orphans.length) return null;
  return <section className="rejected-output" aria-label="거절된 후보">
    {output.concepts.length ? <><h4 className="sub">검사에서 거절된 마지막 후보 <small>{output.concepts.length}개 · 선택·내보내기 대상 아님</small></h4>
    <ul>{output.concepts.map(concept => {
      const lineage = facts?.lineage.get(concept.id);
      const assessment = output.concept_assessments.find(item => item.concept_id === concept.id);
      return <li key={concept.id} data-rejected-concept={concept.id}><span className="id">{concept.id}</span> {concept.title}
        <small> · 대응 Gap {concept.gap_ids.join(', ') || '없음'}{lineage ? ` · ${lineage.valid ? '확인된 불편 Gap에 연결됨' : '확인되지 않은 Gap에 연결됨'}` : ''}{assessment ? ` · ${DUPLICATION[assessment.duplication]} — ${assessment.reason}` : ''}</small>
        {lineage?.codes.length
          ? <span className="scope-flag" data-field="rejection"> · 검사 위반: {lineage.codes.map(code => reasonText(code)).join(' / ')}</span>
          : <span className="scope-flag" data-field="rejection"> · {lineage ? '자기 위반 없음 · 실행 전체가 끝나 선택 불가' : '거절됨(후보별 사유 기록 없음)'}</span>}</li>;
    })}</ul></> : null}
    {orphans.length ? <><h4 className="sub">후보 본문 없이 남은 중복 판단 <small>{orphans.length}건 · 평가 목록 불일치(ASSESSMENT_COVERAGE) 대상</small></h4>
    <ul>{orphans.map(item => <li key={item.concept_id} data-orphan-assessment={item.concept_id}><span className="id">{item.concept_id}</span> {DUPLICATION[item.duplication]}<small> — {item.reason}</small></li>)}</ul></> : null}
  </section>;
}

/** Agent-internal check rounds read from the trace: not the planner's request revisions. Repeats are marked. */
function CheckRounds({ facts, terminal }: { facts: TraceFacts; terminal: string | null }) {
  if (!facts.rounds.length) return null;
  return <section className="check-rounds" aria-label="회차별 검사 결과">
    <h4 className="sub">회차별 검사 결과 <small>Agent 내부 수정 회차 · 사용자 조건 변경 회차와 다름</small></h4>
    <ol>{facts.rounds.map(round => <li key={round.round} data-round={round.round}>{round.round}회차(내부 수정 {round.revision_count}회 뒤) · {DECISION_LABEL[round.action] ?? round.action}
      {round.codes.length ? <small> · 위반 {round.codes.join(', ')}</small> : <small> · 위반 없음</small>}{round.repeated ? <span className="scope-flag" data-field="repeated"> · 이전 회차와 같은 위반 반복</span> : null}</li>)}</ol>
    {terminal ? <p className="muted" data-field="terminal">종료 사유: {TERMINAL_TEXT[terminal] ?? terminal} ({terminal})</p> : null}
  </section>;
}

/** A failed attempt may retain a checked declaration but have no terminal decision. Do not invent a decision. */
function OutputWithoutDecision({ output, status }: { output: JudgementOutput; status: PlanningExecution['status'] }) {
  return <section className="judgement-panel" aria-label="최종 결정 없는 판단 출력">
    <div className="judgement-head"><span className={`run-status ${status === 'failed' ? 'error' : 'notice'}`}>저장된 판단 출력 · {STATUS_LABEL[status]}<small>최종 코어 검사 결정이 없습니다</small></span><span className="id">{output.model_id} · 문서 {output.document_version} · 내부 수정 {output.revision_count}/2 · 입력 {output.input_sha256.slice(0, 12)}</span></div>
    <p className="judgement-detail">판단 출력은 저장되었지만 최종 검사 결정을 얻지 못했습니다. 완료·검수 통과로 취급하지 않으며 후보는 선택할 수 없습니다. 위의 실행 오류와 아래 사유를 확인해 주세요.</p>
    <TextList title="확인할 질문" items={[...output.questions, ...output.gaps.flatMap(gap => gap.questions)]} />
    <TextList title="보류 사유" items={output.hold_reasons} />
    <TextList title="미해결" items={output.unresolved} />
    <TextList title="후보 없음 사유" items={output.no_candidate_reasons} />
    <RejectedCandidates output={output} />
  </section>;
}

const STATUS_LABEL: Record<string, string> = { completed: '완료', held: '보류', failed: '실패' };

/**
 * Record 034 audit U5 (r0d9, r2d10, r3d10): what this run did not verify, read from the record. Rule checks passing
 * only means the contract held; the core decision above still decides the run.
 */
function ScopeNotice({ execution }: { execution: PlanningExecution }) {
  const items = scopeLines(verificationScope(execution), execution.execution_kind);
  if (!items.length) return null;
  return <section className="scope-notice" aria-label="검증 범위">
    <h4 className="sub">검증 범위 <small>이 실행이 확인하지 않은 것</small></h4>
    <ul>{items.map(item => <li key={item}>{item}</li>)}</ul>
  </section>;
}

/** Record 034 audit U5 (r0d10, r0d11): per-call usage and the stored prompt/response, one click away under the same run. */
function ModelCalls({ calls, metrics }: { calls: ModelCallRecord[]; metrics: ExecutionMetrics }) {
  if (!calls.length) return null;
  return <section className="model-calls" aria-label="모델 호출 기록">
    <h4 className="sub">모델 호출 {calls.length}회 <small>호출별 토큰·시간 · 저장된 프롬프트·원 응답 · 재판단 없음</small></h4>
    <ol>{calls.map((call, index) => {
      const item = metrics.calls[index];
      return <li key={`${call.stage}-${index}`} data-call={index + 1}><details>
        <summary><span className="stage">{call.stage}</span> {call.skill_id} · 내부 수정 {call.revision_count}회차 · {item.prompt_tokens === null || item.output_tokens === null ? '토큰 미기록' : `입력 ${grouped(item.prompt_tokens)} / 출력 ${grouped(item.output_tokens)} 토큰`} · {seconds(item.elapsed_ms)}</summary>
        <p className="muted">프롬프트</p>{typeof call.formatted_prompt === 'string' ? <pre>{call.formatted_prompt}</pre> : <p className="muted">저장되지 않음</p>}
        <p className="muted">원 응답</p>{typeof call.raw_response === 'string' ? <pre>{call.raw_response}</pre> : <p className="muted">저장되지 않음</p>}
      </details></li>;
    })}</ol>
  </section>;
}

/**
 * The stored core record of one run (output.planning_execution), under the same run ID as the screen above it:
 * original and final input, the core decision with its declarations, trace, model calls and errors. Nothing here is
 * re-judged in the browser; malformed or inconsistent records are shown as such.
 */
export function ExecutionPanel({ snapshot }: { snapshot: RunSnapshot }) {
  const view = planningExecutionView(snapshot);
  if (view.kind === 'none') return null;
  if (view.kind === 'invalid') return <section className="panel planning-panel execution-panel" aria-label="판단 실행 기록">
    <div className="planning-head"><div><p className="eyebrow">CORE RECORD</p><h3>판단 실행 기록 <span className="id">{snapshot.run.id}</span></h3></div></div>
    <div className="unresolved" role="alert"><strong>저장된 판단 기록의 형식이 맞지 않아 표시하지 않습니다</strong><ul>{view.errors.slice(0, 8).map(item => <li key={item}>{item}</li>)}</ul>{view.errors.length > 8 ? <small>외 {view.errors.length - 8}건</small> : null}</div>
  </section>;
  const { execution } = view;
  const original = execution.original_input.request;
  const revised = execution.input.revision_count;
  // The pill names the record kind; its colour follows how the run ended so a held/failed record never looks successful.
  const accepted = execution.status === 'completed' && execution.decision?.action === 'accept';
  const headTone = execution.execution_kind === 'fixture' ? 'fixture' : accepted ? 'done' : execution.status === 'failed' ? 'error' : 'notice';
  const facts = traceFacts(execution.trace);
  return <section className="panel planning-panel execution-panel" aria-label="판단 실행 기록">
    <div className="planning-head"><div><p className="eyebrow">CORE RECORD</p><h3>판단 실행 기록 <span className="id">{snapshot.run.id}</span></h3></div><span className={`run-status ${headTone}`}>{executionKindText(execution.execution_kind, view.model_calls)}<small>{STATUS_LABEL[execution.status]} · 내부 수정 {revised}/2</small></span></div>
    <dl className="run-meta">
      <div><dt>판단 모델</dt><dd>{view.models.length ? view.models.join(', ') : '호출 기록 없음'}</dd></div>
      <div><dt>모델 호출</dt><dd data-field="model-calls">{view.model_calls}회{view.model_calls ? ` · 모델 시간 ${seconds(view.metrics.model_elapsed_ms)}` : ''}</dd></div>
      <div><dt>토큰 <small>모델 서버 보고</small></dt><dd data-field="tokens">{tokenText(view.metrics)}</dd></div>
      <div><dt>전체 실행 시간 <small>조회·검사 포함</small></dt><dd data-field="run-time">{seconds(view.metrics.run_elapsed_ms)}</dd></div>
      <div><dt>생성 설정</dt><dd data-field="settings">{view.model_calls ? view.metrics.settings.join(' / ') || '미기록' : '호출 없음'}</dd></div>
      <div><dt>회차</dt><dd data-field="rounds">요청 회차 {snapshot.request_revision}(기획자 조건 변경) · Agent 내부 수정 {execution.correction_budget?.revision_count ?? revised}/{execution.correction_budget?.max_revisions ?? 2}(같은 요청 안 자동 수정)</dd></div>
      <div><dt>판단한 제품·문서</dt><dd>{execution.input.product.model_id} · 문서 {execution.input.product.document_version} · {sourceKindLabel(execution.input.product.source_kind)}</dd></div>
      <div><dt>입력 원문·기능</dt><dd>{execution.input.sources.length}건 · {execution.input.features.length}개</dd></div>
    </dl>
    {view.problems.length ? <div className="unresolved" role="alert"><strong>저장 기록 불일치</strong><ul>{view.problems.map(item => <li key={item}>{item}</li>)}</ul></div> : null}
    {execution.errors.length ? <div className="unresolved"><strong>실행 중 기록된 오류·검사 실패 {execution.errors.length}건</strong><ul>{execution.errors.map((item, index) => <li key={`${item.code}-${index}`}><code>{item.code}</code> {item.message}</li>)}</ul></div> : null}
    <h4 className="sub">원 요청 <small>Agent에 그대로 전달된 조건</small></h4>
    <dl className="run-meta">
      <div><dt>개선 과제</dt><dd>{original.improvement_task}</dd></div>
      <div><dt>제외 조건</dt><dd>{original.exclusions.length ? original.exclusions.join(' / ') : '없음'}</dd></div>
    </dl>
    {execution.output && execution.decision
      ? <JudgementPanel input={execution.input} output={execution.output} decision={execution.decision} fixture={execution.execution_kind === 'fixture'} facts={facts} />
      : execution.output ? <OutputWithoutDecision output={execution.output} status={execution.status} />
        : <>{execution.decision ? <DecisionOnly decision={execution.decision} /> : null}<p className="muted">판단 출력이 저장되지 않았습니다({STATUS_LABEL[execution.status]}). 위의 오류와 실행 순서를 확인해 주세요.</p></>}
    {execution.rejected_output ? <RejectedCandidates output={execution.rejected_output} facts={facts} /> : null}
    <CheckRounds facts={facts} terminal={execution.correction_budget?.terminal_reason ?? null} />
    <SemanticReviews execution={execution} />
    <ScopeNotice execution={execution} />
    <ModelCalls calls={execution.model_calls} metrics={view.metrics} />
    <h4 className="sub">실행 순서 <small>trace {execution.trace.length}단계 · 시간은 실행 시작부터 누적</small></h4>
    <ol className="events">{execution.trace.map((step, index) => <li key={`${step.stage}-${step.operation}-${index}`}><span className="stage">{step.stage}</span><span>{step.operation}</span>{typeof step.elapsed_ms === 'number' ? <code title="실행 시작부터 누적">+{(step.elapsed_ms / 1000).toFixed(1)}s</code> : null}</li>)}</ol>
  </section>;
}
