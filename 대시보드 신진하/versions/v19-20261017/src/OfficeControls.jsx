import React from 'react';
import {FolderOpen, Radio, ArrowLeft, ExternalLink} from 'lucide-react';
import OfficeReplayBar from './OfficeReplayBar.jsx';
import {RESULT_VIEW_URL} from './office-store.js';

const time=t=>new Date(t).toLocaleString('ko-KR',{hour12:false,month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
export default function OfficeControls({office,store,onFile,onLive,onFollow,following,onDemo}){
 return <div className="record-tools">
  <div className="inspector-head"><div><h1>CLI 실행 기록</h1><p>지난 작업을 다시 확인합니다</p></div></div>
  <p>실시간 보기는 지금 도착하는 작업을 표시합니다. 기록 재생은 저장된 작업을 다시 보여주며 AI를 실행하거나 작업 속도를 바꾸지 않습니다.</p>
  <div className="button-row record-source-actions"><button onClick={onLive}><Radio size={14}/>실시간 연결</button><label className="office-file"><FolderOpen size={14}/>기록 파일 열기<input aria-label="CLI 실행 기록 파일" type="file" accept=".jsonl,.json,.js,.txt" onChange={onFile}/></label></div>
  <p className="harness-evidence-note">events.jsonl 또는 live.js를 선택하세요. 이 화면에서 파일 내용은 브라우저 밖으로 전송하지 않습니다.</p>
  {office.note&&<p className="record-notice" role="status">{office.note}<button onClick={()=>store.dismissNote()} aria-label="기록 알림 닫기">닫기</button></p>}
  {office.file&&<p className="office-chip">열어본 파일 · {office.file.name}</p>}
  {office.sessions.length>0&&<label className="record-session">세션 선택<select className="office-select" aria-label="세션 선택" value={office.sessionId||''} onChange={e=>store.selectSession(e.target.value)}>{office.sessions.map((s,i)=><option key={s.id} value={s.id}>{i+1}. {s.src==='codex'?'Codex':'Claude'} · {time(s.start)} · 사건 {s.count}개</option>)}</select></label>}
  <OfficeReplayBar office={office} store={store} onFollow={onFollow} following={following}/>
  <details className="harness-setup"><summary>재생 조작은 언제 쓰나요?</summary><dl className="record-help"><dt>세션 선택</dt><dd>여러 번 실행한 작업 중 확인할 대화를 고릅니다.</dd><dt>1~64배속</dt><dd>긴 실행 기록을 빠르게 훑습니다. 실제 AI 처리 속도는 변하지 않습니다.</dd><dt>시간 이동</dt><dd>오류가 난 순간이나 특정 단계로 바로 이동합니다. 타임라인에 초점을 두고 방향키로도 이동할 수 있습니다.</dd><dt>빈 시간 건너뛰기</dt><dd>기록상 작업이 없는 긴 구간을 넘어 다음 작업을 확인합니다.</dd></dl></details>
  {office.result.value&&<section className="office-result-card"><h2>연결된 결과</h2><p>{office.result.value.export_name||'저장된 결과 화면'}</p><a href={RESULT_VIEW_URL} target="_blank" rel="noopener"><ExternalLink size={14}/>결과 화면 열기</a></section>}
  <div className="button-row"><button onClick={onDemo}><ArrowLeft size={14}/>상품기획 화면으로</button></div>
 </div>;
}
