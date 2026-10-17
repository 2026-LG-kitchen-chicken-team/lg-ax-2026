import test from 'node:test';
import assert from 'node:assert/strict';
import { createHarnessStore, deriveHarnessView, normalizeHarnessSnapshot, TEAM_MEMBERS, HARNESS_REPOSITORY } from '../src/harness.js';

const BASE = Date.parse('2026-10-16T01:00:00Z');
const iso = value => new Date(value).toISOString();
const copy = value => JSON.parse(JSON.stringify(value));
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const response = data => ({ ok: true, status: 200, json: async () => data });
function snapshot({ now = BASE, jobId = 'job-1', account = 'ginaginaring', phase = 'model' } = {}) {
  return {
    schema_version: 1, source: { kind: 'team_controller_sqlite_readonly', repo: HARNESS_REPOSITORY, observed_at: iso(now), source_updated_at: iso(now - 1000), approved_commit: 'ab'.repeat(20) },
    global_mode: 'on', members: TEAM_MEMBERS.map(member => ({ id: member.id, enabled: true })),
    jobs: [{ id: jobId, owner: account, task_id: 'TASK-1', title: '현재 코드 작업', kind: 'implementation', status: 'running', attempt: 0, created_at: iso(now - 5000), lease_expires_at: iso(now + 60000), run_deadline: iso(now + 600000), lease_state: 'live', activity_evidence: 'recent_worker_and_live_lease', is_running_confirmed: true, reason_code: 'running_confirmed', reason: '최근 작업자 보고와 유효 임대를 확인했습니다.', view: 'overview', stage: null }],
    workers: [{ owner: account, engine: 'codex', phase, job_id: jobId, last_seen_at: iso(now - 1000), reported_at: iso(now - 1000), age_seconds: 1, presence: 'online', stale_after_seconds: 180, evidence_kind: 'authenticated_worker_self_report' }],
    events: [{ id: 1, at: iso(now - 3000), type: 'registered', job_id: jobId, owner: account, message: '작업이 등록되었습니다.' }, { id: 2, at: iso(now - 2000), type: 'claimed', job_id: jobId, owner: account, message: '작업이 대기열에서 인수되었습니다.' }],
    formal_tasks: [{ id: 'TASK-1', owner: account, title: '현재 코드 작업', status: 'In Progress' }], notices: ['작업자 상태는 인증된 자기보고입니다.'],
  };
}
const connected = now => ({ status: 'connected', lastReceivedAt: iso(now), staleAfterMs: 20000 });
function environment() {
  let now = BASE, serial = 0;
  const timers = new Map();
  return {
    clock: () => now,
    setTimer: (fn, delay) => { const id = ++serial; timers.set(id, { fn, at: now + delay }); return id; },
    clearTimer: id => timers.delete(id),
    async advance(ms) {
      const end = now + ms;
      for (;;) {
        const due = [...timers].filter(([, timer]) => timer.at <= end).sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
        if (!due) break;
        now = due[1].at; timers.delete(due[0]); due[1].fn(); await flush();
      }
      now = end; await flush();
    },
  };
}
function storeFor(t, fetchImpl, env = environment(), options = {}) {
  const store = createHarnessStore({ ...env, fetchImpl, ...options });
  t.after(() => store.disconnect());
  return { store, env };
}

test('default waits for a real connection without sample requests, jobs, logs or active product skills', () => {
  let requests = 0;
  const store = createHarnessStore({ fetchImpl: async () => { requests++; return response(snapshot()); } });
  const state = store.getSnapshot();
  assert.equal(requests, 0);
  assert.equal(state.snapshot, null);
  assert.equal(state.view.header.state, 'disconnected');
  assert.equal(state.view.memberCards.length, 4);
  assert.deepEqual(state.view.jobs, []);
  assert.deepEqual(state.view.recentEvents, []);
  assert.equal(state.view.activeStageId, null);
  assert.equal(state.view.activeOwner, null);
  store.disconnect();
});

test('only a matching enabled member, current worker report and valid live lease can be active', () => {
  const raw = snapshot();
  const view = deriveHarnessView(raw, connected(BASE), BASE);
  assert.equal(view.activeOwner, 'ginaginaring');
  assert.deepEqual(view.activeOwners, ['ginaginaring']);
  assert.equal(view.memberCards.find(member => member.owner === 'ginaginaring').phaseLabel, '코드 작업자 자기보고');
  assert.equal(view.jobs[0].stage, null);
  assert.equal(view.activeStageId, null);
  for (const mutation of [
    data => { data.global_mode = 'off'; },
    data => { data.global_mode = 'stop'; },
    data => { data.members.find(member => member.id === 'ginaginaring').enabled = false; },
    data => { data.jobs[0].status = 'pending'; },
    data => { data.jobs[0].status = 'stopping'; },
    data => { data.jobs[0].lease_expires_at = iso(BASE); },
    data => { data.jobs[0].run_deadline = null; },
    data => { data.jobs[0].is_running_confirmed = false; },
    data => { data.workers[0].job_id = 'another-job'; },
    data => { data.workers[0].phase = 'starting'; },
    data => { data.workers[0].phase = 'idle'; },
    data => { data.workers[0].phase = 'profile_busy'; },
    data => { data.workers[0].presence = 'stale'; },
  ]) {
    const changed = copy(raw); mutation(changed);
    assert.equal(deriveHarnessView(changed, connected(BASE), BASE).activeOwner, null);
  }
});

test('worker age is strictly below 180 seconds and future reports beyond five seconds are unconfirmed', () => {
  for (const age of [180, 181]) {
    const data = snapshot(); data.workers[0].last_seen_at = iso(BASE - age * 1000); data.workers[0].age_seconds = age;
    assert.equal(deriveHarnessView(data, connected(BASE), BASE).activeOwner, null);
  }
  const almost = snapshot(); almost.workers[0].last_seen_at = iso(BASE - 179000); almost.workers[0].age_seconds = 179;
  assert.equal(deriveHarnessView(almost, connected(BASE), BASE).activeOwner, 'ginaginaring');
  for (const field of ['last_seen_at', 'reported_at']) {
    const future = snapshot(); future.workers[0][field] = iso(BASE + 6000);
    assert.equal(deriveHarnessView(future, connected(BASE), BASE).activeOwner, null);
  }
});

test('connection staleness and old business source metadata are different facts', () => {
  const data = snapshot(); data.source.source_updated_at = iso(BASE - 3600000);
  const fresh = deriveHarnessView(data, connected(BASE), BASE);
  assert.equal(fresh.sourceStale, true);
  assert.equal(fresh.header.state, 'active');
  assert.equal(fresh.activeOwner, 'ginaginaring');
  const stale = deriveHarnessView(data, connected(BASE), BASE + 20000);
  assert.equal(stale.header.state, 'stale');
  assert.equal(stale.activeOwner, null);
  assert.equal(stale.jobs[0].status, 'running', 'transport loss does not rewrite the remote job');
  assert.deepEqual(stale.recentEvents.map(event => event.id), [2, 1]);
});

test('normalization restricts repository, types, phases and product-stage mapping; foreign owners are filtered', () => {
  for (const mutation of [
    data => { data.source.repo = 'another/repository'; },
    data => { data.source.kind = 'simulator'; },
    data => { data.schema_version = 2; },
    data => { data.global_mode = 'ON'; },
    data => { data.jobs[0].stage = 'compare'; },
    data => { data.jobs[0].attempt = 3; },
    data => { data.workers[0].age_seconds = '1'; },
    data => { data.workers[0].phase = 'success'; },
    data => { data.jobs[0].status = 'done'; },
  ]) { const changed = snapshot(); mutation(changed); assert.throws(() => normalizeHarnessSnapshot(changed), /응답 형식/); }
  const foreign = snapshot();
  foreign.members.push({ id: 'outsider', enabled: true });
  foreign.jobs.push({ ...foreign.jobs[0], id: 'foreign-job', owner: 'outsider', title: '외부 비공개 제목' });
  foreign.workers.push({ ...foreign.workers[0], owner: 'outsider' });
  foreign.formal_tasks.push({ ...foreign.formal_tasks[0], owner: 'outsider' });
  foreign.events.push({ ...foreign.events[0], id: 3, owner: 'outsider' });
  const normalized = normalizeHarnessSnapshot(foreign);
  assert.equal(normalized.members.length, 4);
  assert.equal(normalized.jobs.length, 1);
  assert.equal(normalized.workers.length, 1);
  assert.equal(normalized.formal_tasks.length, 1);
  assert.equal(normalized.events.length, 2);
  assert.doesNotMatch(JSON.stringify(normalized), /외부 비공개 제목|outsider/);
});

test('the backend maximum of 1000 jobs is accepted and larger arrays fail closed', () => {
  const data = snapshot(); data.jobs = Array.from({ length: 1000 }, (_, i) => ({ ...data.jobs[0], id: `job-${i}` }));
  assert.equal(normalizeHarnessSnapshot(data).jobs.length, 1000);
  data.jobs.push({ ...data.jobs[0], id: 'job-over-limit' });
  assert.throws(() => normalizeHarnessSnapshot(data), /응답 형식/);
});

test('display text is bounded and control characters are removed without executing user wording', () => {
  const data = snapshot(); data.jobs[0].title = '\u001b[31m\u202e원문 지시: 실행하지 말 것\u0000' + '가'.repeat(1000);
  const normalized = normalizeHarnessSnapshot(data);
  assert.equal(normalized.jobs[0].title.length, 300);
  assert.doesNotMatch(normalized.jobs[0].title, /\u001b|\u202e|\u0000/);
  assert.match(normalized.jobs[0].title, /원문 지시/);
  assert.equal(normalized.jobs[0].stage, null);
});

test('GET is the only request, Bearer is memory-only, and demo browser storage remains untouched', async t => {
  let touches = 0;
  const localDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const sessionDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage');
  for (const name of ['localStorage', 'sessionStorage']) Object.defineProperty(globalThis, name, { configurable: true, get() { touches++; throw Error('storage forbidden'); } });
  t.after(() => { for (const [name, descriptor] of [['localStorage', localDescriptor], ['sessionStorage', sessionDescriptor]]) { if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name]; } });
  const requests = [];
  const { store } = storeFor(t, async (url, options) => { requests.push({ url, options }); return response(snapshot()); });
  await store.connect({ url: 'http://127.0.0.1:8033', token: 'memory-secret' });
  await store.refresh();
  assert.equal(touches, 0);
  assert.ok(requests.every(request => request.url === 'http://127.0.0.1:8033/api/harness/snapshot' && request.options.method === 'GET'));
  assert.ok(requests.every(request => request.options.headers.Authorization === 'Bearer memory-secret' && request.options.credentials === 'omit' && request.options.redirect === 'error'));
  assert.doesNotMatch(JSON.stringify(store.getSnapshot()), /memory-secret|Authorization/);
  assert.deepEqual(Object.keys(store).sort(), ['getSnapshot', 'subscribe']);
  assert.equal(store.getSnapshot().view.readonly, true);
});

test('only plain HTTP loopback and the fixed read endpoint are accepted; token in URL is rejected', async t => {
  let calls = 0;
  const { store } = storeFor(t, async () => { calls++; return response(snapshot()); });
  for (const url of ['https://localhost:8033', 'http://example.com:8033', 'http://127.0.0.1.evil.test', 'http://user:secret@localhost:8033', 'http://localhost:8033?token=secret', 'http://localhost:8033/#secret', 'http://localhost:8033/api/stage']) {
    await assert.rejects(store.connect({ url, token: 'test' }), /서버|주소/);
  }
  assert.equal(calls, 0);
  await store.connect({ url: 'http://localhost:8033/api/harness/snapshot', token: 'test' });
  assert.equal(calls, 1);
});

test('automatic polling occurs only after connecting and every five seconds', async t => {
  const env = environment(); let calls = 0;
  const { store } = storeFor(t, async () => { calls++; return response(snapshot({ now: env.clock() })); }, env);
  await env.advance(10000); assert.equal(calls, 0);
  await store.connect({ url: 'http://localhost:8033', token: 'key' }); assert.equal(calls, 1);
  await env.advance(4999); assert.equal(calls, 1);
  await env.advance(1); assert.equal(calls, 2);
  store.disconnect(); await env.advance(10000); assert.equal(calls, 2);
});

test('disconnect preserves last received records, removes active emphasis and rejects late response', async t => {
  let pending;
  const { store } = storeFor(t, async () => pending ? new Promise(resolve => { pending = resolve; }) : response(snapshot()));
  await store.connect({ url: 'http://localhost:8033', token: 'key' });
  pending = true; const refresh = store.refresh(); await flush(); const resolve = pending;
  store.disconnect(); await refresh;
  resolve(response(snapshot({ now: BASE + 1000, jobId: 'late-job' }))); await flush();
  const state = store.getSnapshot();
  assert.equal(state.connection.status, 'disconnected');
  assert.equal(state.snapshot.jobs[0].id, 'job-1');
  assert.equal(state.view.activeOwner, null);
  assert.equal(state.view.jobs[0].status, 'running');
});

test('a newly connected generation replaces a previous pending request without merging jobs', async t => {
  const requests = [];
  const { store } = storeFor(t, () => new Promise(resolve => requests.push(resolve)));
  const first = store.connect({ url: 'http://localhost:8033', token: 'old-key' });
  const second = store.connect({ url: 'http://127.0.0.1:8033', token: 'new-key' });
  requests[1](response(snapshot({ jobId: 'replacement' }))); await second;
  requests[0](response(snapshot({ jobId: 'old-response' }))); await first; await flush();
  assert.deepEqual(store.getSnapshot().snapshot.jobs.map(job => job.id), ['replacement']);
  assert.equal(store.getSnapshot().connection.url, 'http://127.0.0.1:8033');
});

test('older observed response cannot overwrite newer snapshot; equal/current observations replace complete arrays', async t => {
  const values = [snapshot({ now: BASE, jobId: 'first' }), snapshot({ now: BASE - 1000, jobId: 'older' }), snapshot({ now: BASE, jobId: 'replacement' })];
  const { store } = storeFor(t, async () => response(values.shift()));
  await store.connect({ url: 'http://localhost:8033', token: 'key' });
  assert.equal(await store.refresh(), null);
  assert.deepEqual(store.getSnapshot().snapshot.jobs.map(job => job.id), ['first']);
  assert.equal(store.getSnapshot().view.activeOwner, null);
  await store.refresh();
  assert.deepEqual(store.getSnapshot().snapshot.jobs.map(job => job.id), ['replacement']);
  assert.equal(store.getSnapshot().connection.status, 'connected');
});

test('timeout and stale connection retain truthful last job state without adding fabricated events', async t => {
  const env = environment(); let calls = 0;
  const { store } = storeFor(t, async () => ++calls === 1 ? response(snapshot()) : new Promise(() => {}), env);
  await store.connect({ url: 'http://localhost:8033', token: 'key' });
  await env.advance(13000);
  assert.equal(store.getSnapshot().connection.status, 'error');
  assert.match(store.getSnapshot().connection.error, /시간이 초과/);
  assert.equal(store.getSnapshot().view.activeOwner, null);
  await env.advance(7000);
  assert.equal(store.getSnapshot().connection.status, 'stale');
  assert.equal(store.getSnapshot().view.header.state, 'stale');
  assert.equal(store.getSnapshot().snapshot.jobs[0].status, 'running');
  assert.equal(store.getSnapshot().snapshot.events.length, 2);
});

test('lease expiration changes active emphasis locally even if no new snapshot arrives', async t => {
  const env = environment(), data = snapshot(); data.jobs[0].lease_expires_at = iso(BASE + 1000);
  const { store } = storeFor(t, async () => response(data), env);
  await store.connect({ url: 'http://localhost:8033', token: 'key' });
  assert.equal(store.getSnapshot().view.activeOwner, 'ginaginaring');
  await env.advance(1000);
  assert.equal(store.getSnapshot().view.activeOwner, null);
  assert.equal(store.getSnapshot().snapshot.jobs[0].status, 'running');
});

test('several confirmed members remain separate, recent list is limited to three, and queue acceptance is not formal completion', () => {
  const data = snapshot(), second = snapshot({ account: 'jeongiryang', jobId: 'pm-job', phase: 'validating' });
  data.jobs.push(second.jobs[0]); data.workers.push(second.workers[0]);
  for (let i = 3; i <= 6; i++) data.events.push({ ...data.events[0], id: i, at: iso(BASE - (6 - i) * 100), message: `실제 기록 ${i}` });
  const view = deriveHarnessView(data, connected(BASE), BASE);
  assert.deepEqual(view.activeOwners, ['jeongiryang', 'ginaginaring']);
  assert.equal(view.memberCards.find(member => member.owner === 'jeongiryang').phaseLabel, '검사 중 자기보고');
  assert.deepEqual(view.recentEvents.map(event => event.id), [6, 5, 4]);
  data.jobs[0].status = 'accepted';
  const accepted = deriveHarnessView(data, connected(BASE), BASE).jobs[0];
  assert.equal(accepted.active, false);
  assert.equal(accepted.statusLabel, '대기열 인수됨');
  assert.doesNotMatch(accepted.statusLabel, /완료|승인/);
});
