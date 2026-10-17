/** Installed product observations (any product-vX.Y.Z). Product text and native logs are data, not code. */
import {normalizeActivity,activityPresentation} from './releaseActivity.js';
import {CONTINUATIONS,RELEASE_PATTERN,selectedNative} from './office-records.js';
import {PRODUCT_SKILLS,PRODUCT_ROLES} from './skill-catalog.js';
import {instructionSkills,instructionLookup,instructionOnly,skillWorkEvent,workSkills,currentAgentInstances} from './skill-semantics.js';
export const RELEASE_SKILLS = PRODUCT_SKILLS;
export const RELEASE_ROLES = PRODUCT_ROLES;
const SKILLS = new Map(RELEASE_SKILLS.map(skill => [skill.id, skill]));
const ROLES = new Map(RELEASE_ROLES.map(role => [role.id, role]));
const NODES = Object.fromEntries(RELEASE_SKILLS.map(s=>[s.node,s.label]));
const ACTORS = new Set(['main', ...ROLES.keys(), 'other_subagent', 'unknown_subagent']);
const EVENT_NODES = new Set([...ACTORS, ...SKILLS.keys(), 'unknown_skill']);
const KINDS = new Set(['lifecycle', 'tool', 'delegate', 'handback', 'handback_delivered', 'notification', 'request', 'subagent', 'skill_op', 'skill_load', 'shell', 'file', 'web', 'turn_cancelled', 'turn_end', 'session']);
const HOOKS = new Set(['PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'UserPromptSubmit', 'Stop', 'SubagentStart', 'SubagentStop', 'SessionStart', 'SessionEnd']);
const AREAS = new Set(['exports', 'web_evidence', 'catalogs', 'deliverables', 'conversation', 'runtime', 'skills', 'agents', 'docs', 'data', 'tools', 'web', 'outside', 'harness']);
const PROGRAMS = new Set(['ls', 'dir', 'cat', 'type', 'head', 'tail', 'find', 'grep', 'rg', 'wc', 'pwd', 'cd', 'echo', 'mkdir', 'cp', 'mv', 'rm', 'python', 'python3', 'py', 'uv', 'git', 'sed', 'awk', 'jq', 'curl', 'wget', 'sort', 'uniq', 'node', 'npm', 'npx', 'get-childitem', 'get-content', 'set-location', 'test-path', 'select-string', 'new-item', 'remove-item', 'copy-item', 'move-item', 'invoke-webrequest', 'out-file', 'set-content', 'get-item', 'write-output', 'measure-object', 'product_doctor', 'other']);
const DEFAULTS = Object.freeze({ pollMs: 2000, timeoutMs: 8000, staleMs: 20000, sourceStaleMs: 120000, freshnessMs: 1000 });
PROGRAMS.add('product-doctor.py');
class ReleaseError extends Error { constructor(code, message) { super(message); this.name = 'ReleaseError'; this.code = code; } }
const invalid = field => { throw new ReleaseError('schema', `릴리즈 관찰 응답 형식이 맞지 않습니다 (${field}).`); };
const object = (value, field) => value && typeof value === 'object' && !Array.isArray(value) ? value : invalid(field);
const array = (value, field, max = 2000) => Array.isArray(value) && value.length <= max ? value : invalid(field);
const integer = (value, field, max = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(value) && value >= 0 && value <= max ? value : invalid(field);
const boolean = (value, field) => typeof value === 'boolean' ? value : invalid(field);
const option = (value, allowed, field) => allowed.has(value) ? value : invalid(field);
function cleanText(value, field, limit = 500) {
  if (typeof value !== 'string') invalid(field);
  return value.replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, '').replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f]/g, '').trim().slice(0, limit);
}
function id(value, field, nullable = true) {
  if (value == null && nullable) return null;
  if (typeof value !== 'string' || !/^[A-Za-z0-9_.:-]{1,200}$/.test(value)) invalid(field);
  return value;
}
function timestamp(value, field, nullable = true) {
  if (value == null && nullable) return null;
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) invalid(field);
  return value;
}
function hash(value, field, nullable = true) {
  if (value == null && nullable) return null;
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/i.test(value)) invalid(field);
  return value.toLowerCase();
}
function freeze(value) { if (value && typeof value === 'object' && !Object.isFrozen(value)) { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
function binding(value, field) {
  if (value == null) return null;
  const raw = object(value, field);
  return { session_id: id(raw.session_id, `${field}.session_id`, false), turn_id: id(raw.turn_id, `${field}.turn_id`, false), request_key: id(raw.request_key, `${field}.request_key`, false) };
}
function details(value) {
  const raw = object(value ?? {}, 'event.detail'), out = {};
  for (const key of ['interrupted', 'background', 'accepted', 'other_skill_operation']) if (raw[key] != null) out[key] = boolean(raw[key], `detail.${key}`);
  if (raw.duration_ms != null) { if (typeof raw.duration_ms !== 'number' || !Number.isFinite(raw.duration_ms) || raw.duration_ms < 0) invalid('duration_ms'); out.duration_ms = raw.duration_ms; }
  if (raw.exit_code != null) { if (!Number.isSafeInteger(raw.exit_code)) invalid('exit_code'); out.exit_code = raw.exit_code; }
  for (const key of ['result_version', 'revision_count']) if (raw[key] != null) out[key] = integer(raw[key], key, key === 'revision_count' ? 2 : 3);
  for (const key of ['reason', 'error', 'turn_status', 'response_status', 'launched_agent_id', 'from_agent_id']) if (raw[key] != null) out[key] = id(raw[key], `detail.${key}`, false);
  if (raw.host != null) { if (typeof raw.host !== 'string' || raw.host.length > 253 || !/^[A-Za-z0-9.:-]+$/.test(raw.host)) invalid('host'); out.host = raw.host; }
  if (raw.area != null) out.area = option(raw.area, AREAS, 'detail.area');
  if (raw.skill != null) out.skill = option(raw.skill, new Set(SKILLS.keys()), 'detail.skill');
  if (raw.programs != null) out.programs = array(raw.programs, 'programs', 30).map(program => option(program, PROGRAMS, 'program'));
  if (raw.business_binding != null) out.business_binding = binding(raw.business_binding, 'detail.business_binding');
  return out;
}
function database(value) {
  if (value == null) return null;
  const raw = object(value, 'db'), available = boolean(raw.available, 'db.available');
  const state = option(raw.binding_status, new Set(['matched', 'unmatched', 'unavailable']), 'db.binding_status');
  const common = { available, binding_status: state, binding: null, read_at: timestamp(raw.read_at, 'db.read_at') };
  if (!available || state !== 'matched') return common; // Never expose another request's payload or counts.
  common.binding = binding(raw.binding, 'db.binding'); if (!common.binding) invalid('db.binding');
  const optionalCount = (value, field) => value == null ? null : integer(value, field);
  const nullableText = (value, field, limit = 120) => value == null ? null : cleanText(value, field, limit);
  const workflow = raw.workflow == null ? null : object(raw.workflow, 'workflow');
  common.workflow = workflow ? { research_id: id(workflow.research_id, 'research_id', false), started_at: timestamp(workflow.started_at, 'workflow.started_at'), budget_seconds: optionalCount(workflow.budget_seconds, 'budget_seconds'), research_stopped_at: timestamp(workflow.research_stopped_at, 'research_stopped_at'), finished_at: timestamp(workflow.finished_at, 'finished_at') } : null;
  common.workflow_events = array(raw.workflow_events ?? [], 'workflow_events', 100).map(value => {
    const item = object(value, 'workflow_event');
    const out = { kind: option(item.kind, new Set(['research_plan', 'source_scan', 'research_stop', 'analysis_scope', 'finish']), 'workflow_event.kind'), observed_at: timestamp(item.observed_at, 'workflow_event.observed_at', false) };
    for (const key of ['product', 'host', 'page', 'status', 'source_type', 'code', 'layout_review']) if (item[key] != null) out[key] = cleanText(item[key], `workflow_event.${key}`, 150);
    for (const key of ['reviews', 'sources']) if (item[key] != null) out[key] = integer(item[key], `workflow_event.${key}`);
    return out;
  });
  const turn = raw.turn == null ? null : object(raw.turn, 'turn');
  common.turn = turn ? { turn_id: id(turn.turn_id, 'turn.turn_id', false), status: id(turn.status, 'turn.status'), revision_count: turn.revision_count == null ? null : integer(turn.revision_count, 'turn.revision_count', 2), result_version: turn.result_version == null ? null : integer(turn.result_version, 'turn.result_version', 3), valid: boolean(turn.valid, 'turn.valid'), created_at: timestamp(turn.created_at, 'turn.created_at') } : null;
  const request = raw.request == null ? null : object(raw.request, 'request');
  common.request = request ? { turn_id: id(request.turn_id, 'request.turn_id'), request_key: id(request.request_key, 'request.request_key'), status: id(request.status, 'request.status') } : null;
  if (common.turn && common.turn.turn_id !== common.binding.turn_id || common.request && (common.request.turn_id !== common.binding.turn_id || common.request.request_key !== common.binding.request_key)) invalid('db.binding consistency');
  common.results = optionalCount(raw.results, 'db.results');
  common.candidates = array(raw.candidates ?? [], 'candidates', 3).map(value => {
    const item = object(value, 'candidate'), counts = object(item.counts ?? {}, 'candidate.counts');
    const out = { result_version: item.result_version == null ? null : integer(item.result_version, 'candidate.result_version', 3), created_at: timestamp(item.created_at, 'candidate.created_at'), status: id(item.status, 'candidate.status'), counts: {} };
    for (const key of ['pains', 'existing_features', 'remaining_pains', 'concepts']) out.counts[key] = optionalCount(counts[key], `candidate.${key}`);
    for (const key of ['contract_valid', 'structural_valid', 'acceptance_ready']) if (item[key] != null) out[key] = boolean(item[key], `candidate.${key}`);
    if (item.semantic_status != null) out.semantic_status = nullableText(item.semantic_status, 'semantic_status');
    return out;
  });
  common.evidence_delivered = optionalCount(raw.evidence_delivered, 'evidence_delivered'); common.evidence_reviews = optionalCount(raw.evidence_reviews, 'evidence_reviews');
  common.cancelled = raw.cancelled == null ? null : boolean(raw.cancelled, 'db.cancelled');
  const latest = raw.latest_export == null ? null : object(raw.latest_export, 'latest_export');
  common.latest_export = latest ? { available: boolean(latest.available, 'latest_export.available'), created_at: timestamp(latest.created_at, 'latest_export.created_at') } : null;
  return common;
}

export function normalizeReleaseSnapshot(input) {
  const raw = object(input, 'snapshot'), source = object(raw.source, 'source');
  if (raw.schema_version !== 1 || source.kind !== 'lgax_release_observer' || source.release != null && (typeof source.release !== 'string' || !RELEASE_PATTERN.test(source.release))) invalid('source/version');
  const seen = new Map();
  const events = array(raw.events, 'events', 1500).flatMap(value => {
    const item = object(value, 'event'); if (item.v !== 1) invalid('event.v');
    const event = {
      v: 1, id: id(item.id, 'event.id', false), ts: timestamp(item.ts, 'event.ts', false), ts_basis: option(item.ts_basis, new Set(['hook_received', 'codex_log', 'reader_received']), 'ts_basis'),
      src: option(item.src, new Set(['codex', 'claude']), 'event.src'), hook: option(item.hook, HOOKS, 'event.hook'), session: id(item.session, 'event.session'), prompt_id: id(item.prompt_id, 'event.prompt_id'), agent_id: id(item.agent_id, 'event.agent_id'),
      actor: option(item.actor, ACTORS, 'event.actor'), tool: id(item.tool, 'event.tool'), call: id(item.call, 'event.call'), kind: option(item.kind, KINDS, 'event.kind'), node: option(item.node, EVENT_NODES, 'event.node'),
      op: id(item.op, 'event.op'), ops: array(item.ops ?? [], 'event.ops', 8).map(value => { const op = object(value, 'event.ops[]'); return { skill: option(op.skill, new Set(SKILLS.keys()), 'op.skill'), op: id(op.op, 'op.op', false) }; }),
      phase: option(item.phase, new Set(['start', 'end', 'fail', 'point']), 'event.phase'), basis: option(item.basis, new Set(['observed', 'instruction_loaded', 'command_based_mapping']), 'event.basis'), detail: details(item.detail),
    };
    if (event.kind === 'skill_op' && (!SKILLS.has(event.node) || event.basis !== 'command_based_mapping')) invalid('skill_op.basis');
    if (event.kind === 'skill_load' && (!SKILLS.has(event.node) && event.node !== 'unknown_skill' || event.basis !== 'instruction_loaded')) invalid('skill_load.basis');
    const encoded = JSON.stringify(event); if (seen.has(event.id)) { if (seen.get(event.id) !== encoded) invalid('event.id conflict'); return []; } seen.set(event.id, encoded);
    return [event];
  });
  return freeze({ schema_version: 1, source: { kind: 'lgax_release_observer', release: source.release ?? null, origin: source.origin == null ? 'release_server' : option(source.origin, new Set(['release_server', 'office_live', 'office_replay']), 'source.origin'), engine: option(source.engine, new Set(['codex', 'claude']), 'source.engine'), observed_at: timestamp(source.observed_at, 'source.observed_at', false), source_updated_at: timestamp(source.source_updated_at, 'source.source_updated_at'), observer_status: option(source.observer_status, new Set(['waiting_for_session', 'observing', 'recorded']), 'source.observer_status'), asset_sha256: hash(source.asset_sha256, 'asset_sha256'), product_install_sha256: hash(source.product_install_sha256, 'product_install_sha256') }, events, activity:normalizeActivity(raw.activity), db: database(raw.db), notices: array(raw.notices ?? [], 'notices', 50).map(value => cleanText(value, 'notice', 700)) });
}

const byTime = (a, b) => Date.parse(a.ts) - Date.parse(b.ts);
const sameBinding = (a, b) => Boolean(a && b && ['session_id', 'turn_id', 'request_key'].every(key => a[key] === b[key]));
const mainEvent = event => event.actor === 'main' && !event.agent_id;
const callKey = event => [event.src, event.session, event.prompt_id || '', event.agent_id || 'main', event.call || `unpaired:${event.id}`].join('|');
function labelFor(event) {
  const skill = SKILLS.get(event.node), role = ROLES.get(event.node) || ROLES.get(event.actor);
  if (instructionOnly(event)) return event.kind==='skill_load' ? `${skill?.label || '미확인 Skill'} 지침 파일 조회 관측` : '작업 설명서 조회 · 조회한 본문은 기록에 미제공';
  if (event.kind === 'skill_op') return workSkills(event).map(id=>SKILLS.get(id).label).join(' · ')+' · 작업 명령 관측';
  if (event.kind === 'delegate') return `${role?.label || '기타 역할'} 위임 호출 관측${event.detail.background ? ' · 비동기 시작 응답' : ''}`;
  if (event.kind === 'subagent') return `${role?.label || '기타 하위 에이전트'} ${event.phase === 'start' ? '시작' : '종료'} 관측`;
  if (event.kind === 'turn_cancelled') return '네이티브 turn 취소 관측 · Tool 종료 결과는 별도 확인';
  if (event.kind === 'turn_end') return '메인 최종 응답 종료 관측';
  if (event.kind === 'request') return '네이티브 요청 접수 관측';
  if (event.kind === 'web') return `웹 Tool 관측${event.detail.host ? ` · ${event.detail.host}` : ''}`;
  if (event.kind === 'shell') return '일반 코드·셸 Tool 관측 · Skill 호출과 구분';
  if (event.kind === 'file') return '파일 Tool 관측';
  if (event.kind === 'handback' || event.kind === 'handback_delivered') return '하위 에이전트 반환 전달 관측';
  if (event.kind === 'tool') return `${event.tool || '네이티브 Tool'} 호출 관측`;
  return '네이티브 세션 사건 관측';
}
function spansFor(events) {
  // Async hooks can record a call's end a few milliseconds before its start; that start is then already closed.
  const spans = [], pending = new Map(), cancelled = new Map(), endedFirst = new Map();
  const turnKey = event => JSON.stringify([event.session, event.prompt_id]);
  for (const event of events) {
    if (mainEvent(event) && ['turn_cancelled', 'turn_end'].includes(event.kind) || event.kind === 'session' && event.phase === 'end') {
      const cancellation = event.kind === 'turn_cancelled';
      if (cancellation) cancelled.set(turnKey(event), Date.parse(event.ts));
      for (const span of pending.values()) {
        if (span.status !== 'open') continue;
        const sameTurn = span.start.prompt_id === event.prompt_id;
        if (event.kind === 'session' || (mainEvent(span.start) && sameTurn)) { span.status = cancellation ? 'cancelled' : 'unknown'; span.closedBy = event.id; span.endedAt = event.ts; span.resultKnown = false; }
      }
      continue;
    }
    if(event.kind==='subagent'&&['end','fail'].includes(event.phase)&&event.agent_id){for(const span of pending.values())if(span.status==='open'&&span.start.kind!=='subagent'&&span.start.agent_id===event.agent_id){span.status='unknown';span.endedAt=event.ts;span.closedBy=event.id;span.resultKnown=false;}}
    if (!['start', 'end', 'fail'].includes(event.phase) || event.kind === 'session') continue;
    const key = event.kind === 'subagent' ? `role|${event.session}|${event.agent_id || `unpaired:${event.id}`}` : callKey(event);
    if (event.phase === 'start') {
      if (endedFirst.has(key)) { const span = endedFirst.get(key); endedFirst.delete(key); Object.assign(span, { id: event.id, start: event, startUnobserved: false }); }
      else if (!pending.has(key)) { const span = { id: event.id, key, start: event, end: null, status: 'open', resultKnown: false, endedAt: null, closedBy: null }; pending.set(key, span); spans.push(span); }
    } else {
      const span = pending.get(key);
      const cancelledAt = cancelled.get(turnKey(event));
      const cancelledBeforeEnd = cancelledAt != null && (!span || Date.parse(span.start.ts) <= cancelledAt);
      if (span) {
        if (span.status === 'cancelled' || cancelledBeforeEnd) { span.lateEnd = event; continue; }
        span.end = event; span.endedAt = event.ts; span.status = event.phase === 'fail'||Number.isSafeInteger(event.detail.exit_code)&&event.detail.exit_code!==0 ? 'failed' : event.detail.accepted === false ? 'rejected' : 'completed'; span.resultKnown = true;
      } else { const early = { id: event.id, key, start: event, end: event, status: cancelledBeforeEnd ? 'cancelled' : event.phase === 'fail'||Number.isSafeInteger(event.detail.exit_code)&&event.detail.exit_code!==0 ? 'failed' : event.detail.accepted === false ? 'rejected' : 'completed', resultKnown: !cancelledBeforeEnd, endedAt: event.ts, startUnobserved: true }; spans.push(early); if (event.call) endedFirst.set(key, early); }
    }
  }
  return spans;
}

// Needs structuring, feature comparison and concept writing usually run inside the main planner's own turn with no
// Skill command. Their workshops follow the harness's recorded flow instead: the research-stop / final-bundle marker,
// the review step that receives the 6-field candidate draft, and the bound DB candidate's counts. Never a guessed
// per-stage start or end.
const ANALYSIS_NODES = ['structure', 'compare', 'concept'];
const ANALYSIS_START = new Set(['resolve_request_bundle', 'open_request_bundle']);
const DRAFT_OPS = new Set(['prepare_review_packet', 'review_product_result', 'validate_result_contract', 'save_reviewed_result', 'save_and_export', 'save_result']);
const OUTPUTS = { structure: c => `불편 ${c.pains ?? '미기록'}건`, compare: c => `기존 기능 ${c.existing_features ?? '미기록'}건 · 남은 불편 ${c.remaining_pains ?? '미기록'}건`, concept: c => `콘셉트 ${c.concepts ?? '미기록'}건` };
const opsOf = event => [event.op, ...event.ops.map(item => item.op)].filter(Boolean);
function stageEvidence(current, spans, db, open) {
  const ids = new Set(current.map(event => event.id));
  const done = names => spans.filter(span => ids.has(span.start.id) && mainEvent(span.start) && span.start.kind === 'skill_op' && ['completed', 'rejected'].includes(span.status) && opsOf(span.start).some(op => names.has(op))).map(span => ({ event: span.end || span.start, op: opsOf(span.start).find(op => names.has(op)) })).sort((a, b) => byTime(a.event, b.event));
  const first = kind => db?.workflow_events?.find(event => event.kind === kind) || null;
  const plan = first('research_plan'), stop = first('research_stop'), scope = first('analysis_scope'), finish = first('finish');
  const scans = db?.workflow_events?.filter(event => event.kind === 'source_scan') || [];
  const bundle = done(ANALYSIS_START)[0], draft = done(DRAFT_OPS)[0];
  const stopLine = stop && { time: stop.observed_at, label: `하네스 조사 종료 기록 · ${stop.code || '사유 미제공'}`, basis: 'db_workflow' };
  const starts = [stopLine, bundle && { time: bundle.event.ts, label: `최종 근거 묶음 확인 명령 완료 · ${bundle.op}`, basis: 'command_based_mapping' }, scope && { time: scope.observed_at, label: `분석 범위 기록 · 원문 ${scope.sources ?? '미기록'}건`, basis: 'db_workflow' }].filter(Boolean).sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
  const candidate = db ? db.candidates?.findLast(item => item.result_version === db.turn?.result_version) || db.candidates?.at(-1) || null : null;
  const draftLine = draft && { time: draft.event.ts, label: `검토 단계 명령이 6필드 후보 초안을 받음 · ${draft.op}`, basis: 'command_based_mapping' };
  const savedLine = candidate && { time: candidate.created_at, label: `DB 저장 후보 v${candidate.result_version ?? '?'} · ${candidate.status || '상태 미기록'}`, basis: 'db_saved_result' };
  const out = {};
  for (const node of ANALYSIS_NODES) {
    const evidence = [starts[0], draftLine, savedLine].filter(Boolean);
    if (candidate) out[node] = { status: 'completed', statusLabel: candidate.status === 'held' ? '보류 결과 저장' : '저장 결과 확인', task: `저장된 후보 v${candidate.result_version ?? '?'}: ${OUTPUTS[node](candidate.counts)}`, evidence, basis: 'db_saved_result' };
    else if (draft) out[node] = { status: 'completed', statusLabel: '초안 확인', task: '검토 단계가 이 단계의 결과가 담긴 6필드 후보 초안을 받았습니다. 이 단계만의 시작·끝 시각은 따로 기록되지 않습니다.', evidence, basis: 'review_handoff' };
    else if (starts.length) out[node] = { status: 'analysis', statusLabel: open ? '분석 구간' : '분석 구간 기록', task: '조사를 마친 뒤 결과를 저장하기 전 구간입니다. 니즈 구조화·기능 대조·콘셉트 작성은 별도 명령 없이 메인 기획자가 이어서 작성하므로 지금 어느 단계인지는 구분하지 않습니다.', evidence, basis: 'analysis_window' };
  }
  out.web = { evidence: [plan && { time: plan.observed_at, label: '하네스 조사 계획 기록', basis: 'db_workflow' }, scans.length && { time: scans.at(-1).observed_at, label: `출처 스캔 기록 ${scans.length}건 · 사이트 ${new Set(scans.map(scan => scan.host).filter(Boolean)).size}곳 · 후기 ${scans.reduce((sum, scan) => sum + (scan.reviews || 0), 0)}건`, basis: 'db_workflow' }, stopLine].filter(Boolean) };
  out.retrieve={evidence:[bundle&&{time:bundle.event.ts,label:'저장 자료 조회 명령 확인',basis:'command_based_mapping'}].filter(Boolean)};
  out.validate = { evidence: [draftLine, savedLine, finish && { time: finish.observed_at, label: '하네스 업무 종료(finish) 기록', basis: 'db_workflow' }, db?.latest_export?.created_at && { time: db.latest_export.created_at, label: '세션 기록 내보내기 파일 확인', basis: 'db_export' }].filter(Boolean), candidate };
  return out;
}

export function deriveReleaseView(snapshot, connection = {}, nowMs = Date.now()) {
  const data = snapshot ? normalizeReleaseSnapshot(snapshot) : null;
  const received = connection.lastReceivedAt ? nowMs - Date.parse(connection.lastReceivedAt) : null;
  const observed = data ? nowMs - Date.parse(data.source.observed_at) : null;
  let connectionStatus = connection.status || 'disconnected';
  if (['connected', 'error', 'stale'].includes(connectionStatus) && data && (received === null || received >= (connection.staleAfterMs ?? DEFAULTS.staleMs) || observed === null || observed >= (connection.staleAfterMs ?? DEFAULTS.staleMs) || observed < -5000)) connectionStatus = 'stale';
  const connected = connectionStatus === 'connected';
  const engineEvents = (data?.events || []).filter(event => event.src === data.source.engine).sort(byTime);
  const main = engineEvents.filter(event => mainEvent(event) && event.session);
  const anchors = main.filter(event => event.kind === 'request' || event.kind === 'session' && event.phase === 'start');
  const anchor = anchors.at(-1), sessionId = anchor?.session || main.at(-1)?.session || null;
  const sessionEvents = sessionId ? engineEvents.filter(event => event.session === sessionId) : [];
  const sessionStart = sessionEvents.findLastIndex(event => mainEvent(event) && event.kind === 'session' && event.phase === 'start');
  const sessionMain = sessionEvents.slice(Math.max(0, sessionStart)).filter(mainEvent);
  const latestRequest = sessionMain.filter(event => event.kind === 'request').at(-1);
  const promptId = latestRequest ? latestRequest.prompt_id : sessionStart >= 0 ? null : anchor?.prompt_id || null;
  // The file and server views share the same verified request/child continuation boundary.
  const native = selectedNative(sessionEvents);
  const promptIds = latestRequest ? native.prompts : new Set([promptId]);
  const floor = latestRequest ? native.floor : Math.max(0, sessionStart);
  const eligibleMain = sessionEvents.slice(floor).filter(event => mainEvent(event) && promptIds.has(event.prompt_id));
  const linkedChildren = native.children || new Set();
  const currentEvents = anchor ? sessionEvents.slice(floor).filter(event => mainEvent(event) ? promptIds.has(event.prompt_id) : Boolean(event.agent_id) && (linkedChildren.has(event.agent_id) || Boolean(promptId) && promptIds.has(event.prompt_id))) : [];
  const turnMarker = anchor ? eligibleMain.filter(event => ['request', 'turn_end', 'turn_cancelled'].includes(event.kind) || CONTINUATIONS.has(event.kind)).at(-1) : null;
  const events = [...sessionEvents].sort(byTime);
  const spans = spansFor(events), lastEventAt = events.at(-1)?.ts || null;
  const currentEventAt = currentEvents.at(-1)?.ts || null;
  const eventAge = currentEventAt ? Math.max(0, nowMs - Date.parse(currentEventAt)) : null;
  const observationFresh = connected && data?.source.observer_status === 'observing' && eventAge !== null && eventAge < (connection.sourceStaleAfterMs ?? DEFAULTS.sourceStaleMs) && Date.parse(currentEventAt) <= nowMs + 5000;
  const latestMainCancelled = turnMarker?.kind === 'turn_cancelled';
  const currentIds = new Set(currentEvents.map(event => event.id));
  const activeSpans = observationFresh && !latestMainCancelled ? spans.filter(span => span.status === 'open' && currentIds.has(span.start.id) && span.start.kind !== 'skill_load') : [];
  const activeSkills = [...new Set(activeSpans.filter(span => skillWorkEvent(span.start)).flatMap(span=>workSkills(span.start)))];
  const activeNodes = [...new Set(activeSkills.map(skill => SKILLS.get(skill).node))];
  const nativeTerminal=['turn_cancelled','turn_end'].includes(turnMarker?.kind);
  const activityInput=nativeTerminal&&data?.activity?{...data.activity,state:turnMarker.kind==='turn_cancelled'?'cancelled':'finished',reported_stage:null,last_event_at:turnMarker.ts}:data?.activity;
  const activity=activityPresentation(activityInput,sessionId,promptId,connected,nowMs);
  // UserPromptSubmit (or a delivered role result) until Stop: the main planner is answering, with or without a tool.
  const turnOpen = Boolean(observationFresh && !latestMainCancelled && turnMarker && turnMarker.kind !== 'turn_end');
  if(activity?.working&&!activeNodes.length)activeNodes.push(activity.reported_stage||'overview');
  let boundDb = null, bindingState = data?.db?.available ? 'unmatched' : 'unavailable';
  if (data?.db?.binding_status === 'matched' && data.db.binding && currentEvents.some(event => mainEvent(event) && sameBinding(event.detail.business_binding, data.db.binding))) { bindingState = 'matched'; boundDb = data.db; }
  const candidate = boundDb?.candidates?.findLast(item => item.result_version === boundDb.turn?.result_version) || null;
  const counts = { events: events.length, skills: new Set(currentEvents.flatMap(workSkills)).size, instructions: new Set(currentEvents.flatMap(instructionSkills)).size+spans.filter(s=>currentIds.has(s.start.id)&&instructionLookup(s.start)).length, toolCalls: spans.filter(span => span.start.kind !== 'subagent').length, openCalls: spans.filter(span => currentIds.has(span.start.id)&&span.status === 'open').length, results: boundDb?.results ?? null, evidenceDelivered: boundDb?.evidence_delivered ?? null, evidenceReviews: boundDb?.evidence_reviews ?? null, pains: candidate?.counts.pains ?? null, existingFeatures: candidate?.counts.existing_features ?? null, remainingPains: candidate?.counts.remaining_pains ?? null, concepts: candidate?.counts.concepts ?? null };
  const usedSkills = RELEASE_SKILLS.map(skill => {
    const related = currentEvents.filter(event => instructionSkills(event).includes(skill.id)||workSkills(event).includes(skill.id));
    const operations = related.filter(event => workSkills(event).includes(skill.id)), relevantSpans = spans.filter(span => currentIds.has(span.start.id)&&workSkills(span.start).includes(skill.id));
    const instructionSpans=spans.filter(span=>currentIds.has(span.start.id)&&instructionSkills(span.start).includes(skill.id)),lastInstruction=instructionSpans.at(-1);
    const latest = relevantSpans.at(-1), active = activeSkills.includes(skill.id), loaded = instructionSpans.some(span=>span.status==='completed')||related.some(event=>instructionSkills(event).includes(skill.id)&&event.phase==='point')||Boolean(activity?.skill_reads.some(r=>r.id===skill.id));
    const status = active ? 'running' : latest?.status === 'failed' ? 'failed' : latest?.status === 'rejected' ? 'review' : latest?.status === 'cancelled' ? 'cancelled' : latest?.status === 'completed' ? 'completed' : operations.length ? 'unknown' : lastInstruction?.status==='open'?'reading':lastInstruction?.status==='failed'?'instruction_error':loaded ? 'loaded' : 'idle';
    const statusLabel = { running: 'Skill 명령 진행', failed: 'Skill 명령 실패', review: '저장 확인 필요', cancelled: '취소 · 종료 결과 미확인', completed: 'Skill 명령 완료', unknown: '명령 종료 미확인', loaded: '지침 조회 확인', reading:'지침 확인 중', instruction_error:'지침 조회 실패', idle: '실행 기록 없음' }[status];
    const read=activity?.skill_reads.find(r=>r.id===skill.id);
    const displayEvents=read&&!related.some(e=>e.kind==='skill_load')?[...related,{id:'read-'+skill.id,ts:read.time,time:read.time,kind:'skill_load',node:skill.id,actor:'main',phase:'end',basis:'command_result',message:skill.label+' 지침 조회 명령 완료'}]:related;
    return { ...skill, used: related.length > 0||loaded, instructionLoaded: loaded, operationObserved: operations.length > 0, status, statusLabel, active, events: displayEvents, lastEventAt: displayEvents.at(-1)?.ts || null, basis: operations.length ? 'command_based_mapping' : loaded ? 'instruction_loaded' : null, task: related.length ? labelFor(related.at(-1)) : loaded?'지침 조회 명령 확인 · Skill 업무 실행 대기':'실제 Skill 실행 기록이 아직 없습니다.' };
  });
  const stages = stageEvidence(currentEvents, spans, bindingState === 'matched' ? boundDb : null, turnOpen);
  const nodes = Object.fromEntries(Object.entries(NODES).map(([node, label]) => {
    const skills = usedSkills.filter(skill => skill.node === node), related = [...currentEvents.filter(event => workSkills(event).some(id=>SKILLS.get(id)?.node===node)||instructionSkills(event).some(id=>SKILLS.get(id)?.node===node)),...skills.flatMap(skill=>skill.events.filter(event=>event.basis==='command_result'))].sort(byTime);
    const active = activeNodes.includes(node), latest = related.at(-1), lastSkill = latest ? skills.find(skill => workSkills(latest).includes(skill.id)||instructionSkills(latest).includes(skill.id)) : skills.find(skill=>skill.instructionLoaded);
    const status = active ? 'running' : lastSkill?.status || 'idle';
    const flow = stages[node], quiet = !active && ['idle', 'loaded'].includes(status), saved = node === 'validate' && flow?.candidate && !active && !['running', 'failed'].includes(status);
    const base = { id: node, label, status, statusLabel: active ? (activeSkills.some(id=>SKILLS.get(id).node===node)?'Skill 명령 진행':'CLI 진행 보고') : lastSkill?.statusLabel || '실행 기록 없음', task: active&&activity?.reported_stage===node?activity.text:latest ? labelFor(latest) : lastSkill?.instructionLoaded?'Skill 지침 조회 확인 · 업무 실행 대기':'이 공간의 Skill 실행 기록이 아직 없습니다.', skills, actor: latest?.actor || null, actors: [...new Set(related.map(event => event.actor))], events: related, activity: latest ? { eventId: latest.id, time: latest.ts, message: labelFor(latest), basis: latest.basis } : null, active, grouped: false, evidence: flow?.evidence || [], basis: null };
    if (quiet && flow?.status) Object.assign(base, { status: flow.status, statusLabel: flow.statusLabel, task: flow.task, basis: flow.basis });
    else if (quiet && node === 'retrieve' && flow.evidence.length) Object.assign(base, { statusLabel: '조사 기록 확인', task: flow.evidence.at(-1).label, basis: 'db_workflow' });
    else if (saved) Object.assign(base, { status: 'completed', statusLabel: flow.candidate.status === 'held' ? '보류 결과 저장' : '결과 저장 확인', task: `후보 v${flow.candidate.result_version ?? '?'} 저장 · 계약 검사 ${flow.candidate.contract_valid === true ? '통과' : flow.candidate.contract_valid === false ? '미통과' : '미기록'} · 의미 검토 ${flow.candidate.semantic_status || '미기록'}`, basis: 'db_saved_result' });
    return [node, base];
  }));
  const currentSpans=spans.filter(span=>currentIds.has(span.start.id));
  const agents=currentAgentInstances(currentEvents,currentSpans,{fresh:observationFresh,cancelled:latestMainCancelled});
  const currentAgentIds=new Set(agents.map(a=>a.id)),mainPrompts=new Set(sessionMain.map(e=>e.prompt_id).filter(Boolean));
  // v0.18 Codex child starts have no parent prompt; the spawn result ID is absent.
  // Keep these as session history. Neither timestamp proximity nor a child turn proves parentage.
  const unboundAgents=currentAgentInstances(events,spans).filter(a=>!currentAgentIds.has(a.id)&&a.nativeStart&&a.events.some(e=>e.kind==='subagent'&&e.phase==='start'&&(!e.prompt_id||!mainPrompts.has(e.prompt_id)))).map(a=>({...a,binding:'unverified',active:false,activeSkills:[],statusLabel:a.status==='completed'?'도우미 종료 기록':a.status==='failed'?'도우미 오류 기록':'도우미 시작 기록 · 현재 상태 미확인'}));
  const lookupSpans=currentSpans.filter(s=>instructionLookup(s.start)),lookup=lookupSpans.at(-1);
  const instructionQuery=lookup?{status:lookup.status==='open'?'reading':lookup.status==='failed'?'failed':lookup.status==='completed'?'completed':'unknown',label:lookup.status==='open'?'작업 설명서를 가져오고 있어요':lookup.status==='failed'?'작업 설명서를 가져오지 못했어요':lookup.status==='completed'?'작업 설명서 조회가 끝났어요':'작업 설명서 조회 결과 확인 중',detail:'이 명령은 여러 설명서 중 필요한 것을 고를 수 있어요. 어떤 본문이 전달됐는지는 현재 기록에 없어요.',eventId:lookup.start.id}:null;
  const roleIds=[...new Set([...agents.map(a=>a.role),...currentEvents.filter(e=>e.kind==='delegate'&&ROLES.has(e.node)).map(e=>e.node)])];
  const roles=roleIds.map(roleId=>{
    const definition=ROLES.get(roleId)||{id:roleId,label:'역할 미확인 도우미'};
    const related=currentEvents.filter(e=>e.node===roleId||e.actor===roleId),instances=agents.filter(a=>a.role===roleId),running=instances.filter(a=>a.active);
    const last=related.at(-1),status=running.length?'running':instances.at(-1)?.status||'requested';
    return {...definition,used:true,active:running.length>0,status,statusLabel:running.length?'도우미 작업 중':instances.at(-1)?.statusLabel||'위임 요청 · 시작 미확인',agentIds:instances.map(a=>a.id),agents:instances,events:related,task:last?labelFor(last):'실제 위임 기록을 확인하고 있어요.',lastEventAt:last?.ts||null};
  });
  const product = boundDb?.workflow_events?.filter(event => event.kind === 'research_plan' && event.product).at(-1)?.product || null;
  const latestActive = activeSpans.at(-1)?.start;
  const recentEvents = events.slice(-3).reverse().map(event => ({ ...event, time: event.ts, at: event.ts, message: labelFor(event), factoryNode: SKILLS.get(event.node)?.node || null }));
  let header, nextAction;
  if (connectionStatus === 'connecting') header = { state: 'connecting', text: '릴리즈 관찰 연결 확인 중', detail: '추가 모델 호출 없이 관찰 데이터를 읽습니다.' };
  else if (connectionStatus === 'disconnected') header = { state: 'disconnected', text: '릴리즈 하네스 연결 대기', detail: data ? '마지막 관찰 기록을 보존했습니다.' : '설치 제품의 실제 관측 파일을 아직 읽지 않았습니다.' };
  else if (connectionStatus === 'stale') header = { state: 'stale', text: '릴리즈 관찰 수신 오래됨', detail: '마지막 관측 기록입니다. 원격 프로세스의 중지나 완료를 뜻하지 않습니다.' };
  else if (connectionStatus === 'error' || !data) header = { state: 'error', text: '릴리즈 관찰 연결 확인 필요', detail: connection.error || '관찰 데이터를 읽지 못했습니다.' };
  else if (!events.length || data.source.observer_status === 'waiting_for_session') header = { state: 'waiting', text: `릴리즈 연결됨 · ${data.source.engine === 'codex' ? 'Codex' : 'Claude Code'} 세션 대기`, detail: '실제 사용 사건이 기록되면 표시합니다. 가상 사건을 만들지 않습니다.' };
  else if (latestMainCancelled) header = { state: 'cancelled', text: '네이티브 turn 취소 관측', detail: '열린 Tool의 종료 결과와 원격 프로세스 종료는 별도 확인이 필요합니다.' };
  else if (!latestActive && turnOpen) header = { state: 'active', text: ANALYSIS_NODES.some(node => nodes[node].status === 'analysis') ? '분석 구간 · 메인 기획자 직접 작성' : '메인 기획자 작업 중 · 진행 중인 도구 호출 없음', detail: '질문 접수(또는 하위 역할 결과 전달) 뒤 최종 응답 전입니다. 훅 기록이며 모델 내부 상태를 뜻하지 않습니다.' };
  else if (latestActive) header = { state: 'active', text: labelFor(latestActive), detail: latestActive.kind === 'skill_op' ? '명령 경로에 따른 Tool 관찰입니다. Skill의 의미 판단이나 성공을 자동 인증하지 않습니다.' : '네이티브 사건을 관측한 범위이며 모델 내부 상태를 뜻하지 않습니다.' };
  else if (turnMarker?.kind === 'turn_end') header = { state: 'recorded', text: '메인 최종 응답 종료 관측', detail: '데이터 저장·원문 의미 승인·전체 프로세스 종료와 구분합니다.' };
  else header = { state: 'recorded', text: '릴리즈 연결됨 · 마지막 관측 기록', detail: spans.some(span => span.status === 'open') ? '열린 호출의 종료 결과를 아직 관측하지 못했습니다. 현재 실행 여부를 단정하지 않습니다.' : '기록된 사건을 표시합니다. 현재 실행 여부는 추가 관측이 필요합니다.' };
  if(activity&&connected){header={state:activity.working?'active':activity.state==='cancelled'?'cancelled':'recorded',text:activity.text,detail:activity.reported?'CLI의 공개 진행 보고입니다. 실제 Skill 명령 호출 기록과 구분합니다.':'선택한 네이티브 요청의 시작·완료와 명령 결과를 표시합니다.'};}
  nextAction = connectionStatus === 'disconnected' || connectionStatus === 'error' ? '로컬 관찰 읽기 서버 주소와 Bearer 키로 연결하세요.' : connectionStatus === 'stale' ? '읽기 연결을 확인하고 상태를 다시 읽으세요.' : !events.length ? '관찰기가 설치 제품의 실제 네이티브 세션을 기록할 때까지 기다리세요.' : 'Skill·역할의 실제 기록과 현재 버전의 저장 결과를 확인하세요.';
  if(activity&&connected)nextAction=activity.next;
  // The file view reads observer files beside the page; it has no release server to connect to.
  const origin = data?.source.origin || connection.origin || 'release_server';
  if (origin !== 'release_server') {
    const replay = origin === 'office_replay', texts = { connecting: '관측 파일 읽는 중', error: '관측 파일 확인 필요', stale: '관측 파일 갱신 지연', disconnected: '관측 파일 읽기 멈춤', waiting: replay ? '재생할 기록 없음' : `실제 기록 대기 · ${data?.source.engine === 'codex' ? 'Codex' : 'Claude Code'} 질문을 기다립니다` };
    if (texts[header.state]) header = { ...header, text: texts[header.state], detail: header.state === 'stale' ? '마지막으로 읽은 기록입니다. AI 업무의 중지나 완료를 뜻하지 않습니다.' : header.detail };
    else if (header.text === '릴리즈 연결됨 · 마지막 관측 기록') header = { ...header, text: replay ? '기록 재생 · 이 시각에 진행 중인 호출 없음' : '관측 파일 연결 · 마지막 관측 기록' };
    if (['disconnected', 'error', 'stale'].includes(connectionStatus)) nextAction = '이 화면이 하네스의 runtime-data/agent-office 폴더에서 열렸는지, 옆에 live.js가 있는지 확인하세요. 자동으로 다시 읽습니다.';
    else if (!events.length) nextAction = replay ? '다른 세션이나 기록 파일을 고르세요.' : '이 하네스 폴더에서 Claude Code로 질문하거나, Codex는 관찰 창을 켠 뒤 질문하세요. 기록이 생기면 바로 표시합니다.';
  }
  return freeze({ readonly: true, sourceMode: 'release', origin, release: data?.source.release || null, activity, mainActive:Boolean(connected&&observationFresh&&!latestMainCancelled&&(activity?activity.working:turnOpen)), header, nextAction, connectionStatus, nodes, activeNodes, activeSkills, skills: usedSkills, roles, agents, unboundAgents, instructionQuery, currentEvents, actors: [...new Set(currentEvents.map(event => event.actor))].filter(actor => actor === 'main' || ROLES.has(actor)), recentEvents:activity?activity.actions.filter(a=>a.code!=='local_command').slice(-3).reverse():recentEvents, events, spans, sessionId, promptId, promptIds: [...promptIds], product, bindingState, binding: boundDb?.binding || null, database: boundDb, counts, lastEventAt, sourceAgeSeconds: data?.source.source_updated_at ? Math.max(0, (nowMs - Date.parse(data.source.source_updated_at)) / 1000) : null, observationFresh: Boolean(observationFresh), notices: data?.notices || [] });
}

function endpointFor(value) {
  let url;
  try { url = new URL(value); } catch { throw new ReleaseError('url', '로컬 읽기 서버 주소를 확인해 주세요.'); }
  if (url.protocol !== 'http:' || !['localhost', '127.0.0.1'].includes(url.hostname.toLowerCase()) || url.username || url.password || url.search || url.hash || !['/', '/api/harness/snapshot'].includes(url.pathname)) throw new ReleaseError('url', 'http://localhost 또는 http://127.0.0.1의 읽기 서버만 연결할 수 있습니다. 키를 URL에 넣지 마세요.');
  return { url: url.origin, endpoint: `${url.origin}/api/harness/snapshot` };
}

export class ReleaseStore {
  #state; #listeners = new Set(); #token = ''; #endpoint = ''; #fetch; #clock; #setTimer; #clearTimer; #Abort;
  #pollTimer = null; #freshnessTimer = null; #controller = null; #generation = 0; #request = 0; #options;
  constructor(options = {}) {
    this.#fetch = options.fetchImpl || globalThis.fetch?.bind(globalThis);
    this.#clock = options.clock || (() => Date.now());
    this.#setTimer = options.setTimer || globalThis.setTimeout.bind(globalThis);
    this.#clearTimer = options.clearTimer || globalThis.clearTimeout.bind(globalThis);
    this.#Abort = options.AbortControllerImpl || globalThis.AbortController;
    this.#options = { ...DEFAULTS };
    for (const name of Object.keys(DEFAULTS)) if (options[name] != null) { const value = options[name]; if (!Number.isFinite(value) || value < 1 || value > 3600000) throw new ReleaseError('option', '읽기 연결 시간 설정이 맞지 않습니다.'); this.#options[name] = value; }
    const connection = { status: 'disconnected', url: '', lastReceivedAt: null, error: null, staleAfterMs: this.#options.staleMs, sourceStaleAfterMs: this.#options.sourceStaleMs };
    this.#state = { snapshot: null, connection, view: deriveReleaseView(null, connection, this.#clock()) };
    this.getSnapshot = () => this.#state;
    this.subscribe = listener => { this.#listeners.add(listener); return () => this.#listeners.delete(listener); };
  }
  #publish(snapshot = this.#state.snapshot, patch = {}) {
    let connection = { ...this.#state.connection, ...patch };
    const view = deriveReleaseView(snapshot, connection, this.#clock());
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
    if (typeof token !== 'string' || token.length > 4096 || /[\s\u0000-\u001f\u007f]/.test(token)) throw new ReleaseError('token', 'Bearer 키 형식을 확인해 주세요.');
    if (typeof this.#fetch !== 'function' || typeof this.#Abort !== 'function') throw new ReleaseError('runtime', '이 환경에서 읽기 연결을 사용할 수 없습니다.');
    this.#generation++; this.#request++; this.#controller?.abort(); this.#clearTimers();
    this.#endpoint = target.endpoint; this.#token = token;
    this.#publish(this.#state.snapshot, { status: 'connecting', url: target.url, error: null });
    this.#scheduleFreshness(this.#generation);
    return this.refresh();
  }
  async refresh() {
    if (!this.#endpoint) throw new ReleaseError('disconnected', '읽기 서버에 연결한 뒤 새로 읽을 수 있습니다.');
    const generation = this.#generation, request = ++this.#request;
    this.#controller?.abort();
    const controller = new this.#Abort(); this.#controller = controller;
    if (this.#pollTimer !== null) { this.#clearTimer(this.#pollTimer); this.#pollTimer = null; }
    const headers = { Accept: 'application/json' };
    if (this.#token) headers.Authorization = `Bearer ${this.#token}`;
    let timer;
    const stillCurrent = () => generation === this.#generation && request === this.#request && Boolean(this.#endpoint);
    try {
      const timeout = new Promise((_, reject) => { timer = this.#setTimer(() => { reject(new ReleaseError('timeout', '하네스 읽기 응답 시간이 초과되었습니다.')); controller.abort(); }, this.#options.timeoutMs); });
      const cancelled = new Promise((_, reject) => controller.signal.addEventListener('abort', () => reject(new ReleaseError('cancelled', '이전 읽기 요청을 취소했습니다.')), { once: true }));
      const read = (async () => {
        const response = await this.#fetch(this.#endpoint, { method: 'GET', headers, cache: 'no-store', credentials: 'omit', redirect: 'error', signal: controller.signal });
        if (!response?.ok) throw new ReleaseError('http', response?.status === 401 || response?.status === 403 ? '하네스 읽기 인증을 확인해 주세요.' : '하네스 읽기 응답을 받지 못했습니다.');
        return normalizeReleaseSnapshot(await response.json());
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
      const safe = error instanceof ReleaseError ? error : new ReleaseError('network', '하네스 읽기 연결을 확인해 주세요.');
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
export function createReleaseStore(options = {}) { return new ReleaseStore(options); }
export const releaseStore = createReleaseStore();
export default releaseStore;
