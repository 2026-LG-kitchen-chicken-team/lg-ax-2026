import test from 'node:test';
import assert from 'node:assert/strict';
import {ROOM_ORDER,factoryLayout,worldToField,ZONE_FLOOR} from '../src/factory-layout.js';
import {researcherPresence,SEATED_DOCKS} from '../src/researcher-presence.js';

test('numbered rooms read left to right on desktop and phone, with main AI in the aisle',()=>{
 for(const [width,height,columns] of [[1440,900,3],[754,668,3],[390,844,2],[320,568,2],[844,390,3]]){
  for(const activeIds of [[],['compare'],ROOM_ORDER]){
   const layout=factoryLayout({width,height,roomIds:ROOM_ORDER,activeIds});assert.equal(layout.columns,columns);
   const projected=ROOM_ORDER.map(id=>worldToField(layout.zones[id].x,0,layout.zones[id].z));
   projected.forEach((p,i)=>{if(i%columns)assert.ok(p.u>projected[i-1].u);if(i>=columns)assert.ok(p.v>projected[i-columns].v);});
   const main=worldToField(layout.zones.overview.x,0,layout.zones.overview.z);assert.equal(main.u,0);assert.equal(main.v,0);
  }
 }
});
test('idle rooms keep one seated decoration, regardless of execution assignment count',()=>{
 for(const workerCount of [0,1,3,4])for(let worker=0;worker<4;worker++){
  const p=researcherPresence({worker,workerCount});assert.equal(p.visible,worker===0);assert.equal(p.mode,'seated');assert.equal(p.animate,false);assert.equal(p.showWorkSeat,false);
 }
 for(const [x,z] of Object.values(SEATED_DOCKS)){assert.ok(Math.abs(x)+.5<ZONE_FLOOR.halfX);assert.ok(Math.abs(z)+.5<ZONE_FLOOR.halfZ);}
});
test('working actors retain their count and pausing freezes their existing work pose',()=>{
 for(let worker=0;worker<4;worker++){
  const active=researcherPresence({working:true,worker,workerCount:2});assert.equal(active.visible,worker<2);assert.equal(active.animate,true);
  const paused=researcherPresence({paused:true,hasWorkPose:true,worker,workerCount:2});assert.equal(paused.mode,'frozen');assert.equal(paused.animate,false);assert.equal(paused.visible,worker<2);
 }
 assert.equal(researcherPresence({paused:true}).mode,'seated');
 assert.equal(researcherPresence({working:true,paused:true}).mode,'work');
});
