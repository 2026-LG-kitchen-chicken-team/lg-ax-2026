import { useEffect, useState } from 'react';

/** "1분 5초" style elapsed time; seconds only below a minute. */
export function elapsedText(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return seconds < 60 ? `${seconds}초` : `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
}

/**
 * Shown while a save/rerun waits for the server, which stores the request and runs the judgement before it answers
 * (a real model call can take minutes). The server reports no intermediate stage, so this never invents one: it only
 * says the request is in flight, how long it has waited, that nothing is resent automatically, and where the stage
 * results will appear. The elapsed counter is hidden from screen readers so the live region is announced once.
 */
export function PendingJudgement({ active, action }: { active: boolean; action: string }) {
  const [started, setStarted] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) { setStarted(null); return; }
    const start = Date.now();
    setStarted(start); setNow(start);
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  if (!active || started === null) return null;
  return <div className="pending-judgement" role="status" aria-live="polite">
    <strong>{action} · 서버 응답 대기 중 <span aria-hidden="true">({elapsedText(now - started)})</span></strong>
    <p>서버가 요청을 저장한 뒤 판단까지 마치고 응답합니다. 실제 모델 판단은 몇 분 걸릴 수 있습니다. 같은 요청이 두 번 저장되지 않도록 버튼을 잠갔고, 요청을 자동으로 다시 보내지 않습니다. 창을 닫거나 새로고침하지 마세요.</p>
    <p>단계별 진행은 서버가 응답한 뒤 저장된 실행 기록(판단 순서)으로 보여 드립니다. 지금은 단계 정보를 받지 않으므로 표시하지 않습니다.</p>
  </div>;
}
