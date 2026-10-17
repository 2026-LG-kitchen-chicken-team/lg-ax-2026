// Fixed labels only. Public CLI commentary reports a task; it is not a Skill call.
const skills=new Set(['evidence-retrieval','web-evidence-collection','needs-structuring','feature-comparison','concept-writing','review-and-revise']);
const stages=new Set(['retrieve','structure','compare','concept','validate']);
const identifier=x=>typeof x==='string'&&/^[A-Za-z0-9_.:-]{1,200}$/.test(x);
const stamp=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}T/.test(x)&&Number.isFinite(Date.parse(x));
const number=x=>Number.isSafeInteger(x)&&x>=0&&x<=1e6;
export const ACTIVITY_LABELS=Object.freeze({
 main_work:['메인 기획자가 요청을 처리하고 있습니다','메인 작업 기록'],
 check_setup:['하네스 지침과 실행 준비를 확인하고 있습니다','하네스 설치·실행 환경 검사'],
 check_storage:['로컬 파일과 SQLite 저장·조회를 확인하고 있습니다','파일·SQLite 저장·조회 검사'],
 read_skill_instructions:['Skill 지침을 조회하고 있습니다','Skill 지침 조회 명령'],
 research_sources:['자료와 웹 근거를 조사하고 있습니다','자료·웹 근거 조사'],
 structure_needs:['고객 상황과 불편을 정리하고 있습니다','고객 니즈 구조화'],
 compare_features:['고객 불편을 기존 제품 기능과 대조하고 있습니다','기존 기능·잔여 불편 대조'],
 write_concepts:['남은 불편을 해결할 콘셉트를 작성하고 있습니다','콘셉트·요구사항 작성'],
 review_results:['콘셉트와 연결 근거를 검토하고 있습니다','근거·결과 검토'],
 local_command:['로컬 명령을 처리하고 있습니다','로컬 명령'],
 web_lookup:['웹 자료를 확인하고 있습니다','웹 자료 조회'],
 readiness_finished:['실행 준비 확인','준비 확인 응답'],
 turn_finished:['메인 요청 처리','메인 최종 응답'],
});
export function normalizeActivity(raw){
 if(raw==null)return null;
 try{
  if(raw.kind!=='codex_native_activity'||!identifier(raw.session_id)||!identifier(raw.prompt_id)||!['working','finished','cancelled'].includes(raw.state)||!['general','readiness','planning'].includes(raw.intent)||!ACTIVITY_LABELS[raw.task_code]||!stamp(raw.last_event_at)||raw.reported_stage!=null&&!stages.has(raw.reported_stage)||!number(raw.command_count)||!number(raw.web_count))return null;
  const checks={};for(const key of ['installation','file','sqlite']){if(raw.checks?.[key]!=null){if(typeof raw.checks[key]!=='boolean')return null;checks[key]=raw.checks[key];}}
  if(!Array.isArray(raw.skill_reads)||raw.skill_reads.length>6||!Array.isArray(raw.installed_skills)||raw.installed_skills.length>6||!Array.isArray(raw.actions)||raw.actions.length>12)return null;
  const reads=raw.skill_reads.map(r=>{if(!skills.has(r.id)||!stamp(r.time)||r.basis!=='read_command_output')throw Error();return {id:r.id,time:r.time,basis:r.basis};});
  if(raw.installed_skills.some(x=>!skills.has(x)))return null;
  const actions=raw.actions.map(a=>{if(!identifier(a.id)||!stamp(a.time)||!ACTIVITY_LABELS[a.code]||!['reported','completed','failed','finished','cancelled'].includes(a.status)||a.stage!=null&&!stages.has(a.stage))throw Error();return {id:a.id,time:a.time,code:a.code,status:a.status,stage:a.stage||null};});
  return {kind:raw.kind,session_id:raw.session_id,prompt_id:raw.prompt_id,state:raw.state,intent:raw.intent,task_code:raw.task_code,reported_stage:raw.reported_stage||null,last_event_at:raw.last_event_at,checks,installed_skills:[...new Set(raw.installed_skills)],skill_reads:reads,command_count:raw.command_count,web_count:raw.web_count,actions};
 }catch{return null;}
}
export function activityPresentation(raw,session,prompt,connected,now){
 if(!raw||raw.session_id!==session||raw.prompt_id!==prompt)return null;
 const age=now-Date.parse(raw.last_event_at),fresh=connected&&age>=-5000&&age<120000;
 const working=raw.state==='working'&&fresh;
 const ready=raw.intent==='readiness'&&raw.state==='finished'&&['installation','file','sqlite'].every(k=>raw.checks[k]===true);
 const line=ACTIVITY_LABELS[raw.task_code][0];
 const reported=raw.reported_stage&&working;
 let text=working?line:raw.state==='working'?`마지막 작업: ${ACTIVITY_LABELS[raw.task_code][1]} · 후속 상태 확인 필요`:raw.state==='cancelled'?'CLI 요청이 취소됐습니다':ready?'실행 준비 확인 완료 · 상품기획 요청 대기':raw.intent==='readiness'?'준비 확인 응답 완료 · 검사 결과 확인':'CLI 요청 응답 완료 · 작업 결과 확인';
 const actions=raw.actions.map(a=>({...a,ts:a.time,actor:'main',basis:a.status==='reported'?'cli_report':'command_result',message:`${ACTIVITY_LABELS[a.code][1]} · ${{reported:'CLI 진행 보고',completed:'명령 완료',failed:'명령 실패',finished:'응답 완료',cancelled:'취소'}[a.status]}`}));
 return {...raw,working,ready,reported:!!reported,text,actions,next:working?'현재 CLI 요청을 처리하고 있습니다. 선택한 공간과 실행 중인 작업은 구분됩니다.':raw.state==='working'?'마지막 기록 이후의 CLI 상태를 확인하세요. 종료 결과를 아직 받지 못했습니다.':raw.state==='cancelled'?'CLI에서 재개할 작업을 선택하거나 새 요청을 입력하세요.':ready?'CLI에 제품군과 원하는 상품기획 요청을 입력하세요.':'CLI의 최종 응답과 검사 결과를 확인하세요.'};
}
