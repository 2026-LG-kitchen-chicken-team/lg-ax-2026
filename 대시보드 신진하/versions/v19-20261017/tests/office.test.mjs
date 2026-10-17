import test from 'node:test';
import assert from 'node:assert/strict';
import {officeSnapshot,parseRecordFile,prepareEvents,projectEvent,safeDb,selectedNative,sessionsOf,busyIntervals,quietUntil,observerStatus,resultMetadata} from '../src/office-records.js';
import {deriveReleaseView,normalizeReleaseSnapshot} from '../src/release.js';
import {OfficeStore,stripModel,readHash} from '../src/office-store.js';

// agent-office observe.py lines (synthetic): only ids, names, times and host names, as the hook writes them.
const BASE=Date.parse('2026-10-16T12:00:00Z'),iso=t=>new Date(t).toISOString();
const TRIPLE={session_id:'business-session',turn_id:'business-turn',request_key:'request-key'};
let seq=0;
function line(sec,changes={}){return {v:1,id:'e'+(++seq).toString(16).padStart(6,'0'),ts:iso(BASE+sec*1000),ts_basis:'hook_received',src:'claude',hook:'PreToolUse',session:'native-1',prompt_id:'p1',agent_id:null,actor:'main',tool:null,call:null,kind:'lifecycle',node:'main',op:null,ops:[],phase:'point',basis:'observed',detail:{},keys:['session_id'],input_keys:[],...changes};}
const ask=(sec,c={})=>line(sec,{hook:'UserPromptSubmit',kind:'request',...c});
const stop=(sec,c={})=>line(sec,{hook:'Stop',kind:'turn_end',...c});
function op(sec,skill,name,call,c={}){return [line(sec,{tool:'Bash',call,kind:'skill_op',node:skill,op:name,ops:[{skill,op:name}],phase:'start',basis:'command_based_mapping'}),line(sec+1,{hook:'PostToolUse',tool:'Bash',call,kind:'skill_op',node:skill,op:name,ops:[{skill,op:name}],phase:'end',basis:'command_based_mapping',...c})];}
function db(changes={}){return {available:true,read_at:iso(BASE+400000),binding:TRIPLE,binding_status:'unverified_native_session',
  workflow:{research_id:'research-x',started_at:iso(BASE+5000),budget_seconds:1800,research_stopped_at:iso(BASE+60000),finished_at:iso(BASE+300000)},
  workflow_events:[{kind:'research_plan',observed_at:iso(BASE+10000),product:'PRIVATE_PRODUCT_TEXT'},{kind:'source_scan',observed_at:iso(BASE+30000),host:'reviews.example',page:'PRIVATE_PAGE',status:'observed',reviews:10,source_type:'review_list'},{kind:'research_stop',observed_at:iso(BASE+60000),code:'sufficient_evidence'},{kind:'analysis_scope',observed_at:iso(BASE+200000),sources:21},{kind:'finish',observed_at:iso(BASE+300000),layout_review:null}],
  request:{turn_id:'business-turn',request_key:'request-key',status:'needs_input'},turn:{turn_id:'business-turn',status:'completed',revision_count:0,result_version:1,valid:true,created_at:iso(BASE+62000)},
  results:1,candidates:[{result_version:1,created_at:iso(BASE+290000),status:'completed',counts:{pains:6,existing_features:8,remaining_pains:3,concepts:2,evidence_refs:21},contract_valid:true,structural_valid:true,acceptance_ready:false,semantic_status:'unverified'}],
  evidence_delivered:76,evidence_reviews:1,cancelled:false,latest_export:{name:'export-PRIVATE.json',modified_at:iso(BASE+301000),count:7},...changes};}
function microwaveRun(){
  seq=0;
  return [line(0,{hook:'SessionStart',kind:'session',phase:'start',prompt_id:null,detail:{reason:'startup'}}),ask(1),
    ...op(10,'evidence-retrieval','open_product_workflow','c-open'),...op(30,'web-evidence-collection','fetch_web_page','c-fetch'),
    ...op(61,'evidence-retrieval','resolve_request_bundle','c-bundle'),
    ...op(180,'review-and-revise','prepare_review_packet','c-packet',{detail:{business_binding:TRIPLE}}),
    line(185,{tool:'Agent',call:'c-agent',kind:'delegate',node:'product_evidence_reviewer',phase:'start'}),
    line(186,{hook:'SubagentStart',kind:'subagent',actor:'product_evidence_reviewer',node:'product_evidence_reviewer',agent_id:'child-1',phase:'start'}),
    stop(190),line(250,{hook:'SubagentStop',kind:'subagent',actor:'product_evidence_reviewer',node:'product_evidence_reviewer',agent_id:'child-1',phase:'end'}),
    line(251,{hook:'UserPromptSubmit',kind:'handback_delivered',prompt_id:'p2',detail:{from_agent_id:'child-1'}}),
    ...op(280,'review-and-revise','verify_review_packet','c-verify',{prompt_id:'p2'}).map(e=>({...e,prompt_id:'p2'})),stop(310,{prompt_id:'p2'})];
}
const at=(events,sec,c={})=>{const t=BASE+sec*1000,snap=officeSnapshot({events,db:db(),release:'product-v0.16.4',origin:'office_replay',session:'native-1',at:t,...c});return deriveReleaseView(snap,{status:'connected',lastReceivedAt:iso(t)},t);};

test('manual record view never polls neighboring executable files and still replays an opened record',async()=>{
  let liveReads=0,resultReads=0;
  const store=new OfficeStore({pollFiles:false,clock:()=>BASE+20000,setTimer:()=>1,clearTimer:()=>{},
    liveTransport:()=>{liveReads++;return()=>{};},resultTransport:()=>{resultReads++;return()=>{};}});
  store.start();await store.refresh();
  assert.equal(liveReads,0);assert.equal(resultReads,0);
  assert.equal(store.getSnapshot().connection.status,'disconnected');
  const records=[ask(1),stop(10)];
  assert.equal(store.openFile(records.map(x=>JSON.stringify(x)).join('\n'),'test-records.jsonl'),true);
  assert.equal(store.getSnapshot().office.mode,'replay');
  assert.equal(store.getSnapshot().office.sessions.length,1);
  store.setSpeed(64);store.seek(BASE+5000);
  assert.equal(store.getSnapshot().office.speed,64);
  assert.equal(store.getSnapshot().office.at,BASE+5000);
  await store.refresh();store.stop();
  assert.equal(liveReads,0);assert.equal(resultReads,0);
});

test('observer lines become release events with only allow-listed fields, unknown lines are counted not read',()=>{
  const events=[ask(1),{...line(2),kind:'invented'},{...line(3),detail:{programs:['ls','rm -rf /'],host:'Example.COM',raw:'PRIVATE',business_binding:TRIPLE}}];
  const {events:kept,dropped}=prepareEvents(events);
  assert.equal(dropped,1);assert.equal(kept.length,2);
  assert.deepEqual(kept[1].detail,{host:'example.com',programs:['ls'],business_binding:TRIPLE});
  assert.equal('keys' in kept[0],false);assert.equal(projectEvent({...ask(1),ts:'yesterday'}),null);
  const snap=officeSnapshot({events,db:null,now:BASE+5000});
  assert.doesNotThrow(()=>normalizeReleaseSnapshot(snap));assert.match(snap.notices.at(-1),/1개는 읽지 않았습니다/);
});

test('a delivered role result continues the request: binding, header and turn end follow the real flow',()=>{
  const events=microwaveRun(),{session,prompts}=selectedNative(prepareEvents(events).events);
  assert.equal(session,'native-1');assert.deepEqual([...prompts].sort(),['p1','p2']);
  const late=at(events,300);
  assert.equal(late.bindingState,'matched');assert.equal(late.mainActive,true);
  assert.equal(at(events,320).header.text,'메인 최종 응답 종료 관측');
  const between=at(events,200);// first Stop at 190, the reviewer still running: the main turn ended, the role did not
  assert.equal(between.roles.find(r=>r.id==='product_evidence_reviewer').active,true);
});

test('the three analysis workshops follow research stop, review hand-off and the saved candidate, never invented times',()=>{
  const events=microwaveRun();
  const research=at(events,40);
  for(const node of ['structure','compare','concept'])assert.equal(research.nodes[node].statusLabel,'실행 기록 없음');
  const analysis=at(events,120);
  for(const node of ['structure','compare','concept']){assert.equal(analysis.nodes[node].status,'analysis');assert.equal(analysis.nodes[node].statusLabel,'분석 구간');assert.equal(analysis.nodes[node].evidence[0].label,'최종 근거 묶음 확인 명령 완료 · resolve_request_bundle');}
  assert.deepEqual(analysis.activeNodes,[]);assert.equal(analysis.mainActive,true);assert.equal(analysis.header.text,'분석 구간 · 메인 기획자 직접 작성');
  const draft=at(events,182);
  assert.equal(draft.nodes.structure.statusLabel,'초안 확인');assert.equal(draft.nodes.structure.basis,'review_handoff');
  const saved=at(events,400);
  assert.equal(saved.nodes.structure.task,'저장된 후보 v1: 불편 6건');assert.equal(saved.nodes.compare.task,'저장된 후보 v1: 기존 기능 8건 · 남은 불편 3건');assert.equal(saved.nodes.concept.task,'저장된 후보 v1: 콘셉트 2건');
  assert.equal(saved.nodes.validate.statusLabel,'결과 저장 확인');assert.match(saved.nodes.web.evidence.map(e=>e.label).join('|'),/출처 스캔 기록 1건 · 사이트 1곳 · 후기 10건/);
  assert.doesNotMatch(JSON.stringify(saved),/PRIVATE/);
});

test('replay cuts the DB summary to the chosen moment and an unbound DB never fills another request',()=>{
  const events=prepareEvents(microwaveRun()).events;
  const early=safeDb(db(),events.filter(e=>Date.parse(e.ts)<=BASE+250000),BASE+250000);
  assert.equal(early.binding_status,'matched');assert.deepEqual(early.candidates,[]);assert.equal(early.evidence_delivered,null);
  assert.deepEqual(early.workflow_events.map(e=>e.kind),['research_plan','source_scan','research_stop','analysis_scope']);assert.equal(early.workflow.finished_at,null);
  const other=safeDb(db({binding:{...TRIPLE,turn_id:'other-turn'}}),events);
  assert.deepEqual(Object.keys(other).sort(),['available','binding','binding_status','read_at']);
  assert.equal(safeDb(db(),events).latest_export.created_at,iso(BASE+301000));
});

test('an end recorded before its start (async hooks) does not leave a call open',()=>{
  seq=0;const events=[ask(1),line(5,{hook:'PostToolUse',tool:'ToolSearch',call:'c-early',kind:'tool',phase:'end'}),line(5,{tool:'ToolSearch',call:'c-early',kind:'tool',phase:'start'})];
  const {events:kept}=prepareEvents(events);
  const view=deriveReleaseView(officeSnapshot({events,now:BASE+10000}),{status:'connected',lastReceivedAt:iso(BASE+10000)},BASE+10000);
  assert.equal(view.spans.filter(s=>s.status==='open').length,0);assert.equal(view.header.text,'메인 기획자 작업 중 · 진행 중인 도구 호출 없음');
  assert.equal(observerStatus(kept,BASE+10000),'observing');// the request is open, the call is not
  assert.equal(stripModel(kept,null).spans.filter(s=>s.status==='open').length,0);
});

test('sessions, quiet gaps, records files and result metadata',()=>{
  const events=[...microwaveRun(),ask(5000,{session:'native-2',prompt_id:'q1'})];
  const list=sessionsOf(events);
  assert.deepEqual(list.map(s=>[s.id,s.requests,s.roles]),[['native-1',1,['product_evidence_reviewer']],['native-2',1,[]]]);
  const busy=busyIntervals(prepareEvents(events).events.filter(e=>e.session==='native-1'));
  assert.equal(quietUntil(busy,BASE+500000),null);assert.ok(busy.length>=1);
  const jsonl=events.map(e=>JSON.stringify(e)).join('\n')+'\n{"unfinished":';
  const parsed=parseRecordFile(jsonl);assert.equal(parsed.events.length,events.length);assert.equal(parsed.skipped,1);assert.equal(parsed.live,null);
  const live=parseRecordFile('/* agent-office observe.py writes this file; do not edit. */\nwindow.LGAX_OFFICE_LIVE = '+JSON.stringify({kind:'lgax-agent-office-live',version:1,written_at:iso(BASE),harness_release:'product-v0.16.4',events,db:db()})+';\n');
  assert.equal(live.live.harness_release,'product-v0.16.4');assert.equal(live.events.length,events.length);
  assert.deepEqual(resultMetadata({kind:'lgax-view',generated_at:'2026-10-16T21:18:25+09:00',context:{file:{name:'export-a.json'},status:[{text:'완료',tone:'ok'}]},pages:[{}]}),{generated_at:'2026-10-16T21:18:25+09:00',export_name:'export-a.json',status:['완료']});
  assert.equal(resultMetadata({kind:'lgax-view',pages:[]}),null);
  assert.deepEqual(readHash('#mode=replay&s=2&t=95&sel=compare&play=0'),{mode:'replay',s:2,t:95,play:'0',speed:0,sel:'compare'});
});

test('installed release label follows the records; a missing or malformed label is unknown, not a pinned version',()=>{
  const events=[ask(1)];
  assert.equal(normalizeReleaseSnapshot(officeSnapshot({events,release:'product-v0.17.0',now:BASE})).source.release,'product-v0.17.0');
  assert.equal(normalizeReleaseSnapshot(officeSnapshot({events,release:'<b>v9</b>',now:BASE})).source.release,null);
  const view=deriveReleaseView(officeSnapshot({events,release:'product-v0.16.4',now:BASE+2000}),{status:'connected',lastReceivedAt:iso(BASE+2000)},BASE+2000);
  assert.equal(view.release,'product-v0.16.4');assert.equal(view.origin,'office_live');assert.equal(view.sourceMode,'release');
});

function fakeClock(){let now=BASE+500000,next=0;const timers=new Map();return {clock:()=>now,setTimer:(fn,ms)=>{const id=++next;timers.set(id,{fn,at:now+ms});return id;},clearTimer:id=>timers.delete(id),
  run(ms){const end=now+ms;for(;;){const due=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!due)break;now=due[1].at;timers.delete(due[0]);due[1].fn();}now=end;}};}
test('office store: live polling, replay with speed and quiet-gap skip, records file, and failed reads keep the last view',()=>{
  const env=fakeClock(),events=microwaveRun();let reads=0,fail=false;
  const live={kind:'lgax-agent-office-live',version:1,written_at:iso(BASE+400000),harness_release:'product-v0.16.4',events,db:db()};
  const store=new OfficeStore({...env,hash:'',liveTransport:(ok,no)=>{reads++;fail?no('unavailable'):ok(live);return()=>{};},resultTransport:(ok,no)=>{no('unavailable');return()=>{};}});
  store.start();
  let state=store.getSnapshot();
  assert.equal(state.office.mode,'live');assert.equal(state.office.sessions.length,1);assert.equal(state.view.release,'product-v0.16.4');assert.equal(state.connection.status,'connected');
  env.run(3000);assert.ok(reads>=3);
  fail=true;env.run(25000);state=store.getSnapshot();
  assert.equal(state.connection.status,'error');assert.equal(state.office.sessions.length,1);// the last good records stay
  fail=false;store.replay('native-1');state=store.getSnapshot();
  assert.equal(state.office.mode,'replay');assert.equal(state.office.at,BASE);assert.equal(state.view.origin,'office_replay');
  store.setSpeed(64);env.run(1000);assert.ok(store.getSnapshot().office.at>BASE+30000);
  store.seek(BASE+120000);store.play(false);state=store.getSnapshot();assert.equal(state.view.nodes.structure.status,'analysis');
  assert.equal(store.openFile('not a record','x.txt'),false);assert.match(store.getSnapshot().office.note,/읽을 수 있는 실행 기록이 없습니다/);
  assert.equal(store.openFile(events.map(e=>JSON.stringify(e)).join('\n'),'events.jsonl'),true);state=store.getSnapshot();
  assert.equal(state.office.file.name,'events.jsonl');assert.equal(state.office.file.db,false);assert.match(state.office.note,/DB 정보가 없습니다/);
  store.goLive();assert.equal(store.getSnapshot().office.mode,'live');assert.equal(store.getSnapshot().office.file,null);
  store.stop();
});
test('before the first hook writes live.js the file view waits for records instead of reporting a broken connection',()=>{
  const env=fakeClock(),store=new OfficeStore({...env,hash:'',liveTransport:(ok,no)=>{no('unavailable');return()=>{};},resultTransport:(ok,no)=>{no('unavailable');return()=>{};}});
  store.start();const state=store.getSnapshot();
  assert.equal(state.office.missing,true);assert.equal(state.connection.status,'connected');
  assert.equal(state.view.header.state,'waiting');assert.match(state.view.header.text,/실제 기록 대기/);assert.match(state.view.nextAction,/Claude Code로 질문/);
  assert.equal(state.view.counts.events,0);assert.deepEqual(state.view.activeNodes,[]);
  store.stop();
});


test('a stale child handback or unverified notification never binds the newest request in file or server views',()=>{
  for(const [kind,detail] of [['handback_delivered',{from_agent_id:'child-a'}],['notification',{}]]){
    const events=[ask(1,{prompt_id:'a'}),line(2,{kind:'delegate',prompt_id:'a',detail:{launched_agent_id:'child-a'}}),
      ask(3,{prompt_id:'b'}),stop(4,{prompt_id:'b'}),line(5,{kind,prompt_id:'late-a',detail}),
      line(6,{kind:'shell',prompt_id:'late-a',detail:{business_binding:TRIPLE}})];
    const clean=prepareEvents(events).events;
    assert.deepEqual([...selectedNative(clean).prompts],['b']);
    const file=at(events,10);assert.equal(file.promptId,'b');assert.equal(file.bindingState,'unmatched');
    assert.equal(file.counts.concepts,null);assert.equal(file.mainActive,false);
    const snapshot=officeSnapshot({events,now:BASE+10000});
    snapshot.db={...db(),binding_status:'matched',latest_export:{available:true,created_at:iso(BASE+301000)}}; // Also reject a server that sends a stale matched DB.
    const server=deriveReleaseView(snapshot,{status:'connected',lastReceivedAt:iso(BASE+10000)},BASE+10000);
    assert.equal(server.bindingState,'unmatched');assert.equal(server.database,null);assert.equal(server.counts.concepts,null);
  }
});

test('non-string release metadata becomes unknown in a record and is rejected in an external snapshot',()=>{
  for(const release of [['product-v0.16.4'],{},42,true]){
    const snapshot=officeSnapshot({events:[ask(1)],release,now:BASE+5000});
    assert.equal(snapshot.source.release,null);
    assert.doesNotThrow(()=>deriveReleaseView(snapshot,{status:'connected',lastReceivedAt:iso(BASE+5000)},BASE+5000));
    snapshot.source.release=release;
    assert.throws(()=>normalizeReleaseSnapshot(snapshot));
  }
});


test('a missing prompt id never proves an old SubagentStart belongs to the new request',()=>{
  const events=[ask(1,{prompt_id:'a'}),line(2,{kind:'delegate',prompt_id:'a',detail:{launched_agent_id:'child-a'}}),
    ask(3,{prompt_id:null}),stop(4,{prompt_id:null}),
    line(5,{kind:'subagent',phase:'start',actor:'product_evidence_reviewer',node:'product_evidence_reviewer',agent_id:'child-a',prompt_id:null}),
    line(6,{kind:'handback_delivered',prompt_id:'late-a',detail:{from_agent_id:'child-a'}}),
    line(7,{kind:'shell',prompt_id:'late-a',detail:{business_binding:TRIPLE}})];
  const selection=selectedNative(prepareEvents(events).events);
  assert.deepEqual([...selection.prompts],[null]);assert.deepEqual([...selection.children],[]);
  const projected=at(events,10);assert.equal(projected.bindingState,'unmatched');assert.equal(projected.mainActive,false);
  const snapshot=officeSnapshot({events,now:BASE+10000});snapshot.db={...db(),binding_status:'matched',latest_export:null};
  const view=deriveReleaseView(snapshot,{status:'connected',lastReceivedAt:iso(BASE+10000)},BASE+10000);
  assert.equal(view.bindingState,'unmatched');assert.equal(view.counts.concepts,null);
  assert.ok(view.roles.every(role=>!role.active));assert.deepEqual(view.activeNodes,[]);
});
