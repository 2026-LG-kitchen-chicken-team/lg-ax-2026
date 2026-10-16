import {PRODUCT_SKILLS,SKILL_BY_ID,SKILL_BY_ROOM,ROLE_BY_ID,actorLabel} from './skill-catalog.js';
import {skillWorkEvent,workSkills,eventOperations} from './skill-semantics.js';

const MAIN={id:'main',kind:'main',label:'메인 기획 AI'};
const ACTIONS={retrieve_product_facts:'제품 설명서에서 기존 기능을 찾고 있어요.',retrieve_reviews:'모아 둔 고객 후기를 읽고 있어요.',select_evidence:'이번 질문에 필요한 자료를 고르고 있어요.',capture_source:'인터넷에서 확인한 자료를 모으고 있어요.',collect_source:'인터넷 자료를 가져오고 있어요.',import_sources:'찾은 자료를 저장소에 정리하고 있어요.',resolve_request_bundle:'이번 질문에 사용할 근거 자료를 한데 모으고 있어요.',match_product_scope:'자료가 같은 제품 모델의 것인지 확인하고 있어요.',prepare_review_packet:'아이디어와 근거를 검토할 수 있도록 묶고 있어요.',review_product_result:'아이디어와 근거를 다시 살펴보고 있어요.',validate_result_contract:'결과에 필요한 항목이 빠졌는지 검사하고 있어요.',save_reviewed_result:'검토한 기획 결과를 저장하고 있어요.',save_and_export:'기획 결과를 저장하고 꺼내 볼 자료를 만들고 있어요.'};
export function observerWork(view){
  const connected=view.connectionStatus==='connected',current=view.currentEvents||[];
  const activeSkills=connected?(view.activeSkills||[]):[],agents=view.agents||[];
  const workingAgents=connected?agents.filter(a=>a.active):[];
  const directSpans=(view.spans||[]).filter(s=>s.status==='open'&&current.some(e=>e.id===s.start.id)&&skillWorkEvent(s.start));
  const rooms=Object.fromEntries(PRODUCT_SKILLS.map(def=>{
    const node=view.nodes?.[def.node],skill=view.skills?.find(s=>s.id===def.id),confirmed=activeSkills.includes(def.id);
    const reporting=connected&&!confirmed&&Boolean(node?.active)&&view.activity?.reported_stage===def.node;
    const related=directSpans.filter(s=>workSkills(s.start).includes(def.id));
    const actors=[];
    if(confirmed&&related.some(s=>s.start.actor==='main'&&!s.start.agent_id))actors.push(MAIN);
    for(const agent of workingAgents)if(agent.activeSkills.includes(def.id))actors.push({id:agent.id,kind:'helper',label:actorLabel(agent.role),role:agent.role});
    // Native SubagentStart proves the helper is working, but not which Skill it uses.
    const helpersHere=workingAgents.filter(a=>!a.activeSkills.length&&ROLE_BY_ID[a.role]?.home===def.node);
    const helpers=helpersHere.map(a=>({id:a.id,kind:'helper',label:actorLabel(a.role),role:a.role,unmapped:true}));
    const observedHelper=helpers.length>0;
    const status=confirmed?'running':reporting?'reported':observedHelper?'helper':skill?.status==='loaded'?'loaded':node?.status||'idle';
    const statusLabel=confirmed?'SKILL 사용 중':reporting?'진행 보고':observedHelper?'도우미 작업':status==='completed'?'기록 완료':status==='failed'?'오류':status==='loaded'?'지침 확인':status==='reading'?'지침 확인 중':status==='instruction_error'?'지침 조회 실패':status==='analysis'?'분석 구간':'대기';
    const task=confirmed?def.verb:reporting?'CLI가 이 작업을 보고했어요':observedHelper?'도우미가 자료를 확인해요':status==='loaded'?'설명서 조회 완료 · 작업 전':status==='reading'?'설명서를 가져오는 중이에요':status==='instruction_error'?'설명서를 가져오지 못했어요':def.verb;
    const op=eventOperations(related.at(-1)?.start).findLast(x=>x.skill===def.id)?.op;
    const detailLine=confirmed?ACTIONS[op]||def.description:reporting?def.verb+' · CLI가 알려준 진행 소식이에요.':observedHelper?'도우미가 일하기 시작했어요. 사용하는 Skill은 아직 확인 중이에요.':status==='completed'?'이 구역의 작업 기록이 끝났어요. 아래에서 기록과 결과를 확인하세요.':status==='reading'?'Skill 설명서를 가져오고 있어요. 아직 실제 작업을 시작한 것은 아니에요.':status==='loaded'?'Skill 설명서를 확인한 기록이에요. 작업 명령은 아직 확인되지 않았어요.':status==='instruction_error'?'설명서를 가져오지 못했어요. 조회 기록의 오류를 확인하세요.':status==='failed'?'이 구역의 작업 명령에서 오류가 났어요. 아래 기록을 확인하세요.':status==='analysis'?'메인 AI가 분석하는 구간이에요. 이 Skill을 쓰는 순간인지는 따로 기록되지 않았어요.':'이 구역은 지금 사용 중이라는 기록이 없어요.';
    const roleText=actors.length?actors.map(a=>a.kind==='helper'?'도우미 · '+a.label:'담당 · 메인 AI').join(' + '):reporting?'담당 · 메인 AI':observedHelper?'도우미 · '+helpers.map(a=>a.label).join(' + '):confirmed?'담당 AI · 확인 중':null;
    return [def.node,{...def,status,statusLabel,task,detailLine,confirmed,reporting,actors,helpers,helperActive:observedHelper,roleText,helperRole:actors.some(a=>a.kind==='helper')||observedHelper,caption:task,workerCount:confirmed?Math.max(1,actors.length):reporting?1:observedHelper?helpers.length:1,animate:confirmed||reporting||observedHelper}];
  }));
  const roomIds=PRODUCT_SKILLS.map(s=>s.node),activeNodes=roomIds.filter(id=>rooms[id].animate);
  const mainWorking=Boolean(connected&&view.mainActive);
  const first=PRODUCT_SKILLS.find(s=>activeSkills.includes(s.id));
  let line=view.header?.text||'하네스 연결을 기다려요';
  if(!connected)line=view.connectionStatus==='stale'?'작업 소식이 늦어지고 있어요 · 연결을 확인하세요':view.connectionStatus==='error'?'작업 소식을 읽지 못했어요 · 연결을 확인하세요':'하네스 연결 대기 · CLI에서 하는 일을 연결해 보세요';
  else if(first)line='SKILL 사용 중 · '+first.verb+(activeSkills.length>1?' 외 '+(activeSkills.length-1)+'개':'');
  else if(workingAgents.length)line='도우미 AI '+workingAgents.length+'명이 일해요 · 사용 Skill은 기록을 확인 중';
  else if(mainWorking&&view.instructionQuery?.status==='reading')line='작업 설명서를 가져오고 있어요 · 사용 Skill 확인 중';
  else if(mainWorking&&view.activity?.reported_stage)line='메인 AI · '+(SKILL_BY_ROOM[view.activity.reported_stage]?.verb||'작업을 진행해요')+' (CLI 진행 보고)';
  else if(mainWorking)line='메인 AI가 작업 중이에요 · 어떤 Skill인지는 확인 중';
  else if(view.activity?.ready)line='준비가 끝났어요 · CLI에 상품기획을 부탁해 보세요';
  else if(view.header?.state==='cancelled')line='이번 요청을 취소했어요 · 마지막 기록을 볼 수 있어요';
  else if(view.header?.state==='waiting')line='연결됐어요 · CLI에 입력할 질문을 기다려요';
  else if(view.header?.state==='recorded')line='최근 작업 기록을 보고 있어요 · 현재 사용 중인 Skill 없음';
  return {rooms,roomIds,activeNodes,skillActiveNodes:roomIds.filter(id=>rooms[id].confirmed),mainWorking,workingAgents,line};
}
