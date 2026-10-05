import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError } from './api';
import { exportJudgement } from './judgement';
import { contractErrors, heldItems } from './planning';
import type { DataMode, PlanningRequest, RunSnapshot } from './planning';

/** Questions are taken from this stored run only; answering one never rewrites its decision or evidence. */
export function clarificationQuestions(snapshot: RunSnapshot): string[] {
  const record = exportJudgement(snapshot);
  if (record && !record.record_valid) return [];
  return [...new Set([...(record?.record_valid ? record.questions : []),
    ...heldItems(snapshot).flatMap(item => item.questions), ...snapshot.unconfirmed].map(text => text.trim()).filter(Boolean))];
}

export function buildClarificationRequest(snapshot: RunSnapshot, answers: Record<string, string>): PlanningRequest {
  const questions = clarificationQuestions(snapshot);
  if (Object.keys(answers).some(question => !questions.includes(question))) {
    throw new ApiError('INVALID_ARGUMENT', '현재 실행에 없는 질문의 답변입니다. 실행을 다시 선택하세요.');
  }
  const entered = questions.flatMap(question => {
    const answer = (answers[question] ?? '').trim();
    return answer ? [{ question, answer }] : [];
  });
  if (!entered.length) throw new ApiError('INVALID_ARGUMENT', '답변을 하나 이상 입력하세요.');
  if (entered.some(item => item.answer.length > 2000)) throw new ApiError('INVALID_ARGUMENT', '각 답변은 2,000자 이내로 적어 주세요.');
  // Common PlanningRequest has no answer field. Preserve the original task and append explicit user input,
  // leaving model/document scope and exclusions unchanged. Evidence sufficiency is decided by the next run.
  const appended = `\n\n[기획자의 추가 답변 · 원 실행 ${snapshot.run.id}]\n${entered.map(item => `질문: ${item.question}\n답변: ${item.answer}`).join('\n\n')}`;
  const request = { ...snapshot.request, model_ids: [...snapshot.request.model_ids], exclusions: [...snapshot.request.exclusions],
    improvement_task: snapshot.request.improvement_task + appended };
  const errors = contractErrors('PlanningRequest', request);
  if (errors.length) throw new ApiError('INVALID_ARGUMENT', `요청 규격을 확인하세요. ${errors.join('; ')}`);
  return request;
}

export function ClarificationPanel({ snapshot, mode, busy = false, onSubmit }: {
  snapshot: RunSnapshot; mode: DataMode; busy?: boolean; onSubmit: (request: PlanningRequest) => Promise<void>;
}) {
  const questions = clarificationQuestions(snapshot);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const inFlight = useRef(false);
  const locked = busy || submitting;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || inFlight.current) return;
    try {
      const request = buildClarificationRequest(snapshot, answers);
      inFlight.current = true; setSubmitting(true); setError('');
      await onSubmit(request);
      setAnswers({});
    } catch (failure) { setError(failure instanceof Error ? failure.message : '답변을 저장하지 못했습니다.'); }
    finally { inFlight.current = false; setSubmitting(false); }
  }

  return <form className="panel planning-panel clarification-panel" aria-label="추가 질문에 답변" onSubmit={submit}>
    <p className="eyebrow">CLARIFICATION</p><h3>추가로 확인할 내용</h3>
    <p className="hint">{snapshot.run.id}에 저장된 질문입니다. 답변은 원 요청을 보존한 새 변경 요청으로 전달합니다. 자료를 추가하거나 기존 보류를 해제한 결과가 아니며, 다음 실행에서 다시 판단합니다.</p>
    {mode === 'fixture' ? <p className="fixture-note">화면 확인용 합성 예시 · 답변은 브라우저 초안만 생성하며 모델을 호출하지 않습니다.</p> : null}
    {questions.length ? <>
      <ol className="clarification-list">{questions.map((question, index) => <li key={question}>
        <label htmlFor={`clarification-answer-${index}`}>{question}</label>
        <textarea id={`clarification-answer-${index}`} rows={3} maxLength={2000} disabled={locked}
          value={answers[question] ?? ''} onChange={event => { const text = event.target.value; setAnswers(previous => ({ ...previous, [question]: text })); }} />
      </li>)}</ol>
      <div className="form-footer"><p>답하지 않은 질문은 남겨 둡니다. 제품·문서 버전·제외 조건은 그대로 유지됩니다.</p>
        <button className="text-button" type="button" disabled={locked} onClick={() => { setAnswers({}); setError(''); }}>입력 취소</button>
        <button className="primary-button" type="submit" disabled={locked}>{submitting ? '저장 중…' : mode === 'fixture' ? '답변으로 새 실행 초안' : '답변으로 다시 검토'}</button>
      </div>
    </> : <p className="muted">이 실행에 저장된 추가 질문이 없습니다. 조건을 바꾸려면 아래 재실행 패널을 이용하세요.</p>}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </form>;
}
