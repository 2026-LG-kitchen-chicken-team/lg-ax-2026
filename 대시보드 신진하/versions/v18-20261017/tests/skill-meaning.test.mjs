import test from 'node:test';
import assert from 'node:assert/strict';
import {deriveReleaseView} from '../src/release.js';
import {observerWork} from '../src/factory-work-view.js';
import {PRODUCT_SKILLS,PRODUCT_ROOM_IDS} from '../src/skill-catalog.js';
import {factoryLayout,ZONE_FLOOR,PLANNER_FLOOR,transitionFactory} from '../src/factory-layout.js';
import {skillResearcherRoute} from '../src/skill-researcher-route.js';

const NOW=Date.parse('2026-10-17T03:00:00Z'),iso=t=>new Date(t).toISOString();
const event=(id,patch={})=>({v:1,id,ts:iso(NOW-1000),ts_basis:'codex_log',src:'codex',hook:'PreToolUse',session:'session',prompt_id:'current',agent_id:null,actor:'main',tool:'exec_command',call:'call-'+id,kind:'skill_op',node:'feature-comparison',op:'retrieve_product_facts',ops:[],phase:'start',basis:'command_based_mapping',detail:{},...patch});
const request=(patch={})=>event('request',{ts:iso(NOW-10000),hook:'UserPromptSubmit',call:null,tool:null,kind:'request',node:'main',op:null,phase:'point',basis:'observed',...patch});
const source={kind:'lgax_release_observer',release:'product-v0.18.0',engine:'codex',observed_at:iso(NOW),source_updated_at:iso(NOW-1000),observer_status:'observing',asset_sha256:null,product_install_sha256:null};
const view=(events,connection={status:'connected',lastReceivedAt:iso(NOW)})=>deriveReleaseView({schema_version:1,source,events,db:null,notices:[]},connection,NOW);

test('six audited Skills have separate rooms; web collection never lights stored retrieval',()=>{
 const v=view([request(),event('web',{node:'web-evidence-collection',op:'capture_source'})]),w=observerWork(v);
 assert.equal(v.skills.length,6);assert.equal(Object.keys(v.nodes).length,6);assert.equal(new Set(PRODUCT_SKILLS.map(s=>s.node)).size,6);
 assert.deepEqual(v.activeNodes,['web']);assert.deepEqual(w.skillActiveNodes,['web']);assert.equal(w.rooms.retrieve.confirmed,false);assert.equal(w.rooms.web.statusLabel,'SKILL 사용 중');
});
test('v0.18 instruction retrieval is never promoted to an active Skill operation',()=>{
 const v=view([request(),event('read',{op:'get_work_instructions'})]),w=observerWork(v);
 assert.deepEqual(v.activeSkills,[]);assert.deepEqual(w.skillActiveNodes,[]);assert.equal(v.counts.skills,0);assert.equal(v.counts.instructions,1);
 assert.equal(v.skills.find(s=>s.node==='compare').operationObserved,false);assert.equal(v.skills.find(s=>s.node==='compare').instructionLoaded,false);assert.equal(w.rooms.compare.statusLabel,'대기');assert.equal(v.instructionQuery.status,'reading');assert.equal(w.mainWorking,true);
});
test('mixed wrapper operations track the actually used Skill, not the wrapper path or guideline reads',()=>{
 const v=view([request(),event('mixed',{node:'evidence-retrieval',op:'get_work_instructions',ops:[{skill:'evidence-retrieval',op:'get_work_instructions'},{skill:'feature-comparison',op:'retrieve_product_facts'}]})]),w=observerWork(v);
 assert.deepEqual(v.activeSkills,['feature-comparison']);assert.equal(w.rooms.compare.confirmed,true);assert.equal(w.rooms.retrieve.confirmed,false);assert.equal(v.counts.skills,1);
});
test('instruction failure stays failed and a successful instruction response stays separate from work',()=>{
 const read=event('read',{op:'get_work_instructions'});
 for(const phase of ['fail','end']){const v=view([request(),read,event('read-'+phase,{...read,id:'read-'+phase,phase,ts:iso(NOW-100)})]),s=v.skills.find(s=>s.node==='compare');assert.equal(s.instructionLoaded,false);assert.equal(s.operationObserved,false);assert.equal(s.status,'idle');assert.equal(v.instructionQuery.status,phase==='fail'?'failed':'completed');assert.deepEqual(observerWork(v).skillActiveNodes,[]);}
});
test('completion of a mixed call preserves the secondary Skill result status',()=>{
 const mixed=event('mixed',{node:'evidence-retrieval',op:'get_work_instructions',ops:[{skill:'evidence-retrieval',op:'get_work_instructions'},{skill:'feature-comparison',op:'retrieve_product_facts'}]});
 const v=view([request(),mixed,event('mixed-end',{...mixed,id:'mixed-end',phase:'end',ts:iso(NOW-100)})]);assert.equal(v.nodes.compare.status,'completed');assert.equal(observerWork(v).rooms.compare.statusLabel,'기록 완료');
});
test('a nonzero command exit code is failed even when the Tool end itself succeeded',()=>{
 const read=event('read',{op:'get_work_instructions'}),end=event('read-end',{...read,id:'read-end',phase:'end',ts:iso(NOW-100),detail:{exit_code:1}});
 for(const starts of [[],[read]]){const v=view([request(),...starts,end]),s=v.skills.find(s=>s.node==='compare');assert.equal(s.instructionLoaded,false);assert.equal(s.status,'idle');assert.equal(v.instructionQuery.status,'failed');assert.equal(v.spans.find(s=>s.start.kind==='skill_op').status,'failed');assert.deepEqual(v.activeSkills,[]);}
});
test('native helper stop removes its unfinished Skill emphasis without inventing a Tool success',()=>{
 const role='product_official_researcher',start=event('child',{kind:'subagent',actor:role,node:role,agent_id:'child',op:null,basis:'observed'});
 const v=view([request(),start,event('child-work',{actor:role,agent_id:'child'}),event('child-end',{...start,id:'child-end',phase:'end',ts:iso(NOW-100)})]);assert.equal(v.agents[0].status,'completed');assert.deepEqual(v.activeSkills,[]);assert.deepEqual(observerWork(v).skillActiveNodes,[]);assert.equal(v.spans.find(s=>s.start.id==='child-work').resultKnown,false);
});
test('native cancellation or final response takes precedence over an older CLI progress report',()=>{
 const activity={kind:'codex_native_activity',session_id:'session',prompt_id:'current',state:'working',intent:'planning',task_code:'compare_features',reported_stage:'compare',last_event_at:iso(NOW-1500),checks:{},installed_skills:[],skill_reads:[],command_count:0,web_count:0,actions:[]};
 for(const kind of ['turn_end','turn_cancelled']){const events=[request(),event('terminal',{kind,node:'main',op:null,phase:'point',basis:'observed',ts:iso(NOW-500)})],v=deriveReleaseView({schema_version:1,source,events,activity,db:null,notices:[]},{status:'connected',lastReceivedAt:iso(NOW)},NOW),w=observerWork(v);assert.equal(w.mainWorking,false);assert.deepEqual(w.activeNodes,[]);assert.notEqual(v.header.state,'active');}
});
test('two helpers with the same role retain two native identities and an explicit Skill relation',()=>{
 const role='product_official_researcher';
 const events=[request(),...['child-1','child-2'].flatMap((id,i)=>[
  event('launch-'+i,{ts:iso(NOW-5000+i*10),kind:'delegate',node:role,phase:'end',op:null,basis:'observed',detail:{launched_agent_id:id}}),
  event('start-'+i,{ts:iso(NOW-4000+i*10),kind:'subagent',node:role,actor:role,agent_id:id,op:null,basis:'observed'}),
  event('work-'+i,{actor:role,agent_id:id,node:'web-evidence-collection',op:'capture_source'}),
 ])];
 const v=view(events),w=observerWork(v);assert.equal(v.agents.length,2);assert.equal(w.workingAgents.length,2);assert.equal(v.roles.length,1);
 assert.deepEqual(v.roles[0].agentIds,['child-1','child-2']);assert.equal(w.rooms.web.actors.length,2);assert.equal(w.rooms.web.workerCount,2);assert.equal(w.rooms.web.helperRole,true);
});
test('a native helper start without a Skill command is purple helper work, not orange Skill use',()=>{
 const role='product_review_researcher',v=view([request(),event('child',{kind:'subagent',actor:role,node:role,agent_id:'child',op:null,basis:'observed'})]),w=observerWork(v);
 assert.equal(w.rooms.web.helperActive,true);assert.equal(w.rooms.web.confirmed,false);assert.deepEqual(w.skillActiveNodes,[]);assert.equal(w.rooms.web.statusLabel,'도우미 작업');
});
test('previous-request Skill and helper history cannot appear as current actors',()=>{
 const role='product_official_researcher',v=view([request({id:'old',prompt_id:'old',ts:iso(NOW-30000)}),event('old-work',{prompt_id:'old',phase:'end',ts:iso(NOW-20000)}),event('old-child',{prompt_id:'old',kind:'subagent',actor:role,node:role,agent_id:'old-child',op:null,basis:'observed',ts:iso(NOW-19000)}),request()]);
 assert.equal(v.agents.length,0);assert.equal(v.roles.length,0);assert.equal(v.nodes.compare.actor,null);assert.equal(v.skills.find(s=>s.node==='compare').used,false);assert.equal(v.events.length,4);
});
test('failure, completion and cancellation preserve the actual helper lifecycle',()=>{
 const role='other_subagent',start=event('child',{kind:'subagent',actor:role,node:role,agent_id:'unknown-role-child',op:null,basis:'observed'});
 for(const [phase,status] of [['end','completed'],['fail','failed']]){const v=view([request(),start,event('end-'+phase,{...start,id:'end-'+phase,ts:iso(NOW-100),phase})]);assert.equal(v.agents[0].status,status);assert.equal(v.agents[0].active,false);}
 const cancelled=view([request(),start,event('cancel',{ts:iso(NOW-100),kind:'turn_cancelled',node:'main',op:null,phase:'point',basis:'observed'})]);assert.equal(cancelled.agents[0].status,'cancelled');assert.equal(observerWork(cancelled).mainWorking,false);
});
test('stale or disconnected observation stops all working effects without fabricating a process exit',()=>{
 for(const connection of [{status:'disconnected'},{status:'connected',lastReceivedAt:iso(NOW-30000)}]){
  const v=view([request(),event('work')],connection),w=observerWork(v);assert.equal(w.mainWorking,false);assert.deepEqual(w.activeNodes,[]);assert.deepEqual(w.skillActiveNodes,[]);assert.equal(v.events.length,2);
 }
});
test('each six-Skill parallel combination fits without floor overlap, including planner activity',()=>{
 const screens=[[1600,1000,0],[390,844,0],[844,390,0],[1280,800,470]],floor=z=>z.id==='overview'?PLANNER_FLOOR:ZONE_FLOOR;
 const separate=zones=>{const a=Object.values(zones);for(let i=0;i<a.length;i++)for(let j=i+1;j<a.length;j++){const x=a[i],y=a[j],xf=floor(x),yf=floor(y);assert.ok(Math.abs(x.x-y.x)>=xf.halfX*x.scale+yf.halfX*y.scale-.001||Math.abs(x.z-y.z)>=xf.halfZ*x.scale+yf.halfZ*y.scale-.001,JSON.stringify({x,y}));}};
 for(const [width,height,panelWidth] of screens){let previous=factoryLayout({width,height,panelWidth,roomIds:PRODUCT_ROOM_IDS}).zones;for(let mask=0;mask<64;mask++){const activeIds=['overview',...PRODUCT_ROOM_IDS.filter((_,i)=>mask&(1<<i))],next=factoryLayout({width,height,panelWidth,roomIds:PRODUCT_ROOM_IDS,activeIds});assert.equal(Object.keys(next.zones).length,7);separate(next.zones);for(const age of [.1,.3,.7])separate(transitionFactory(previous,next.zones,age));previous=next.zones;}}
});
test('Skill-specific researcher routes stay inside their room and stop beside different tools',()=>{
 const docks=[];for(const id of PRODUCT_ROOM_IDS){const first=skillResearcherRoute(id,0);docks.push([first.x,first.z].join(','));assert.equal(first.walking,false);let walks=false;for(let t=0;t<first.cycle;t+=.1){const p=skillResearcherRoute(id,t);assert.ok(Math.abs(p.x)+.15<ZONE_FLOOR.halfX);assert.ok(Math.abs(p.z)+.15<ZONE_FLOOR.halfZ);if(p.walking)walks=true;}assert.ok(walks);assert.equal(skillResearcherRoute(id,first.cycle).walking,false);}assert.ok(new Set(docks).size>=5);
});

test('a wrapper querying main or known_context never certifies that wrapper Skill instructions loaded',()=>{
 const lookup=event('lookup',{node:'evidence-retrieval',op:'get_work_instructions'}),v=view([request(),lookup,event('lookup-end',{...lookup,id:'lookup-end',phase:'end',ts:iso(NOW-100)})]);
 assert.ok(v.skills.every(s=>!s.instructionLoaded&&!s.used));assert.equal(v.instructionQuery.status,'completed');assert.deepEqual(v.activeSkills,[]);
});
test('actual v0.18 Codex child without returned parent ID is visible only as unbound session history',()=>{
 const role='product_official_researcher',v=view([request(),event('delegate',{kind:'delegate',node:role,op:null,phase:'end',basis:'observed',detail:{background:true}}),event('native-child',{kind:'subagent',node:role,actor:role,agent_id:'native-child',prompt_id:null,op:null,basis:'observed'}),event('child-skill',{actor:role,agent_id:'native-child',prompt_id:'child-native-turn',node:'web-evidence-collection',op:'capture_source'})]),w=observerWork(v);
 assert.equal(v.agents.length,0);assert.equal(v.unboundAgents.length,1);assert.equal(v.unboundAgents[0].id,'native-child');assert.equal(v.unboundAgents[0].active,false);assert.deepEqual(v.unboundAgents[0].activeSkills,[]);assert.deepEqual(v.unboundAgents[0].observedSkills,['web-evidence-collection']);assert.deepEqual(w.workingAgents,[]);assert.deepEqual(w.skillActiveNodes,[]);
 const closed=view([...v.events,event('child-stop',{kind:'subagent',node:role,actor:role,agent_id:'native-child',prompt_id:'child-native-turn',op:null,phase:'end',basis:'observed',ts:iso(NOW-50)})]);assert.equal(closed.unboundAgents[0].status,'completed');
});
test('a helper explicitly linked to an older main request is history, never an unbound current helper',()=>{
 const role='product_official_researcher',v=view([request({id:'old',prompt_id:'old',ts:iso(NOW-30000)}),event('old-child',{prompt_id:'old',kind:'subagent',actor:role,node:role,agent_id:'old-child',op:null,basis:'observed',ts:iso(NOW-19000)}),request()]);
 assert.equal(v.agents.length,0);assert.equal(v.unboundAgents.length,0);
});
