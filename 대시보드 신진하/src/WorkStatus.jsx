import React from 'react';
import {ArrowUpRight,Clock3} from 'lucide-react';
import {getOverallPresentation,getStagePresentation} from './presentation.js';
const time=t=>t?new Date(t).toLocaleTimeString('ko-KR',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—';
function oneLine(state){
 const work=getOverallPresentation(state),product=state.brief?.product||'제품',step=getStagePresentation(state,state.active).label;
 const accepted=state.results?.validate?.acceptedConcepts;
 const concepts=Array.isArray(accepted)?accepted:Array.isArray(state.results?.concept?.concepts)?state.results.concept.concepts:[];
 const running={retrieve:`${product} 리뷰와 제품 자료를 확인하고 있습니다`,structure:`${product} 리뷰에서 고객 불편을 묶고 있습니다`,compare:`${product} 리뷰를 기존 제품 기능과 대조하고 있습니다`,concept:'남은 불편을 해결할 콘셉트를 작성하고 있습니다',validate:'콘셉트의 근거와 중복 여부를 검사하고 있습니다'};
 const compact={retrieve:`${product} 리뷰·제품 자료 확인 중`,structure:'고객 불편을 묶고 있습니다',compare:`${product} 리뷰·기존 기능 대조 중`,concept:'남은 불편의 콘셉트 작성 중',validate:'콘셉트 근거·중복 검사 중'};
 switch(state.status){
  case 'running':return {full:running[state.active]||work.title,compact:compact[state.active]||work.title};
  case 'completed':return {full:`기획 완료 · 콘셉트 ${concepts.length}개 검토 가능`,compact:`기획 완료 · 콘셉트 ${concepts.length}개 검토 가능`};
  case 'awaiting':return {full:'고객 불편의 해석에 대한 사용자 확인을 기다립니다',compact:'고객 불편 해석 · 사용자 확인 대기'};
  case 'paused':return {full:`${step} · 일시정지`,compact:`${step} · 일시정지`};
  case 'failed':return {full:`${step} · 오류 확인이 필요합니다`,compact:`${step} · 오류`};
  case 'review':return {full:'검토 필요 · 남은 검사 문제를 확인해 주세요',compact:'검토 필요 · 검사 문제 확인'};
  case 'stopped':return {full:'실행 중지 · 완료 결과와 기록을 보존했습니다',compact:'실행 중지 · 완료 결과 보존'};
  default:return {full:`${product} 상품기획 · 요청과 자료를 준비해 주세요`,compact:`${product} 상품기획 준비`};
 }
}
export function HeaderWorkStatus({state,onOpen}){
 const work=getOverallPresentation(state),line=oneLine(state);
 return <button className={`header-work-status state-${state.status}`} onClick={onOpen} aria-label={line.full} title={`${line.full}\n${work.summary}`}><i aria-hidden="true"/><small>{state.mode==='python'?'Python · 로컬 규칙':'데모 · 로컬 규칙'}</small><span className="work-line-full" aria-hidden="true">{line.full}</span><span className="work-line-compact" aria-hidden="true">{line.compact}</span></button>;
}
export function ExecutionActivity({state,onSelect,onNext}){
 const work=getOverallPresentation(state),active=getStagePresentation(state,state.active);
 const useful=(state.logs||[]).filter(l=>l.type!=='info');
 const recent=(useful.length?useful:state.logs||[]).slice(-3).reverse();
 const nextLabel={awaiting:'질문 확인',paused:'계속 실행',idle:'실행 시작',running:'실행 단계 보기',failed:'오류 단계 보기',stopped:'재실행 단계 보기',review:'검사 결과 보기',completed:'콘셉트 보기'}[state.status]||'결과 보기';
 const reason=state.status==='awaiting'?state.question?.text:state.status==='failed'?state.error||state.steps?.[state.active]?.task:state.status==='paused'?work.summary:null;
 return <section className="execution-activity" aria-label="최근 작업과 다음 행동"><div className="execution-state-line"><b>전체 실행 · {work.statusLabel}</b>{['running','paused','awaiting'].includes(state.status)&&<span>실제 실행 단계: {active.label}</span>}</div><h2><Clock3 size={13}/>최근 작업</h2><ol>{recent.length?recent.map((item,i)=><li key={`${item.time}-${i}`}><time>{time(item.time)}</time><button onClick={()=>onSelect(item.stage||'overview')}><i className={item.type}/><span>{item.message}</span></button></li>):<li className="execution-empty">실행하면 실제 작업이 기록됩니다.</li>}</ol>{reason&&<div className="execution-wait-reason"><b>{state.status==='failed'?'오류 사유':'대기 사유'}</b><p>{reason}</p></div>}<div className="execution-next"><b>다음 행동</b><p>{work.nextAction}</p><button onClick={onNext}>{nextLabel}<ArrowUpRight size={13}/></button></div></section>;
}
