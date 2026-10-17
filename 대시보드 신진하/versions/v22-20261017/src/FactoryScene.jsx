import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { createResearchers } from './ResearcherCharacters.js';
import {factoryLayout,fitFactory,transitionFactory,fieldToWorld,ZONE_IDS,ALL_ZONE_IDS,ZONE_FLOOR,PLANNER_FLOOR} from './factory-layout.js';
import './factory-scene.css';
import {createSkillWorkAnimations} from './skill-work-animations.js';
import {SKILL_BY_ROOM} from './skill-catalog.js';
import {Wrench,UserRound} from 'lucide-react';
import {arrangeLabelRects,intersects} from './factory-label-layout.js';
import {buildWorkroom} from './factory-workshop.js';
import {createWorkshopArtwork} from './WorkshopArtwork.js';
import {composeWorkshopLayout} from './workshop-composition.js';
import {createLabEnvironment} from './lab-environment.js';
import './approved-workshops.css';
import {createPremiumLab,batchLabFurniture} from './premium-lab.js';

const STATIONS = [
  { id: 'retrieve', no: '01', title: '자료 조회', caption: '리뷰 · 제품 문서 수집', x: -5.9, z: .1, labelY: 3.04, labelZ: -1.30 },
  { id: 'structure', no: '02', title: '니즈 구조화', caption: '고객의 불편을 구조화', x: -2.9, z: -4.9, labelY: 3.04, labelZ: -1.30 },
  { id: 'compare', no: '03', title: '기능 대조', caption: '기존 기능과 남은 불편', x: 3.4, z: -4.05, labelY: 3.04, labelZ: -1.30 },
  { id: 'concept', no: '04', title: '콘셉트 작성', caption: '근거에서 새로운 가능성으로', x: 5.3, z: 1.9, labelY: 3.04, labelZ: -1.30 },
  { id: 'validate', no: '05', title: '검토 · 수정', caption: '근거와 요구사항 최종 점검', x: -1.05, z: 5.7, labelY: 3.04, labelZ: -1.30 },
  { id: 'web', no: '06', title: '웹 근거 수집', caption: '인터넷에서 자료를 찾아요', x: -14, z: -7.7, labelY: 3.04, labelZ: -1.30 },
];
const COLORS = { dark: '#344e43', slate: '#80978b', base: '#eeeee4', white: '#f7f5ec', steel: '#b6c3b8', orange: '#fc762c', green: '#219464', blue: '#3a98b9' };
function stageStatus(value) {
  const s = typeof value === 'object' ? value?.status : value;
  if (['complete', 'completed', 'done', 'passed', 'succeeded'].includes(s)) return 'done';
  if (['running', 'active', 'processing'].includes(s)) return 'running';
  if (s === 'reporting') return 'reported';
  if (s === 'helper') return 'helper';
  if (s === 'paused') return 'paused';
  if (s === 'stopped') return 'stopped';
  if (['awaiting', 'needs_input', 'needs_confirmation', 'awaiting_confirmation'].includes(s)) return 'awaiting';
  if (['failed', 'error', 'blocked'].includes(s)) return 'error';
  return 'pending';
}
function statusText(s) { return { done: '완료', running: '실행 중', reported:'진행 보고', helper:'도우미 작업', paused: '일시정지', stopped: '중지됨', awaiting: '확인 필요', error: '확인 필요', pending: '대기' }[s]; }

function createFactory(renderer) {
  const scene = new THREE.Scene();
  const materials = new Map(), geometries = new Map(), resources = [];
  const mat = (color, roughness = .55, metalness = 0) => {
    const key = `${color}:${roughness}:${metalness}`;
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({ color, roughness, metalness }));
    return materials.get(key);
  };
  const roundedGeo = (w, h, d, radius = .07) => {
    const key = `round:${w},${h},${d},${radius}`;
    if (geometries.has(key)) return geometries.get(key);
    const r = Math.min(radius, w / 4, h / 4, d / 4), shape = new THREE.Shape();
    const x = -w / 2 + r, y = -h / 2 + r, right = w / 2 - r, top = h / 2 - r;
    shape.moveTo(x, y - r); shape.lineTo(right, y - r); shape.quadraticCurveTo(right + r, y - r, right + r, y);
    shape.lineTo(right + r, top); shape.quadraticCurveTo(right + r, top + r, right, top + r);
    shape.lineTo(x, top + r); shape.quadraticCurveTo(x - r, top + r, x - r, top);
    shape.lineTo(x - r, y); shape.quadraticCurveTo(x - r, y - r, x, y - r);
    const g = new THREE.ExtrudeGeometry(shape, { depth: d - r * 2, bevelEnabled: true, bevelSegments: 2, steps: 1, bevelSize: r * .4, bevelThickness: r, curveSegments: 3 });
    g.translate(0, 0, -d / 2 + r); g.computeVertexNormals(); geometries.set(key, g); return g;
  };
  const cube = (parent, w, h, d, x, y, z, color = COLORS.white, radius = .045, metal = 0) => {
    const mesh = new THREE.Mesh(roundedGeo(w, h, d, radius), mat(color, .48, metal));
    mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh;
  };
  const cylinder = (parent, r, h, x, y, z, color, r2 = r, segments = 20) => {
    const key = `cyl:${r},${r2},${h},${segments}`;
    if (!geometries.has(key)) geometries.set(key, new THREE.CylinderGeometry(r, r2, h, segments));
    const m = new THREE.Mesh(geometries.get(key), mat(color, .4, .15)); m.position.set(x,y,z); m.castShadow=true; m.receiveShadow=true; parent.add(m); return m;
  };
  const sphere = (parent, r, x,y,z,color,scale=[1,1,1]) => {
    const key = `sphere:${r}`; if(!geometries.has(key)) geometries.set(key,new THREE.SphereGeometry(r,10,8));
    const m = new THREE.Mesh(geometries.get(key),mat(color,.8)); m.position.set(x,y,z); m.scale.set(...scale); m.castShadow=true; parent.add(m); return m;
  };
  const strip = (parent, a, b, y, width, color) => {
    const dx = b[0]-a[0], dz=b[1]-a[1];
    const m = cube(parent,width,.018,Math.hypot(dx,dz), (a[0]+b[0])/2,y,(a[1]+b[1])/2,color,.002); m.rotation.y=Math.atan2(dx,dz); return m;
  };
  const canvasTexture = (draw, w=512,h=256) => {
    const c = document.createElement('canvas'); c.width=w;c.height=h;const ctx=c.getContext('2d');draw(ctx,w,h);
    const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=Math.min(4,renderer.capabilities.getMaxAnisotropy());resources.push(t);return t;
  };
  const screenTexture = canvasTexture((ctx,w,h)=>{
    ctx.fillStyle='#123440';ctx.fillRect(0,0,w,h);ctx.fillStyle='#63d7e1';ctx.font='bold 27px sans-serif';ctx.fillText('KITCHEN / AX',28,43);
    for(let i=0;i<6;i++){ctx.fillStyle=i%2?'#247083':'#2c8596';ctx.fillRect(28,71+i*24,100+(i*57)%196,10);}
    ctx.strokeStyle='#9ee1c2';ctx.lineWidth=4;ctx.beginPath();for(let i=0;i<11;i++){const x=315+i*15,y=170-Math.sin(i*.8)*40-i*6;i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();
    ctx.fillStyle='#ffb761';ctx.fillRect(316,207,155,6);
  });
  const boardTexture = (kind) => canvasTexture((ctx,w,h)=>{
    ctx.fillStyle='#fbfcf8';ctx.fillRect(0,0,w,h);ctx.fillStyle='#253943';ctx.font='bold 28px sans-serif';ctx.fillText(kind==='blueprint'?'CONCEPT STUDY':kind==='check'?'QUALITY CHECK':kind==='compare'?'FEATURE REVIEW':kind==='web'?'WEB RESEARCH':'CUSTOMER NEEDS',27,43);
    ctx.fillStyle='#f47732';ctx.fillRect(26,58,w-52,4);
    if(kind==='sticky'){
      const items=[['수납 · 정리','#e8f1b3'],['세척 불편','#f1dfb4'],['사용 조건','#bad7d0'],['모델 구분','#c9d5ec'],['잔여 불편','#f2c6c1'],['원문 연결','#d0e1cb']];
      items.forEach((a,i)=>{const x=25+(i%3)*158,y=83+Math.floor(i/3)*85;ctx.fillStyle=a[1];ctx.fillRect(x,y,145,71);ctx.fillStyle='#354849';ctx.font='bold 21px sans-serif';ctx.fillText(a[0],x+13,y+39);});
    }else if(kind==='compare'){
      ['기존 제품 기능','사용 조건','남은 불편','연결된 원문'].forEach((text,i)=>{ctx.strokeStyle='#b4c3ac';ctx.lineWidth=2;ctx.strokeRect(30,82+i*42,20,20);ctx.fillStyle='#52664d';ctx.font='22px sans-serif';ctx.fillText(text,65,102+i*42);});
    }else if(kind==='check'){
      ['모델 · 기능 일치','원문 근거 확인','중복 후보 제외','요구사항 연결'].forEach((t,i)=>{ctx.fillStyle='#239a73';ctx.fillRect(29,81+i*40,21,21);ctx.fillStyle='#fff';ctx.font='bold 18px sans-serif';ctx.fillText('✓',31,98+i*40);ctx.fillStyle='#34464a';ctx.font='21px sans-serif';ctx.fillText(t,66,100+i*40);});
    }else{
      ctx.strokeStyle='#87a9ba';ctx.lineWidth=2;for(let j=0;j<3;j++){const x=42+j*159;ctx.strokeRect(x,91,101,133);ctx.strokeRect(x+9,101,83,45);ctx.strokeRect(x+9,158,83,55);ctx.beginPath();ctx.moveTo(x+48,92);ctx.lineTo(x+48,223);ctx.stroke();ctx.fillStyle='#bfccd1';ctx.fillRect(x+17,235,68,5);}
    }
  },512,280);
  const textures = { sticky:boardTexture('sticky'), check:boardTexture('check'), blueprint:boardTexture('blueprint'), compare:boardTexture('compare'), web:boardTexture('web') };
  const board = (group,kind,x,y,z,w=2.5,h=1.52) => {
    lab.wood(cube(group,w+.15,h+.16,.12,x,y,z,'#c5b18a',.045,.15));
    cube(group,w+.08,h+.08,.025,x,y,z+.063,'#f4f1e5',.025);
    const material=new THREE.MeshStandardMaterial({map:textures[kind],roughness:.75});resources.push(material);
    const plane=new THREE.Mesh(new THREE.PlaneGeometry(w,h),material);resources.push(plane.geometry);plane.position.set(x,y,z+.095);group.add(plane);
    for(const dx of [-w*.38,w*.38]){cube(group,.065,y-h/2,.065,x+dx,(y-h/2)/2,z,COLORS.slate,.012,.4);cube(group,.38,.055,.36,x+dx,.12,z,COLORS.slate);}
  };
  const monitor = (group,x,y,z,scale=1) => {
    cube(group,.62*scale,.41*scale,.085*scale,x,y,z,COLORS.dark,.03);
    const material=new THREE.MeshStandardMaterial({map:screenTexture,emissive:'#1a6370',emissiveIntensity:.22,roughness:.5});resources.push(material);
    const g=new THREE.PlaneGeometry(.53*scale,.31*scale);resources.push(g);const s=new THREE.Mesh(g,material);s.position.set(x,y,z+.049*scale);group.add(s);
    cube(group,.05*scale,.22*scale,.05*scale,x,y-.29*scale,z,COLORS.slate);
    cube(group,.32*scale,.035*scale,.2*scale,x,y-.4*scale,z+.035,COLORS.slate);
  };
  const lab=createPremiumLab({cube,cylinder,canvasTexture,resources});
  const plant=lab.plant;
  scene.add(new THREE.HemisphereLight('#fffaf0','#a69f88',1.45));
  const sun=new THREE.DirectionalLight('#fff3db',3.2);sun.position.set(-12,22,-23);sun.castShadow=true;
  sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-29;sun.shadow.camera.right=29;sun.shadow.camera.top=27;sun.shadow.camera.bottom=-27;sun.shadow.camera.near=.5;sun.shadow.camera.far=90;
  sun.shadow.normalBias=.018;sun.shadow.bias=-.00015;sun.shadow.radius=4;scene.add(sun);
  const fill=new THREE.DirectionalLight('#edf2ee',.8);fill.position.set(13,9,12);scene.add(fill);
  const floor=new THREE.Group();scene.add(floor);const fieldProps=[];
  const groundMaterial=new THREE.MeshStandardMaterial({map:lab.tile,bumpMap:lab.tile,bumpScale:.018,roughness:.56,metalness:.035,color:'#fffdf9'});resources.push(groundMaterial);
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(512,512),groundMaterial);ground.rotation.x=-Math.PI/2;ground.position.y=-.012;ground.receiveShadow=true;floor.add(ground);
  const workshopTools={cube,cylinder,monitor,board,plant,mat,resources,canvasTexture,lab};
  const environment=createLabEnvironment(scene,workshopTools);

  const stations = {};
  const stationRims=[];
  const platform=(s)=>{
    const group=new THREE.Group();group.position.set(s.x,0,s.z);group.userData.station=s.id;scene.add(group);stations[s.id]=group;
    lab.shade(group,6.7,5.9);
    cube(group,ZONE_FLOOR.halfX*2,.28,ZONE_FLOOR.halfZ*2,0,.22,0,'#7b8e7d',.14,.12);
    cube(group,5.54,.045,4.74,0,.375,0,'#cbb992',.045,.2);
    cube(group,5.48,.13,4.68,0,.445,0,'#fffcf4',.08);
    const rimMaterial=new THREE.MeshStandardMaterial({color:'#b6c7bb',emissive:'#fc8b30',emissiveIntensity:0,roughness:.4});resources.push(rimMaterial);
    const rimPart=(w,h,d,x,y,z)=>{const m=new THREE.Mesh(roundedGeo(w,h,d,.015),rimMaterial);m.position.set(x,y,z);group.add(m);};
    for(const [w,d,x,z] of [[5.42,.065,0,-2.28],[.065,4.56,-2.68,0],[.065,4.56,2.68,0],[1.95,.065,-1.73,2.28],[1.95,.065,1.73,2.28]])rimPart(w,.065,d,x,.66,z);
    for(const x of [-2.66,2.66])for(const z of [-2.26,2.26]){rimPart(.075,.30,.075,x,.79,z);rimPart(.13,.045,.13,x,.96,z);}
    const glowMaterial=new THREE.MeshBasicMaterial({color:'#ffb14d',transparent:true,opacity:0,depthWrite:false,blending:THREE.AdditiveBlending});resources.push(glowMaterial);
    for(const [w,d,x,z] of [[5.4,.23,0,-2.28],[.23,4.56,-2.68,0],[.23,4.56,2.68,0],[1.95,.23,-1.73,2.28],[1.95,.23,1.73,2.28]]){const glow=new THREE.Mesh(roundedGeo(w,.025,d,.01),glowMaterial);glow.position.set(x,.51,z);group.add(glow);}
    for(const x of [-1.32,1.32]){cube(group,.055,2.52,.065,x,1.78,-1.30,'#b8aa87',.01,.4);cube(group,.11,.08,.12,x,3.01,-1.30,'#ded0ad');}
    cube(group,2.80,.07,.10,0,3.00,-1.30,'#b3a17c',.018,.3);
    stationRims.push({id:s.id,material:rimMaterial,glowMaterial,group});
    for(const x of [-2.46,2.46])for(const z of [-2.08,2.08])cube(group,.25,.23,.28,x,.15,z,'#657b71');
    plant(group,-2.42,-2.02,.72);plant(group,2.42,2.02,.65);
    const interior=new THREE.Group();interior.position.y=.10;group.add(interior);
    return interior;
  };
  const roomParts={};
  STATIONS.forEach(s=>{const room=platform(s);roomParts[s.id]=buildWorkroom(s.id,room,workshopTools);batchLabFurniture(room,resources);});

  const center = new THREE.Group();center.userData.station='overview';scene.add(center);stations.overview=center;
  lab.shade(center,3.8,3.45);
  cube(center,3,.22,2.7,0,.22,0,'#728474',.17,.2);cube(center,2.82,.12,2.5,0,.4,0,'#faf8ee',.1);
  for(const x of [-1.18,1.18])cube(center,.23,.05,1.96,x,.49,0,'#e5b14e');
  cube(center,1.47,1.37,1.27,0,1.12,-.07,'#e6e9e2',.13,.1);
  cube(center,.97,.46,.055,0,1.39,.6,'#304b55',.025);
  monitor(center,.88,1.52,.2,.73);
  cube(center,.55,.23,.55,-.89,.72,.4,'#ced7d2',.05,.3);
  cylinder(center,.3,.1,-.89,.87,.4,'#e4ede9');
  const beacon=cylinder(center,.105,.23,0,1.96,-.09,'#ff8f30');const beaconMaterial=new THREE.MeshStandardMaterial({color:'#ff9f2f',emissive:'#ff6200',emissiveIntensity:1.3,roughness:.25});resources.push(beaconMaterial);beacon.material=beaconMaterial;cylinder(center,.17,.045,0,1.825,-.09,'#4f6269');
  lab.wood(cube(center,.54,.06,.15,-.22,1.81,.34,'#c5d4cf'));
  cube(center,.44,.22,.04,0,.91,.62,'#f47b34');
  const plannerActivity=new THREE.Group();center.add(plannerActivity);plannerActivity.visible=false;
  const plannerGlow=new THREE.MeshStandardMaterial({color:'#ff9b3b',emissive:'#f47c18',emissiveIntensity:.75,roughness:.45});resources.push(plannerGlow);
  for(const [w,d,x,z]of [[2.85,.065,0,1.23],[2.85,.065,0,-1.23],[.065,2.45,-1.42,0],[.065,2.45,1.42,0]]){const strip=cube(plannerActivity,w,.06,d,x,.52,z,'#ff9b3b',.01);strip.material=plannerGlow;}
  const plannerInterior=new THREE.Group();for(const child of [...center.children])plannerInterior.add(child);center.add(plannerInterior);plannerInterior.scale.setScalar(1.65);
  const packets=[],links=[];
  const addConveyor=(end,index)=>{
    const e=new THREE.Vector3(end.x,0,end.z),dir=e.clone().normalize(),start=dir.clone().multiplyScalar(1.7),finish=e.clone().addScaledVector(dir,-1.8),len=start.distanceTo(finish);
    const belt=new THREE.Group();belt.position.copy(start).add(finish).multiplyScalar(.5);belt.rotation.y=Math.atan2(dir.x,dir.z);scene.add(belt);
    cube(belt,.78,.10,len,0,.35,0,'#becabd',.025,.2);
    const glass=cube(belt,.65,.035,len,0,.422,0,'#c8dfd0',.012,.2);
    const glassMaterial=new THREE.MeshPhysicalMaterial({color:'#e4dfcc',roughness:.26,metalness:.28,transparent:true,opacity:.88});glass.material=glassMaterial;resources.push(glassMaterial);
    for(const x of [-.35,.35])cube(belt,.035,.045,len,x,.45,0,'#f7f4dd',.008,.3);
    for(let j=0;j<Math.ceil(len/.62);j++){const dash=cube(belt,.20,.012,.06,0,.448,-len/2+(j+.5)*len/Math.ceil(len/.62),'#f5df9b',.005);dash.material=mat('#f5df9b',.25,.15);}
    for(let j=0;j<3;j++){const packet=new THREE.Group();
     cube(packet,.24,.115,.29,0,.075,0,'#e5d0a8',.014);cube(packet,.04,.12,.30,0,.078,0,'#f7ebd1',.003);cube(packet,.12,.012,.10,.045,.137,.04,'#fdf8e8',.002);
     const m=new THREE.MeshBasicMaterial({color:'#ffd17a',transparent:true,opacity:.9,depthWrite:false});resources.push(m);
     for(const side of [-1,1]){const arrow=cube(packet,.035,.013,.16,side*.045,0,0,'#ffd17a',.002);arrow.rotation.y=side*.55;arrow.material=m;}
     scene.add(packet);packets.push({mesh:packet,start,finish,phase:j/3+index*.11,id:end.id});}
    links.push({group:belt,baseLength:len,start,finish,id:end.id});
  };
  STATIONS.forEach(addConveyor);
  // All path surfaces are drawn behind the room/people illustration.
  links.forEach(link=>link.group.traverse(m=>{if(m.isMesh)m.renderOrder=-4;}));
  packets.forEach(p=>p.mesh.traverse(m=>{if(m.isMesh)m.renderOrder=-3;}));
  const artwork=createWorkshopArtwork(stations);
  return {
    scene, stations, stationRims, packets, links, fieldProps, beaconMaterial, plannerActivity, environment,
    artwork,
    workMotions:createSkillWorkAnimations(stations,workshopTools,roomParts,artwork),
    dispose(){this.artwork.dispose();scene.traverse(o=>{if(o.isInstancedMesh)o.dispose();if(o.isMesh){if(o.geometry&&!Array.from(geometries.values()).includes(o.geometry))o.geometry.dispose();}});geometries.forEach(x=>x.dispose());materials.forEach(x=>x.dispose());resources.forEach(x=>x.dispose?.());},
  };
}

export default function FactoryScene({ selected='overview', onSelect, active=null, stepStates={}, reducedMotion=false, onHome, panelWidth=0, stationLabels={}, centerLabel=null, activeNodes=null, onFrame=null, sceneLabel=null, recording=false, roomIds=ZONE_IDS.slice(1), skillActiveNodes=null, workerAssignments=null, semantics=false, leftInset=0, bottomInset=0 }) {
  const hostRef=useRef(null), labelsRef=useRef({}), leadersRef=useRef({}), dataRef=useRef({ selected, active, stepStates, reducedMotion, onSelect, onHome, panelWidth, activeNodes });
  const [unavailable,setUnavailable]=useState(false);
  const plannerWorking=centerLabel?centerLabel.status==='working':Boolean(activeNodes?.length||active);
  dataRef.current={selected,active,stepStates,reducedMotion,onSelect,onHome,panelWidth,activeNodes,centerLabel,onFrame,recording,roomIds,skillActiveNodes,workerAssignments,leftInset,bottomInset};
  useEffect(()=>{
    const host=hostRef.current;if(!host)return;
    let renderer, factory, frame=0, recordingTimer=0, stopped=false, last=0;
    try{
      renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.6));renderer.setClearColor('#f4ebdd',0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.0;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;
      renderer.domElement.className='factory-webgl';renderer.domElement.setAttribute('aria-hidden','true');host.prepend(renderer.domElement);
      factory=createFactory(renderer);
      host.dataset.researchers='loading';
      factory.researchers=createResearchers(factory.scene,state=>{host.dataset.researchers=state;},factory.stations);
    }catch(err){setUnavailable(true);renderer?.dispose();return;}
    const camera=new THREE.OrthographicCamera(-12,12,12,-12,.1,500),direction=new THREE.Vector3(13,17,18).normalize();
    const target=new THREE.Vector3(0,.35,0),desiredTarget=target.clone(),projection=new THREE.Vector3();
    let width=1,height=1,currentPanelWidth=0,currentLeftInset=0,currentExtent=12,layoutKey='',desiredLayout=null,lastShadow=0;
    let reflow=null,metricAt=0,metricFrames=0,labelLayoutKey='',labelLayout=[];
    const clampPanel=value=>Math.min(Math.max(0,Number(value)||0),Math.max(0,width-280));
    function resize(){const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;width=w;height=h;currentPanelWidth=clampPanel(currentPanelWidth);renderer.setSize(width,height,false);}
    const observer=new ResizeObserver(resize);observer.observe(host);resize();
    currentPanelWidth=clampPanel(dataRef.current.panelWidth);
    const raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2();let down=null;
    function locate(ev){const rect=renderer.domElement.getBoundingClientRect();pointer.set((ev.clientX-rect.left)/rect.width*2-1,-(ev.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hits=raycaster.intersectObjects(factory.scene.children,true);for(const hit of hits){let visible=true;for(let p=hit.object;p;p=p.parent)if(!p.visible)visible=false;if(!visible)continue;let o=hit.object;while(o){if(o.userData.station)return o.userData.station;o=o.parent;}}return null;}
    const pointerDown=e=>{down={x:e.clientX,y:e.clientY};};
    const pointerUp=e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)<6){const id=locate(e);if(id)dataRef.current.onSelect?.(id);}down=null;};
    const pointerMove=e=>{renderer.domElement.style.cursor=locate(e)?'pointer':'default';};
    renderer.domElement.addEventListener('pointerdown',pointerDown);renderer.domElement.addEventListener('pointerup',pointerUp);renderer.domElement.addEventListener('pointermove',pointerMove);
    const onLost=e=>{e.preventDefault();setUnavailable(true);};renderer.domElement.addEventListener('webglcontextlost',onLost);
    const onVisibility=()=>{last=0;};document.addEventListener('visibilitychange',onVisibility);
    let oldSelected='',oldActive='',oldStates='';
    function render(ms){
      if(stopped)return;
      // Explicit video export keeps feeding MediaRecorder when the browser
      // throttles animation frames for an occluded preview window.
      if(dataRef.current.recording)recordingTimer=setTimeout(()=>render(performance.now()),1000/30);
      else frame=requestAnimationFrame(render);
      if(document.hidden&&!dataRef.current.recording)return;
      const {selected:sel,active:activeId,stepStates:states,reducedMotion:reduce,panelWidth:requestedPanelWidth}=dataRef.current;
      const interval=reduce?120:1000/30;if(ms-last<interval)return;const dt=last?Math.min((ms-last)/1000,.08):.033;last=ms;
      const reportedIds=Array.isArray(dataRef.current.activeNodes)?dataRef.current.activeNodes:activeId?[activeId]:[];
      const visibleRoomIds=dataRef.current.roomIds,visibleIds=['overview',...visibleRoomIds],activeIds=[...new Set([...reportedIds,...(dataRef.current.centerLabel?.status==='working'?['overview']:[])])].filter(id=>visibleIds.includes(id)),activeKey=[...activeIds].sort().join('|'),stateKey=JSON.stringify(states),elapsed=ms/1000;
      const smooth=reduce?1:1-Math.exp(-dt*6);
      currentPanelWidth+=(clampPanel(requestedPanelWidth)-currentPanelWidth)*smooth;
      if(Math.abs(currentPanelWidth-clampPanel(requestedPanelWidth))<.1)currentPanelWidth=clampPanel(requestedPanelWidth);
      currentLeftInset+=((Number(dataRef.current.leftInset)||0)-currentLeftInset)*smooth;
      const usableWidth=Math.max(180,width-currentPanelWidth-currentLeftInset),usableRight=width-currentPanelWidth,aspect=width/height;
      const nextKey=[Math.round(usableWidth/4),Math.round(height/4),activeKey,visibleRoomIds.join('|')].join(':');
      if(nextKey!==layoutKey){
        const nextLayout=composeWorkshopLayout(factoryLayout({width,height,panelWidth:currentPanelWidth+currentLeftInset,activeIds,roomIds:visibleRoomIds}));
        if(!desiredLayout||visibleIds.some(id=>{const a=desiredLayout.zones[id],b=nextLayout.zones[id];return !a||Math.abs(a.x-b.x)+Math.abs(a.z-b.z)+Math.abs(a.scale-b.scale)>.001;})){
          const from=desiredLayout?Object.fromEntries(Object.entries(factory.stations).filter(([id])=>visibleIds.includes(id)).map(([id,g])=>[id,{id,x:g.position.x,z:g.position.z,scale:g.scale.x}])):Object.fromEntries(Object.entries(nextLayout.zones).map(([id,g])=>[id,{...g,scale:.01}]));
          reflow={from,at:elapsed};
        }
        desiredLayout=nextLayout;layoutKey=nextKey;host.dataset.fieldLayout=desiredLayout.compact?'compact':'wide';
      }
      const moving=transitionFactory(reflow.from,desiredLayout.zones,elapsed-reflow.at,reduce);
      let changed=false;
      for(const [id,group] of Object.entries(factory.stations))if(!visibleIds.includes(id))group.visible=false;
      for(const [id,dest] of Object.entries(moving)){
        const group=factory.stations[id];if(!group)continue;
        changed=changed||Math.abs(group.position.x-dest.x)+Math.abs(group.position.z-dest.z)+Math.abs(group.scale.x-dest.scale)>.001;
        group.position.set(dest.x,0,dest.z);group.scale.setScalar(dest.scale);group.visible=dest.visible;
      }
      const currentShapes=Object.fromEntries(Object.entries(factory.stations).filter(([id])=>visibleIds.includes(id)).map(([id,g])=>[id,{id,x:g.position.x,z:g.position.z,scale:g.scale.x}]));
      const pausedIds=Object.keys(states).filter(id=>stageStatus(states[id])==='paused');
      const artState=factory.artwork.update({activeIds,pausedIds});
      host.classList.toggle('has-illustrated-workshops',artState.ready);
      host.dataset.workshopArtwork=artState.ready?'ready':artState.error?'fallback':'loading';
      factory.environment.update({...desiredLayout,zones:currentShapes});
      const fitShapes={...currentShapes,...Object.fromEntries(Object.entries(desiredLayout.zones).map(([id,g])=>[id+'-target',g]))};
      const fit=fitFactory(fitShapes,{width,height,panelWidth:currentPanelWidth+currentLeftInset,top:Math.max(width<600?82:68,(host.closest('.fullscreen-app')?.querySelector('.topbar')?.getBoundingClientRect().bottom||0)+10),bottom:Math.max(height<500?54:width<600?72:66,Number(dataRef.current.bottomInset)||0),artwork:artState.ready});
      desiredTarget.set(fit.x,.35,fit.z);target.lerp(desiredTarget,smooth);
      currentExtent=fit.extent>currentExtent?fit.extent:currentExtent+(fit.extent-currentExtent)*smooth;
      camera.zoom=1;camera.left=-currentExtent*aspect;camera.right=currentExtent*aspect;camera.top=currentExtent;camera.bottom=-currentExtent;
      camera.setViewOffset(width,height,(currentPanelWidth-currentLeftInset)/2,0,width,height);
      camera.position.copy(direction).multiplyScalar(Math.max(31,currentExtent*2.1)).add(target);camera.lookAt(target);camera.updateMatrixWorld();
      if(changed&&elapsed-lastShadow>.12){renderer.shadowMap.needsUpdate=true;lastShadow=elapsed;}
      const centerGroup=factory.stations.overview;
      factory.links.forEach(link=>{
        const end=factory.stations[link.id],dir=end.position.clone().sub(centerGroup.position),distance=dir.length();dir.normalize();
        const edge=(g,w,d)=>Math.min(Math.abs(dir.x)>.001?w*g.scale.x/Math.abs(dir.x):Infinity,Math.abs(dir.z)>.001?d*g.scale.x/Math.abs(dir.z):Infinity);
        link.start.copy(centerGroup.position).addScaledVector(dir,edge(centerGroup,1.5,1.35)+.12);
        link.finish.copy(end.position).addScaledVector(dir,-edge(end,ZONE_FLOOR.halfX,ZONE_FLOOR.halfZ)-.12);
        const len=distance-edge(centerGroup,1.5,1.35)-edge(end,ZONE_FLOOR.halfX,ZONE_FLOOR.halfZ)-.24;
        link.group.visible=end.visible&&len>.2;if(!link.group.visible)return;
        link.group.position.copy(link.start).add(link.finish).multiplyScalar(.5);link.group.rotation.y=Math.atan2(dir.x,dir.z);link.group.scale.z=len/link.baseLength;
      });
      factory.fieldProps.forEach(prop=>{prop.group.visible=!(prop.detail&&desiredLayout.compact)&&!Object.values(currentShapes).some(z=>Math.hypot(z.x-prop.x,z.z-prop.z)<(z.id==='overview'?2.0:3.3)*z.scale+(prop.radius||1.0));});
      host.style.setProperty('--zone-label-width',Math.min(width<600?164:166,Math.max(104,(usableWidth-36)/2))+'px');
      host.style.setProperty('--zone-active-label-width',Math.min(width<600?164:activeIds.filter(id=>id!=='overview').length>=3?184:220,Math.max(110,(usableWidth-36)/2))+'px');
      if(sel!==oldSelected||activeKey!==oldActive||stateKey!==oldStates){
        factory.stationRims.forEach(r=>{const status=stageStatus(states[r.id]),isActive=activeIds.includes(r.id),isSelected=sel===r.id,activeColor=status==='helper'?'#a58acb':status==='reported'?'#709eb0':COLORS.orange;r.material.color.set(isActive?activeColor:isSelected?'#5bc6c4':status==='done'?COLORS.green:'#b6c1bf');r.material.emissive.set(isActive?activeColor:isSelected?'#2b979d':COLORS.green);r.material.emissiveIntensity=isActive ? 1.5 : isSelected ? .15 : status==='done' ? .05 : 0;});oldSelected=sel;oldActive=activeKey;oldStates=stateKey;
      }
      factory.stationRims.forEach(r=>{r.glowMaterial.opacity=activeIds.includes(r.id)?(reduce?.24:.22+Math.sin(elapsed*2)*.035):0;});
      factory.researchers.update({activeIds,assignments:dataRef.current.workerAssignments,plannerWorking:dataRef.current.centerLabel ? dataRef.current.centerLabel.status==='working' : activeIds.length>0,reducedMotion:reduce,elapsed,dt,pausedIds,artwork:factory.artwork,illustratedIdle:artState.idleRooms,illustratedRooms:artState.ready?visibleRoomIds:[]});
      const researchersShown=factory.researchers.status();host.dataset.seatedResearchers=String(researchersShown.seated);host.dataset.workingResearchers=String(researchersShown.moving);
      const mainWorking=dataRef.current.centerLabel?dataRef.current.centerLabel.status==='working':activeIds.length>0;
      const preciseIds=Array.isArray(dataRef.current.skillActiveNodes)?dataRef.current.skillActiveNodes:activeIds;
      factory.workMotions.update({activeIds:preciseIds,reducedMotion:reduce,dt});
      host.dataset.plannerWorking=String(mainWorking);host.dataset.skillWork=preciseIds.join(',');
      factory.packets.forEach(p=>{const t=reduce?p.phase%1:(elapsed*.105+p.phase)%1;p.mesh.position.copy(p.start).lerp(p.finish,t);p.mesh.position.y=.48;p.mesh.visible=preciseIds.includes(p.id)&&factory.stations[p.id].visible;});
      factory.plannerActivity.visible=mainWorking;
      factory.beaconMaterial.color.set(mainWorking?'#ff972e':'#89988a');
      factory.beaconMaterial.emissiveIntensity=mainWorking?(reduce?1:1.1+Math.sin(elapsed*4)*.18):0;
      factory.scene.updateMatrixWorld(true);
      const app=host.closest('.fullscreen-app'),hostRect=host.getBoundingClientRect();
      const uiRect=selector=>{const element=app?.querySelector(selector);if(!element)return null;const rect=element.getBoundingClientRect();return rect.width&&rect.height?{top:rect.top-hostRect.top,bottom:rect.bottom-hostRect.top,left:rect.left-hostRect.left,right:rect.right-hostRect.left}:null;};
      const header=uiRect('.topbar'),footerControls=[uiRect('.scene-controls'),uiRect('.floating-run')].filter(rect=>rect&&rect.right>0&&rect.left<usableWidth&&rect.top>height*.45);
      const safeTop=header?Math.max(8,header.bottom+8):8,safeBottom=Math.max(safeTop+70,Math.min(height-8,height-(Number(dataRef.current.bottomInset)||0),...footerControls.map(rect=>rect.top-8)));
      const mobileReturn=width<=760?uiRect('.panel-return'):null,sheetBottom=mobileReturn?mobileReturn.top-8:null,projectedLabels=[];
      for(const s of [...STATIONS.filter(s=>visibleRoomIds.includes(s.id)),{id:'overview',x:0,z:0,labelY:2.8}]){
        const el=labelsRef.current[s.id];if(!el)continue;
        const group=factory.stations[s.id],art=factory.artwork.room(s.id);
        let projectedX,y;
        if(art?.frame){
          art.sprite.getWorldPosition(projection);projection.project(camera);
          const pixels=height/(2*currentExtent)*group.scale.x,artW=art.sprite.scale.x*pixels,artH=art.sprite.scale.y*pixels;
          const baseX=(projection.x*.5+.5)*width,baseY=(-projection.y*.5+.5)*height,plate=art.frame.plate;
          projectedX=baseX+(plate.x-.5)*artW;y=baseY-(1-plate.y)*artH;
          const plateW=plate.width*artW*.96;
          el.style.setProperty('--fascia-width',Math.max(40,Math.min(plateW,320))+'px');
          el.style.setProperty('--fascia-angle',plate.angle+'deg');
          el.dataset.illustrated='true';el.dataset.compactPlate='false';
          const fasciaFont=Math.max(6,Math.min(16,plateW/((s.title.replace(/\s/g,'').length||6)+3.8)));
          el.style.setProperty('--fascia-font',fasciaFont+'px');
          el.style.setProperty('--sign-height',Math.max(fasciaFont*1.55,Math.min(40,artH*(plate.height||.075)))+'px');
          el.style.setProperty('--active-offset',Math.min(-32,-artH*.68)+'px');
          if(art.idle)projectedLabels.push({id:s.id+'-person',protectOnly:true,left:baseX-artW*.24,top:baseY-artH*.75,w:artW*.48,h:artH*.36});
        }else{
          if(s.id==='overview'&&artState.ready){const pw=Math.max(72,Math.min(125,group.scale.x*height/(2*currentExtent)*5.7));el.style.setProperty('--planner-width',pw+'px');el.style.setProperty('--planner-font',Math.max(8,Math.min(12,pw/10.2))+'px');}
          const floor=s.id==='overview'?PLANNER_FLOOR:ZONE_FLOOR;const plannerFront=artState.ready&&s.id==='overview'?fieldToWorld(0,1.6):null;projection.set(plannerFront?.x??floor.halfX,.25,plannerFront?.z??floor.halfZ);group.localToWorld(projection);projection.project(camera);projectedX=(projection.x*.5+.5)*width;y=(-projection.y*.5+.5)*height;
        }
        const w=el.offsetWidth,h=el.offsetHeight;if(!w||!h)continue;
        const gutter=w/2+8,x=Math.min(Math.max(projectedX,currentLeftInset+gutter),Math.max(currentLeftInset+gutter,usableRight-gutter));
        el.style.opacity=Math.min(1,group.scale.x/desiredLayout.zones[s.id].scale*1.8);
        el.style.visibility=group.visible?'visible':'hidden';if(!group.visible&&leadersRef.current[s.id])leadersRef.current[s.id].style.visibility='hidden';
        projectedLabels.push({id:s.id,el,w,h,left:x-w/2,top:y-(art?.frame?h/2:-4),anchorX:projectedX,anchorY:y,working:s.id==='overview'?mainWorking:activeIds.includes(s.id),visible:group.visible&&projection.z>-1&&projection.z<1});
      }
      const bakedProtection=projectedLabels.filter(b=>b.protectOnly);
      const actualLabels=projectedLabels.filter(b=>!b.protectOnly);
      const protectedRects=factory.researchers.protectedRegions({precise:artState.ready}).map(region=>{
        const group=factory.stations[region.id],points=[];
        if(region.billboards){
          const pixels=height/(2*currentExtent)*group.scale.x;
          for(const figure of region.billboards){const p=new THREE.Vector3(figure.x,figure.y,figure.z);group.localToWorld(p);p.project(camera);const x=(p.x*.5+.5)*width,y=(-p.y*.5+.5)*height;points.push({x:x-figure.width*figure.anchor*pixels,y:y-figure.height*pixels},{x:x+figure.width*(1-figure.anchor)*pixels,y:y+2});}
        }else{
        for(const x of [region.minX,region.maxX])for(const z of [region.minZ,region.maxZ])for(const y of [.45,2.35]){const p=new THREE.Vector3(x,y,z);group.localToWorld(p);p.project(camera);points.push({x:(p.x*.5+.5)*width,y:(-p.y*.5+.5)*height});}
        }
        const left=Math.min(...points.map(p=>p.x)),top=Math.min(...points.map(p=>p.y));
        return {id:region.id,left,top,w:Math.max(...points.map(p=>p.x))-left,h:Math.max(...points.map(p=>p.y))-top};
      });
      protectedRects.push(...bakedProtection);
      const layoutSignature=JSON.stringify([Math.round(usableWidth),safeTop,safeBottom,sel,sheetBottom,actualLabels.map(b=>[b.id,b.w,b.h,Math.round(b.left/3),Math.round(b.top/3),b.working,b.visible]),protectedRects.map(b=>[b.id,Math.round(b.left/3),Math.round(b.top/3),Math.round(b.w/3),Math.round(b.h/3)])]);
      if(layoutSignature!==labelLayoutKey){
        if(artState.ready){
          const attached=actualLabels.filter(p=>p.id!=='overview').map(p=>({...p,protectedClear:!protectedRects.some(r=>intersects(p,r,1))}));
          const planner=actualLabels.filter(p=>p.id==='overview');
          labelLayout=[...attached,...arrangeLabelRects(planner,usableRight,safeTop,safeBottom,sel,sheetBottom,[...protectedRects,...attached,...(currentLeftInset>1?[{left:0,top:safeTop,w:currentLeftInset,h:safeBottom-safeTop}]:[])])];
        }else labelLayout=arrangeLabelRects(actualLabels,usableWidth,safeTop,safeBottom,sel,sheetBottom,protectedRects);
        labelLayoutKey=layoutSignature;
      }
      let covered=0;
      for(const label of labelLayout){
        const current=actualLabels.find(p=>p.id===label.id)||label;
        label.el.style.transform=`translate3d(${label.left+label.w/2}px,${label.top+label.h}px,0) translate(-50%,-100%)`;label.el.style.visibility=current.visible?'visible':'hidden';
        label.el.dataset.researcherClear=String(label.protectedClear);if(!label.protectedClear)covered++;
        const line=leadersRef.current[label.id];if(line){const x=Math.max(label.left+8,Math.min(label.left+label.w-8,current.anchorX)),y=current.anchorY>label.top+label.h/2?label.top+label.h:label.top;line.setAttribute('d',`M${x} ${y} L${current.anchorX} ${current.anchorY}`);line.style.visibility=current.visible?'visible':'hidden';line.classList.toggle('is-working',label.working);}
      }
      host.dataset.coveredResearcherRegions=String(covered);
      renderer.render(factory.scene,camera);
      metricFrames++;if(ms-metricAt>1000){host.dataset.renderFps=(metricFrames*1000/(ms-metricAt)).toFixed(1);host.dataset.drawCalls=String(renderer.info.render.calls);metricFrames=0;metricAt=ms;}
      dataRef.current.onFrame?.({canvas:renderer.domElement,host,labels:labelsRef.current,elapsed});
    }
    frame=requestAnimationFrame(render);
    return()=>{stopped=true;cancelAnimationFrame(frame);clearTimeout(recordingTimer);observer.disconnect();document.removeEventListener('visibilitychange',onVisibility);renderer.domElement.removeEventListener('pointerdown',pointerDown);renderer.domElement.removeEventListener('pointerup',pointerUp);renderer.domElement.removeEventListener('pointermove',pointerMove);renderer.domElement.removeEventListener('webglcontextlost',onLost);factory.researchers?.dispose();factory.dispose();renderer.dispose();renderer.domElement.remove();};
  },[]);
  return <div className={`factory-scene ${semantics?'has-work-meaning':''} ${(activeNodes||[active]).filter(id=>id&&id!=='overview').length>=3?'many-active-rooms':''} ${unavailable?'factory-no-webgl':''}`} ref={hostRef} style={{'--factory-panel-width':`${Math.max(0,Number(panelWidth)||0)}px`}} aria-label={sceneLabel||(centerLabel?'하네스 공장 3D 작업 공간':'상품기획 공장 3D 작업 공간')}>
    <div className="factory-scene-grain" aria-hidden="true" />
    <div className="factory-scene-corner"><span className="factory-isometric-mark" aria-hidden="true">◇</span><span>AX PLANNING FACTORY<small>작은 불편에서, 더 나은 일상으로</small></span></div>
    <svg className="factory-label-leaders" aria-hidden="true">{['overview',...roomIds].map(id=><path key={id} ref={el=>{leadersRef.current[id]=el;}}/>)}</svg>
    <div className="factory-label-layer">
      {STATIONS.filter(s=>roomIds.includes(s.id)).map(base=>{const s={...base,...stationLabels[base.id],id:base.id},status=stageStatus(stepStates[s.id]),stateLabel=s.statusLabel||statusText(status);return <button key={s.id} ref={el=>{labelsRef.current[s.id]=el;}} className={`factory-station-label ${selected===s.id?'is-selected':''} status-${status} ${s.helperRole?'has-helper':''} ${s.reporting?'is-reported':''}`} onClick={()=>onSelect?.(s.id)} aria-pressed={selected===s.id} aria-label={`${s.no} ${s.title} · ${stateLabel}${selected===s.id?' · 선택됨':''}`} title={`${s.title} — ${s.caption}`}>
        {semantics&&<span className="station-kind"><Wrench size={11}/>SKILL · 일하는 방법</span>}
        <span className="station-sign-row"><span className="factory-station-number">{s.no}</span><span className="factory-station-title"><strong>{s.title}</strong></span><span className="factory-station-state"><i/><span className="station-state-full">{stateLabel}</span><span className="station-state-short" aria-hidden="true">{statusText(status)}</span></span></span>
        <span className="factory-station-caption">{semantics?(s.task||SKILL_BY_ROOM[s.id]?.verb||s.caption):s.caption}</span>
        <span className="artwork-active-badge" aria-hidden="true"><Wrench size={11}/>{stateLabel}</span>
        {semantics&&s.roleText&&<span className={'station-actor '+(s.helperRole?'helper':'main')}><UserRound size={10}/>{s.roleText}</span>}
      </button>;})}
      <button ref={el=>{labelsRef.current.overview=el;}} className={`factory-planner-label ${plannerWorking?'status-running':''} ${selected==='overview'?'is-selected':''}`} onClick={()=>onHome?onHome():onSelect?.('overview')} aria-pressed={selected==='overview'} aria-label={(centerLabel?.title||'메인 기획 AI')+(plannerWorking?' · 작업 중':' · 대기')}><span className="factory-planner-eyebrow"><i/> {semantics?'AGENT · 일하는 AI':centerLabel?.eyebrow||'ORCHESTRATOR'}</span><strong>{centerLabel?.title||'메인 기획 Agent'}</strong>{!semantics&&centerLabel?.caption!==null&&<span className="factory-planner-caption">{centerLabel?.caption||'필요한 Skill을 골라 작업을 연결해요'}</span>}</button>
    </div>
    {unavailable&&<p className="factory-fallback-message">3D 화면을 표시할 수 없습니다. 업무 공간 이름을 선택해 진행하세요.</p>}
    <div className="factory-scene-legend" aria-hidden="true"><span><i className="legend-active"/>실행 중</span><span><i className="legend-done"/>완료</span><span>{semantics?'도구 표시 = Skill · 사람 표시 = 담당 AI':'업무 공간을 눌러 자세히 보기'} <b>↗</b></span></div>
  </div>;
}
