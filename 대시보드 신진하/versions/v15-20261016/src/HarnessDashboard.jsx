import React,{useEffect,useState,useSyncExternalStore} from 'react';
import {ArrowLeft,X,Settings2,Clock3,Focus,RefreshCw,ExternalLink,Layers,Unplug,ShieldCheck} from 'lucide-react';
import FactoryScene from './FactoryScene.jsx';
import {createHarnessStore} from './harness.js';
import './harness.css';

const store=createHarnessStore();
const members=[
 {node:'retrieve',id:'jeongiryang',name:'정이량',role:'PM · 규격·통합'},
 {node:'structure',id:'unknownamed',name:'황대겸',role:'CORE · 핵심 판단'},
 {node:'compare',id:'ginaginaring',name:'신진하',role:'DATA · 자료·근거'},
 {node:'concept',id:'choigilung',name:'최길웅',role:'WEB · 기획 작업실'},
];
const statusNames={pending:'배정 대기',stopping:'중지 처리 보고',completed_review:'검수 보고 완료',queued:'배정 대기',registered:'등록',running:'실행 보고',leased:'할당됨',review_requested:'검수 요청',accepted:'하네스 인수',failed:'실패 기록',blocked:'막힘',orphaned:'실행 확인 필요',cancelled:'취소',stopped:'중지',rejected:'반려'};
const phaseNames={model:'코드 작성 · Worker 자기보고',preflight:'실행 준비 · Worker 자기보고',validating:'검사 · Worker 자기보고',publishing:'게시 · Worker 자기보고',idle:'대기 · Worker 자기보고',starting:'시작 준비',profile_busy:'실행기 사용 대기'};
const formalNames={pending:'대기',ready:'착수 가능',doing:'진행 기록',blocked:'막힘',deferred:'보류',individual_verified:'개인 검증 기록',pm_review_requested:'PM 검수 요청',pm_approved:'PM 승인 기록',merged:'병합 기록',integration_verified:'통합 확인 기록',done:'정식 완료 기록'};
const time=value=>value?new Date(value).toLocaleString('ko-KR',{hour12:false}):'수신 전';
const eventNames={claimed:'작업 할당',registered:'작업 등록',heartbeat:'작업 생존 보고',worker_presence:'Worker 상태 수신',review_requested:'검수 요청',accepted:'하네스 인수',failed:'실패 기록',mode:'모드 변경',orphaned:'실행 확인 필요'};

function Job({job,worker,confirmed}){
 return <article className="harness-job">
  <div className="harness-job-title"><b>{job.task_id||'작업 ID 미제공'}</b><span className={`status-chip ${confirmed?'running':''}`}>{confirmed?'최근 실행 보고':statusNames[job.status]||job.status}</span></div>
  <h3>{job.title||'작업 제목 미제공'}</h3>
  <dl className="harness-facts"><dt>실행기</dt><dd>{worker?.engine||'정보 미제공'}</dd><dt>마지막 작업 보고</dt><dd>{phaseNames[worker?.phase]||'단계 보고 없음'}</dd><dt>실행 확인</dt><dd>{confirmed?'최근 Worker 보고와 유효한 작업 할당 확인':job.confirmationReason||job.reason||'현재 실행을 확인할 정보가 부족합니다'}</dd><dt>작업 할당 기한</dt><dd>{job.lease_state==='expired'?'기한 만료 · 실제 실행 여부 확인 필요':job.lease_state==='live'?'유효':'기한 정보 미제공'}</dd></dl>
  <p className="harness-evidence-note">하네스 상태·자기보고입니다. 명령 원문, LLM 내부 작업, 실제 병합 완료를 추정하지 않습니다.</p>
 </article>;
}

export default function HarnessDashboard({onDemo,onMotion}){
 const state=useSyncExternalStore(store.subscribe,store.getSnapshot),snapshot=state.snapshot,connection=state.connection;
 const [selected,setSelected]=useState('overview'),[panel,setPanel]=useState(null),[follow,setFollow]=useState(false),[menu,setMenu]=useState(false),[width,setWidth]=useState(window.innerWidth),[reduced,setReduced]=useState(false);
 const [url,setUrl]=useState('http://127.0.0.1:8033'),[token,setToken]=useState(''),[formError,setFormError]=useState('');
 const panelWidth=panel&&width>760?Math.min(470,width*.42):0;
 const close=()=>{setPanel(null);setSelected('overview');setFollow(false);setMenu(false);};
 const connected=connection.status==='connected';
 const activeOwners=connected?(state.view.activeOwners||[state.view.activeOwner].filter(Boolean)):[];
 const activeMember=members.find(m=>activeOwners.includes(m.id));
 const jobs=state.view.jobs||[],workers=snapshot?.workers||[];
 const reviewJobs=jobs.filter(j=>j.status==='review_requested');
 const confirmed=job=>connected&&activeOwners.includes(job.owner)&&job.active===true;
 const select=node=>{setSelected(node);setPanel('inspector');setFollow(false);setMenu(false);};
 const followNow=()=>{setFollow(true);setSelected(activeMember?.node||'overview');setPanel('inspector');};
 useEffect(()=>{const resize=()=>setWidth(window.innerWidth),key=e=>{if(e.key==='Escape')close();};addEventListener('resize',resize);addEventListener('keydown',key);const mq=matchMedia('(prefers-reduced-motion: reduce)');setReduced(mq.matches);const motion=()=>setReduced(mq.matches);mq.addEventListener('change',motion);return()=>{removeEventListener('resize',resize);removeEventListener('keydown',key);mq.removeEventListener('change',motion);};},[]);
 useEffect(()=>{if(follow)setSelected(activeMember?.node||'overview');},[follow,activeMember?.node]);
 const labels={},steps={};
 for(const member of members){const list=jobs.filter(j=>j.owner===member.id),worker=workers.find(w=>w.owner===member.id),running=list.some(confirmed);labels[member.node]={title:member.name,caption:running?`${worker?.engine||'실행기'} · ${list.find(confirmed)?.task_id||'작업 보고'}`:member.role,kind:'MEMBER',statusLabel:!snapshot?'미연결':running?'실행 확인':worker?.presence==='stale'?'보고 오래됨':list.length?'작업 보기':'작업 보고 없음'};steps[member.node]={status:running?'running':'pending'};}
 labels.validate={title:'팀 검수 대기',caption:'검수 요청과 인수 기록',kind:'REVIEW',statusLabel:snapshot?`요청 ${reviewJobs.length}개`:'미연결'};
 steps.validate={status:'pending'};
 const member=members.find(m=>m.node===selected),selectedJobs=member?jobs.filter(j=>j.owner===member.id):selected==='validate'?reviewJobs:jobs;
 const formalTasks=(snapshot?.formal_tasks||[]).filter(task=>member?task.owner===member.id:selected==='validate'?['individual_verified','pm_review_requested','pm_approved','merged','integration_verified'].includes(task.status):true);
 const openConnection=()=>{setPanel('connection');setMenu(false);};
 const disconnect=()=>{store.disconnect();setToken('');};
 const returnDemo=()=>{disconnect();onDemo();};
 const connect=async e=>{e.preventDefault();setFormError('');try{await store.connect({url,token});}catch{setFormError('연결하지 못했습니다. 읽기 서버 주소·인증 코드·브라우저 접근 허용을 확인해 주세요.');}finally{setToken('');}};
 return <div className={`app-shell fullscreen-app work-clarity harness-app ${panel?'panel-open':''}`} data-drawer={panel==='connection'?'form':panel?'inspector':'none'} style={{'--drawer-width':`${panelWidth||Math.min(470,width)}px`}}>
  <header className="topbar"><button className="brand" onClick={close}><b>KITCHEN <em>AX</em></b><span>팀 개발 하네스</span></button>
   <button className={`header-work-status state-${connected&&activeOwners.length?'running':'idle'}`} onClick={()=>{setPanel('inspector');setSelected('overview');}} title={state.view.header.detail}><i/><small>하네스 · 읽기 전용</small><span className="work-line-full">{state.view.header.text}</span><span className="work-line-compact">{state.view.header.text}</span></button>
   <button className="mobile-menu-toggle" aria-label="기능 메뉴" aria-expanded={menu} onClick={()=>setMenu(!menu)}><Layers size={15}/>메뉴</button>
   <div className={`header-actions ${menu?'menu-open':''}`}><button onClick={()=>{setPanel('inspector');setSelected('overview');setMenu(false);}}><Clock3 size={14}/>현재 작업</button><button onClick={openConnection}><Settings2 size={14}/>하네스 연결</button><button onClick={onMotion}>연구원 모션</button><button onClick={returnDemo}>상품기획 데모</button></div>
  </header>
  {panel&&<div className="panel-return"><button onClick={close}><ArrowLeft size={14}/>전체 화면으로</button><button aria-label="오른쪽 패널 닫기" onClick={close}><X size={17}/></button></div>}
  <main className="workspace"><section className="factory-panel" aria-label="팀 개발 하네스 공장">
   <FactoryScene selected={selected} onSelect={select} onHome={()=>select('overview')} active={activeMember?.node||null} activeNodes={members.filter(m=>activeOwners.includes(m.id)).map(m=>m.node)} stepStates={steps} reducedMotion={reduced} panelWidth={panelWidth} stationLabels={labels} centerLabel={{eyebrow:'TEAM HARNESS',title:'팀 개발 현황',caption:snapshot?'실제 보고와 연결된 작업 보기':'하네스 연결을 기다립니다'}}/>
   <div className="scene-controls"><button onClick={followNow} className={follow?'following':''}><Focus size={14}/>실행 작업 따라가기</button><button onClick={openConnection}><ShieldCheck size={14}/>{connected?'읽기 연결됨':'하네스 연결'}</button><button onClick={()=>{store.refresh().catch(()=>{});}} disabled={!connection.url||connection.status==='connecting'}><RefreshCw size={14}/>상태 새로고침</button></div>
  </section>
  {panel!=='connection'&&<aside className="inspector harness-inspector" aria-label="팀원과 실제 작업 상세">
   <p className="selection-context">지금 열어본 공간 · {member?.name||(selected==='validate'?'검수 대기':'전체 현황')}<span>실제 실행 보고: {activeOwners.map(id=>members.find(m=>m.id===id)?.name||id).join(' · ')||'확인된 실행 없음'}</span></p>
   <div className="inspector-head"><span className="inspector-symbol"><Layers size={23}/></span><div><h1>{member?.name|| (selected==='validate'?'팀 검수 대기':'팀 개발 현황')}</h1><p>{member?.role||'정이량 하네스의 팀원·CLI 개발 작업'}</p></div></div>
   <section className="harness-current"><small>현재 확인된 상태</small><h2>{state.view.header.text}</h2><p>{state.view.header.detail}</p><p className="harness-evidence-note">조회 시각 {time(snapshot?.source?.observed_at)}<br/>마지막 원본 기록 {time(snapshot?.source?.source_updated_at)} · 팀 모드 {snapshot?.global_mode?.toUpperCase()||'미확인'}</p></section>
   {!snapshot?<section className="harness-empty"><h3>실제 하네스에 아직 연결되지 않았습니다</h3><p>정이량 PC의 읽기 서버가 보내는 상태를 연결하면 담당자·배정 작업·코드 작성·검사·게시 보고가 여기에 표시됩니다.</p><button className="primary" onClick={openConnection}>읽기 연결 설정</button></section>:<>
    {!member&&selected!=='validate'&&<div className="harness-members">{members.map(m=><button key={m.id} onClick={()=>select(m.node)}><b>{m.name}</b><span>{jobs.filter(j=>j.owner===m.id).length}개 수신 작업</span></button>)}</div>}
    <section><div className="harness-section-title"><h2>{selected==='validate'?'검수 요청':member?'담당 작업':'수신한 작업'}</h2><span>{selectedJobs.length}개 작업</span></div>
     {selectedJobs.length?selectedJobs.map(job=><Job key={job.id} job={job} worker={workers.find(w=>w.owner===job.owner&&w.job_id===job.id)} confirmed={confirmed(job)}/>):<p className="harness-evidence-note">수신한 범위에 해당 작업이 없습니다. 다른 작업의 완료 여부로 해석하지 않습니다.</p>}
    </section>
    <section className="harness-formal"><div className="harness-section-title"><h2>정식 개발 과제 · 하네스 기록</h2><span>{formalTasks.length}개 과제</span></div><p className="harness-evidence-note">자동화 대기열과 별도의 정식 과제 상태입니다. 이 기록만으로 CLI가 현재 실행 중이라고 판단하지 않습니다.</p>{formalTasks.length?<details open={!!member}><summary>과제와 정식 상태 보기</summary>{formalTasks.map(task=><article key={task.id}><b>{task.id}</b><p>{task.title||'제목 미제공'}</p><span>{formalNames[task.status]||task.status}</span></article>)}</details>:<p className="harness-evidence-note">해당 범위의 정식 과제가 수신되지 않았습니다.</p>}</section>
   </>}
   <section className="harness-events"><h2>최근 실제 기록</h2>{state.view.recentEvents?.length?<ol>{state.view.recentEvents.map(event=><li key={event.id}><time>{time(event.at)}</time><b>{eventNames[event.type]||event.type}</b>{event.job_id&&<span>{event.job_id}</span>}</li>)}</ol>:<p>아직 수신한 실행 기록이 없습니다.</p>}</section>
   <section className="harness-next"><h2>다음 행동</h2><p>{!snapshot?'정이량 PC에서 읽기 서버를 실행한 뒤 연결 주소와 인증 코드를 입력하세요.':connection.status!=='connected'?'연결 상태를 확인하세요. 마지막 수신 내용은 보존하며 실행 강조는 멈춥니다.':snapshot.global_mode!=='on'?'팀 실행 모드가 켜져 있지 않습니다. 이 화면에서는 조회만 하며 운영 상태를 변경하지 않습니다.':'담당자 공간을 선택해 최신 Worker 보고와 작업 상태를 확인하세요.'}</p><div className="button-row"><button onClick={openConnection}><Settings2 size={14}/>연결 설정</button><a href="https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/28" target="_blank" rel="noreferrer">팀 운영 기록<ExternalLink size={13}/></a></div></section>
  </aside>}
  </main>
  {panel==='connection'&&<div className="modal-backdrop"><section className="modal" role="dialog" aria-label="팀 하네스 읽기 연결"><div className="modal-header"><div><span>TEAM HARNESS / READ ONLY</span><h2>팀 하네스 연결</h2></div><button autoFocus aria-label="연결 패널 닫기" onClick={close}><X size={20}/></button></div><div className="modal-body"><form className="connection harness-connection" onSubmit={connect}>
   <span className="badge">{connected?'읽기 연결됨':'실제 연결 대기'} · {connection.status}</span><h3>디자인은 그대로, 실제 보고를 연결합니다.</h3><p>이 브라우저가 열려 있는 PC의 읽기 서버에 연결합니다. 정이량 PC의 기존 운영 서버를 직접 제어하지 않습니다.</p>
   <label>읽기 서버 주소<input value={url} onChange={e=>setUrl(e.target.value)} placeholder="http://127.0.0.1:8033" type="url" required autoComplete="off"/></label>
   <label>읽기 연결 인증 코드<input value={token} onChange={e=>setToken(e.target.value)} type="password" required autoComplete="off" placeholder="읽기 서버에서 설정한 코드"/></label>
   <p className="harness-evidence-note">인증 코드는 현재 탭 메모리에서만 사용하며 브라우저 저장소나 URL에 저장하지 않습니다. 채팅으로 보내지 마세요.</p>
   {(formError||connection.error)&&<p className="error-box" role="alert">{formError||connection.error}</p>}
   <div className="button-row"><button className="primary" type="submit" disabled={connection.status==='connecting'}>{connection.status==='connecting'?'연결 확인 중':'읽기 연결'}</button><button type="button" onClick={disconnect}><Unplug size={14}/>연결 해제</button></div>
   <details className="harness-setup"><summary>처음 연결하는 방법</summary><ol><li>소스의 <b>docs/HARNESS-CONNECTION.md</b>를 정이량 PC에서 확인합니다.</li><li>실제 하네스 DB 경로와 별도의 읽기 인증 코드를 환경 변수로 지정합니다.</li><li><code>python -m backend.harness_server</code>로 읽기 서버만 실행합니다. Worker·팀 ON/OFF·작업 할당은 바꾸지 않습니다.</li><li>같은 PC의 이 화면에서 연결합니다. 다른 PC에서 보려면 인증된 중계 서버가 별도로 필요합니다.</li></ol><p>공개 HTTPS 화면의 로컬 네트워크 접근이 브라우저에서 제한되면 같은 소스의 로컬 화면을 이용하세요. 실제 연결 전에는 작업 수·활동을 생성하지 않습니다.</p></details>
  </form></div></section></div>}
 </div>;
}
