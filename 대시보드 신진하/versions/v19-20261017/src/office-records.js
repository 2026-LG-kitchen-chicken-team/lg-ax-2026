/** agent-office observer records -> the release observation snapshot this factory already draws.
 * Same projection rules as backend/release_reader.py (field allow-lists, business binding, observer status), applied in
 * the browser so one HTML file next to runtime-data/agent-office/live.js works without a server. Records are data. */
const SKILLS=new Set(['evidence-retrieval','web-evidence-collection','needs-structuring','feature-comparison','concept-writing','review-and-revise']);
const ACTORS=new Set(['main','product_official_researcher','product_review_researcher','product_evidence_reviewer','other_subagent','unknown_subagent']);
const ROLE_IDS=['product_official_researcher','product_review_researcher','product_evidence_reviewer'];
const NODES=new Set([...ACTORS,...SKILLS,'unknown_skill']);
const KINDS=new Set(['lifecycle','tool','delegate','handback','handback_delivered','notification','request','subagent','skill_op','skill_load','shell','file','web','turn_cancelled','turn_end','session']);
const HOOKS=new Set(['PreToolUse','PostToolUse','PostToolUseFailure','UserPromptSubmit','Stop','SubagentStart','SubagentStop','SessionStart','SessionEnd']);
const PHASES=new Set(['start','end','fail','point']),BASES=new Set(['observed','instruction_loaded','command_based_mapping']),TS_BASES=new Set(['hook_received','codex_log','reader_received']);
const AREAS=new Set(['exports','web_evidence','catalogs','deliverables','conversation','runtime','skills','agents','docs','data','tools','web','outside','harness']);
const PROGRAMS=new Set(['ls','dir','cat','type','head','tail','find','grep','rg','wc','pwd','cd','echo','mkdir','cp','mv','rm','python','python3','py','uv','git','sed','awk','jq','curl','wget','sort','uniq','node','npm','npx','get-childitem','get-content','set-location','test-path','select-string','new-item','remove-item','copy-item','move-item','invoke-webrequest','out-file','set-content','get-item','write-output','measure-object','product_doctor','product-doctor.py','other']);
const WORKFLOW_KINDS=new Set(['research_plan','source_scan','research_stop','analysis_scope','finish']);
export const CONTINUATIONS=new Set(['handback_delivered','notification']);
export const RELEASE_PATTERN=/^product-v\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$/;
const MAX_EVENTS=1500;

const idToken=(value,limit=200)=>typeof value==='string'&&value.length>=1&&value.length<=limit&&/^[A-Za-z0-9_.:-]+$/.test(value)&&!/^(?:sk[-_]|gh[pousr]_|github_pat_|Bearer|eyJ)/i.test(value)?value:null;
const codeToken=value=>typeof value==='string'&&/^[a-z][a-z0-9_]{0,59}$/.test(value)?value:null;
const count=value=>Number.isSafeInteger(value)&&value>=0?value:null;
export const ms=value=>{const t=typeof value==='string'?Date.parse(value):NaN;return Number.isFinite(t)?t:null;};
export function iso(value){
  if(typeof value!=='string'||value.length>40||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(value))return null;
  const t=Date.parse(value);return Number.isFinite(t)?new Date(t).toISOString():null;
}
const isoAt=t=>new Date(t).toISOString();
function binding(value){
  if(!value||typeof value!=='object')return null;
  const out={session_id:idToken(value.session_id),turn_id:idToken(value.turn_id),request_key:idToken(value.request_key)};
  return out.session_id&&out.turn_id&&out.request_key?out:null;
}
export const sameBinding=(a,b)=>Boolean(a&&b&&['session_id','turn_id','request_key'].every(key=>a[key]===b[key]));

function safeDetail(raw){
  const out={};if(!raw||typeof raw!=='object')return out;
  for(const key of ['interrupted','background','accepted','other_skill_operation'])if(typeof raw[key]==='boolean')out[key]=raw[key];
  if(typeof raw.duration_ms==='number'&&Number.isFinite(raw.duration_ms)&&raw.duration_ms>=0)out.duration_ms=raw.duration_ms;
  for(const key of ['result_version','revision_count']){const limit=key==='revision_count'?2:3;if(Number.isSafeInteger(raw[key])&&raw[key]>=0&&raw[key]<=limit)out[key]=raw[key];}
  if(Number.isSafeInteger(raw.exit_code))out.exit_code=raw.exit_code;
  for(const key of ['reason','error','turn_status','response_status']){const value=codeToken(raw[key]);if(value)out[key]=value;}
  for(const key of ['launched_agent_id','from_agent_id']){const value=idToken(raw[key]);if(value)out[key]=value;}
  if(typeof raw.host==='string'&&raw.host.length<=253&&/^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$/.test(raw.host))out.host=raw.host.toLowerCase();
  if(AREAS.has(raw.area))out.area=raw.area;
  if(SKILLS.has(raw.skill))out.skill=raw.skill;
  if(Array.isArray(raw.programs))out.programs=[...new Set(raw.programs.filter(p=>PROGRAMS.has(p)))].slice(0,6);
  const joined=binding(raw.business_binding);if(joined)out.business_binding=joined;
  return out;
}

/** One observer line -> one release event, or null when it is not a complete, known record. */
export function projectEvent(raw){
  if(!raw||typeof raw!=='object'||raw.v!==1||!['codex','claude'].includes(raw.src)||!KINDS.has(raw.kind)||!PHASES.has(raw.phase)||!BASES.has(raw.basis))return null;
  const id=idToken(raw.id),ts=iso(raw.ts),session=idToken(raw.session);
  if(!id||!ts||!session||!TS_BASES.has(raw.ts_basis)||!HOOKS.has(raw.hook)||!ACTORS.has(raw.actor)||!NODES.has(raw.node))return null;
  if(raw.kind==='skill_op'&&(!SKILLS.has(raw.node)||raw.basis!=='command_based_mapping'))return null;
  if(raw.kind==='skill_load'&&(!SKILLS.has(raw.node)&&raw.node!=='unknown_skill'||raw.basis!=='instruction_loaded'))return null;
  const ops=Array.isArray(raw.ops)?raw.ops.slice(0,8).filter(op=>op&&SKILLS.has(op.skill)&&idToken(op.op,60)).map(op=>({skill:op.skill,op:op.op})):[];
  return {v:1,id,ts,ts_basis:raw.ts_basis,src:raw.src,hook:raw.hook,session,prompt_id:idToken(raw.prompt_id),agent_id:idToken(raw.agent_id),actor:raw.actor,
    tool:idToken(raw.tool,100),call:idToken(raw.call),kind:raw.kind,node:raw.node,op:idToken(raw.op,60),ops,phase:raw.phase,basis:raw.basis,detail:safeDetail(raw.detail)};
}

const isMain=event=>event.actor==='main'&&!event.agent_id;
/** The latest native request and the prompts that continue it. Claude Code delivers a background role's result
 * (and task notices) as a new prompt id; that is the same request, not a new question. */
export function selectedNative(events){
  const anchors=[];events.forEach((event,index)=>{if(isMain(event)&&(event.kind==='request'||event.kind==='session'&&event.phase==='start'))anchors.push(index);});
  if(!anchors.length)return {session:null,prompt:null,prompts:new Set(),floor:events.length};
  const session=events[anchors.at(-1)].session;
  let floor=0,request=-1;
  events.forEach((event,index)=>{if(isMain(event)&&event.session===session&&event.kind==='session'&&event.phase==='start')floor=index;});
  const started=events.some(event=>isMain(event)&&event.session===session&&event.kind==='session'&&event.phase==='start');
  events.forEach((event,index)=>{if(index>=floor&&isMain(event)&&event.session===session&&event.kind==='request')request=index;});
  if(request<0){const prompt=started?null:events[anchors.at(-1)].prompt_id;return {session,prompt,prompts:new Set([prompt]),floor:started?floor:anchors.at(-1)};}
  const prompt=events[request].prompt_id,prompts=new Set([prompt]),children=new Set();
  // A late result can belong to an older request in this same session. Only a child explicitly linked to this
  // request can introduce a continuation prompt; a bare notification is not proof of parentage.
  for(const event of events.slice(request)){
    if(event.session!==session)continue;
    if(isMain(event)&&CONTINUATIONS.has(event.kind)&&event.prompt_id&&children.has(event.detail?.from_agent_id))prompts.add(event.prompt_id);
    const linked=Boolean(event.prompt_id)&&prompts.has(event.prompt_id)||event.agent_id&&children.has(event.agent_id);
    if(!linked)continue;
    if(event.kind==='delegate'&&event.detail?.launched_agent_id)children.add(event.detail.launched_agent_id);
    if(event.kind==='subagent'&&event.phase==='start'&&event.agent_id)children.add(event.agent_id);
  }
  return {session,prompt,prompts,children,floor:request};
}

/** Observer status at time `now`: observing while the selected request has an open call, role or turn. */
export function observerStatus(events,now){
  if(!events.length)return 'waiting_for_session';
  const {session,prompts,floor}=selectedNative(events),current=events.slice(floor).filter(event=>event.session===session&&prompts.has(event.prompt_id));
  const opened=new Set(),closed=new Set();let turnOpen=false;
  for(const event of current){
    if(isMain(event)&&(event.kind==='request'||CONTINUATIONS.has(event.kind)))turnOpen=true;
    // Async hooks may record a call's end just before its start: a start whose end is already seen is closed.
    if(event.call){if(event.phase==='start'){if(!closed.has(event.call))opened.add(event.call);}else if(['end','fail'].includes(event.phase)){opened.delete(event.call);closed.add(event.call);}}
    if(event.kind==='subagent'){const key='agent:'+(event.agent_id||event.actor);if(event.phase==='start')opened.add(key);else opened.delete(key);}
    if(isMain(event)&&['turn_end','turn_cancelled'].includes(event.kind)){turnOpen=false;if(event.kind==='turn_cancelled')opened.clear();}
    if(isMain(event)&&event.kind==='session'&&event.phase==='end'){opened.clear();turnOpen=false;}
  }
  const age=current.length?now-Date.parse(current.at(-1).ts):null;
  return current.length&&(opened.size||turnOpen)&&age>=-5000&&age<=120000?'observing':'recorded';
}

/** The read-only DB summary, only for the request its business ids are bound to; `at` cuts it to that moment. */
export function safeDb(raw,events,at=null){
  if(!raw||typeof raw!=='object'||raw.available!==true)return {available:false,binding_status:'unavailable',binding:null,read_at:raw&&typeof raw==='object'?iso(raw.read_at):null};
  const readAt=iso(raw.read_at),expected=binding(raw.binding),{session,prompts,floor}=selectedNative(events);
  const matched=expected&&events.slice(floor).some(event=>isMain(event)&&event.session===session&&prompts.has(event.prompt_id)&&sameBinding(event.detail.business_binding,expected));
  if(!matched)return {available:true,binding_status:'unmatched',binding:null,read_at:readAt};
  const past=at!=null&&(ms(readAt)??Infinity)>at,visible=value=>!past||(ms(value)??Infinity)<=at;
  const out={available:true,binding_status:'matched',binding:expected,read_at:past?isoAt(at):readAt,workflow:null,workflow_events:[],request:null,turn:null,results:null,candidates:[],
    evidence_delivered:past?null:count(raw.evidence_delivered),evidence_reviews:past?null:count(raw.evidence_reviews),cancelled:past?null:raw.cancelled===true,latest_export:null};
  const workflow=raw.workflow;
  if(workflow&&typeof workflow==='object'&&idToken(workflow.research_id)&&visible(workflow.started_at)){
    const when=value=>visible(value)?iso(value):null;
    out.workflow={research_id:workflow.research_id,started_at:iso(workflow.started_at),budget_seconds:count(workflow.budget_seconds),research_stopped_at:when(workflow.research_stopped_at),finished_at:when(workflow.finished_at)};
  }
  for(const event of (Array.isArray(raw.workflow_events)?raw.workflow_events:[]).slice(-80)){
    if(!event||!WORKFLOW_KINDS.has(event.kind)||!iso(event.observed_at)||!visible(event.observed_at))continue;
    const item={kind:event.kind,observed_at:iso(event.observed_at)};
    for(const key of ['status','source_type','code','layout_review'])if(codeToken(event[key]))item[key]=event[key];
    for(const key of ['reviews','sources'])if(count(event[key])!=null)item[key]=event[key];
    const host=safeDetail({host:event.host}).host;if(host)item.host=host;
    out.workflow_events.push(item);
  }
  if(raw.request&&raw.request.turn_id===expected.turn_id&&raw.request.request_key===expected.request_key)out.request={turn_id:expected.turn_id,request_key:expected.request_key,status:past?null:codeToken(raw.request.status)};
  const turn=raw.turn;
  if(turn&&turn.turn_id===expected.turn_id&&visible(turn.created_at))out.turn={turn_id:expected.turn_id,status:past?null:codeToken(turn.status),revision_count:past?null:count(turn.revision_count),result_version:past?null:count(turn.result_version),valid:!past&&turn.valid===true,created_at:iso(turn.created_at)};
  for(const candidate of (Array.isArray(raw.candidates)?raw.candidates:[]).slice(-3)){
    if(!candidate||typeof candidate!=='object'||!visible(candidate.created_at))continue;
    const item={result_version:count(candidate.result_version),created_at:iso(candidate.created_at),status:codeToken(candidate.status),counts:{}};
    for(const key of ['pains','existing_features','remaining_pains','concepts','evidence_refs'])item.counts[key]=count(candidate.counts?.[key]);
    for(const key of ['contract_valid','structural_valid','acceptance_ready'])if(typeof candidate[key]==='boolean')item[key]=candidate[key];
    if(codeToken(candidate.semantic_status))item.semantic_status=candidate.semantic_status;
    out.candidates.push(item);
  }
  // During replay the turn's current version is not known yet; the newest candidate saved so far stands for it.
  if(past&&out.turn&&out.candidates.length)out.turn.result_version=out.candidates.at(-1).result_version;
  out.results=past?out.candidates.length:count(raw.results);
  const latest=raw.latest_export,exportedAt=latest&&typeof latest==='object'?iso(latest.created_at||latest.modified_at):null;
  if(exportedAt&&visible(exportedAt))out.latest_export={available:true,created_at:exportedAt};
  return out;
}

export function validLiveFile(value){return value&&typeof value==='object'&&value.kind==='lgax-agent-office-live'&&Array.isArray(value.events)?value:null;}
/** events.jsonl (one event per line), live.js, or a live-like JSON file. Unfinished or unknown lines are counted, not read. */
export function parseRecordFile(text){
  const trimmed=String(text).replace(/^﻿/,'').trim(),brace=trimmed.indexOf('{');
  if(/^\/\*|^window\.|^\{\s*"kind"\s*:\s*"lgax-agent-office-live"/.test(trimmed)&&brace>=0){
    try{const live=validLiveFile(JSON.parse(trimmed.slice(brace,trimmed.lastIndexOf('}')+1)));if(live)return {events:live.events,live,skipped:0};}catch{/* lines below */}
  }
  const events=[];let skipped=0;
  for(const line of trimmed.split(/\r?\n/)){if(!line.trim())continue;try{const value=JSON.parse(line);if(value&&typeof value==='object'&&typeof value.ts==='string')events.push(value);else skipped++;}catch{skipped++;}}
  return {events,live:null,skipped};
}
/** Only the result viewer fields this page shows: kind, build time, export name and status chips. */
export function resultMetadata(raw){
  if(!raw||raw.kind!=='lgax-view'||!Array.isArray(raw.pages)||!raw.pages.length)return null;
  const name=raw.context?.file?.name,status=Array.isArray(raw.context?.status)?raw.context.status.filter(s=>s&&typeof s.text==='string').slice(0,4).map(s=>String(s.text).slice(0,80)):[];
  return {generated_at:typeof raw.generated_at==='string'?raw.generated_at:null,export_name:typeof name==='string'?name.slice(0,120):null,status};
}

/** Projected, de-duplicated records in time order; `dropped` counts unknown or conflicting lines. */
export function prepareEvents(rawEvents=[]){
  const events=[],seen=new Map();let dropped=0;
  for(const raw of rawEvents){const event=projectEvent(raw);if(!event){dropped++;continue;}const key=JSON.stringify(event);if(seen.has(event.id)){if(seen.get(event.id)!==key)dropped++;continue;}seen.set(event.id,key);events.push(event);}
  events.sort((a,b)=>Date.parse(a.ts)-Date.parse(b.ts));
  return {events,dropped};
}
/** Every recorded session, oldest first (agent-office numbering). */
export function sessionsOf(events,projected=false){
  const by=new Map();
  for(const raw of events){
    const event=projected?raw:projectEvent(raw);if(!event)continue;
    const t=Date.parse(event.ts),s=by.get(event.session)||{id:event.session,src:event.src,start:t,end:t,count:0,requests:0,roles:[]};
    s.start=Math.min(s.start,t);s.end=Math.max(s.end,t);s.count++;
    if(isMain(event)&&event.kind==='request')s.requests++;
    if(ROLE_IDS.includes(event.actor)&&!s.roles.includes(event.actor))s.roles.push(event.actor);
    by.set(event.session,s);
  }
  return [...by.values()].sort((a,b)=>a.start-b.start);
}
/** Busy intervals of one session (calls, roles and open turns), used to skip quiet time while replaying. */
export function busyIntervals(events){
  const out=[],open=new Map(),closed=new Set();let turn=null;
  for(const event of events){
    const t=Date.parse(event.ts),key=event.kind==='subagent'?'agent:'+(event.agent_id||event.actor):event.call;
    if(key&&event.phase==='start'){if(!closed.has(key))open.set(key,t);}
    else if(key&&['end','fail'].includes(event.phase)){if(open.has(key))out.push([open.get(key),t]);else out.push([t,t]);open.delete(key);if(event.kind!=='subagent')closed.add(key);}
    else if(!key)out.push([t,t]);
    if(isMain(event)&&(event.kind==='request'||CONTINUATIONS.has(event.kind)))turn??=t;
    if(isMain(event)&&['turn_end','turn_cancelled'].includes(event.kind)&&turn!=null){out.push([turn,t]);turn=null;}
  }
  out.sort((a,b)=>a[0]-b[0]);
  const merged=[];for(const [a,b] of out){const last=merged.at(-1);if(last&&a<=last[1]+1000)last[1]=Math.max(last[1],b);else merged.push([a,b]);}
  return merged;
}
export function quietUntil(busy,t){for(const [a,b] of busy){if(t<a)return a;if(t<=b)return null;}return null;}

/** Records -> {schema_version:1, source, events, db, notices} for normalizeReleaseSnapshot/deriveReleaseView.
 * Live: all records of the newest session's engine at `now`. Replay: one session cut at `at`. */
export function officeSnapshot({events:rawEvents=[],prepared=null,db=null,release=null,writtenAt=null,origin='office_live',session=null,at=null,now=Date.now()}={}){
  const {events:projected,dropped}=prepared||prepareEvents(rawEvents);
  const chosen=session?projected.filter(event=>event.session===session):projected;
  const latestMain=[...chosen].reverse().find(isMain)||chosen.at(-1),engine=latestMain?.src||'claude';
  const cut=at==null?chosen:chosen.filter(event=>Date.parse(event.ts)<=at);
  const events=cut.filter(event=>event.src===engine).slice(-MAX_EVENTS),clock=at??now;
  const summary=safeDb(db,events,at),updates=[...events.map(event=>event.ts),summary.read_at,at==null?iso(writtenAt):null].filter(Boolean);
  const notices=[origin==='office_replay'?'저장된 관측 기록을 고른 시각까지 다시 그립니다. 그 시각 이후의 기록과 DB 값은 쓰지 않습니다.':'runtime-data/agent-office의 관측 파일(live.js)을 1초마다 다시 읽습니다. 모델·업무·훅·DB를 실행하거나 바꾸지 않습니다.',
    '관측 중 표시는 최근 열린 사건의 기록이며 프로세스 생존·모델 성공의 독립 확인이 아닙니다.','Skill 지침 읽기와 명령 기반 작업 추정을 실제 의미 판단·완료와 구분합니다.'];
  if(dropped)notices.push(`형식을 알 수 없는 관측 기록 ${dropped}개는 읽지 않았습니다.`);
  return {schema_version:1,source:{kind:'lgax_release_observer',release:typeof release==='string'&&RELEASE_PATTERN.test(release)?release:null,engine,origin,observed_at:isoAt(clock),
    source_updated_at:updates.length?updates.reduce((a,b)=>Date.parse(a)>=Date.parse(b)?a:b):null,observer_status:observerStatus(events,clock),asset_sha256:null,product_install_sha256:null},
    events,activity:null,db:summary,notices};
}
