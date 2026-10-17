/** The factory's file:// observation: live.js next to the page (re-read every second), the result viewer's
 * view-data.js (every 4 s), replay of a recorded session, and records files the viewer opens. Read-only; it never
 * starts AI work. The {snapshot, connection, view} contract is the same one ReleaseDashboard draws for the server. */
import {deriveReleaseView} from './release.js';
import {officeSnapshot,prepareEvents,parseRecordFile,validLiveFile,resultMetadata,sessionsOf,busyIntervals,quietUntil} from './office-records.js';

export const SPEEDS=[1,4,8,16,32,64];
export const RESULT_VIEW_URL='../visual-viewer/index.html';
const ROLE_IDS=new Set(['product_official_researcher','product_review_researcher','product_evidence_reviewer']);
const SKILL_IDS=new Set(['evidence-retrieval','web-evidence-collection','needs-structuring','feature-comparison','concept-writing','review-and-revise']);

/** A <script src> read of a file that assigns window[key]. Only this request's own assignment is accepted. */
export function scriptTransport(url,key,validate){
  return (ok,fail)=>{
    let active=true,raw,assigned=false;
    const tag=document.createElement('script'),previous=Object.getOwnPropertyDescriptor(window,key);
    const get=()=>previous?.get?previous.get.call(window):previous?.value;
    const set=next=>{if(active&&document.currentScript===tag){raw=next;assigned=true;}};
    Object.defineProperty(window,key,{configurable:true,get,set});
    const cleanup=()=>{
      if(!active)return;active=false;tag.onload=null;tag.onerror=null;tag.remove();
      const current=Object.getOwnPropertyDescriptor(window,key);
      if(current?.get!==get||current?.set!==set)return;
      if(previous)Object.defineProperty(window,key,previous);else delete window[key];
    };
    tag.src=`${url}?ts=${Date.now()}`;tag.charset='utf-8';
    tag.onload=()=>{if(!active)return;let value=null;try{value=assigned?validate(raw):null;}catch{value=null;}cleanup();value?ok(value):fail('invalid');};
    tag.onerror=()=>{if(active){cleanup();fail('unavailable');}};
    document.head.appendChild(tag);
    return cleanup;
  };
}

function laneOf(event){
  if(event.kind==='delegate'||event.kind==='handback'||ROLE_IDS.has(event.actor))return 'roles';
  if(SKILL_IDS.has(event.node))return 'skills';
  if(event.kind==='web')return 'web';
  if(event.kind==='shell'||event.kind==='file')return 'tools';
  return 'main';
}
/** The replay strip of one session: calls by lane, open turns, requests and DB moments. */
export function stripModel(events,db){
  const spans=[],open=new Map(),closed=new Set(),points=[];let turn=null;
  for(const event of events){
    const t=Date.parse(event.ts),key=event.kind==='subagent'?'agent:'+(event.agent_id||event.actor):event.call;
    if(key&&event.phase==='start'){if(closed.has(key))continue;open.set(key,{lane:event.kind==='subagent'?'roles':laneOf(event),start:t,end:null,status:'open'});spans.push(open.get(key));}
    else if(key&&['end','fail'].includes(event.phase)){const span=open.get(key),status=event.phase==='fail'||event.detail.accepted===false?'failed':'done';if(span){span.end=t;span.status=status;open.delete(key);}else if(event.kind!=='subagent'){spans.push({lane:laneOf(event),start:t,end:t,status});closed.add(key);}}
    if(event.actor==='main'&&!event.agent_id){
      if(event.kind==='request'){points.push({lane:'db',t,kind:'request'});turn??=t;}
      if(['handback_delivered','notification'].includes(event.kind))turn??=t;
      if(['turn_end','turn_cancelled'].includes(event.kind)){points.push({lane:'main',t,kind:event.kind});if(turn!=null)spans.push({lane:'turn',start:turn,end:t,status:'turn'});turn=null;}
    }
  }
  if(turn!=null)spans.push({lane:'turn',start:turn,end:null,status:'turn'});
  if(db?.binding_status==='matched'){
    for(const item of db.workflow_events||[])points.push({lane:'db',t:Date.parse(item.observed_at),kind:'db'});
    for(const item of db.candidates||[])if(item.created_at)points.push({lane:'db',t:Date.parse(item.created_at),kind:'db'});
  }
  return {spans,points:points.filter(p=>Number.isFinite(p.t))};
}
export function readHash(hash){const params=new URLSearchParams(String(hash||'').replace(/^#/,''));return {mode:['replay','live'].includes(params.get('mode'))?params.get('mode'):null,s:Number(params.get('s')),t:params.has('t')?Number(params.get('t')):null,play:params.get('play'),speed:Number(params.get('speed')),sel:params.get('sel')};}

export class OfficeStore{
  #state;#listeners=new Set();#options;#timers=new Map();#cancel={};#records={live:null,file:null};#prepared=new Map();#lastTick=0;#lastLivePublish=0;#busy=[];#started=false;
  constructor(options={}){
    this.#options={pollFiles:true,pollMs:1000,resultMs:4000,tickMs:125,staleMs:20000,clock:()=>Date.now(),setTimer:(fn,ms)=>setTimeout(fn,ms),clearTimer:id=>clearTimeout(id),
      liveTransport:scriptTransport('live.js','LGAX_OFFICE_LIVE',validLiveFile),resultTransport:scriptTransport('../visual-viewer/view-data.js','LGAX_VIEW',resultMetadata),hash:typeof location==='object'?location.hash:'',...options};
    const deep=readHash(this.#options.hash);
    this.#state={snapshot:null,connection:{status:'connecting',url:'live.js',lastReceivedAt:null,error:null},view:deriveReleaseView(null,{status:'connecting'},this.#options.clock()),
      office:{pollFiles:this.#options.pollFiles,mode:deep.mode==='replay'?'replay':'live',deep,read:{status:'waiting',lastSuccessAt:null,error:null},file:null,note:null,sessions:[],sessionId:null,at:null,start:null,end:null,playing:deep.play!=='0',speed:SPEEDS.includes(deep.speed)?deep.speed:8,skipQuiet:true,skipped:null,strip:{spans:[],points:[]},release:null,result:{value:null,error:null,lastSuccessAt:null}}};
    this.getSnapshot=()=>this.#state;
    this.subscribe=listener=>{this.#listeners.add(listener);return()=>this.#listeners.delete(listener);};
  }
  start(){if(this.#started)return;this.#started=true;if(this.#options.pollFiles){this.#readLive();this.#readResult();}this.#tick();}
  stop(){this.#started=false;for(const id of this.#timers.values())this.#options.clearTimer(id);this.#timers.clear();Object.values(this.#cancel).forEach(cancel=>cancel?.());this.#cancel={};}
  #later(name,fn,ms){if(this.#timers.has(name))this.#options.clearTimer(this.#timers.get(name));if(this.#started)this.#timers.set(name,this.#options.setTimer(()=>{this.#timers.delete(name);fn();},ms));}
  #source(){return this.#state.office.mode==='replay'&&this.#records.file?this.#records.file:this.#records.live;}
  #prepare(source){if(!source)return {events:[],dropped:0};if(!this.#prepared.has(source))this.#prepared.set(source,prepareEvents(source.events));return this.#prepared.get(source);}
  #readLive(){
    this.#cancel.live?.();
    const done=()=>{this.#cancel.live=null;this.#later('live',()=>this.#readLive(),this.#options.pollMs);};
    try{
      this.#cancel.live=this.#options.liveTransport(live=>{
        const changed=JSON.stringify([live.written_at,live.events.length,live.events.at(-1)?.id,live.db?.read_at])!==this.#records.live?.identity;
        if(changed){this.#prepared.delete(this.#records.live);this.#records.live={events:live.events,db:live.db??null,writtenAt:live.written_at,release:live.harness_release??null,name:'live.js',identity:JSON.stringify([live.written_at,live.events.length,live.events.at(-1)?.id,live.db?.read_at])};}
        this.#patchOffice({read:{status:'ready',lastSuccessAt:this.#options.clock(),error:null}});
        this.#publish();done();
      },error=>{this.#patchOffice({read:{...this.#state.office.read,status:'error',error}});this.#publish();done();});
    }catch{this.#patchOffice({read:{...this.#state.office.read,status:'error',error:'unavailable'}});this.#publish();done();}
  }
  #readResult(){
    this.#cancel.result?.();
    const done=()=>{this.#cancel.result=null;this.#later('result',()=>this.#readResult(),this.#options.resultMs);};
    try{
      this.#cancel.result=this.#options.resultTransport(value=>{this.#patchOffice({result:{value,error:null,lastSuccessAt:this.#options.clock()}});this.#emit();done();},
        error=>{this.#patchOffice({result:{...this.#state.office.result,error}});this.#emit();done();});
    }catch{done();}
  }
  #tick(){
    const now=this.#options.clock(),dt=this.#lastTick?Math.min(250,now-this.#lastTick):0;this.#lastTick=now;
    const office=this.#state.office;
    if(office.mode==='replay'&&office.playing&&office.at!=null){
      let at=office.at+dt*office.speed,skipped=office.skipped&&now-office.skipped.at<2500?office.skipped:null;
      const next=office.skipQuiet?quietUntil(this.#busy,at):null;
      if(next!=null&&next-at>2000*office.speed){const lead=600*office.speed;skipped={ms:next-lead-at,at:now};at=next-lead;}
      const playing=at<office.end;this.#patchOffice({at:Math.min(at,office.end),playing,skipped});this.#publish();
    }else if(office.mode==='live'&&now-(this.#lastLivePublish||0)>=1000)this.#publish();
    this.#later('tick',()=>this.#tick(),this.#options.tickMs);
  }
  #patchOffice(patch){this.#state={...this.#state,office:{...this.#state.office,...patch}};}
  #emit(){this.#listeners.forEach(listener=>listener());}
  #publish(){
    const office=this.#state.office,source=this.#source(),now=this.#options.clock(),prepared=this.#prepare(source);
    const sessions=sessionsOf(prepared.events,true);
    let sessionId=office.sessionId,at=office.at;
    if(office.mode==='live'){sessionId=sessions.at(-1)?.id||null;at=null;this.#lastLivePublish=now;}
    else if(!sessions.some(s=>s.id===sessionId)){
      const deep=office.deep,index=Number.isInteger(deep.s)&&deep.s>=1&&deep.s<=sessions.length?deep.s-1:sessions.length-1;
      sessionId=sessions[index]?.id||null;const s=sessions[index];at=s?(deep.t!=null&&Number.isFinite(deep.t)&&!office.deepUsed?Math.min(s.end,s.start+deep.t*1000):s.start):null;
      this.#patchOffice({deepUsed:true});
    }
    const session=sessions.find(s=>s.id===sessionId)||null;
    const scoped=session?prepared.events.filter(e=>e.session===session.id):[];
    this.#busy=busyIntervals(scoped);
    const snapshot=source?officeSnapshot({prepared,db:source.db,release:source.release,writtenAt:source.writtenAt,origin:office.mode==='replay'?'office_replay':'office_live',session:office.mode==='replay'?sessionId:null,at:office.mode==='replay'?at:null,now}):null;
    const read=office.read,lastReceivedAt=office.mode==='replay'?(at!=null?new Date(at).toISOString():null):read.lastSuccessAt?new Date(read.lastSuccessAt).toISOString():null;
    // Before the first hook there is no live.js yet: that is an empty record set, not a broken page.
    const missing=office.mode==='live'&&!source&&read.error==='unavailable';
    const status=!this.#options.pollFiles&&!source?'disconnected':office.mode==='replay'?(snapshot?'connected':'disconnected'):read.lastSuccessAt?(read.error&&now-read.lastSuccessAt>this.#options.staleMs?'error':'connected'):missing?'connected':read.error?'error':'connecting';
    const empty=missing?officeSnapshot({events:[],origin:'office_live',now}):null;
    const connection={status,origin:office.mode==='replay'?'office_replay':'office_live',url:source?.name||'live.js',lastReceivedAt:lastReceivedAt||(missing?new Date(now).toISOString():null),error:status==='error'?'관측 파일(live.js)을 읽지 못했습니다. 이 화면이 runtime-data/agent-office 폴더에 있는지 확인하세요.':null,staleAfterMs:office.mode==='replay'?Infinity:this.#options.staleMs,sourceStaleAfterMs:120000};
    let view;
    try{view=deriveReleaseView(snapshot||empty,connection,office.mode==='replay'?(at??now):now);}catch{view=deriveReleaseView(null,{...connection,status:'error',error:'관측 기록의 형식을 읽지 못했습니다.'},now);}
    const strip=session?stripModel(scoped,snapshot?.db):{spans:[],points:[]};
    this.#state={snapshot:snapshot||empty,connection,view,office:{...office,missing,sessions,sessionId,at,start:session?.start??null,end:session?(office.mode==='live'?Math.max(session.end,now):session.end):null,strip,release:snapshot?.source.release??null,dropped:prepared.dropped}};
    this.#emit();
  }
  refresh(){if(this.#options.pollFiles)this.#readLive();else this.#publish();return Promise.resolve(null);}
  connect(){return Promise.reject(new Error('파일 보기에서는 읽기 서버에 연결하지 않습니다.'));}
  disconnect(){}
  goLive(){this.#records.file=null;this.#patchOffice({mode:'live',file:null,note:null,skipped:null});this.#publish();}
  replay(sessionId=null,at=null){
    const sessions=this.#state.office.sessions,s=sessions.find(item=>item.id===(sessionId??this.#state.office.sessionId))||sessions.at(-1);if(!s)return;
    this.#patchOffice({mode:'replay',sessionId:s.id,at:at??s.start,playing:at==null,deepUsed:true});this.#publish();
  }
  selectSession(id){const s=this.#state.office.sessions.find(item=>item.id===id);if(!s)return;this.#patchOffice({mode:'replay',sessionId:id,at:s.start,playing:true,deepUsed:true,skipped:null});this.#publish();}
  seek(t){const office=this.#state.office,session=office.sessions.find(s=>s.id===office.sessionId);if(office.start==null||!session)return;const at=Math.min(Math.max(t,session.start),session.end);
    if(office.mode==='live'){this.#patchOffice({mode:'replay',at,playing:false,deepUsed:true});}else this.#patchOffice({at,skipped:null});this.#publish();}
  play(value){const office=this.#state.office;if(office.mode!=='replay')return;this.#patchOffice({playing:value,at:value&&office.at>=office.end?office.start:office.at});this.#publish();}
  setSpeed(speed){if(SPEEDS.includes(speed)){this.#patchOffice({speed});this.#emit();}}
  setSkipQuiet(value){this.#patchOffice({skipQuiet:Boolean(value)});this.#emit();}
  openFile(text,name){
    let parsed;try{parsed=parseRecordFile(text);}catch{parsed={events:[],skipped:0};}
    const usable=prepareEvents(parsed.events);
    if(!usable.events.length){this.#patchOffice({note:'이 파일에는 읽을 수 있는 실행 기록이 없습니다. events.jsonl 또는 live.js를 선택해 주세요. 기존 기록은 유지됩니다.'});this.#emit();return false;}
    this.#records.file={events:parsed.events,db:parsed.live?.db??null,writtenAt:parsed.live?.written_at??null,release:parsed.live?.harness_release??null,name:String(name||'기록 파일').slice(0,120)};
    const skipped=parsed.skipped+usable.dropped;
    this.#patchOffice({mode:'replay',sessionId:null,at:null,playing:true,deepUsed:true,file:{name:this.#records.file.name,events:usable.events.length,db:Boolean(parsed.live?.db)},note:`${this.#records.file.name}: 사건 ${usable.events.length}개를 재생합니다.${parsed.live?'':' 이 파일에는 DB 정보가 없습니다.'}${skipped?` 읽을 수 없는 항목 ${skipped}개는 제외했습니다.`:''}`});
    this.#publish();return true;
  }
  dismissNote(){this.#patchOffice({note:null});this.#emit();}
}
export function createOfficeStore(options){return new OfficeStore(options);}
