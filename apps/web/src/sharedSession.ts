export type SharedPrototypeSession = Readonly<{ token: string; shared_prototype: true }>;
const PENDING_JOB_KEY = 'lgax.research.pending-job';
export function pendingResearchJob(): string | null {
  try {
    const id = sessionStorage.getItem(PENDING_JOB_KEY);
    return id && /^[a-f0-9]{32}$/.test(id) ? id : null;
  } catch { return null; }
}
/** Only an opaque job ID is kept in this tab. Credentials and request bodies remain in memory. */
export function retainResearchJob(id: string): void {
  if (!/^[a-f0-9]{32}$/.test(id)) return;
  try { sessionStorage.setItem(PENDING_JOB_KEY, id); } catch { /* Storage may be disabled. */ }
}
export function forgetResearchJob(id: string): void {
  try { if (sessionStorage.getItem(PENDING_JOB_KEY) === id) sessionStorage.removeItem(PENDING_JOB_KEY); } catch { /* No credential fallback. */ }
}

/** One in-memory check per mounted app, including StrictMode's effect replay. */
export function createSharedSessionLoader(transport: typeof fetch = (input, init) => fetch(input, init)) {
  let pending: Promise<SharedPrototypeSession | null> | undefined;
  return (): Promise<SharedPrototypeSession | null> => {
    if (!pending) pending = (async (): Promise<SharedPrototypeSession | null> => {
      try {
        const response = await transport('/api/prototype/session', {
          method: 'GET', credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
        });
        if (response.status === 404) return null;
        if (!response.ok) throw new Error();
        const body: unknown = await response.json();
        if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error();
        const session = body as Record<string, unknown>;
        if (session.shared_prototype !== true || typeof session.token !== 'string'
          || session.token.length < 32 || session.token.length > 256 || /\s/.test(session.token)) throw new Error();
        return { token: session.token, shared_prototype: true };
      } catch {
        throw new Error('공유 프로토타입 연결을 확인하지 못했습니다. 링크를 다시 열어 주세요.');
      }
    })();
    return pending;
  };
}
