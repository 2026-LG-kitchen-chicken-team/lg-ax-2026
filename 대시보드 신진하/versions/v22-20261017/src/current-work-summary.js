import {workSkills} from './skill-semantics.js';
const finite=n=>Number.isSafeInteger(n)&&n>=0;
export function currentWorkSummary(view,work,{preview=false,replay=false,playing=true,previewIds=[]}={}){
 if(preview)return {preview:true,live:false,active:playing&&previewIds.length>0,title:playing?'동작 예시를 보고 있어요':'동작 예시 · 일시정지',basis:'실제 CLI 실행 아님',rooms:previewIds.map(id=>({...work.rooms[id],actor:'메인 AI의 동작 예시',progress:'모션 예시 · 업무 처리 수 없음'})),recent:[],raw:[],next:'시연 방식을 골라 한 구역 또는 병렬 동작을 살펴보세요.'};
 const live=view.connectionStatus==='connected',ids=work.activeNodes;
 const raw=(view.currentEvents||view.recentEvents||[]).slice(-30);
 const rooms=ids.map(id=>{const r=work.rooms[id];let progress=r.confirmed?'처리 중 · 진행 수 집계 전':r.reporting?'진행 보고 수신 · 처리 수 미제공':'도우미 동작 관측 · 사용 Skill 확인 중';
  // Result counts are only attributed when the existing observer verified the business binding.
  if(view.bindingState==='matched'){
   const c=view.counts||{};
   if(id==='structure'&&finite(c.pains))progress='저장된 불편 '+c.pains+'개';
   if(id==='compare'&&finite(c.remainingPains))progress='저장된 남은 불편 '+c.remainingPains+'개';
   if(id==='concept'&&finite(c.concepts))progress='저장된 콘셉트 '+c.concepts+'개';
  }
  return {...r,actor:r.actors?.map(a=>a.label).join(' · ')||r.helpers?.map(a=>a.label).join(' · ')||(r.reporting?'메인 기획 AI':'담당 AI 연결 확인 중'),progress};
 });
 const recent=(view.recentEvents||[]).slice(0,3).map(e=>({id:e.id,text:e.message||[e.tool,e.op,e.phase].filter(Boolean).join(' · '),time:e.time||e.ts||e.at}));
 return {preview:false,live,active:live&&Boolean(ids.length||work.mainWorking),title:work.line,basis:replay?'기록 재생 · 선택한 시각':live?'하네스 관측 기록':view.connectionStatus==='stale'?'마지막 수신 기록 · 연결 지연':'실제 연결 대기',rooms,recent,raw:raw.map(e=>({id:e.id,time:e.time||e.ts||e.at,actor:e.actor,tool:e.tool,operation:e.op,phase:e.phase,basis:e.basis,skills:workSkills(e)})),next:view.nextAction||(!live?'설치된 하네스의 읽기 연결을 설정하세요.':'CLI의 다음 작업 기록을 기다려요.')};
}
export function workDockInsets(width,{visible=false,listOpen=false,height=800}={}){
 const compact=width<=700&&!(width>=600&&height<520);
 return {right:!compact&&visible?298:0,left:!compact&&listOpen?204:0,bottom:compact&&(visible||listOpen)?212:0};
}
