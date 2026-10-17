/** Read-only team-controller observer. No execution endpoint or browser storage. */
export const HARNESS_REPOSITORY = '2026-LG-kitchen-chicken-team/lg-ax-2026';
export const TEAM_MEMBERS = Object.freeze([
  Object.freeze({ id: 'jeongiryang', owner: 'jeongiryang', name: '정이량', role: 'PM' }),
  Object.freeze({ id: 'unknownamed', owner: 'unknownamed', name: '황대겸', role: 'CORE' }),
  Object.freeze({ id: 'ginaginaring', owner: 'ginaginaring', name: '신진하', role: 'DATA' }),
  Object.freeze({ id: 'choigilung', owner: 'choigilung', name: '최길웅', role: 'WEB' }),
]);
const MEMBERS = new Map(TEAM_MEMBERS.map(member => [member.id, member]));
const JOB_STATUSES = new Set(['pending', 'running', 'stopping', 'orphaned', 'review_requested', 'completed_review', 'blocked', 'failed', 'accepted']);
const PHASES = new Set(['starting', 'idle', 'profile_busy', 'preflight', 'model', 'validating', 'publishing']);
const ACTIVE_PHASES = new Set(['preflight', 'model', 'validating', 'publishing']);
const EVENT_TYPES = new Set(['registered', 'claimed', 'finished', 'reconciled', 'orphaned', 'mode', 'formal_snapshot']);
const OUTCOMES = new Set(['review_requested', 'completed_review', 'blocked', 'failed']);
const LEASE_STATES = new Set(['live', 'expired', 'inactive', 'unknown']);
const REASONS = new Set(['running_confirmed', 'worker_unconfirmed', 'lease_expired', 'stopping', 'orphaned', 'review_requested', 'completed_review', 'blocked', 'failed', 'accepted', 'pending', 'automation_off']);
const PHASE_LABELS = Object.freeze({ starting: '시작 준비 자기보고', idle: '대기 자기보고', profile_busy: '프로필 사용 중 자기보고', preflight: '사전 확인 자기보고', model: '코드 작업자 자기보고', validating: '검사 중 자기보고', publishing: '게시 중 자기보고' });
const STATUS_LABELS = Object.freeze({ pending: '작업 대기', running: '실행 확인 대기', stopping: '종료 확인 대기', orphaned: '작업 연결 확인 필요', review_requested: '검수 대기', completed_review: '검수 완료', blocked: '차단됨', failed: '실패', accepted: '대기열 인수됨' });
const DEFAULTS = Object.freeze({ pollMs: 5000, timeoutMs: 8000, staleMs: 20000, sourceStaleMs: 180000, freshnessMs: 1000 });
const WORKER_FRESH_SECONDS = 180;

class HarnessError extends Error {
  constructor(code, message) { super(message); this.name = 'HarnessError'; this.code = code; }
}
const invalid = field => { throw new HarnessError('schema', `하네스 응답 형식이 맞지 않습니다 (${field}).`); };
const record = (value, field) => value && typeof value === 'object' && !Array.isArray(value) ? value : invalid(field);
const array = (value, field, limit) => Array.isArray(value) && value.length <= limit ? value : invalid(field);
const integer = (value, field, max = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(value) && value >= 0 && value <= max ? value : invalid(field);
const boolean = (value, field) => typeof value === 'boolean' ? value : invalid(field);
const option = (value, allowed, field) => allowed.has(value) ? value : invalid(field);
function cleanText(value, field, limit = 500) {
  if (typeof value !== 'string') return invalid(field);
  return value.replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, '').replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f]/g, '').trim().slice(0, limit);
}
function identifier(value, field, allowEmpty = false) {
  if (typeof value !== 'string' || value.length > 160 || (!allowEmpty && !value.trim()) || /[\u0000-\u001f\u007f]/.test(value)) return invalid(field);
  return value.trim();
}
function owner(value, field) {
  const id = identifier(value, field).toLowerCase();
  return MEMBERS.has(id) ? id : null;
}
function timestamp(value, field, nullable = true) {
  if (value == null && nullable) return null;
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) return invalid(field);
  return value;
}
function freeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}

export function normalizeHarnessSnapshot(input) {
  const raw = record(input, 'snapshot'), source = record(raw.source, 'source');
  if (raw.schema_version !== 1) invalid('schema_version');
  if (source.kind !== 'team_controller_sqlite_readonly') invalid('source.kind');
  if (typeof source.repo !== 'string' || source.repo.toLowerCase() !== HARNESS_REPOSITORY.toLowerCase()) invalid('source.repo');
  const approved = source.approved_commit ?? null;
  if (approved !== null && (typeof approved !== 'string' || !/^[a-f0-9]{40}$/i.test(approved))) invalid('source.approved_commit');
  const normalizedSource = {
    kind: source.kind, repo: HARNESS_REPOSITORY,
    observed_at: timestamp(source.observed_at, 'source.observed_at', false),
    source_updated_at: timestamp(source.source_updated_at, 'source.source_updated_at'),
    approved_commit: approved,
  };
  const memberIds = new Set(), jobIds = new Set();
  const members = array(raw.members, 'members', 32).flatMap(value => {
    const item = record(value, 'members[]'), id = owner(item.id, 'member.id');
    if (!id) return [];
    if (memberIds.has(id)) invalid('member duplicate'); memberIds.add(id);
    return [{ id, enabled: boolean(item.enabled, 'member.enabled') }];
  });
  const jobs = array(raw.jobs, 'jobs', 1000).flatMap(value => {
    const item = record(value, 'jobs[]'), account = owner(item.owner, 'job.owner');
    if (!account) return [];
    const id = identifier(item.id, 'job.id');
    if (jobIds.has(id)) invalid('job duplicate'); jobIds.add(id);
    if (item.stage != null || (item.view != null && item.view !== 'overview')) invalid('job stage mapping');
    const reasonCode = item.reason_code == null ? null : option(item.reason_code, REASONS, 'job.reason_code');
    return [{
      id, owner: account, task_id: identifier(item.task_id, 'job.task_id', true), title: cleanText(item.title, 'job.title', 300),
      kind: option(item.kind, new Set(['implementation', 'review']), 'job.kind'), status: option(item.status, JOB_STATUSES, 'job.status'),
      attempt: item.attempt == null ? null : integer(item.attempt, 'job.attempt', 2),
      created_at: timestamp(item.created_at, 'job.created_at'), lease_expires_at: timestamp(item.lease_expires_at, 'job.lease_expires_at'), run_deadline: timestamp(item.run_deadline, 'job.run_deadline'),
      lease_state: option(item.lease_state, LEASE_STATES, 'job.lease_state'),
      activity_evidence: option(item.activity_evidence, new Set(['recent_worker_and_live_lease', 'unconfirmed']), 'job.activity_evidence'),
      is_running_confirmed: boolean(item.is_running_confirmed, 'job.is_running_confirmed'),
      reason_code: reasonCode, reason: item.reason == null ? '' : cleanText(item.reason, 'job.reason', 500),
      view: 'overview', stage: null,
    }];
  });
  const workers = array(raw.workers, 'workers', 100).flatMap(value => {
    const item = record(value, 'workers[]'), account = owner(item.owner, 'worker.owner');
    if (!account) return [];
    if (item.evidence_kind !== 'authenticated_worker_self_report') invalid('worker.evidence_kind');
    if (item.stale_after_seconds !== WORKER_FRESH_SECONDS) invalid('worker.stale_after_seconds');
    const age = item.age_seconds ?? null;
    if (age !== null && (typeof age !== 'number' || !Number.isFinite(age) || age < 0 || age > 315360000)) invalid('worker.age_seconds');
    return [{
      owner: account, engine: item.engine == null ? null : option(item.engine, new Set(['codex', 'claude']), 'worker.engine'),
      phase: item.phase == null ? null : option(item.phase, PHASES, 'worker.phase'),
      job_id: item.job_id == null ? null : identifier(item.job_id, 'worker.job_id'),
      last_seen_at: timestamp(item.last_seen_at, 'worker.last_seen_at'), reported_at: timestamp(item.reported_at, 'worker.reported_at'),
      age_seconds: age, presence: option(item.presence, new Set(['online', 'stale', 'never_seen']), 'worker.presence'),
      stale_after_seconds: WORKER_FRESH_SECONDS, evidence_kind: item.evidence_kind,
    }];
  });
  const events = array(raw.events, 'events', 1000).flatMap(value => {
    const item = record(value, 'events[]');
    const account = item.owner == null ? null : owner(item.owner, 'event.owner');
    if (item.owner != null && !account) return [];
    const jobId = item.job_id == null ? null : identifier(item.job_id, 'event.job_id');
    if (!account && jobId && !jobIds.has(jobId)) return [];
    return [{
      id: integer(item.id, 'event.id'), at: timestamp(item.at, 'event.at', false), type: option(item.type, EVENT_TYPES, 'event.type'),
      job_id: jobId, owner: account, outcome: item.outcome == null ? null : option(item.outcome, OUTCOMES, 'event.outcome'), message: cleanText(item.message, 'event.message', 700),
    }];
  });
  const formalTasks = array(raw.formal_tasks, 'formal_tasks', 2000).flatMap(value => {
    const item = record(value, 'formal_tasks[]'), account = owner(item.owner, 'formal_task.owner');
    return account ? [{ id: identifier(item.id, 'formal_task.id'), owner: account, title: cleanText(item.title, 'formal_task.title', 300), status: cleanText(item.status, 'formal_task.status', 80) }] : [];
  });
  return freeze({
    schema_version: 1, source: normalizedSource, global_mode: option(raw.global_mode, new Set(['on', 'off', 'stop']), 'global_mode'),
    members, jobs, workers, events, formal_tasks: formalTasks,
    notices: array(raw.notices, 'notices', 50).map(value => cleanText(value, 'notice', 700)),
  });
}

function ageSeconds(value, nowMs) { return value == null ? null : Math.max(0, (nowMs - Date.parse(value)) / 1000); }
function workerAge(worker, snapshot, nowMs) {
  const timestampAge = worker.last_seen_at == null ? null : (nowMs - Date.parse(worker.last_seen_at)) / 1000;
  if (timestampAge !== null && timestampAge < -5) return null;
  if (worker.reported_at !== null && Date.parse(worker.reported_at) > nowMs + 5000) return null;
  const observedAge = ageSeconds(snapshot.source.observed_at, nowMs) || 0;
  const reportedAge = worker.age_seconds == null ? null : worker.age_seconds + observedAge;
  const ages = [timestampAge, reportedAge].filter(value => value !== null && Number.isFinite(value));
  return ages.length ? Math.max(0, ...ages) : null;
}

export function deriveHarnessView(snapshot, connection = {}, nowMs = Date.now()) {
  const data = snapshot ? normalizeHarnessSnapshot(snapshot) : null;
  const staleMs = connection.staleAfterMs ?? DEFAULTS.staleMs;
  const receivedAge = ageSeconds(connection.lastReceivedAt, nowMs);
  const observationAge = data ? ageSeconds(data.source.observed_at, nowMs) : null;
  const clockSkew = data ? Date.parse(data.source.observed_at) > nowMs + 5000 : false;
  let connectionStatus = connection.status || 'disconnected';
  if (connectionStatus === 'connected' && (receivedAge == null || receivedAge * 1000 >= staleMs || observationAge == null || observationAge * 1000 >= staleMs || clockSkew)) connectionStatus = 'stale';
  if (['error', 'stale'].includes(connectionStatus) && data && receivedAge !== null && receivedAge * 1000 >= staleMs) connectionStatus = 'stale';
  const fresh = connectionStatus === 'connected';
  const enabled = new Map((data?.members || []).map(member => [member.id, member.enabled]));
  const workers = (data?.workers || []).map(worker => {
    const effectiveAge = workerAge(worker, data, nowMs);
    const online = worker.presence === 'online' && worker.last_seen_at !== null && worker.reported_at !== null && effectiveAge !== null && effectiveAge < WORKER_FRESH_SECONDS;
    return { ...worker, effective_age_seconds: effectiveAge, effective_presence: online ? 'online' : worker.last_seen_at ? 'stale' : 'never_seen', online };
  });
  const jobs = (data?.jobs || []).map(job => {
    const matchingWorker = workers.find(worker => worker.owner === job.owner && worker.job_id === job.id && worker.online && ACTIVE_PHASES.has(worker.phase));
    const liveLease = job.lease_state === 'live' && job.lease_expires_at !== null && Date.parse(job.lease_expires_at) > nowMs;
    const beforeDeadline = job.run_deadline !== null && Date.parse(job.run_deadline) > nowMs;
    const active = Boolean(fresh && data.global_mode === 'on' && enabled.get(job.owner) === true && job.status === 'running' && job.is_running_confirmed === true && job.activity_evidence === 'recent_worker_and_live_lease' && liveLease && beforeDeadline && matchingWorker);
    let confirmationReason = job.reason;
    if (!fresh) confirmationReason = '현재 연결에서 실행 상태를 확인할 수 없습니다. 마지막 수신 기록입니다.';
    else if (data.global_mode !== 'on') confirmationReason = `팀 컨트롤러가 ${data.global_mode.toUpperCase()}입니다.`;
    else if (job.status === 'running' && !liveLease) confirmationReason = '유효한 작업 임대를 확인할 수 없습니다.';
    else if (job.status === 'running' && !matchingWorker) confirmationReason = '같은 작업을 보고하는 최근 인증 작업자를 확인할 수 없습니다.';
    return { ...job, active, statusLabel: active ? PHASE_LABELS[matchingWorker.phase] : STATUS_LABELS[job.status], phase: active ? matchingWorker.phase : null, confirmationReason };
  });
  const activeOwners = TEAM_MEMBERS.filter(member => jobs.some(job => job.owner === member.id && job.active)).map(member => member.id);
  const memberCards = TEAM_MEMBERS.map(member => {
    const ownJobs = jobs.filter(job => job.owner === member.id);
    const job = ownJobs.find(item => item.active) || ownJobs.find(item => item.status === 'running') || ownJobs[0] || null;
    const ownWorkers = workers.filter(worker => worker.owner === member.id).sort((a, b) => (Date.parse(b.last_seen_at) || 0) - (Date.parse(a.last_seen_at) || 0));
    const worker = ownWorkers.find(item => item.job_id === job?.id) || ownWorkers[0] || null;
    const active = Boolean(job?.active);
    let statusLabel = job?.statusLabel || (worker?.effective_presence === 'online' ? '작업 대기' : worker?.effective_presence === 'stale' ? '작업자 보고 오래됨' : '작업자 상태 미수신');
    if (enabled.get(member.id) === false) statusLabel = '팀원 비활성';
    if (!fresh && data) statusLabel = '마지막 수신 상태';
    return {
      ...member, enabled: enabled.has(member.id) ? enabled.get(member.id) : null, active, statusLabel,
      phase: worker?.phase || null, phaseLabel: worker?.phase ? PHASE_LABELS[worker.phase] : '작업 단계 미제공',
      task: job?.title || null, jobId: job?.id || null, taskId: job?.task_id || null,
      presence: worker?.effective_presence || 'never_seen', lastSeenAt: worker?.last_seen_at || null,
      ageSeconds: worker?.effective_age_seconds ?? null, engine: worker?.engine || null,
      evidenceLabel: worker ? '인증 작업자 자기보고' : '작업자 보고 미수신', detail: job?.confirmationReason || null,
    };
  });
  const recentEvents = [...(data?.events || [])].sort((a, b) => Date.parse(b.at) - Date.parse(a.at) || b.id - a.id).slice(0, 3).map(event => ({ ...event, time: event.at }));
  const reviewQueue = jobs.filter(job => job.status === 'review_requested');
  const sourceAge = data ? ageSeconds(data.source.source_updated_at, nowMs) : null;
  const sourceStale = sourceAge !== null && sourceAge * 1000 > (connection.sourceStaleAfterMs ?? DEFAULTS.sourceStaleMs);
  let header, nextAction;
  if (connectionStatus === 'connecting') {
    header = { state: 'connecting', text: '하네스 연결 확인 중', detail: '읽기 전용 상태 응답을 기다리고 있습니다.' };
    nextAction = '연결 결과를 기다리거나 연결을 해제하세요.';
  } else if (connectionStatus === 'disconnected') {
    header = { state: 'disconnected', text: '하네스 연결 대기', detail: data ? '연결을 해제했습니다. 마지막 수신 기록을 보존합니다.' : '실제 하네스 상태를 아직 수신하지 않았습니다.' };
    nextAction = '로컬 읽기 서버 주소와 Bearer 키로 연결하세요.';
  } else if (connectionStatus === 'stale') {
    header = { state: 'stale', text: clockSkew ? '하네스 관측 시각 확인 필요' : '하네스 수신 오래됨', detail: '마지막 수신 기록입니다. 현재 실행 상태를 확인할 수 없습니다.' };
    nextAction = '읽기 서버 연결을 확인하고 상태를 다시 읽으세요.';
  } else if (connectionStatus === 'error' || !data) {
    header = { state: 'error', text: '하네스 연결 확인 필요', detail: connection.error || '실제 하네스 상태를 수신하지 못했습니다.' };
    nextAction = '서버 주소와 인증을 확인한 뒤 다시 연결하세요.';
  } else if (data.global_mode !== 'on') {
    header = { state: 'team_off', text: `팀 컨트롤러 ${data.global_mode.toUpperCase()}`, detail: '읽기 전용 관제입니다. 현재 실행 중이라고 표시하지 않습니다.' };
    nextAction = '수신된 작업·검수 기록을 확인하세요. 원격 실행 제어는 제공하지 않습니다.';
  } else if (activeOwners.length) {
    const first = memberCards.find(member => member.owner === activeOwners[0]);
    header = { state: 'active', text: activeOwners.length === 1 ? `${first.name} · ${first.phaseLabel}${first.task ? ` · ${first.task}` : ''}` : `${activeOwners.map(account => MEMBERS.get(account).name).join(' · ')} 작업자 자기보고 확인`, detail: '최근 인증 작업자 자기보고와 같은 작업의 유효 임대를 확인했습니다.' };
    nextAction = '현재 작업과 최근 기록을 확인하세요.';
  } else {
    header = { state: 'waiting', text: reviewQueue.length ? `검수 대기 ${reviewQueue.length}건 · 확인된 실행 작업 없음` : '확인된 실행 작업 없음', detail: '등록·대기·과거 기록을 실제 실행으로 표시하지 않습니다.' };
    nextAction = '작업 상태와 검수 대기 목록을 확인하세요.';
  }
  return freeze({
    readonly: true, sourceMode: 'harness', activeStageId: null,
    header, nextAction, connectionStatus, memberCards, jobs, recentEvents, formalTasks: data?.formal_tasks || [], reviewQueue,
    activeOwner: activeOwners[0] || null, activeOwners, globalMode: data?.global_mode ?? null,
    observedAt: data?.source.observed_at ?? null, sourceUpdatedAt: data?.source.source_updated_at ?? null,
    sourceAgeSeconds: sourceAge, sourceStale, notices: data?.notices || [],
  });
}

function endpointFor(value) {
  let url;
  try { url = new URL(value); } catch { throw new HarnessError('url', '로컬 읽기 서버 주소를 확인해 주세요.'); }
  if (url.protocol !== 'http:' || !['localhost', '127.0.0.1'].includes(url.hostname.toLowerCase()) || url.username || url.password || url.search || url.hash || !['/', '/api/harness/snapshot'].includes(url.pathname)) throw new HarnessError('url', 'http://localhost 또는 http://127.0.0.1의 읽기 서버만 연결할 수 있습니다. 키를 URL에 넣지 마세요.');
  return { url: url.origin, endpoint: `${url.origin}/api/harness/snapshot` };
}

export class HarnessStore {
  #state; #listeners = new Set(); #token = ''; #endpoint = ''; #fetch; #clock; #setTimer; #clearTimer; #Abort;
  #pollTimer = null; #freshnessTimer = null; #controller = null; #generation = 0; #request = 0; #options;
  constructor(options = {}) {
    this.#fetch = options.fetchImpl || globalThis.fetch?.bind(globalThis);
    this.#clock = options.clock || (() => Date.now());
    this.#setTimer = options.setTimer || globalThis.setTimeout.bind(globalThis);
    this.#clearTimer = options.clearTimer || globalThis.clearTimeout.bind(globalThis);
    this.#Abort = options.AbortControllerImpl || globalThis.AbortController;
    this.#options = { ...DEFAULTS };
    for (const name of Object.keys(DEFAULTS)) if (options[name] != null) { const value = options[name]; if (!Number.isFinite(value) || value < 1 || value > 3600000) throw new HarnessError('option', '읽기 연결 시간 설정이 맞지 않습니다.'); this.#options[name] = value; }
    const connection = { status: 'disconnected', url: '', lastReceivedAt: null, error: null, staleAfterMs: this.#options.staleMs, sourceStaleAfterMs: this.#options.sourceStaleMs };
    this.#state = { snapshot: null, connection, view: deriveHarnessView(null, connection, this.#clock()) };
    this.getSnapshot = () => this.#state;
    this.subscribe = listener => { this.#listeners.add(listener); return () => this.#listeners.delete(listener); };
  }
  #publish(snapshot = this.#state.snapshot, patch = {}) {
    let connection = { ...this.#state.connection, ...patch };
    const view = deriveHarnessView(snapshot, connection, this.#clock());
    if (['connected', 'error'].includes(connection.status) && view.connectionStatus === 'stale') connection = { ...connection, status: 'stale' };
    this.#state = freeze({ snapshot, connection, view });
    this.#listeners.forEach(listener => listener());
  }
  #clearTimers() {
    if (this.#pollTimer !== null) this.#clearTimer(this.#pollTimer);
    if (this.#freshnessTimer !== null) this.#clearTimer(this.#freshnessTimer);
    this.#pollTimer = null; this.#freshnessTimer = null;
  }
  #scheduleFreshness(generation) {
    if (generation !== this.#generation || !this.#endpoint) return;
    this.#freshnessTimer = this.#setTimer(() => {
      if (generation !== this.#generation || !this.#endpoint) return;
      this.#publish(); this.#scheduleFreshness(generation);
    }, this.#options.freshnessMs);
  }
  #schedulePoll(generation) {
    if (this.#pollTimer !== null) this.#clearTimer(this.#pollTimer);
    if (generation !== this.#generation || !this.#endpoint) return;
    this.#pollTimer = this.#setTimer(() => { this.#pollTimer = null; if (generation === this.#generation) this.refresh().catch(() => {}); }, this.#options.pollMs);
  }
  async connect({ url, token = '' } = {}) {
    const target = endpointFor(url);
    if (typeof token !== 'string' || token.length > 4096 || /[\s\u0000-\u001f\u007f]/.test(token)) throw new HarnessError('token', 'Bearer 키 형식을 확인해 주세요.');
    if (typeof this.#fetch !== 'function' || typeof this.#Abort !== 'function') throw new HarnessError('runtime', '이 환경에서 읽기 연결을 사용할 수 없습니다.');
    this.#generation++; this.#request++; this.#controller?.abort(); this.#clearTimers();
    this.#endpoint = target.endpoint; this.#token = token;
    this.#publish(this.#state.snapshot, { status: 'connecting', url: target.url, error: null });
    this.#scheduleFreshness(this.#generation);
    return this.refresh();
  }
  async refresh() {
    if (!this.#endpoint) throw new HarnessError('disconnected', '읽기 서버에 연결한 뒤 새로 읽을 수 있습니다.');
    const generation = this.#generation, request = ++this.#request;
    this.#controller?.abort();
    const controller = new this.#Abort(); this.#controller = controller;
    if (this.#pollTimer !== null) { this.#clearTimer(this.#pollTimer); this.#pollTimer = null; }
    const headers = { Accept: 'application/json' };
    if (this.#token) headers.Authorization = `Bearer ${this.#token}`;
    let timer;
    const stillCurrent = () => generation === this.#generation && request === this.#request && Boolean(this.#endpoint);
    try {
      const timeout = new Promise((_, reject) => { timer = this.#setTimer(() => { reject(new HarnessError('timeout', '하네스 읽기 응답 시간이 초과되었습니다.')); controller.abort(); }, this.#options.timeoutMs); });
      const cancelled = new Promise((_, reject) => controller.signal.addEventListener('abort', () => reject(new HarnessError('cancelled', '이전 읽기 요청을 취소했습니다.')), { once: true }));
      const read = (async () => {
        const response = await this.#fetch(this.#endpoint, { method: 'GET', headers, cache: 'no-store', credentials: 'omit', redirect: 'error', signal: controller.signal });
        if (!response?.ok) throw new HarnessError('http', response?.status === 401 || response?.status === 403 ? '하네스 읽기 인증을 확인해 주세요.' : '하네스 읽기 응답을 받지 못했습니다.');
        return normalizeHarnessSnapshot(await response.json());
      })();
      const snapshot = await Promise.race([read, timeout, cancelled]);
      if (!stillCurrent()) return null;
      if (this.#state.snapshot && Date.parse(snapshot.source.observed_at) < Date.parse(this.#state.snapshot.source.observed_at)) {
        this.#publish(this.#state.snapshot, { status: 'stale', error: '이전 관측 응답을 건너뛰었습니다. 마지막 수신 기록을 보존합니다.' });
        return null;
      }
      this.#publish(snapshot, { status: 'connected', lastReceivedAt: new Date(this.#clock()).toISOString(), error: null });
      return snapshot;
    } catch (error) {
      if (!stillCurrent()) return null;
      const safe = error instanceof HarnessError ? error : new HarnessError('network', '하네스 읽기 연결을 확인해 주세요.');
      this.#publish(this.#state.snapshot, { status: 'error', error: safe.message });
      throw safe;
    } finally {
      if (timer !== undefined) this.#clearTimer(timer);
      if (stillCurrent()) { this.#controller = null; this.#schedulePoll(generation); }
    }
  }
  disconnect() {
    this.#generation++; this.#request++; this.#controller?.abort(); this.#controller = null;
    this.#clearTimers(); this.#token = ''; this.#endpoint = '';
    this.#publish(this.#state.snapshot, { status: 'disconnected', error: null });
  }
}
export function createHarnessStore(options = {}) { return new HarnessStore(options); }
export const harnessStore = createHarnessStore();
export default harnessStore;
