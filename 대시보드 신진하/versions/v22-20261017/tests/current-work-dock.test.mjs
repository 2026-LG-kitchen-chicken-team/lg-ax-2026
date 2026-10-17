import test from 'node:test';
import assert from 'node:assert/strict';
import {currentWorkSummary,workDockInsets} from '../src/current-work-summary.js';
import {SKILL_ACTIONS,illustratedWorkPose} from '../src/skill-choreography.js';
import {observerWork} from '../src/factory-work-view.js';
import {deriveReleaseView} from '../src/release.js';
import {advanceResearcherClock} from '../src/researcher-motion.js';
const NOW=Date.parse('2026-10-17T05:00:00Z'),iso=n=>new Date(n).toISOString();
const event=(id,patch={})=>({v:1,id,ts:iso(NOW-1000),ts_basis:'codex_log',src:'codex',hook:'PreToolUse',session:'test-session',prompt_id:'test-request',agent_id:null,actor:'main',tool:'exec_command',call:'test-call-'+id,kind:'skill_op',node:'feature-comparison',op:'retrieve_product_facts',ops:[],phase:'start',basis:'command_based_mapping',detail:{},...patch});
const request=event('request',{ts:iso(NOW-10000),hook:'UserPromptSubmit',call:null,tool:null,kind:'request',node:'main',op:null,phase:'point',basis:'observed'});
const source={kind:'lgax_release_observer',release:'product-v0.18.0',engine:'codex',observed_at:iso(NOW),source_updated_at:iso(NOW-1000),observer_status:'observing'};
const view=(events,status='connected')=>deriveReleaseView({schema_version:1,source,events,db:null,notices:[]},{status,lastReceivedAt:iso(NOW)},NOW);
test('work dock never turns unconnected or stale history into current activity',()=>{
 for(const status of ['disconnected','stale','error']){const v=view([request,event('work')],status),w=observerWork(v),d=currentWorkSummary(v,w);assert.equal(d.active,false);assert.equal(d.rooms.length,0);assert.ok(!d.title.includes('SKILL 사용 중'));}
});
test('progress is unknown until matched results exist; absent units are never invented',()=>{
 const v=view([request,event('work')]),w=observerWork(v),s=currentWorkSummary(v,w);assert.equal(s.rooms[0].progress,'처리 중 · 진행 수 집계 전');
 assert.equal(currentWorkSummary(v,w,{replay:true}).basis,'기록 재생 · 선택한 시각');assert.ok(s.raw.every(e=>!('command' in e)&&!('detail' in e)));
 const unbound={...v,counts:{remainingPains:5},bindingState:'unmatched'};assert.equal(currentWorkSummary(unbound,w).rooms[0].progress,'처리 중 · 진행 수 집계 전');
 const matched={...unbound,bindingState:'matched'};assert.equal(currentWorkSummary(matched,w).rooms[0].progress,'저장된 남은 불편 5개');
 const absent={...matched,counts:{}};assert.equal(currentWorkSummary(absent,w).rooms[0].progress,'처리 중 · 진행 수 집계 전');
});
test('guideline load and unbound helpers do not become Skill use in the dock',()=>{
 const v=view([request,event('instructions',{op:'get_work_instructions'})]),w=observerWork(v),s=currentWorkSummary(v,w);assert.deepEqual(s.rooms,[]);assert.equal(s.active,true);assert.equal(w.mainWorking,true);
});
test('motion example produces no CLI events, processing counts or actual actor claims',()=>{
 const w=observerWork(view([])),s=currentWorkSummary({},w,{preview:true,previewIds:['compare']});assert.equal(s.preview,true);assert.equal(s.live,false);assert.deepEqual(s.raw,[]);assert.deepEqual(s.recent,[]);assert.ok(s.rooms[0].progress.includes('업무 처리 수 없음'));assert.equal(s.basis,'실제 CLI 실행 아님');
});
test('each role has a distinct tool pose and movement inside the room above the nameplate',()=>{
 assert.equal(new Set(Object.values(SKILL_ACTIONS).map(a=>a.pose)).size,6);
 for(const [id,d]of Object.entries(SKILL_ACTIONS)){let walked=false,worked=false;for(let t=0;t<d.cycle;t+=.04){const p=illustratedWorkPose(id,t);assert.ok(Math.abs(p.u)<.32);assert.ok(p.foot>=.34&&p.foot<.50);walked||=p.walking;worked||=!p.walking;}assert.ok(walked&&worked);assert.deepEqual(illustratedWorkPose(id,0),illustratedWorkPose(id,d.cycle));}
});
test('idle, pause, reduced motion and selecting a different space cannot advance a character clock',()=>{
 for(const options of [{working:false,dt:.1},{working:true,reducedMotion:true,dt:.1}]){const before=3.6,after=advanceResearcherClock(before,options);assert.equal(after,before);for(const id of Object.keys(SKILL_ACTIONS))assert.deepEqual(illustratedWorkPose(id,before),illustratedWorkPose(id,after));}
});
test('responsive work panels reserve space only when opened or executing',()=>{
 assert.deepEqual(workDockInsets(1200),{left:0,right:0,bottom:0});assert.deepEqual(workDockInsets(1200,{visible:true,listOpen:true}),{left:204,right:298,bottom:0});assert.deepEqual(workDockInsets(390,{visible:true}),{left:0,right:0,bottom:212});assert.equal(workDockInsets(650,{visible:true,height:390}).right,298);
});
