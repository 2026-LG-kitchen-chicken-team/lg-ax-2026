import React,{memo,useCallback,useRef} from 'react';
import {Play,Pause,SkipBack,Radio,RefreshCw,Focus} from 'lucide-react';
import {SPEEDS} from './office-store.js';
import './office.css';

// Lanes of the recorded session, like the agent-office timeline: calls by kind, open main turns, requests and DB moments.
const LANES=[['main','메인'],['roles','연구 역할'],['skills','Skill'],['web','웹'],['tools','셸·파일'],['db','DB·질문']];
const COLORS={main:'#f19236',roles:'#7f6bc4',skills:'#2f9a72',web:'#3a98b9',tools:'#8d9a92',db:'#c9a24b'};
const two=n=>String(n).padStart(2,'0');
const clock=t=>{const d=new Date(t);return `${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`;};
const mmss=ms=>{const s=Math.max(0,Math.round(ms/1000));return `${Math.floor(s/60)}:${two(s%60)}`;};
const secs=ms=>ms<60000?`${Math.max(0,Math.round(ms/1000))}초`:`${Math.round(ms/60000)}분`;
const Strip=memo(function Strip({strip,start,end}){
  const span=Math.max(1,end-start),x=t=>(t-start)/span*1000,y=lane=>Math.max(0,LANES.findIndex(([id])=>id===lane))*10;
  return <svg viewBox="0 0 1000 60" preserveAspectRatio="none" aria-hidden="true">
    {LANES.map(([id],i)=><rect key={id} x={0} y={i*10} width={1000} height={10} fill={i%2?'#eef2ee':'#f7f9f6'}/>)}
    {strip.spans.map((s,i)=>{const lane=s.lane==='turn'?'main':s.lane,turn=s.lane==='turn';return <rect key={i} x={x(s.start)} y={y(lane)+(turn?1:2)} width={Math.max(.7,x(s.end??end)-x(s.start))} height={turn?8:6} fill={s.status==='failed'?'#d4553f':COLORS[lane]} opacity={turn?.18:.9}/>;})}
    {strip.points.map((p,i)=><rect key={'p'+i} x={x(p.t)-.5} y={y(p.lane)} width={1} height={10} fill={p.kind==='request'?'#5a6fb0':p.kind==='db'?COLORS.db:'#f19236'}/>)}
  </svg>;
});
export default function OfficeReplayBar({office,store,onFollow,following}){
  const track=useRef(null),drag=useRef(false),live=office.mode==='live';
  const start=office.start,end=office.end??start,at=live?Date.now():office.at;
  const seekAt=useCallback(clientX=>{const rect=track.current?.getBoundingClientRect();if(!rect||start==null)return;store.seek(start+Math.min(1,Math.max(0,(clientX-rect.left)/rect.width))*Math.max(1,end-start));},[store,start,end]);
  if(start==null)return <div className="office-replay office-replay-empty" role="status"><Radio size={14}/>{'기록 파일을 열면 지난 작업을 재생할 수 있습니다. 지금 실행 중인 작업은 실시간 연결에서 확인하세요.'}</div>;
  const frac=Math.min(1,Math.max(0,(at-start)/Math.max(1,end-start))),read=office.read,lastEvent=office.sessions.at(-1)?.end;
  return <div className="office-replay" aria-label={live?'실시간 실행 기록':'실행 기록 재생'}>
    <div className="office-replay-controls">
      {live?<span className="office-chip live"><i/>실시간</span>:<button className="primary" aria-label={office.playing?'재생 일시정지':'재생'} onClick={()=>store.play(!office.playing)}>{office.playing?<Pause size={14}/>:<Play size={14}/>}{office.playing?'일시정지':'재생'}</button>}
      <button aria-label="처음으로" onClick={()=>store.seek(start)}><SkipBack size={14}/>처음</button>
      {!live&&<div className="office-speeds" role="group" aria-label="재생 속도">{SPEEDS.map(s=><button key={s} className={office.speed===s?'on':''} aria-pressed={office.speed===s} onClick={()=>store.setSpeed(s)}>{s}x</button>)}</div>}
      {!live&&<label className="office-skip"><input type="checkbox" checked={office.skipQuiet} onChange={e=>store.setSkipQuiet(e.target.checked)}/>빈 시간 건너뛰기</label>}
      {!live&&office.skipped&&<span className="office-chip">빈 시간 {secs(office.skipped.ms)} 건너뜀</span>}
      {live&&<span className={`office-chip ${read.error?'warn':''}`}>{lastEvent?`마지막 실제 사건 ${secs(Date.now()-lastEvent)} 전`:'실제 사건 대기'}</span>}
      {live&&read.lastSuccessAt&&<span className="office-chip office-wide">화면 읽기 {read.error?'지연':'성공'} {secs(Date.now()-read.lastSuccessAt)} 전</span>}
      {live&&<button onClick={()=>store.refresh()}><RefreshCw size={13}/>기록 다시 확인</button>}
      {onFollow&&<button className={following?'on':''} aria-pressed={Boolean(following)} onClick={onFollow}><Focus size={13}/>실행 작업 따라가기</button>}
      <span className="office-time"><b>{clock(at)}</b><span>{mmss(at-start)} / {mmss(end-start)}</span></span>
      {!live&&!office.file&&<button onClick={()=>store.goLive()}><Radio size={13}/>실시간 보기</button>}
    </div>
    <div className="office-strip-row">
      <div className="office-lanes" aria-hidden="true">{LANES.map(([id,label])=><span key={id}>{label}</span>)}</div>
      <div ref={track} className="office-strip" role="slider" tabIndex={0} aria-label="기록 시각" aria-valuemin={0} aria-valuemax={Math.round((end-start)/1000)} aria-valuenow={Math.round((at-start)/1000)} aria-valuetext={`${mmss(at-start)} / ${mmss(end-start)}`}
        onPointerDown={e=>{drag.current=true;e.currentTarget.setPointerCapture?.(e.pointerId);seekAt(e.clientX);}} onPointerMove={e=>drag.current&&seekAt(e.clientX)} onPointerUp={()=>{drag.current=false;}}
        onKeyDown={e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();store.seek(at+(e.key==='ArrowRight'?5000:-5000));}}}>
        <Strip strip={office.strip} start={start} end={end}/><i className="office-playhead" style={{left:`${frac*100}%`}}/>
      </div>
    </div>
  </div>;
}
