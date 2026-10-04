import type { Evidence } from './domain';
import { judgementView } from './judgement';
import type { JudgementDecision, JudgementInput, JudgementOutput } from './judgement';

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
export function JudgementPanel({ input, output, decision, fixture }: { input: JudgementInput; output: JudgementOutput; decision: JudgementDecision; fixture: boolean }) {
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
