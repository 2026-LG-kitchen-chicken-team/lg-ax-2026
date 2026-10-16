import React,{useEffect,useRef,useState} from 'react';
import {ArrowLeft,Play,Pause,Video,Download,X} from 'lucide-react';
import FactoryScene from './FactoryScene.jsx';
import {createFactoryRecording} from './factory-recording.js';
import './researcher-preview.css';
import {previewActiveNodes} from './researcher-motion.js';
import {motionVideo} from 'virtual:factory-assets';

const SPACES=[
  ['overview','메인 기획자','요청을 읽고 담당 작업을 연결하는 동작'],
  ['retrieve','자료 조회','문서를 스캔하고 수집 자료를 확인하는 동작'],
  ['structure','니즈 구조화','고객의 불편을 메모 보드에 정리하는 동작'],
  ['compare','기능 대조','제품 기능과 남은 불편을 대조하는 동작'],
  ['concept','콘셉트 작성','시제품을 살피며 새 기능을 구상하는 동작'],
  ['validate','검토 · 수정','체크리스트와 원문 근거를 확인하는 동작'],
];
export default function ResearcherPreview({onBack}){
  const [elapsed,setElapsed]=useState(0),[playing,setPlaying]=useState(()=>!matchMedia('(prefers-reduced-motion: reduce)').matches),[reduced,setReduced]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [selected,setSelected]=useState('overview'),[panel,setPanel]=useState(false),[width,setWidth]=useState(innerWidth),[recording,setRecording]=useState(false),[video,setVideo]=useState(''),[error,setError]=useState('');
  const clock=useRef(0),last=useRef(null),capture=useRef(null),caption=useRef(''),videoRef=useRef('');
  const [mode,setMode]=useState('single'),[single,setSingle]=useState('retrieve');
  const demoIds=mode==='single'?[single]:previewActiveNodes(elapsed,mode),activeNodes=playing?demoIds:[],active=activeNodes[0]||null;
  const names=demoIds.map(id=>SPACES.find(s=>s[0]===id)?.[1]).join(' + ');
  caption.current=playing?`모션 시연 · ${names} · 작업실 안에서 이동·자료 확인`:'모션 시연 · 일시정지';
  useEffect(()=>{const m=matchMedia('(prefers-reduced-motion: reduce)'),change=()=>{setReduced(m.matches);if(m.matches)setPlaying(false);},resize=()=>setWidth(innerWidth),key=e=>{if(e.key==='Escape')setPanel(false);};m.addEventListener('change',change);addEventListener('resize',resize);addEventListener('keydown',key);return()=>{m.removeEventListener('change',change);removeEventListener('resize',resize);removeEventListener('keydown',key);};},[]);
  useEffect(()=>{let frame;last.current=null;const tick=ms=>{if(last.current!==null)clock.current+=(ms-last.current)/1000;last.current=ms;setElapsed(clock.current);frame=requestAnimationFrame(tick);};if(playing)frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame);},[playing]);
  useEffect(()=>()=>{capture.current?.cancel();if(videoRef.current)URL.revokeObjectURL(videoRef.current);},[]);
  const select=id=>{setSelected(id);setPanel(true);};
  const record=()=>{setError('');setPanel(false);clock.current=0;last.current=null;setElapsed(0);setPlaying(true);setRecording(true);if(videoRef.current){URL.revokeObjectURL(videoRef.current);videoRef.current='';setVideo('');}
    try{capture.current=createFactoryRecording({getCaption:()=>caption.current,onComplete:blob=>{const url=URL.createObjectURL(blob);videoRef.current=url;setVideo(url);setRecording(false);capture.current=null;},onError:message=>{setError(message);setRecording(false);capture.current=null;}});}catch(e){setError(e.message);setRecording(false);}
  };
  const labels=Object.fromEntries(SPACES.filter(([id])=>id!=='overview').map(([id])=>[id,{statusLabel:activeNodes.includes(id)?'작업 시연':'대기'}]));
  const states=Object.fromEntries(SPACES.map(([id])=>[id,{status:activeNodes.includes(id)?'running':'pending'}]));
  const shown=SPACES.find(([id])=>id===selected)||SPACES[0],panelWidth=panel&&width>760?Math.min(360,width*.38):0;
  return <div className={`fullscreen-app researcher-preview ${panel?'preview-panel-open':''}`}>
    <header className="topbar"><button className="brand" onClick={onBack}><b>KITCHEN <em>AX</em></b></button><div className="researcher-preview-status" role="status"><small>연구원 모션 미리보기 · 실제 CLI 실행 아님</small><strong>{playing?`${demoIds.length}개 구역 · ${names} · 작업실 안에서 이동하며 일하는 모션`:'일시정지 · 연구원의 이동을 멈췄습니다'}</strong></div><div className="researcher-preview-actions"><select aria-label="모션 시연 방식" value={mode} disabled={recording} onChange={e=>{setMode(e.target.value);clock.current=0;last.current=null;setElapsed(0);}}><option value="single">한 구역</option><option value="parallel2">동시 2구역</option><option value="parallel3">동시 3구역</option><option value="parallel4">동시 4구역</option><option value="all">동시 5구역</option></select>{mode==='single'&&<select aria-label="시연할 작업실" value={single} disabled={recording} onChange={e=>{setSingle(e.target.value);clock.current=0;last.current=null;setElapsed(0);}}>{SPACES.filter(([id])=>id!=='overview').map(([id,title],i)=><option key={id} value={id}>{String(i+1).padStart(2,'0')} {title}</option>)}</select>}<button aria-label={playing?'모션 일시정지':'모션 재생'} onClick={()=>setPlaying(!playing)} disabled={recording||reduced}>{playing?<Pause size={16}/>:<Play size={16}/>}</button>{motionVideo&&<button onClick={()=>setVideo(motionVideo)} disabled={recording}><Play size={15}/>시연 영상</button>}<button className="primary" onClick={record} disabled={recording||reduced}><Video size={15}/>{recording?'영상 기록 중…':'24초 영상 만들기'}</button><button aria-label="대시보드로 돌아가기" onClick={onBack} disabled={recording}><ArrowLeft size={15}/><span>대시보드로</span></button></div></header>
    <FactoryScene recording={recording} sceneLabel="연구원 모션 미리보기 공장" selected={selected} onSelect={select} onHome={()=>select('overview')} active={active} activeNodes={activeNodes} stepStates={states} reducedMotion={reduced||!playing} stationLabels={labels} centerLabel={{eyebrow:'CHARACTER PREVIEW',title:'메인 기획자',caption:'연구원 모션 미리보기',status:activeNodes.includes('overview')?'working':'idle'}} panelWidth={panelWidth} onFrame={frame=>capture.current?.draw(frame)}/>
    {panel&&<aside className="researcher-preview-panel"><button className="researcher-close" aria-label="모션 설명 닫기" onClick={()=>{setPanel(false);setSelected('overview');}}><X size={18}/></button><small>CHARACTER MOTION</small><h1>{shown[1]}</h1><p>{shown[2]}입니다. 연구원 세 명이 커진 사각형 작업실 안에서 이동하며 문서·보드·제품을 확인합니다.</p><p>흰 연구복·세이지 셔츠·주황색 사원증을 입은 연구원 캐릭터입니다. 실제 대시보드에서는 실행 중인 담당자에게만 작업 모션이 나타납니다.</p><p className="notice">현재 화면은 동작 시연입니다. 실행 결과·진행 수·CLI 기록을 생성하거나 변경하지 않습니다.</p><button onClick={()=>{setPanel(false);setSelected('overview');}}><ArrowLeft size={15}/>전체 화면으로</button></aside>}
    {reduced&&<p className="researcher-notice">동작 축소 설정에 따라 캐릭터를 정지 상태로 표시합니다.</p>}
    {error&&<p className="researcher-notice" role="alert">{error}</p>}
    {video&&<div className="researcher-video-backdrop"><section role="dialog" aria-label="연구원 작업 모션 영상"><header><h2>연구원 작업 모션 · 약 24초</h2><button aria-label="영상 미리보기 닫기" onClick={()=>setVideo('')}><X size={20}/></button></header><video src={video} controls playsInline autoPlay muted/><p>현재 공장 장면을 기록한 모션 미리보기입니다. 실제 CLI 작업 기록과는 구분됩니다.</p><a className="primary" href={video} download={video.endsWith('.mp4')?'kitchen-ax-researcher-motion-v4-20261016.mp4':'kitchen-ax-researcher-motion-v4-20261016.webm'}><Download size={16}/>영상 저장</a></section></div>}
  </div>;
}
