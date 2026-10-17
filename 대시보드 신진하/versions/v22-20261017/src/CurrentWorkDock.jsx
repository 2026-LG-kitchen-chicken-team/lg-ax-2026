import React from 'react';
import {Wrench,UserRound,ChevronRight,ChevronLeft,X,Activity,Link2} from 'lucide-react';
import {PRODUCT_SKILLS} from './skill-catalog.js';
import './current-work-dock.css';
const time=value=>value?new Date(value).toLocaleTimeString('ko-KR',{hour12:false}):'';
export default function CurrentWorkDock({summary,rooms,selected='overview',listOpen,onListToggle,visible,onDismiss,onOpen,onSelect,onConnect,onDetails}){
 return <>
  <nav className={'skill-nav '+(listOpen?'is-open':'')} aria-label="Skill 목록">
   <button className="skill-nav-toggle" onClick={onListToggle} aria-expanded={listOpen}><Wrench size={14}/><span>Skill 목록</span>{listOpen?<ChevronLeft size={13}/>:<ChevronRight size={13}/>}</button>
   {listOpen&&<div className="skill-nav-rows"><small>도구 · 일하는 방법</small>{PRODUCT_SKILLS.map(s=>{const r=rooms[s.node]||{};return <button key={s.node} className={r.confirmed?'is-working':r.helperActive?'is-helper':''} aria-pressed={selected===s.node} onClick={()=>onSelect(s.node)}><b>{s.no}</b><span>{s.label}<small>{r.statusLabel||'대기'}</small></span><i/></button>;})}<p>연구원은 설명용 캐릭터예요.<br/>실제 담당 AI는 작업 기록으로 구분해요.</p></div>}
  </nav>
  {visible?<aside className={'current-work-dock '+(summary.preview?'is-preview':'')} aria-label="지금 하는 일">
   <header><b><Activity size={15}/>지금 하는 일</b><button aria-label="현재 작업 접기" onClick={onDismiss}><X size={15}/></button></header>
   <p className="dock-basis"><i className={summary.active?'running':''}/>{summary.basis}</p>
   <h2>{summary.title}</h2>
   <div className="dock-work-rows">{summary.rooms.map(r=><button className={'dock-work-row '+(r.helperActive&&!r.confirmed?'is-helper':'')} key={r.node} onClick={()=>onSelect(r.node)}><span><Wrench size={12}/>{r.no} {r.label}<em>{r.statusLabel}</em></span><strong>{r.detailLine||r.description}</strong><small><UserRound size={11}/>{r.actor}</small><small>{r.progress}</small></button>)}</div>
   {!summary.rooms.length&&<p className="dock-empty">{summary.live?'현재 사용 중인 Skill 명령은 확인되지 않았어요.':'하네스를 연결하면 실제 작업이 여기에 나타나요.'}</p>}
   {summary.recent.length>0&&<section className="dock-recent"><h3>방금 한 일</h3>{summary.recent.map(e=><p key={e.id}><time>{time(e.time)}</time>{e.text}</p>)}</section>}
   <section className="dock-next"><h3>다음 행동</h3><p>{summary.next}</p></section>
   {!summary.preview&&<div className="dock-buttons"><button onClick={onDetails}>전체 작업 기록</button>{!summary.live&&<button onClick={onConnect}><Link2 size={12}/>실제 연결</button>}</div>}
   {!summary.preview&&<details className="dock-raw"><summary>수신한 CLI 기록 펼치기</summary><p>관측기가 보낸 원문 필드예요. 명령 본문과 LLM 내부 생각은 전송되지 않아요.</p>{summary.raw.length?<pre>{summary.raw.map(e=>JSON.stringify(e,null,2)).join('\n')}</pre>:<p>아직 수신한 CLI 기록이 없어요.</p>}</details>}
  </aside>:<button className="current-work-opener" onClick={onOpen}><Activity size={14}/>{summary.active?'작업 보기':'지금 하는 일'}</button>}
 </>;
}
