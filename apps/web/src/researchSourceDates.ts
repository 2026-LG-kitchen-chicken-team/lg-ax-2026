import type { ResearchSource } from './research';

export function calendarDay(value: string): string | null {
  const match = /^(\d{4}-\d{2}-\d{2})(?:$|T)/.exec(value);
  if (!match) return null;
  const stamp = Date.parse(`${match[1]}T00:00:00Z`);
  return Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0, 10) === match[1] ? match[1] : null;
}
export function confirmedPostingDay(source: ResearchSource): string | null {
  return source.date_kind === 'posting' && source.published_at ? calendarDay(source.published_at) : null;
}
export function sourceDateDisplay(source: ResearchSource): string {
  const posted = confirmedPostingDay(source);
  const purchase = typeof source.metadata?.purchase_date === 'string' && source.metadata.purchase_date.trim()
    ? source.metadata.purchase_date : null;
  return [posted ? `게시일 ${posted}` : '게시일 미확인', purchase ? `구매일 ${purchase}`
    : source.date_kind === 'purchase' ? '원문 날짜 기준 구매일' : ''].filter(Boolean).join(' · ');
}
