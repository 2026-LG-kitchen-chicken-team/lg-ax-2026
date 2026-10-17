import test from 'node:test';
import assert from 'node:assert/strict';
import { RELEASE_SKILLS, RELEASE_ROLES, createReleaseStore, deriveReleaseView, normalizeReleaseSnapshot } from '../src/release.js';

const BASE = Date.parse('2026-10-16T05:00:00Z');
const iso = value => new Date(value).toISOString();
const clone = value => JSON.parse(JSON.stringify(value));
const response = value => ({ ok: true, status: 200, json: async () => value });
const connected = (now = BASE) => ({ status: 'connected', lastReceivedAt: iso(now), staleAfterMs: 20000, sourceStaleAfterMs: 120000 });
const flush = async () => { for (let i = 0; i < 14; i++) await Promise.resolve(); };
function event(id, changes = {}) {
  return { v: 1, id, ts: iso(BASE - 1000), ts_basis: 'codex_log', src: 'codex', hook: 'PreToolUse', session: 'native-session', prompt_id: 'prompt-A', agent_id: null, actor: 'main', tool: 'exec_command', call: `call-${id}`, kind: 'skill_op', node: 'feature-comparison', op: 'compare', ops: [], phase: 'start', basis: 'command_based_mapping', detail: {}, ...changes };
}
const request = (id, changes = {}) => event(id, { ts: iso(BASE - 10000), hook: 'UserPromptSubmit', tool: null, call: null, kind: 'request', node: 'main', op: null, phase: 'point', basis: 'observed', ...changes });
function snapshot(events = [], changes = {}) {
  return { schema_version: 1, source: { kind: 'lgax_release_observer', release: 'product-v0.15.0', engine: 'codex', observed_at: iso(BASE), source_updated_at: events.at(-1)?.ts || null, observer_status: events.length ? 'observing' : 'waiting_for_session', asset_sha256: 'a'.repeat(64), product_install_sha256: 'b'.repeat(64) }, events, db: null, notices: [], ...changes };
}
const viewFor = (events, changes = {}) => deriveReleaseView(snapshot(events, changes), connected(), BASE);
const nativeActivity=(patch={})=>({kind:'codex_native_activity',session_id:'native-session',prompt_id:'prompt-A',state:'working',intent:'readiness',task_code:'check_setup',reported_stage:null,last_event_at:iso(BASE-1000),checks:{},installed_skills:[],skill_reads:[],command_count:0,web_count:0,actions:[],...patch});
test('native preparation animates the central planner and never fabricates Skill execution',()=>{
 const view=viewFor([request('ready-request')],{activity:nativeActivity()});
 assert.deepEqual(view.activeNodes,['overview']);assert.deepEqual(view.activeSkills,[]);assert.equal(view.mainActive,true);assert.match(view.header.text,/실행 준비/);
});
test('actual native readiness results fill the factory while every Skill remains unexecuted',()=>{
 const activity=nativeActivity({state:'finished',checks:{installation:true,file:true,sqlite:true},skill_reads:RELEASE_SKILLS.map(s=>({id:s.id,time:iso(BASE-2000),basis:'read_command_output'}))});
 const view=viewFor([request('ready-request')],{activity});
 assert.deepEqual(view.activeNodes,[]);assert.equal(view.activity.ready,true);assert.match(view.header.text,/상품기획 요청 대기/);
 assert.ok(view.skills.every(s=>s.instructionLoaded&&!s.operationObserved&&!s.active));assert.equal(view.nodes.retrieve.events.length,1);assert.equal(view.nodes.web.events.length,1);assert.equal(view.mainActive,false);assert.equal(view.counts.concepts,null);
});
test('CLI stage reports select a workspace without manufacturing an active Skill',()=>{
 const view=viewFor([request('planning-request')],{activity:nativeActivity({intent:'planning',task_code:'compare_features',reported_stage:'compare'})});
 assert.deepEqual(view.activeNodes,['compare']);assert.deepEqual(view.activeSkills,[]);assert.equal(view.nodes.compare.statusLabel,'CLI 진행 보고');assert.equal(view.skills.find(s=>s.id==='feature-comparison').operationObserved,false);
});
const TRIPLE = { session_id: 'business-session', turn_id: 'business-turn', request_key: 'request-key' };
function db(changes = {}) {
  return { available: true, binding_status: 'matched', binding: TRIPLE, read_at: iso(BASE - 500), workflow: null,
    workflow_events: [{ kind: 'research_plan', observed_at: iso(BASE - 1000), product: '냉장고' }],
    request: { turn_id: TRIPLE.turn_id, request_key: TRIPLE.request_key, status: 'needs_input' },
    turn: { turn_id: TRIPLE.turn_id, status: 'held', revision_count: 0, result_version: 1, valid: true, created_at: iso(BASE - 5000) },
    results: 1, candidates: [{ result_version: 1, created_at: iso(BASE - 500), status: 'held', counts: { pains: 2, existing_features: 3, remaining_pains: 0, concepts: 0 }, contract_valid: true, structural_valid: true, semantic_status: 'unverified', acceptance_ready: false }],
    evidence_delivered: 0, evidence_reviews: 0, cancelled: false, latest_export: { available: true, created_at: iso(BASE - 500) }, ...changes };
}
function environment() {
  let now = BASE, next = 0;
  const timers = new Map();
  return { clock: () => now,
    setTimer: (fn, delay) => { const id = ++next; timers.set(id, { fn, at: now + delay }); return id; },
    clearTimer: id => timers.delete(id),
    async advance(ms) { const end = now + ms; for (;;) { const due = [...timers].filter(([, timer]) => timer.at <= end).sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0]; if (!due) break; now = due[1].at; timers.delete(due[0]); due[1].fn(); await flush(); } now = end; await flush(); },
  };
}
function storeFor(t, fetchImpl, env = environment(), options = {}) {
  const store = createReleaseStore({ ...env, fetchImpl, ...options });
  t.after(() => store.disconnect());
  return { store, env };
}

test('default waits without querying or inventing sessions, people, skills or business counts', () => {
  let calls = 0;
  const store = createReleaseStore({ fetchImpl: async () => { calls++; return response(snapshot()); } });
  const state = store.getSnapshot();
  assert.equal(calls, 0); assert.equal(state.snapshot, null);
  assert.equal(state.view.header.state, 'disconnected'); assert.equal(state.view.sourceMode, 'release');
  assert.deepEqual(state.view.activeNodes, []); assert.deepEqual(state.view.roles, []);
  assert.deepEqual(state.view.events, []); assert.deepEqual(state.view.actors, []);
  assert.equal(state.view.counts.concepts, null); assert.equal(state.view.counts.events, 0);
  store.disconnect();
});

test('a verified installed release with no native events is connected and awaiting a session', () => {
  const view = viewFor([]);
  assert.equal(view.header.state, 'waiting'); assert.match(view.header.text, /릴리즈 연결됨 · Codex 세션 대기/);
  assert.equal(view.sessionId, null); assert.equal(view.observationFresh, false);
  assert.deepEqual(view.activeNodes, []); assert.equal(view.nodes.retrieve.grouped, false);
  assert.equal(Object.keys(view.nodes).length, 6);
  assert.deepEqual(view.nodes.retrieve.skills.map(skill => skill.id), ['evidence-retrieval']);assert.deepEqual(view.nodes.web.skills.map(skill=>skill.id),['web-evidence-collection']);
  assert.equal(view.skills.length, 6); assert.equal(RELEASE_SKILLS.length, 6); assert.equal(RELEASE_ROLES.length, 3);
});

test('reading Skill instructions records use without claiming execution, progress or success', () => {
  const view = viewFor([request('request'), event('load', { kind: 'skill_load', node: 'feature-comparison', basis: 'instruction_loaded', phase:'end' })]);
  const skill = view.nodes.compare.skills[0];
  assert.equal(skill.used, true); assert.equal(skill.instructionLoaded, true); assert.equal(skill.operationObserved, false);
  assert.equal(skill.status, 'loaded'); assert.equal(skill.active, false); assert.deepEqual(view.activeNodes, []);
  assert.match(skill.statusLabel, /지침 조회/); assert.equal(view.counts.skills, 0);assert.equal(view.counts.instructions, 1);
});

test('generic helper with a business binding stays a shell tool, never a promoted Skill', () => {
  const view = viewFor([request('request'), event('helper', { kind: 'shell', node: 'main', basis: 'observed', detail: { business_binding: TRIPLE, programs: ['python'] } })]);
  assert.equal(view.header.state, 'active'); assert.deepEqual(view.activeSkills, []); assert.deepEqual(view.activeNodes, []);
  assert.equal(view.skills.filter(skill => skill.used).length, 0);
  assert.match(view.header.text, /일반 코드·셸 Tool/); assert.equal(view.counts.openCalls, 1);
});

test('command path observation activates the corresponding building and explicit end closes it', () => {
  const start = event('start');
  const active = viewFor([request('request'), start]);
  assert.deepEqual(active.activeSkills, ['feature-comparison']); assert.deepEqual(active.activeNodes, ['compare']);
  assert.equal(active.nodes.compare.status, 'running'); assert.equal(active.nodes.compare.actor, 'main');
  assert.match(active.header.detail, /의미 판단이나 성공을 자동 인증하지/);
  const end = event('end', { phase: 'end', call: start.call, hook: 'PostToolUse', ts: iso(BASE - 500) });
  const completed = viewFor([request('request'), start, end]);
  assert.deepEqual(completed.activeNodes, []); assert.equal(completed.nodes.compare.status, 'completed');
  assert.equal(completed.spans[0].resultKnown, true); assert.match(completed.nodes.compare.statusLabel, /Skill 명령 완료/);
});

test('completed Codex log backfill never fabricates transient current execution', () => {
  const view = viewFor([request('request'), event('backfill-start', { ts: iso(BASE - 5000) }), event('backfill-end', { call: 'call-backfill-start', phase: 'end', ts: iso(BASE - 4000), hook: 'PostToolUse' })]);
  assert.equal(view.spans.length, 1); assert.equal(view.spans[0].status, 'completed');
  assert.deepEqual(view.activeNodes, []); assert.equal(view.nodes.compare.status, 'completed');
});

test('turn cancellation never becomes success after a delayed Tool end, even with truncated start history', () => {
  const start = event('start', { ts: iso(BASE - 3000) });
  const cancel = request('cancel', { kind: 'turn_cancelled', hook: 'Stop', ts: iso(BASE - 2000) });
  const end = event('end', { call: start.call, phase: 'end', ts: iso(BASE - 1000), hook: 'PostToolUse' });
  for (const events of [[request('request'), start, cancel, end], [request('request'), cancel, end]]) {
    const view = viewFor(events);
    assert.equal(view.header.state, 'cancelled'); assert.deepEqual(view.activeNodes, []);
    assert.equal(view.spans[0].status, 'cancelled'); assert.equal(view.spans[0].resultKnown, false);
    assert.equal(view.nodes.compare.status, 'cancelled');
  }
});

test('new request anchor survives older prompt late completion, cancellation and binding', () => {
  const a = event('a', { prompt_id: 'A', ts: iso(BASE - 5000), call: 'a' });
  const b = event('b', { prompt_id: 'B', ts: iso(BASE - 2000), call: 'b', node: 'concept-writing' });
  const late = request('a-late', { prompt_id: 'A', kind: 'turn_cancelled', hook: 'Stop', ts: iso(BASE - 500), detail: { business_binding: TRIPLE } });
  const events = [request('a-req', { prompt_id: 'A', ts: iso(BASE - 6000) }), a, request('b-req', { prompt_id: 'B', ts: iso(BASE - 3000) }), b, late];
  const view = viewFor(events.reverse(), { db: db() });
  assert.equal(view.promptId, 'B'); assert.equal(view.sessionId, 'native-session');
  assert.deepEqual(view.activeNodes, ['concept']); assert.equal(view.bindingState, 'unmatched');
  assert.equal(view.database, null); assert.equal(view.product, null); assert.equal(view.counts.concepts, null);
});

test('a new request with a missing prompt ID is not a wildcard for older prompt events', () => {
  const view = viewFor([
    request('old-request', { prompt_id: 'A', ts: iso(BASE - 6000) }),
    event('old-tool', { prompt_id: 'A', ts: iso(BASE - 5000) }),
    request('new-request', { prompt_id: null, ts: iso(BASE - 3000) }),
    event('new-tool', { prompt_id: null, node: 'needs-structuring', ts: iso(BASE - 2000) }),
    request('late-old', { prompt_id: 'A', kind: 'turn_cancelled', ts: iso(BASE - 1000), detail: { business_binding: TRIPLE } }),
  ], { db: db() });
  assert.equal(view.promptId, null); assert.deepEqual(view.activeNodes, ['structure']);
  assert.equal(view.bindingState, 'unmatched'); assert.equal(view.header.state, 'active');
});

test('a new null-prompt cancellation does not rewrite older nonnull Tool history', () => {
  const view = viewFor([
    request('a-request', { prompt_id: 'A', ts: iso(BASE - 6000) }), event('old-tool', { prompt_id: 'A', ts: iso(BASE - 5000) }),
    request('b-request', { prompt_id: null, ts: iso(BASE - 3000) }),
    request('b-cancel', { prompt_id: null, kind: 'turn_cancelled', ts: iso(BASE - 2000) }),
    event('a-end', { prompt_id: 'A', call: 'call-old-tool', phase: 'end', ts: iso(BASE - 1000) }),
  ]);
  assert.equal(view.header.state, 'cancelled'); assert.equal(view.spans[0].status, 'completed');
  assert.deepEqual(view.activeNodes, []);
});

test('late events from a previous native session do not select that session again', () => {
  const view = viewFor([
    request('old', { session: 'old-session', ts: iso(BASE - 6000) }),
    request('new', { session: 'new-session', prompt_id: 'new-prompt', ts: iso(BASE - 3000) }),
    event('new-tool', { session: 'new-session', prompt_id: 'new-prompt', ts: iso(BASE - 2000) }),
    request('old-end', { session: 'old-session', kind: 'turn_end', ts: iso(BASE - 1000) }),
  ]);
  assert.equal(view.sessionId, 'new-session'); assert.deepEqual(view.events.map(item => item.id), ['new', 'new-tool']);
  assert.deepEqual(view.activeNodes, ['compare']);
});

test('a truncated event window without a request or session-start anchor cannot bind or claim current work', () => {
  const view = viewFor([event('isolated', { detail: { business_binding: TRIPLE } })], { db: db() });
  assert.equal(view.bindingState, 'unmatched'); assert.equal(view.database, null);
  assert.deepEqual(view.activeNodes, []); assert.equal(view.observationFresh, false);
  assert.equal(view.events.length, 1); assert.equal(view.spans[0].status, 'open');
});

test('resuming a session without a new request does not reuse a previous prompt or business binding', () => {
  const view = viewFor([
    request('old-request', { prompt_id: 'A', ts: iso(BASE - 6000) }),
    event('old-tool', { prompt_id: 'A', ts: iso(BASE - 5000), detail: { business_binding: TRIPLE } }),
    request('resume', { prompt_id: null, kind: 'session', phase: 'start', hook: 'SessionStart', ts: iso(BASE - 3000) }),
    request('late-a-end', { prompt_id: 'A', kind: 'turn_end', ts: iso(BASE - 1000), detail: { business_binding: TRIPLE } }),
  ], { db: db() });
  assert.equal(view.promptId, null); assert.equal(view.bindingState, 'unmatched');
  assert.equal(view.header.state, 'recorded'); assert.deepEqual(view.activeNodes, []);
});

test('old child activity cannot join the new request without a matching prompt or explicit launch', () => {
  const role = 'product_official_researcher';
  const oldChild = event('old-child', { actor: role, agent_id: 'child-A', prompt_id: 'A', kind: 'subagent', node: role, basis: 'observed', ts: iso(BASE - 1000) });
  const view = viewFor([request('new-request', { prompt_id: 'B', ts: iso(BASE - 3000) }), oldChild]);
  assert.equal(view.roles.length, 0);assert.equal(view.agents.length,0);assert.deepEqual(view.activeNodes, []);
  // The open request B is the main planner's own turn; the old child still lights nothing.
  assert.equal(view.header.state, 'active'); assert.match(view.header.text, /메인 기획자/); assert.equal(view.mainActive, true);
  const launched = viewFor([request('new-request', { prompt_id: 'B', ts: iso(BASE - 4000) }), event('launch', { prompt_id: 'B', kind: 'delegate', node: role, basis: 'observed', phase: 'end', ts: iso(BASE - 2000), detail: { launched_agent_id: 'child-A', background: true } }), oldChild]);
  assert.equal(launched.roles[0].active, true); assert.equal(launched.roles[0].agentIds[0], 'child-A');
});

test('asynchronous delegation response is a request, not native role completion', () => {
  const role = 'product_review_researcher';
  const delegate = event('delegate', { kind: 'delegate', node: role, phase: 'end', basis: 'observed', detail: { launched_agent_id: 'child-1', background: true } });
  const requested = viewFor([request('request'), delegate]);
  assert.equal(requested.roles.length, 1); assert.equal(requested.roles[0].status, 'requested'); assert.equal(requested.roles[0].active, false);
  const start = event('child-start', { kind: 'subagent', hook: 'SubagentStart', node: role, actor: role, agent_id: 'child-1', call: null, basis: 'observed', ts: iso(BASE - 500) });
  const running = viewFor([request('request'), delegate, start]);
  assert.equal(running.roles[0].status, 'running'); assert.deepEqual(running.activeNodes, []);
  const end = { ...start, id: 'child-end', phase: 'end', hook: 'SubagentStop', ts: iso(BASE - 100) };
  assert.equal(viewFor([request('request'), delegate, start, end]).roles[0].status, 'completed');
});

test('business counts are exposed only for a matching triple in the selected native request', () => {
  const call = event('bound', { kind: 'shell', node: 'main', basis: 'observed', detail: { business_binding: TRIPLE } });
  const view = viewFor([request('request'), call], { db: db() });
  assert.equal(view.bindingState, 'matched'); assert.equal(view.product, '냉장고');
  assert.equal(view.counts.concepts, 0); assert.equal(view.counts.remainingPains, 0); assert.equal(view.counts.results, 1);
  assert.equal(view.database.turn.status, 'held'); assert.equal(view.database.candidates[0].semantic_status, 'unverified');
  assert.equal(view.database.candidates[0].acceptance_ready, false);
  assert.deepEqual(view.database.latest_export, { available: true, created_at: iso(BASE - 500) });
  const mismatched = db({ binding: { ...TRIPLE, request_key: 'different' }, request: null });
  const dropped = viewFor([request('request'), call], { db: mismatched });
  assert.equal(dropped.bindingState, 'unmatched'); assert.equal(dropped.product, null); assert.equal(dropped.counts.results, null);
  assert.throws(() => normalizeReleaseSnapshot(snapshot([], { db: db({ turn: { ...db().turn, turn_id: 'another' } }) })), /형식/);
});

test('unmatched DB never leaks another request through counts, product text or returned database', () => {
  const foreign = db({ binding_status: 'unmatched' });
  const normalized = normalizeReleaseSnapshot(snapshot([], { db: foreign }));
  assert.deepEqual(Object.keys(normalized.db).sort(), ['available', 'binding', 'binding_status', 'read_at']);
  assert.doesNotMatch(JSON.stringify(normalized.db), /냉장고|business-turn/);
  assert.equal(viewFor([], { db: foreign }).counts.concepts, null);
});

test('transport stale and source-old observations remove emphasis without fabricating process exit', () => {
  const data = snapshot([request('request'), event('open')]);
  const stale = deriveReleaseView(data, connected(), BASE + 20000);
  assert.equal(stale.header.state, 'stale'); assert.deepEqual(stale.activeNodes, []); assert.equal(stale.spans[0].status, 'open');
  assert.equal(stale.nodes.compare.status, 'unknown'); assert.match(stale.header.detail, /중지나 완료를 뜻하지/);
  const old = clone(data); old.source.observed_at = iso(BASE + 121000);
  const oldView = deriveReleaseView(old, connected(BASE + 121000), BASE + 121000);
  assert.equal(oldView.connectionStatus, 'connected'); assert.deepEqual(oldView.activeNodes, []);
  assert.equal(oldView.spans[0].status, 'open'); assert.equal(oldView.nodes.compare.status, 'unknown');
  assert.match(oldView.header.detail, /현재 실행 여부를 단정하지/);
});

test('late unrelated prompt traffic cannot refresh the current prompt activity window', () => {
  const view = viewFor([
    request('b-request', { prompt_id: 'B', ts: iso(BASE - 150000) }),
    event('b-open', { prompt_id: 'B', ts: iso(BASE - 140000) }),
    request('old-a-end', { prompt_id: 'A', kind: 'turn_end', ts: iso(BASE - 1000) }),
  ]);
  assert.equal(view.promptId, 'B'); assert.equal(view.observationFresh, false); assert.deepEqual(view.activeNodes, []);
});

test('schema whitelist, hashes and enum types fail closed; untrusted prose is sanitized and bounded', () => {
  for (const mutate of [
    data => { data.source.kind = 'team_controller_sqlite_readonly'; },
    data => { data.source.release = 'latest'; },
    data => { data.source.engine = 'demo'; },
    data => { data.source.product_install_sha256 = 'invalid'; },
    data => { data.events[0].phase = 'complete'; },
    data => { data.events[0].node = 'arbitrary'; },
    data => { data.events[0].detail.accepted = 'yes'; },
    data => { data.events[0].basis = 'instruction_loaded'; },
  ]) { const data = snapshot([event('test')]); mutate(data); assert.throws(() => normalizeReleaseSnapshot(data), /응답 형식/); }
  const raw = snapshot([event('doctor', { kind: 'shell', node: 'main', basis: 'observed', detail: { area: 'conversation', programs: ['product-doctor.py'], raw_command: 'secret' } })], { notices: ['\u001b[31m\u202e원문 지시\u0000' + '가'.repeat(1000)] });
  const normalized = normalizeReleaseSnapshot(raw);
  assert.equal(normalized.notices[0].length, 700); assert.doesNotMatch(normalized.notices[0], /\u001b|\u202e|\u0000/);
  assert.doesNotMatch(JSON.stringify(normalized), /raw_command|secret/); assert.equal(Object.isFrozen(normalized.events[0].detail), true);
  assert.equal(normalizeReleaseSnapshot(snapshot([event('same'), event('same')])).events.length, 1);
  assert.throws(() => normalizeReleaseSnapshot(snapshot([event('same'), event('same', { phase: 'end' })])), /형식/);
});

test('transport only GETs the fixed loopback endpoint, keeps Bearer private and touches no browser storage', async t => {
  let storageTouches = 0;
  const originals = ['localStorage', 'sessionStorage'].map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]);
  originals.forEach(([name]) => Object.defineProperty(globalThis, name, { configurable: true, get() { storageTouches++; throw Error('storage forbidden'); } }));
  t.after(() => originals.forEach(([name, descriptor]) => descriptor ? Object.defineProperty(globalThis, name, descriptor) : delete globalThis[name]));
  const calls = [];
  const { store } = storeFor(t, async (url, options) => { calls.push({ url, options }); return response(snapshot()); });
  await store.connect({ url: 'http://127.0.0.1:8033', token: 'memory-only-secret' });
  await store.refresh();
  assert.equal(storageTouches, 0);
  assert.ok(calls.every(({ url, options }) => url === 'http://127.0.0.1:8033/api/harness/snapshot' && options.method === 'GET' && options.headers.Authorization === 'Bearer memory-only-secret' && options.credentials === 'omit' && options.redirect === 'error'));
  assert.doesNotMatch(JSON.stringify(store.getSnapshot()), /memory-only-secret|Authorization/);
  assert.deepEqual(Object.keys(store).sort(), ['getSnapshot', 'subscribe']);
});

test('non-loopback, URL tokens, alternate paths and unsupported protocols are rejected before fetch', async t => {
  let calls = 0;
  const { store } = storeFor(t, async () => { calls++; return response(snapshot()); });
  for (const url of ['https://localhost:8033', 'http://example.com:8033', 'http://127.0.0.1.evil.test', 'http://user:secret@localhost:8033', 'http://localhost:8033?token=secret', 'http://localhost:8033/#secret', 'http://localhost:8033/api/stage']) await assert.rejects(store.connect({ url, token: 'key' }), /서버|주소/);
  assert.equal(calls, 0);
  await assert.rejects(store.connect({ url: 'http://localhost:8033', token: 'bad key' }), /Bearer/);
  await store.connect({ url: 'http://localhost:8033/api/harness/snapshot', token: 'key' }); assert.equal(calls, 1);
});

test('polling begins after connection and occurs every two seconds until disconnect', async t => {
  const env = environment(); let calls = 0;
  const { store } = storeFor(t, async () => { calls++; const data = snapshot(); data.source.observed_at = iso(env.clock()); return response(data); }, env);
  await env.advance(10000); assert.equal(calls, 0);
  await store.connect({ url: 'http://localhost:8033', token: 'key' }); assert.equal(calls, 1);
  await env.advance(1999); assert.equal(calls, 1);
  await env.advance(1); assert.equal(calls, 2);
  store.disconnect(); await env.advance(5000); assert.equal(calls, 2);
});

test('disconnect preserves the last raw snapshot, clears activity and ignores a late fetch result', async t => {
  let resolve;
  let pending = false;
  const data = snapshot([request('request'), event('open')]);
  const { store } = storeFor(t, async () => pending ? new Promise(done => { resolve = done; }) : response(data));
  await store.connect({ url: 'http://localhost:8033', token: 'key' });
  pending = true; const read = store.refresh(); await flush(); store.disconnect(); await read;
  resolve(response(snapshot([request('late')]))); await flush();
  const state = store.getSnapshot();
  assert.equal(state.connection.status, 'disconnected'); assert.deepEqual(state.snapshot.events.map(item => item.id), ['request', 'open']);
  assert.deepEqual(state.view.activeNodes, []); assert.equal(state.view.spans[0].status, 'open');
  await assert.rejects(store.refresh(), /연결한 뒤/);
});

test('new connection generation discards the prior response and replaces rather than merges events', async t => {
  const pending = [];
  const { store } = storeFor(t, () => new Promise(resolve => pending.push(resolve)));
  const old = store.connect({ url: 'http://localhost:8033', token: 'old' });
  const current = store.connect({ url: 'http://127.0.0.1:8033', token: 'new' });
  pending[1](response(snapshot([request('current')]))); await current;
  pending[0](response(snapshot([request('old')]))); await old; await flush();
  assert.deepEqual(store.getSnapshot().snapshot.events.map(item => item.id), ['current']);
  assert.equal(store.getSnapshot().connection.url, 'http://127.0.0.1:8033');
});

test('older observations cannot replace a new snapshot; equal observations replace the full snapshot', async t => {
  const older = snapshot([request('older')]); older.source.observed_at = iso(BASE - 1000);
  const values = [snapshot([request('first'), event('old-span')]), older, snapshot([request('replacement')])];
  const { store } = storeFor(t, async () => response(values.shift()));
  await store.connect({ url: 'http://localhost:8033', token: 'key' });
  assert.equal(await store.refresh(), null); assert.equal(store.getSnapshot().connection.status, 'stale');
  assert.equal(store.getSnapshot().snapshot.events[0].id, 'first');
  await store.refresh(); assert.deepEqual(store.getSnapshot().snapshot.events.map(item => item.id), ['replacement']);
  assert.equal(store.getSnapshot().connection.status, 'connected');
});

test('timeout and failed authentication reveal safe fixed errors and keep prior observations', async t => {
  const env = environment(); let pending = false;
  const { store } = storeFor(t, async () => pending ? new Promise(() => {}) : response(snapshot([request('saved')])), env);
  await store.connect({ url: 'http://localhost:8033', token: 'private-token' });
  pending = true;
  const promise = store.refresh(); const rejection = assert.rejects(promise, /응답 시간이 초과/);
  await env.advance(8000); await rejection;
  assert.equal(store.getSnapshot().snapshot.events[0].id, 'saved'); assert.doesNotMatch(JSON.stringify(store.getSnapshot()), /private-token/);
  const { store: denied } = storeFor(t, async () => ({ ok: false, status: 401, json: async () => ({ error: 'unsafe secret' }) }));
  await assert.rejects(denied.connect({ url: 'http://localhost:8033', token: 'private-token' }), /인증/);
  assert.doesNotMatch(JSON.stringify(denied.getSnapshot()), /unsafe secret|private-token/);
});
