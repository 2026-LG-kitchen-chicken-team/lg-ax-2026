import React from 'react';
import {Play,Pause,Square,Focus,SlidersHorizontal,Database,AlertCircle} from 'lucide-react';
import {NODE_DEFS} from './engine.js';
import {LABELS} from './planner.js';

export default function FactoryCommandBar({state,onFollow,onToggle,onStop,onBrief,onData,onQuestion}){
 const completed=NODE_DEFS.filter(n=>state.steps?.[n.id]?.status==='completed').length,total=NODE_DEFS.length,busy=['running','paused','awaiting'].includes(state.status);
 const active=NODE_DEFS.find(n=>n.id===state.active)?.label||'기획 준비',toggle=state.status==='running'?'일시정지':state.status==='paused'?'계속':'전체 실행';
 return <div className="floating-run factory-commandbar" aria-label="실행과 자료 제어">
  <button className="command-current" aria-label="실행 노드 따라가기" onClick={onFollow} title="현재 실행 단계와 자세한 작업 보기"><i className={'command-dot '+state.status}/><span>{busy?active:LABELS[state.status]}<small>{busy?LABELS[state.status]:'상품기획'}</small></span><Focus size={13}/></button>
  <div className="command-progress"><div role="progressbar" aria-label="완료한 Skill 단계" aria-valuemin={0} aria-valuemax={total} aria-valuenow={completed} aria-valuetext={`${total}개 단계 중 ${completed}개 완료`}><i style={{width:`${completed/total*100}%`}}/></div><span>{completed}/{total}<small>단계 완료</small></span></div>
  <div className="command-transport"><button aria-label={toggle} disabled={state.status==='awaiting'} onClick={onToggle}>{state.status==='running'?<Pause size={15}/>:<Play size={15}/>}</button><button aria-label="실행 중지" disabled={!busy} onClick={onStop}><Square size={13}/></button></div>
  <span className="command-divider"/>
  <button className="command-tool" aria-label="기획 조건" onClick={onBrief} title="기획 조건"><SlidersHorizontal size={15}/><span>기획 조건</span></button>
  <button className="command-tool" aria-label={`자료 보관소 · 리뷰 ${state.reviews.length}개 · 모델 ${state.models.length}개`} onClick={onData} title={`리뷰 ${state.reviews.length}개 · 모델 ${state.models.length}개`}><Database size={15}/><span>자료</span><b>{state.reviews.length}</b></button>
  {state.question&&<button className="needs-answer" aria-label="확인 질문 보기" title="확인 질문 보기" onClick={onQuestion}><AlertCircle size={14}/><span>질문 확인</span></button>}
 </div>;
}
