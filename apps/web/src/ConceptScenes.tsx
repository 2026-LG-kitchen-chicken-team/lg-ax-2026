import type { ReactNode } from 'react';
import type { ConceptSceneView, Field, SceneStep } from './planningScenes';
import type { Feature } from './planning';

// W1 (record 최길웅-20261007-056): before/after usage scenes, how the concept works and counter cases for one concept.
// Shows only what the stored run recorded (planningScenes.ts). Missing fields say so; malformed ones show why and not
// their content. Citations reuse the caller's evidence chips so originals open the same way as elsewhere.

type Refs = (ids: string[]) => ReactNode;

function FieldState({ field, label }: { field: Exclude<Field<unknown>, { state: 'ok' }>; label: string }) {
  return field.state === 'malformed'
    ? <p className="scene-malformed" role="alert" data-scene-malformed>{label}: 형식 불일치 · {field.reason}. 내용을 표시하지 않습니다.</p>
    : <p className="muted" data-scene-not-provided>{label}: 미제공</p>;
}

function Steps({ title, field, refs }: { title: string; field: Field<SceneStep[]>; refs: Refs }) {
  return <div className="scene-column">
    <h5>{title}</h5>
    {field.state === 'ok'
      ? <ol className="scene-steps">{field.value.map(step => <li key={step.order} data-scene-step={step.basis}>
        <span className={`scene-basis ${step.basis}`}>{step.basis === 'observed' ? '관찰 근거' : '추정'}</span>
        <p>{step.text}</p>
        {step.evidenceIds.length ? refs(step.evidenceIds) : <small className="muted">연결된 근거 없음</small>}
        {step.missingEvidenceIds.length ? <small className="missing-note">원문을 찾을 수 없는 근거: {step.missingEvidenceIds.join(', ')}</small> : null}
      </li>)}</ol>
      : <FieldState field={field} label={title} />}
  </div>;
}

export function ConceptScenes({ view, features, refs }: { view: ConceptSceneView; features: Feature[]; refs: Refs }) {
  if (!view.provided) {
    return <p className="scene-missing" role="note" data-scenes-not-provided>개선 전후 장면·작동 방식·반대 사례: 이 실행 기록에는 없습니다. 공통 계약(P0)이 정해지고 코어가 기록하면 표시합니다. 화면에서 만들어 넣지 않습니다.</p>;
  }
  const { targetUser, usageContext, mechanism, counterEvidence } = view;
  return <div className="concept-scenes" aria-label="사용 장면과 작동 방식" data-concept-scenes={view.conceptId}>
    <dl className="scene-context">
      <dt>대상 사용자</dt><dd>{targetUser.state === 'ok' ? targetUser.value : <FieldState field={targetUser} label="대상 사용자" />}</dd>
      <dt>사용 상황</dt><dd>{usageContext.state === 'ok' ? usageContext.value : <FieldState field={usageContext} label="사용 상황" />}</dd>
    </dl>
    <div className="scene-columns">
      <Steps title="개선 전" field={view.before} refs={refs} />
      <Steps title="개선 후" field={view.after} refs={refs} />
    </div>
    <h5>작동 방식</h5>
    {mechanism.state === 'ok' ? <div className="scene-mechanism" data-scene-mechanism>
      <p>{mechanism.value.summary}</p>
      <dl>
        <dt>연결 기능</dt><dd>{mechanism.value.featureIds.length ? mechanism.value.featureIds.map(id => features.find(item => item.id === id)?.name ?? `${id}(자료에 없는 기능)`).join(', ') : <span className="muted">없음</span>}</dd>
        <dt>동작 조건</dt><dd>{mechanism.value.conditions.length ? <ul>{mechanism.value.conditions.map(item => <li key={item}>{item}</li>)}</ul> : <span className="muted">없음</span>}</dd>
      </dl>
    </div> : <FieldState field={mechanism} label="작동 방식" />}
    <h5>반대 사례</h5>
    {counterEvidence.state === 'ok' ? <ul className="scene-counter">{counterEvidence.value.map(group => <li key={group.ownerId} data-scene-counter={group.ownerId}>
      <span className="id">{group.ownerId}</span>
      {group.evidenceIds.length ? refs(group.evidenceIds) : <span className="muted">반대 사례 없음(코어 기록)</span>}
      {group.missingEvidenceIds.length ? <small className="missing-note">원문을 찾을 수 없는 근거: {group.missingEvidenceIds.join(', ')}</small> : null}
      {group.alsoSupportingIds.length ? <small className="scope-flag" role="note">지지 근거로도 인용됨: {group.alsoSupportingIds.join(', ')}</small> : null}
    </li>)}</ul> : <FieldState field={counterEvidence} label="반대 사례" />}
  </div>;
}
