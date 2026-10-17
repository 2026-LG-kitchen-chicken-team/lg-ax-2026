import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {factoryLayout,fitFactory,ROOM_ORDER,worldToField} from '../src/factory-layout.js';
import {composeWorkshopLayout} from '../src/workshop-composition.js';

test('approved composition preserves every real active state and size, and room addresses stay fixed',()=>{
 for(const viewport of [{width:1440,height:900},{width:390,height:844},{width:1012,height:633,panelWidth:420}]){
  const base=composeWorkshopLayout(factoryLayout({...viewport,roomIds:ROOM_ORDER}));
  for(let mask=0;mask<128;mask++){
   const activeIds=['overview',...ROOM_ORDER].filter((_,i)=>mask&(1<<i));
   const input=factoryLayout({...viewport,roomIds:ROOM_ORDER,activeIds}),saved=JSON.stringify(input),result=composeWorkshopLayout(input);
   assert.equal(JSON.stringify(input),saved,'composition must not mutate execution-derived layout');
   assert.deepEqual(result.active,input.active);assert.equal(result.activeSkillCount,input.activeSkillCount);
   for(const [id,z] of Object.entries(result.zones)){
    assert.equal(z.scale,input.zones[id].scale);assert.equal(z.active,input.zones[id].active);
    assert.equal(z.x,base.zones[id].x);assert.equal(z.z,base.zones[id].z);
   }
  }
 }
});
test('artwork camera contains complete original workroom viewports for one through six concurrent Skills',()=>{
 for(const viewport of [{width:1440,height:900},{width:390,height:844},{width:1012,height:633,panelWidth:420}])for(let mask=0;mask<64;mask++){
  const activeIds=ROOM_ORDER.filter((_,i)=>mask&(1<<i));
  const layout=composeWorkshopLayout(factoryLayout({...viewport,roomIds:ROOM_ORDER,activeIds}));
  const fit=fitFactory(layout.zones,{...viewport,artwork:true});
  for(const id of ROOM_ORDER){const z=layout.zones[id],p=worldToField(z.x,0,z.z);
   assert.ok(p.u-4.6*z.scale>=fit.bounds.minU-.001);assert.ok(p.u+4.6*z.scale<=fit.bounds.maxU+.001);
   assert.ok(p.v-6.45*z.scale>=fit.bounds.minV-.001);assert.ok(p.v+2.15*z.scale<=fit.bounds.maxV+.001);
  }
 }
});
test('approved researcher image remains byte-for-byte identical to the user attachment',()=>{
 const original=readFileSync(new URL('../public/workshops/approved-researchers-original-v1.png',import.meta.url));
 assert.equal(createHash('sha256').update(original).digest('hex'),'2afa9bbf0965b93a05e8b3f70e5afc4f538eeb15ad21b49ea040c6412daac1af');
});
