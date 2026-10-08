export type SharedPrototypeSession = Readonly<{ token: string; shared_prototype: true }>;

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
