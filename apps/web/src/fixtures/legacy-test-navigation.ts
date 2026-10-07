/** Explicit entry for tests of the existing screens; the app now starts in the actual-source flow. */
export function enterLegacyEvidence(host: ParentNode): void {
  const target = [...host.querySelectorAll<HTMLButtonElement>('.nav-item')].find(item => item.textContent?.includes('근거 대조'));
  if (!target) throw new Error('기존 근거 대조 메뉴를 찾을 수 없습니다.');
  target.click();
}
