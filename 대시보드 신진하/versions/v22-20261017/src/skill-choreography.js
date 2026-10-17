// Presentation-only choreography. A stopped clock produces no motion.
export const SKILL_ACTIONS={
 retrieve:{pose:1,action:'문서를 꺼내 스캔해요',cycle:12,stops:[[-.22,.26],[-.07,.32],[.18,.25]],dwell:[2.8,2.5,2.2]},
 structure:{pose:2,action:'비슷한 불편 카드를 모아요',cycle:12,stops:[[-.18,.28],[.15,.40],[.24,.28]],dwell:[2.1,3.1,2.3]},
 compare:{pose:3,action:'제품과 기능표를 번갈아 살펴요',cycle:14,stops:[[-.29,.34],[.03,.28],[.25,.37]],dwell:[3.1,2,3.1]},
 concept:{pose:4,action:'아이디어 모형을 조립해요',cycle:12,stops:[[-.23,.24],[.04,.31],[.22,.24]],dwell:[2.2,3.1,2.2]},
 validate:{pose:5,action:'원문과 검사표를 확인해요',cycle:13,stops:[[-.22,.28],[.03,.35],[.22,.26]],dwell:[2.6,2.8,2.6]},
 web:{pose:0,action:'검색하고 찾은 자료를 모아요',cycle:12,stops:[[-.24,.28],[.01,.31],[.24,.26]],dwell:[2.8,2.3,2.4]}
};
export function illustratedWorkPose(id,time,{worker=0}={}){
 const def=SKILL_ACTIONS[id]||SKILL_ACTIONS.retrieve;
 const phase=((Math.max(0,time)+worker*def.cycle/3)%def.cycle)/def.cycle;
 // Hold at each workstation, then walk to the next. Different paths and tools belong to each Skill.
 const moving=def.cycle-def.dwell.reduce((a,b)=>a+b,0),walk=moving/def.stops.length;
 let at=phase*def.cycle;
 for(let i=0;i<def.stops.length;i++){
  const a=def.stops[i],b=def.stops[(i+1)%def.stops.length];
  if(at<def.dwell[i])return {u:a[0],foot:Math.max(.34,a[1]),walking:false,dx:0,pose:def.pose,action:def.action,phase,station:i};
  at-=def.dwell[i];
  if(at<walk){const t=at/walk;return {u:a[0]+(b[0]-a[0])*t,foot:Math.max(.34,a[1])+(Math.max(.34,b[1])-Math.max(.34,a[1]))*t,walking:true,dx:b[0]-a[0],pose:def.pose,action:def.action,phase,station:i};}
  at-=walk;
 }
 return {u:def.stops[0][0],foot:Math.max(.34,def.stops[0][1]),walking:false,dx:0,pose:def.pose,action:def.action,phase,station:0};
}
