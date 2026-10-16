import test from 'node:test';
import assert from 'node:assert/strict';
import {ZONE_IDS,ZONE_FLOOR,PLANNER_FLOOR,factoryLayout,fitFactory,worldToField,fieldToWorld,popScale,patrolPosition,transitionFactory} from '../src/factory-layout.js';
import {advanceResearcherClock,researcherPose,previewActiveNodes} from '../src/researcher-motion.js';
const screens=[[390,844,0],[320,568,0],[844,390,0],[1280,800,0],[1920,1080,0],[1280,800,470],[800,600,330]];
const groups=[[],['retrieve'],['compare'],['structure'],['overview'],['retrieve','structure'],['concept','validate'],['retrieve','structure','compare'],['retrieve','structure','compare','concept'],['overview','retrieve'],['overview','structure','compare'],ZONE_IDS.slice(1),ZONE_IDS];
const allGroups=Array.from({length:1<<ZONE_IDS.length},(_,mask)=>ZONE_IDS.filter((_,i)=>mask&(1<<i)));
const floor=z=>z.id==='overview'?PLANNER_FLOOR:ZONE_FLOOR;
function separated(zones){const list=Object.values(zones).filter(z=>z.visible!==false);for(let a=0;a<list.length;a++)for(let b=a+1;b<list.length;b++){const one=list[a],two=list[b],af=floor(one),bf=floor(two);assert.ok(Math.abs(one.x-two.x)>=af.halfX*one.scale+bf.halfX*two.scale-.001||Math.abs(one.z-two.z)>=af.halfZ*one.scale+bf.halfZ*two.scale-.001,JSON.stringify({a:one.id,b:two.id,one,two}));}}

test('Skill activation changes scale at its existing address for every viewport',()=>{
 for(const [width,height,panelWidth] of screens){
  const initial=factoryLayout({width,height,panelWidth}).zones;
  for(const activeIds of allGroups){const current=factoryLayout({width,height,panelWidth,activeIds}).zones;for(const id of ZONE_IDS){assert.equal(current[id].x,initial[id].x);assert.equal(current[id].z,initial[id].z);}separated(current);}
 }
 const focused=factoryLayout({activeIds:['compare']}).zones;
 assert.ok(focused.compare.scale/focused.retrieve.scale>=2.9);
});

test('each concurrent Skill count gets a distinct size without counting the planner or duplicate reports',()=>{
 const skills=ZONE_IDS.slice(1);
 for(const [width,height,panelWidth] of screens){
  const idle=factoryLayout({width,height,panelWidth}).zones.retrieve.scale;let previous=Infinity;
  for(let count=1;count<=skills.length;count++){
   const activeIds=skills.slice(0,count),layout=factoryLayout({width,height,panelWidth,activeIds});
   assert.equal(layout.activeSkillCount,count);const size=layout.zones.retrieve.scale;
   assert.ok(size<previous,'more parallel Skills share the field with a smaller room size');
   assert.ok(size>idle,'every running room remains enlarged compared with its idle size');
   for(const id of activeIds)assert.equal(layout.zones[id].scale,size);
   const noisy=factoryLayout({width,height,panelWidth,activeIds:[...activeIds,'overview','retrieve','unknown']});
   assert.equal(noisy.activeSkillCount,count);assert.equal(noisy.zones.retrieve.scale,size);
   separated(noisy.zones);previous=size;
  }
 }
});

test('camera fits actual rectangular floors and models with compact margins',()=>{
 for(const [width,height,panelWidth] of screens)for(const activeIds of groups){const layout=factoryLayout({width,height,panelWidth,activeIds}),fit=fitFactory(layout.zones,{width,height,panelWidth});const scale=height/(2*fit.extent);assert.ok((fit.bounds.maxU-fit.bounds.minU)*scale<=width-panelWidth-24+.01);assert.ok((fit.bounds.maxV-fit.bounds.minV)*scale<=height-76-72+.01);}
 const f=fitFactory(factoryLayout({}).zones,{width:1280,height:800});assert.ok((f.bounds.maxU-f.bounds.minU)/f.unit>850,'whole factory should occupy a large part of the desktop');
});

test('normal Skill transitions stay visible and in place, without intersecting room floors',()=>{
 for(const [width,height,panelWidth] of screens)for(const fromIds of allGroups)for(const toIds of allGroups){
  const from=factoryLayout({width,height,panelWidth,activeIds:fromIds}).zones,to=factoryLayout({width,height,panelWidth,activeIds:toIds}).zones;
  for(const age of [0,.08,.16,.24,.32,.5,.9,1.3]){const frame=transitionFactory(from,to,age);separated(frame);for(const id of ZONE_IDS){assert.equal(frame[id].x,from[id].x);assert.equal(frame[id].z,from[id].z);assert.equal(frame[id].visible,true);}}
 }
});

test('viewport reflow can collapse before relocating and reduced motion snaps directly',()=>{
 const from=factoryLayout({width:1280,height:800,activeIds:['retrieve']}).zones,to=factoryLayout({width:390,height:844,activeIds:['retrieve']}).zones;
 assert.equal(transitionFactory(from,to,.05).retrieve.x,from.retrieve.x);
 assert.equal(transitionFactory(from,to,.3).retrieve.x,to.retrieve.x);
 for(const id of ZONE_IDS){const z=transitionFactory(from,to,.01,true)[id];assert.equal(z.x,to[id].x);assert.equal(z.z,to[id].z);assert.equal(z.scale,to[id].scale);}
});

test('three researchers keep their feet inside the raised square and clear the center furniture',()=>{
 for(const planner of [false,true])for(let worker=0;worker<(planner?1:3);worker++){
  const floor=planner?PLANNER_FLOOR:ZONE_FLOOR,start=patrolPosition(0,{planner,worker}),seen=[];
  for(let t=0;t<start.cycle;t+=.04){const p=patrolPosition(t,{planner,worker});assert.ok(Math.abs(p.x)+.15<floor.halfX);assert.ok(Math.abs(p.z)+.15<floor.halfZ);assert.equal(p.y,floor.y);if(!planner)assert.ok(Math.abs(p.x)>1.7||Math.abs(p.z)>1.45,'walking lane must avoid the middle desks and boards');if(seen.length)assert.ok(Math.hypot(p.x-seen.at(-1).x,p.z-seen.at(-1).z)<.05);seen.push(p);}
  assert.ok(seen.some(p=>p.walking));assert.ok(seen.some(p=>!p.walking));const loop=patrolPosition(start.cycle,{planner,worker});assert.ok(Math.hypot(loop.x-start.x,loop.z-start.z)<1e-8);
 }
 const p0=patrolPosition(0,{worker:0}),p1=patrolPosition(0,{worker:1}),p2=patrolPosition(0,{worker:2});assert.ok(Math.hypot(p0.x-p1.x,p0.z-p1.z)>1);assert.ok(Math.hypot(p1.x-p2.x,p1.z-p2.z)>1);
});

test('pause and reduced motion freeze route clocks and selection does not start work',()=>{
 assert.equal(advanceResearcherClock(5,{working:false,dt:.08}),5);assert.equal(advanceResearcherClock(5,{working:true,reducedMotion:true,dt:.08}),5);assert.equal(advanceResearcherClock(5,{working:true,dt:.08}),5.08);assert.equal(advanceResearcherClock(5,{working:true,dt:50}),5.1);
 assert.equal(researcherPose('compare',{activeIds:['structure'],selected:'compare'}).working,false);assert.equal(researcherPose('structure',{activeIds:['structure'],selected:'compare'}).working,true);
});

test('camera basis round trips and the spring enlarges a room with an overshoot',()=>{
 for(const [u,v] of [[0,0],[-15,10],[12,-9]]){const p=fieldToWorld(u,v),back=worldToField(p.x,0,p.z);assert.ok(Math.abs(back.u-u)<1e-10);assert.ok(Math.abs(back.v-v)<1e-10);}
 assert.equal(popScale(1,2,0),1);assert.ok(popScale(1,2,.3)>2);assert.equal(popScale(1,2,2),2);assert.equal(popScale(1,2,.1,true),2);
});

test('explicit concurrent motion fixtures remain separate from execution state',()=>{
 assert.deepEqual(previewActiveNodes(0,'parallel2'),['structure','compare']);assert.deepEqual(previewActiveNodes(24,'parallel2'),['structure','compare']);assert.equal(previewActiveNodes(0,'parallel3').length,3);assert.equal(previewActiveNodes(0,'parallel4').length,4);assert.deepEqual(previewActiveNodes(0,'all'),ZONE_IDS.slice(1));
});
