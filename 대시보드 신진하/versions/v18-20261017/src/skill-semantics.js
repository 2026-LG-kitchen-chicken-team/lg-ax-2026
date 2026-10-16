import {SKILL_BY_ID} from './skill-catalog.js';

const INSTRUCTIONS=new Set(['get_work_instructions','load_instructions','read_instructions']);
const ADMIN=new Set(['workflow_status','get_completion_summary','get_request_status','get_status','doctor']);
export const eventOperations = event => event?.kind==='skill_op' ? (event.ops?.length?event.ops:[{skill:event.node,op:event.op}]) : [];
export const instructionOperation = op => INSTRUCTIONS.has(op);
export function instructionSkills(event){
  if(event?.kind==='skill_load')return SKILL_BY_ID[event.node]?[event.node]:[];
  // get_work_instructions can select main or any Skill, regardless of its wrapper path.
  // No returned receipt IDs are present in observer schema v1.
  return [];
}
export function workSkills(event){
  return [...new Set(eventOperations(event).filter(x=>SKILL_BY_ID[x.skill]&&x.op&&!INSTRUCTIONS.has(x.op)&&!ADMIN.has(x.op)).map(x=>x.skill))];
}
export const instructionLookup = event => eventOperations(event).some(x=>INSTRUCTIONS.has(x.op));
export const instructionOnly = event => event?.kind==='skill_load'||instructionLookup(event)&&workSkills(event).length===0;
export const skillWorkEvent = event => event?.kind==='skill_op'&&workSkills(event).length>0;

// Use native agent IDs to distinguish two helpers with the same installed role.
// A request to delegate, with no native ID/start, is a request rather than a running helper.
export function currentAgentInstances(events,spans,{fresh=false,cancelled=false}={}){
  const ids=new Set(events.flatMap(e=>[e.agent_id,e.detail?.launched_agent_id]).filter(Boolean));
  return [...ids].map(id=>{
    const related=events.filter(e=>e.agent_id===id||e.detail?.launched_agent_id===id);
    const lives=spans.filter(s=>s.start.kind==='subagent'&&s.start.agent_id===id);
    const life=lives.at(-1),nativeStart=life&&!life.startUnobserved;
    const roleEvent=related.find(e=>e.agent_id===id&&e.actor!=='main')||related.find(e=>e.kind==='delegate');
    const role=roleEvent?.kind==='delegate'?roleEvent.node:roleEvent?.actor||'unknown_subagent';
    const active=Boolean(fresh&&!cancelled&&nativeStart&&life.status==='open');
    const status=active?'running':life?.status==='failed'?'failed':life?.status==='completed'?'completed':cancelled&&nativeStart?'cancelled':nativeStart?'unknown':'requested';
    const statusLabel={running:'도우미가 일하고 있어요',failed:'도우미 작업 오류',completed:'도우미 작업 종료',cancelled:'요청 취소 · 종료는 미확인',unknown:'지금 상태는 확인 중',requested:'도우미에게 요청 · 시작 미확인'}[status];
    const skillSpans=spans.filter(s=>s.start.agent_id===id&&skillWorkEvent(s.start));
    const activeSkills=active?[...new Set(skillSpans.filter(s=>s.status==='open').flatMap(s=>workSkills(s.start)))]:[];
    return {id,role,active,status,statusLabel,events:related,activeSkills,observedSkills:[...new Set(skillSpans.flatMap(s=>workSkills(s.start)))],nativeStart:Boolean(nativeStart),lastEventAt:related.at(-1)?.ts||null};
  });
}
