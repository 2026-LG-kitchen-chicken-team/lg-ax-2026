import {NODE_DEFS,runStage,getClarification,normalizeReviews,normalizeModels} from './engine.js';
import {SAMPLE_REQUEST,SAMPLE_REVIEWS,SAMPLE_MODELS} from './sample-data.js';
export const KEY='kitchen-ax-factory-v1';
export const LABELS={idle:'대기',running:'실행 중',paused:'일시정지',awaiting:'확인 필요',stopped:'중지됨',completed:'완료',failed:'실패',review:'검토 필요'};
const clone=x=>JSON.parse(JSON.stringify(x));
const now=()=>new Date().toISOString();
const steps=()=>Object.fromEntries(NODE_DEFS.map(n=>[n.id,{status:'idle',task:n.description,processed:0,total:null}]));
const initial=()=>({version:1,runId:null,runCount:0,status:'idle',active:null,request:SAMPLE_REQUEST,brief:{product:'냉장고',customer:'1~2인 가구',scope:'수납 · 정리 · 청소',excluded:''},reviews:clone(SAMPLE_REVIEWS),models:clone(SAMPLE_MODELS),results:{},steps:steps(),logs:[],history:[],revisions:[],decisions:{},question:null,backend:'',mode:'browser',storageWarning:'',restored:false});
export class Planner {
 constructor(){this.listeners=new Set();this.epoch=0;this.wake=[];this.questionResolve=null;this.state=initial();try{const saved=JSON.parse(localStorage.getItem(KEY));if(saved?.version===1){this.state={...initial(),...saved,backend:'',mode:'browser',restored:true,question:null};if(['running','paused','awaiting'].includes(saved.status)){this.state.status='stopped';Object.values(this.state.steps).forEach(s=>{if(['running','awaiting'].includes(s.status))s.status='stopped';});this.state.logs.push({time:now(),stage:saved.active||'overview',message:'브라우저를 다시 열어 실행이 중지된 상태로 복원했습니다.',type:'info'});}}}catch{}this.getSnapshot=()=>this.state;this.subscribe=fn=>{this.listeners.add(fn);return()=>this.listeners.delete(fn);};}
 emit(patch={}){this.state={...this.state,...patch};try{localStorage.setItem(KEY,JSON.stringify(this.state));this.state.storageWarning='';}catch{this.state.storageWarning='브라우저 저장 공간이 부족합니다. 결과를 JSON으로 내보내 주세요.';}this.listeners.forEach(fn=>fn());}
 log(stage,message,type='info'){this.state.logs=[...this.state.logs,{time:now(),stage,message,type}].slice(-200);}
 changeBrief(request,brief){this.stop(false);this.log('overview','기획 조건 변경 · 기존 결과를 무효화했습니다.');this.emit({request,brief,results:{},steps:steps(),decisions:{},active:null,status:'idle',error:null});}
 changeData(reviews,models){this.stop(false);this.log('retrieve','자료 변경 · 기존 분석을 무효화했습니다.');this.emit({reviews:normalizeReviews(reviews),models:normalizeModels(models),results:{},steps:steps(),decisions:{},active:null,status:'idle',error:null});}
 reset(){this.stop(false);localStorage.removeItem(KEY);this.emit(initial());}
 context(){const s=this.state;return{request:s.request,conditions:{...s.brief,excludedTerms:s.brief.excluded,text:s.brief.scope,exclude:s.brief.excluded},reviews:s.reviews,models:s.models,results:s.results,decisions:s.decisions};}
 release(){this.wake.splice(0).forEach(fn=>fn());}
 pause(){if(this.state.status==='running'){this.log(this.state.active,'일시정지 요청 · 다음 작업 경계에서 대기합니다.');this.emit({status:'paused'});}}
 resume(){if(this.state.status==='paused'){this.log(this.state.active,'실행을 계속합니다.');this.emit({status:'running'});this.release();}}
 stop(announce=true){this.epoch++;this.release();this.questionResolve?.(null);this.questionResolve=null;if(['running','paused','awaiting'].includes(this.state.status)){const st={...this.state.steps};if(this.state.active)st[this.state.active]={...st[this.state.active],status:'stopped',endedAt:now()};if(announce)this.log(this.state.active,'실행 중지 · 완료 결과를 보존했습니다.');this.emit({status:'stopped',question:null,steps:st});}}
 answer(value){if(!this.state.question||!['include','hold'].includes(value))return;const q=this.state.question;this.log('compare',value==='hold'?'확인 항목을 보류했습니다.':'확인 항목을 가정으로 포함했습니다.');this.emit({decisions:{...this.state.decisions,[q.id]:value},question:null,status:'running'});const fn=this.questionResolve;this.questionResolve=null;fn?.(value);}
 async control(token){while(this.state.status==='paused'&&token===this.epoch)await new Promise(r=>this.wake.push(r));return token===this.epoch;}
 async connect(url){const clean=url.replace(/\/+$/,'');const response=await fetch(clean+'/health');if(!response.ok)throw Error('Python 실행기에 연결할 수 없습니다.');const data=await response.json();if(data.mode!=='local_rules')throw Error('지원하는 로컬 실행기가 아닙니다.');this.stop(false);this.log('overview','Python 실행기 연결 · 로컬 규칙 모드');this.emit({backend:clean,mode:'python'});return data;}
 disconnect(){this.stop(false);this.emit({backend:'',mode:'browser'});}
 async execute(id){if(this.state.mode==='python'){const response=await fetch(this.state.backend+'/api/stage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage:id,context:this.context()})});const data=await response.json();if(!response.ok)throw Error(data.error||'Python 단계 실행 실패');return data.result;}return runStage(id,this.context());}
 async start(from='retrieve'){
  if(['running','paused','awaiting'].includes(this.state.status))return;
  const old=this.state;if(Object.keys(old.results).length)this.state.history=[{runId:old.runId,time:now(),request:old.request,status:old.status,results:clone(old.results),revisions:clone(old.revisions),steps:clone(old.steps),logs:clone(old.logs)},...old.history].slice(0,8);
  let index=NODE_DEFS.findIndex(n=>n.id===from);if(index<0)index=0;for(let i=0;i<index;i++)if(!this.state.results[NODE_DEFS[i].id]){index=i;break;}
  const results={...this.state.results},st={...this.state.steps};for(let i=index;i<5;i++){delete results[NODE_DEFS[i].id];st[NODE_DEFS[i].id]={...steps()[NODE_DEFS[i].id]};}
  const token=++this.epoch,runId=crypto.randomUUID();this.log('overview',`${NODE_DEFS[index].label}부터 실행 · 이후 결과를 다시 계산합니다.`);
  this.emit({results,steps:st,status:'running',active:NODE_DEFS[index].id,runId,runCount:old.runCount+1,revisions:[],question:null,restored:false,error:null});
  let repairCount=0;
  try{for(let i=index;i<5;i++){
   if(!await this.control(token))return;
   const node=NODE_DEFS[i],startedAt=now();this.log(node.id,`${node.label} 실행 중`);this.emit({active:node.id,steps:{...this.state.steps,[node.id]:{status:'running',startedAt,task:node.description,processed:0,total:null}}});
   await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));if(!await this.control(token))return;
   if(node.id==='compare'){
    for(let q=getClarification(this.context());q;q=getClarification(this.context())){this.log('compare','고객 불편의 원인을 확인하고 있습니다.');this.emit({status:'awaiting',question:q,steps:{...this.state.steps,compare:{...this.state.steps.compare,status:'awaiting',task:q.text}}});const answer=await new Promise(r=>{this.questionResolve=r;});if(!answer||token!==this.epoch)return;this.emit({steps:{...this.state.steps,compare:{...this.state.steps.compare,status:'running'}}});}
   }
   const result=await this.execute(node.id);if(token!==this.epoch)return;
   const count=node.id==='retrieve'?result.reviews?.length:node.id==='structure'?this.state.results.retrieve?.matchedReviews?.length:node.id==='compare'?result.comparisons?.length:node.id==='concept'?result.concepts?.length:result.checks?.length;
   this.log(node.id,result.summary,result.needsRepair?'warning':'success');this.emit({results:{...this.state.results,[node.id]:result},steps:{...this.state.steps,[node.id]:{...this.state.steps[node.id],status:'completed',task:result.activity||result.summary,processed:count||0,total:count||0,endedAt:now()}}});
   if(node.id==='validate'&&this.state.revisions.some(round=>!round.after))this.emit({revisions:this.state.revisions.map(round=>round.after?round:{...round,after:clone(this.state.results)})});
   if(node.id==='validate'&&result.needsRepair&&repairCount<2){repairCount++;const targets=(result.repairTargets||[]).map(id=>NODE_DEFS.findIndex(n=>n.id===id)).filter(x=>x>=0),target=targets.length?Math.min(...targets):3;const before=clone(this.state.results);this.log('validate',`자동 수정 ${repairCount}/2 · ${NODE_DEFS[target].label}부터 재검사합니다.`,'warning');this.emit({revisions:[...this.state.revisions,{round:repairCount,time:now(),reason:(result.issues||[]).map(x=>x.message).join(' / ')||'검사 실패 항목 재확인',before,after:null}]});for(let j=target;j<5;j++){const ns={...this.state.steps},rs={...this.state.results};delete rs[NODE_DEFS[j].id];ns[NODE_DEFS[j].id]=steps()[NODE_DEFS[j].id];this.emit({steps:ns,results:rs});}i=target-1;}
  }
  if(token!==this.epoch)return;const status=this.state.results.validate?.needsRepair?'review':'completed';this.log('overview',status==='review'?'미해결 항목이 있습니다. 근거와 검사 기록을 확인해 주세요.':'기획 결과 준비 완료 · 원문과 함께 검토해 주세요.',status==='review'?'warning':'success');this.emit({status,question:null});
  }catch(error){if(token!==this.epoch)return;const st={...this.state.steps};if(this.state.active)st[this.state.active]={...st[this.state.active],status:'failed',task:error.message,endedAt:now()};this.log(this.state.active,error.message,'error');this.emit({status:'failed',steps:st,error:error.message});}
 }
}
export function download(name,data,type='application/json'){const blob=new Blob([typeof data==='string'?data:JSON.stringify(data,null,2)],{type});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export function toCSV(rows){if(!rows.length)return '\ufeff결과 없음\r\n';const cols=Object.keys(rows[0]);return '\ufeff'+[cols,...rows.map(r=>cols.map(k=>r[k]))].map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n');}
