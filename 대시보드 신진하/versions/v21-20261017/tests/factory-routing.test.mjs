import test from 'node:test';
import assert from 'node:assert/strict';
import {ROOM_ORDER,factoryLayout,ZONE_FLOOR,PLANNER_FLOOR} from '../src/factory-layout.js';
import {connectionRoute,routePosition} from '../src/factory-routing.js';
const outside=(p,z,f)=>Math.abs(p.x-z.x)>=f.halfX*z.scale||Math.abs(p.z-z.z)>=f.halfZ*z.scale;
test('shared aisle routes remain finite and end outside each room for every parallel count and viewport',()=>{
 for(const [width,height] of [[1280,800],[390,844],[844,390]])for(let mask=0;mask<64;mask++){
  const activeIds=ROOM_ORDER.filter((id,i)=>mask&(1<<i));const {zones}=factoryLayout({width,height,roomIds:ROOM_ORDER,activeIds:[...activeIds,'overview']});
  for(const id of ROOM_ORDER){const r=connectionRoute(zones[id],zones.overview);assert.ok(r.firstLength>=0&&r.lastLength>0);assert.ok(outside(r.start,zones.overview,PLANNER_FLOOR));assert.ok(outside(r.finish,zones[id],ZONE_FLOOR));
   for(const part of [r.start,r.bend,r.finish]){assert.ok(Number.isFinite(part.x));assert.ok(Number.isFinite(part.z));}
   assert.deepEqual(routePosition(r,0),r.start);const end=routePosition(r,1);assert.ok(Math.hypot(end.x-r.finish.x,end.z-r.finish.z)<1e-9);
  }
 }
});
test('parcels follow the corner at constant distance instead of jumping diagonally',()=>{
 const {zones}=factoryLayout({roomIds:ROOM_ORDER,activeIds:['retrieve']});const route=connectionRoute(zones.retrieve,zones.overview);let previous=routePosition(route,0);
 for(let i=1;i<=1000;i++){const p=routePosition(route,i/1000);assert.ok(Math.hypot(p.x-previous.x,p.z-previous.z)<(route.firstLength+route.lastLength)/1000+.00001);previous=p;}
 assert.ok(route.firstLength>0&&route.lastLength>0);
 const phone=factoryLayout({width:390,height:844,roomIds:ROOM_ORDER}).zones;assert.equal(connectionRoute(phone.compare,phone.overview).firstLength,0);
});
