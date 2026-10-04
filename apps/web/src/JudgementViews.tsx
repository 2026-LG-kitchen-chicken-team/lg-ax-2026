import type { Evidence } from './domain';
import { judgementView, planningExecutionView, violationText } from './judgement';
import type { JudgementDecision, JudgementInput, JudgementOutput, PlanningExecution, SemanticAssessment, StoredDecision } from './judgement';
import type { RunSnapshot } from './planning';

const POLARITY: Record<string, string> = { complaint: '불편', positive: '긍정', conflicting: '상충', irrelevant: '무관', uncertain: '불확실' };
const SUPPORT: Record<string, string> = { explicit_supported: '설명서에 지원 명시', explicit_unsupported: '설명서에 미지원 명시', unmentioned: '설명서 미언급', conflicting: '설명서 상충' };
const RESOLUTION: Record<string, string> = { resolved: '해결됨', remaining: '불편 남음', unknown: '알 수 없음' };
const DUPLICATION: Record<string, string> = { distinct: '기존 기능과 다름', duplicate: '기존 기능과 중복', uncertain: '중복 여부 불확실' };

function TextList({ title, items, empty }: { title: string; items: string[]; empty?: string }) {
  if (!items.length && !empty) return null;
  return <><h4>{title} <span className="count">{items.length}건</span></h4>{items.length ? <ul>{items.map(item => <li key={item}>{item}</li>)}</ul> : <p className="muted">{empty}</p>}</>;
}

/**
 * One core judgement as the planner sees it: the core's review decision first, then the declared assessments it was
 * checked against. Fixture declarations are labelled as such so they never read as model output.
 */
export function JudgementPanel({ input, output, decision, fixture }: { input: JudgementInput; output: JudgementOutput; decision: JudgementDecision | StoredDecision; fixture: boolean }) {
  const view = judgementView(input, output, decision);
  const sources = new Map<string, Evidence>(input.sources.map(item => [item.id, item]));
  const featureName = (id: string) => input.features.find(item => item.id === id)?.name ?? id;
  return <section className="judgement-panel" aria-label="판단 계약 검사 결과">
    <div className="judgement-head">
      <span className={`run-status ${view.tone}`} title={view.detail}>{view.label}<small>코어 검사 결정 · {decision.action}</small></span>
      <span className="id">{output.model_id} · 문서 {output.document_version} · 내부 수정 {output.revision_count}/2 · 입력 {output.input_sha256.slice(0, 12)}</span>
    </div>
    <p className="judgement-detail">{view.detail}</p>
    {fixture ? <p className="fixture-note">사람이 작성한 판단 선언(fixture)과 코어 검사기의 실제 결정입니다. 모델이 생성한 결과가 아닙니다.</p> : null}
    {view.declared_status_overridden ? <p className="scope-flag">판단이 스스로 선언한 상태는 '{output.status}'였지만, 코어 검사 결정에 따라 '{view.label}'로 표시합니다.</p> : null}
    <TextList title="검사에서 발견한 문제" items={view.violations} empty="없음" />
    <TextList title="다른 모델·문서 버전의 원문" items={view.out_of_scope_sources} />
    <h4>리뷰 판단</h4>
    <ul className="quote-list">{output.review_assessments.map(item => <li key={item.evidence_id}><span className={`status-pill ${item.polarity}`}>{POLARITY[item.polarity]}</span>{sources.get(item.evidence_id) ? <q>{sources.get(item.evidence_id)!.text}</q> : <span className="missing-note">{item.evidence_id} · 원문을 찾을 수 없습니다(자료 누락)</span>}<small>{item.evidence_id} · {item.reason}</small></li>)}</ul>
    <h4>기능 대조</h4>
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
const CRITERION: Record<string, string> = { mechanism: '작동 방식', difference_from_current_features: '현재 기능과 차이', unverified_assumptions: '미검증 가정', unsupported_claims: '근거 없는 단정' };

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
function RejectedCandidates({ output }: { output: JudgementOutput }) {
  if (!output.concepts.length) return null;
  return <section className="rejected-output" aria-label="거절된 후보">
    <h4 className="sub">검사에서 거절된 마지막 후보 <small>{output.concepts.length}개 · 선택·내보내기 대상 아님</small></h4>
    <ul>{output.concepts.map(concept => <li key={concept.id}><span className="id">{concept.id}</span> {concept.title}<span className="scope-flag"> · 거절됨</span></li>)}</ul>
  </section>;
}

const KIND_LABEL: Record<string, string> = { live_model: '실제 모델 실행 기록(저장된 결과)', fixture: 'fixture 실행 기록(모델 호출 아님)' };
const STATUS_LABEL: Record<string, string> = { completed: '완료', held: '보류', failed: '실패' };

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
  return <section className="panel planning-panel execution-panel" aria-label="판단 실행 기록">
    <div className="planning-head"><div><p className="eyebrow">CORE RECORD</p><h3>판단 실행 기록 <span className="id">{snapshot.run.id}</span></h3></div><span className={`run-status ${execution.execution_kind === 'fixture' ? 'fixture' : 'done'}`}>{KIND_LABEL[execution.execution_kind]}<small>{STATUS_LABEL[execution.status]} · 내부 수정 {revised}/2</small></span></div>
    <dl className="run-meta">
      <div><dt>판단 모델</dt><dd>{view.models.length ? view.models.join(', ') : '호출 기록 없음'}</dd></div>
      <div><dt>모델 호출</dt><dd>{view.model_calls}회{view.elapsed_ms !== null ? ` · ${(view.elapsed_ms / 1000).toFixed(1)}초` : ''}</dd></div>
      <div><dt>판단한 제품·문서</dt><dd>{execution.input.product.model_id} · 문서 {execution.input.product.document_version} · {execution.input.product.source_kind}</dd></div>
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
      ? <JudgementPanel input={execution.input} output={execution.output} decision={execution.decision} fixture={execution.execution_kind === 'fixture'} />
      : <>{execution.decision ? <DecisionOnly decision={execution.decision} /> : null}<p className="muted">판단 출력이 저장되지 않았습니다({STATUS_LABEL[execution.status]}). 위의 오류와 실행 순서를 확인해 주세요.</p></>}
    {execution.rejected_output ? <RejectedCandidates output={execution.rejected_output} /> : null}
    <SemanticReviews execution={execution} />
    <h4 className="sub">실행 순서 <small>trace {execution.trace.length}단계</small></h4>
    <ol className="events">{execution.trace.map((step, index) => <li key={`${step.stage}-${step.operation}-${index}`}><span className="stage">{step.stage}</span><span>{step.operation}</span>{typeof step.elapsed_ms === 'number' ? <code>{(step.elapsed_ms / 1000).toFixed(1)}s</code> : null}</li>)}</ol>
  </section>;
}
