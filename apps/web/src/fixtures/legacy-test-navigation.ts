import { vi } from 'vitest';

/** Legacy tests explicitly represent a manual server, which has no shared-session endpoint.
 * An offline transport is an authentication error, not evidence of that server profile. */
export function installManualSessionFixture(): void {
  const transport = globalThis.fetch;
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    input === '/api/prototype/session'
      ? Promise.resolve(new Response('{}', { status: 404, headers: { 'Content-Type': 'application/json' } }))
      : transport(input, init)));
}

/** Explicit entry for tests of the existing screens; the app now starts in the actual-source flow. */
export function enterLegacyEvidence(host: ParentNode): void {
  const target = [...host.querySelectorAll<HTMLButtonElement>('.nav-item')].find(item => item.textContent?.includes('근거 대조'));
  if (!target) throw new Error('기존 근거 대조 메뉴를 찾을 수 없습니다.');
  target.click();
}
