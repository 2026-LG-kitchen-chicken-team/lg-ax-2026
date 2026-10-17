import {fieldToWorld,worldToField,ZONE_FLOOR,PLANNER_FLOOR} from './factory-layout.js';
const distance=(a,b)=>Math.hypot(b.x-a.x,b.z-a.z);
const edge=(zone,direction,floor)=>Math.min(Math.abs(direction.x)>.001?floor.halfX*zone.scale/Math.abs(direction.x):Infinity,Math.abs(direction.z)>.001?floor.halfZ*zone.scale/Math.abs(direction.z):Infinity);
// Rooms connect through one central aisle, instead of six crossing bridges.
// This is display geometry only; it neither creates nor advances a job.
export function connectionRoute(room,planner){
 const field=worldToField(room.x,0,room.z),middle=fieldToWorld(field.u,0);
 const branchLength=distance(middle,room);
 if(branchLength<.01){
  const length=distance(planner,room),direction={x:(room.x-planner.x)/length,z:(room.z-planner.z)/length};
  const start={x:planner.x+direction.x*(edge(planner,direction,PLANNER_FLOOR)+.12),z:planner.z+direction.z*(edge(planner,direction,PLANNER_FLOOR)+.12)};
  const finish={x:room.x-direction.x*(edge(room,direction,ZONE_FLOOR)+.12),z:room.z-direction.z*(edge(room,direction,ZONE_FLOOR)+.12)};
  return {start,bend:{...start},finish,firstLength:0,lastLength:distance(start,finish)};
 }
 const toward={x:(room.x-middle.x)/branchLength,z:(room.z-middle.z)/branchLength};
 const finish={x:room.x-toward.x*(edge(room,toward,ZONE_FLOOR)+.12),z:room.z-toward.z*(edge(room,toward,ZONE_FLOOR)+.12)};
 const horizontal=distance(planner,middle);
 let start,bend;
 if(horizontal<.01){start={x:planner.x+toward.x*(edge(planner,toward,PLANNER_FLOOR)+.12),z:planner.z+toward.z*(edge(planner,toward,PLANNER_FLOOR)+.12)};bend={...start};}
 else{const side={x:(middle.x-planner.x)/horizontal,z:(middle.z-planner.z)/horizontal};start={x:planner.x+side.x*(edge(planner,side,PLANNER_FLOOR)+.12),z:planner.z+side.z*(edge(planner,side,PLANNER_FLOOR)+.12)};bend=middle;}
 return {start,bend,finish,firstLength:distance(start,bend),lastLength:distance(bend,finish)};
}
export function routePosition(route,fraction){
 const length=route.firstLength+route.lastLength,at=Math.max(0,Math.min(1,fraction))*length;
 const first=at<route.firstLength,a=first?route.start:route.bend,b=first?route.bend:route.finish;
 const size=first?route.firstLength:route.lastLength,t=size?(at-(first?0:route.firstLength))/size:0;
 return {x:a.x+(b.x-a.x)*t,z:a.z+(b.z-a.z)*t};
}
