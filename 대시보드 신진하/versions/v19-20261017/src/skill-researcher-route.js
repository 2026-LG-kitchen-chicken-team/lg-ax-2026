const DOCKS={retrieve:[1.82,.54],structure:[1.82,-.72],compare:[-1.82,-.25],concept:[1.82,.44],validate:[-1.82,.44],web:[1.82,.50]};
// Walk around the perimeter, then stop beside the tool for that Skill.
// These are visual footsteps, not extra subagent instances or execution events.
export function skillResearcherRoute(id,time,{worker=0}={}){
 const dock=DOCKS[id]||[1.82,.5],side=Math.sign(dock[0]),points=[dock,[side*2.10,dock[1]],[side*2.10,-1.75],[-side*2.10,-1.75],[-side*2.10,1.75],[side*2.10,1.75],[side*2.10,dock[1]],dock];
 const lengths=points.slice(1).map((p,i)=>Math.hypot(p[0]-points[i][0],p[1]-points[i][1])),distance=lengths.reduce((a,b)=>a+b,0),dwell=6.5,cycle=dwell+distance/.85,phase=((Math.max(0,time)+worker*cycle/3)%cycle+cycle)%cycle;
 if(phase<dwell)return {x:dock[0],y:.49,z:dock[1],walking:false,dx:-side,dz:0,cycle};
 let travel=(phase-dwell)*.85;
 for(let i=0;i<lengths.length;i++){if(travel<=lengths[i]){const p=travel/lengths[i],a=points[i],b=points[i+1];return {x:a[0]+(b[0]-a[0])*p,y:.49,z:a[1]+(b[1]-a[1])*p,walking:true,dx:(b[0]-a[0])/lengths[i],dz:(b[1]-a[1])/lengths[i],cycle};}travel-=lengths[i];}
 return {x:dock[0],y:.49,z:dock[1],walking:false,dx:-side,dz:0,cycle};
}
