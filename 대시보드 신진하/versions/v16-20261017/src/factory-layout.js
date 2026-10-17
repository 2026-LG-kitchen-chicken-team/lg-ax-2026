export const ZONE_IDS=['overview','retrieve','structure','compare','concept','validate'];
export const ZONE_FLOOR={halfX:2.8,halfZ:2.4,y:.49};
export const PLANNER_FLOOR={halfX:1.5,halfZ:1.35,y:.49};
// A Skill keeps its own address. Activating it changes size, never its slot.
const BASE={overview:[0,1.8],retrieve:[-7.8,-.2],structure:[-4.4,-7.7],compare:[5.6,-7],concept:[7.4,3],validate:[-2.5,8]};
const horizontal=Math.hypot(13,18),length=Math.hypot(13,17,18);
export const VIEW={rx:18/horizontal,rz:-13/horizontal,dx:17/length*13/horizontal,dz:17/length*18/horizontal,uy:horizontal/length};
export function worldToField(x,y,z){return {u:VIEW.rx*x+VIEW.rz*z,v:VIEW.dx*x+VIEW.dz*z-VIEW.uy*y};}
export function fieldToWorld(u,v){const d=VIEW.rx*VIEW.dz-VIEW.rz*VIEW.dx;return {x:(u*VIEW.dz-VIEW.rz*v)/d,z:(VIEW.rx*v-VIEW.dx*u)/d};}
// Share the available field between concurrently running Skills. The planner
// connects their work and is not counted as an extra Skill.
const ROOM_SCALES={wide:[1.05,2,1.48,1.36,1.25,1.16],compact:[.96,1.25,1.18,1.12,1.08,1.04]};
export function factoryLayout({width=1280,height=800,panelWidth=0,activeIds=[]}={}){
 const available=Math.max(240,width-Math.max(0,panelWidth)),active=ZONE_IDS.filter(id=>activeIds.includes(id)),compact=available<650,short=compact&&height<540&&available/height>1.22;
 const activeSkillCount=active.filter(id=>id!=='overview').length,roomScale=ROOM_SCALES[compact?'compact':'wide'][activeSkillCount];
 const idleScale=compact?(activeSkillCount>1?.60:activeSkillCount?.72:.96):(activeSkillCount>1?.52:activeSkillCount?.66:1.05);
 const plannerScale=active.includes('overview')?(activeSkillCount?.72:compact?1.22:1.65):(compact?.85:.82);
 const zones=Object.fromEntries(ZONE_IDS.map(id=>[id,{id,x:BASE[id][0],z:BASE[id][1],active:active.includes(id),scale:id==='overview'?plannerScale:active.includes(id)?roomScale:idleScale}]));
 if(compact){
   const order=short?['retrieve','structure','compare','validate','overview','concept']:['retrieve','structure','overview','compare','validate','concept'],columns=short?3:2,rows=Math.ceil(order.length/columns);
   order.forEach((id,i)=>Object.assign(zones[id],fieldToWorld((i%columns-(columns-1)/2)*9.8,(Math.floor(i/columns)-(rows-1)/2)*7.2)));
 }
 return {zones,compact,short,active,activeSkillCount};
}
export function fitFactory(zones,{width,height,panelWidth=0,top=76,bottom=72}={}){
 const availableWidth=Math.max(180,width-panelWidth-24),availableHeight=Math.max(140,height-top-bottom);
 let minU=Infinity,maxU=-Infinity,minV=Infinity,maxV=-Infinity;
 for(const zone of Object.values(zones)){
   const f=zone.id==='overview'?PLANNER_FLOOR:ZONE_FLOOR;
   const points=[];
   // Fit occupied geometry rather than an empty tall box over the whole floor.
   for(const x of [-f.halfX,f.halfX])for(const z of [-f.halfZ,f.halfZ])points.push([x,0,z]);
   const small=zone.id==='overview';
   for(const x of small?[-.8,.8]:[-1.6,1.6])points.push([x,small?2.2:2.85,small?0:-1.1]);
   points.push([0,small?3.4:4.1,0]);
   for(const x of small?[-1.03,1.03]:[-2.1,2.1])for(const z of small?[-.97,.97]:[-1.75,1.75])points.push([x,small?2.65:2.7,z]);
   for(const [x,y,z] of points){
     const p=worldToField(zone.x+x*zone.scale,y*zone.scale,zone.z+z*zone.scale);
     minU=Math.min(minU,p.u);maxU=Math.max(maxU,p.u);minV=Math.min(minV,p.v);maxV=Math.max(maxV,p.v);
   }
 }
 const unit=Math.max((maxU-minU+.45)/availableWidth,(maxV-minV+.55)/availableHeight),centerU=(minU+maxU)/2,centerV=(minV+maxV)/2-(top+(height-top-bottom)/2-height/2)*unit;
 return {extent:Math.max(4,unit*height/2),...fieldToWorld(centerU,centerV+VIEW.uy*.35),bounds:{minU,maxU,minV,maxV},unit};
}
export function popScale(from,to,age,reduced=false){
 if(reduced||age>=1.2)return to;
 const t=Math.max(0,age),response=1-Math.exp(-7*t)*(Math.cos(12*t)+7/12*Math.sin(12*t));
 return from+(to-from)*response;
}
export function patrolPosition(time,{planner=false,worker=0}={}){
 const x=planner?1.03:2.10,z=planner?.97:1.75;
 const points=[[0,z],[x,z],[x,-z],[-x,-z],[-x,z],[0,z]],lengths=points.slice(1).map((p,i)=>Math.hypot(p[0]-points[i][0],p[1]-points[i][1]));
 const distance=lengths.reduce((a,b)=>a+b,0),walking=distance/.9,cycle=walking+3.8,phase=((Math.max(0,time)+worker*cycle/3)%cycle+cycle)%cycle;
 if(phase>=walking)return {x:0,z,y:.49,walking:false,dx:0,dz:0,cycle};
 let at=phase*.9;
 for(let i=0;i<lengths.length;i++){
  if(at<=lengths[i]){const t=at/lengths[i],a=points[i],b=points[i+1];return {x:a[0]+(b[0]-a[0])*t,z:a[1]+(b[1]-a[1])*t,y:.49,walking:true,dx:(b[0]-a[0])/lengths[i],dz:(b[1]-a[1])/lengths[i],cycle};}
  at-=lengths[i];
 }
 return {x:0,z,y:.49,walking:false,dx:0,dz:0,cycle};
}
export function transitionFactory(from,to,age,reduced=false){
 const relocate=Object.entries(to).some(([id,z])=>from[id]&&(Math.abs(from[id].x-z.x)+Math.abs(from[id].z-z.z)>.01)),t=Math.max(0,age),collapse=.15;
 return Object.fromEntries(Object.entries(to).map(([id,dest])=>{
  const start=from[id]||dest;
  if(reduced)return [id,{...dest,visible:true}];
  // Only a viewport reflow changes addresses. Normal Skill changes scale in place.
  if(relocate&&t<collapse){const p=t/collapse,e=p*p*(3-2*p),scale=start.scale*(1-e);return [id,{...start,scale,visible:scale>.06}];}
  const fromScale=relocate?0:start.scale,scale=Math.max(.01,Math.min(Math.max(fromScale,dest.scale)*1.045,popScale(fromScale,dest.scale,t-(relocate?collapse:0))));
  return [id,{...dest,scale,visible:scale>.06}];
 }));
}
