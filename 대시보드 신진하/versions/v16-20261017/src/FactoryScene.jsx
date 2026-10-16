import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { createResearchers } from './ResearcherCharacters.js';
import {factoryLayout,fitFactory,transitionFactory,ZONE_IDS,ZONE_FLOOR} from './factory-layout.js';
import './factory-scene.css';
import {buildWorkroom,buildWorkshopBackdrop} from './factory-workshop.js';

const STATIONS = [
  { id: 'retrieve', no: '01', title: '자료 조회', caption: '리뷰 · 제품 문서 수집', x: -5.9, z: .1, labelY: 3.04, labelZ: -1.30 },
  { id: 'structure', no: '02', title: '니즈 구조화', caption: '고객의 불편을 구조화', x: -2.9, z: -4.9, labelY: 3.04, labelZ: -1.30 },
  { id: 'compare', no: '03', title: '기능 대조', caption: '기존 기능과 남은 불편', x: 3.4, z: -4.05, labelY: 3.04, labelZ: -1.30 },
  { id: 'concept', no: '04', title: '콘셉트 작성', caption: '근거에서 새로운 가능성으로', x: 5.3, z: 1.9, labelY: 3.04, labelZ: -1.30 },
  { id: 'validate', no: '05', title: '검토 · 수정', caption: '근거와 요구사항 최종 점검', x: -1.05, z: 5.7, labelY: 3.04, labelZ: -1.30 },
];
const COLORS = { dark: '#344e43', slate: '#80978b', base: '#eeeee4', white: '#f7f5ec', steel: '#b6c3b8', orange: '#fc762c', green: '#219464', blue: '#3a98b9' };
function stageStatus(value) {
  const s = typeof value === 'object' ? value?.status : value;
  if (['complete', 'completed', 'done', 'passed', 'succeeded'].includes(s)) return 'done';
  if (['running', 'active', 'processing'].includes(s)) return 'running';
  if (s === 'paused') return 'paused';
  if (s === 'stopped') return 'stopped';
  if (['awaiting', 'needs_input', 'needs_confirmation', 'awaiting_confirmation'].includes(s)) return 'awaiting';
  if (['failed', 'error', 'blocked'].includes(s)) return 'error';
  return 'pending';
}
function statusText(s) { return { done: '완료', running: '실행 중', paused: '일시정지', stopped: '중지됨', awaiting: '확인 필요', error: '확인 필요', pending: '대기' }[s]; }

// Reserve the planner name before placing other labels. Only the labels move;
// camera, buildings and their world projections remain unchanged.
function arrangeLabelRects(items, usableWidth, safeTop, safeBottom, selected, sheetBottom) {
  const gap=7,order=['overview','structure','retrieve','compare','validate','concept'];
  const overlap=(a,b)=>a.left<b.left+b.w+gap&&a.left+a.w+gap>b.left&&a.top<b.top+b.h+gap&&a.top+a.h+gap>b.top;
  const labels=items.map(item=>{
    const bottom=sheetBottom!=null&&item.id===selected?Math.min(safeBottom,sheetBottom):safeBottom;
    const maxTop=Math.max(safeTop,bottom-item.h);
    return {...item,baseLeft:item.left,baseTop:Math.min(Math.max(item.top,safeTop),maxTop),top:Math.min(Math.max(item.top,safeTop),maxTop),maxTop};
  }).sort((a,b)=>(sheetBottom!=null&&a.id===selected?-1:sheetBottom!=null&&b.id===selected?1:order.indexOf(a.id)-order.indexOf(b.id)));
  const placed=[];
  for(const item of labels){
    if(placed.some(other=>overlap(item,other))){
      const xs=[item.baseLeft,8,usableWidth-item.w-8,...placed.flatMap(other=>[other.left-gap-item.w,other.left+other.w+gap])];
      const ys=[item.baseTop,safeTop,item.maxTop,...placed.flatMap(other=>[other.top-gap-item.h,other.top+other.h+gap])];
      const choices=xs.flatMap(left=>ys.map(top=>({...item,left,top})))
        .filter(box=>box.left>=8&&box.left+box.w<=usableWidth-8&&box.top>=safeTop&&box.top<=box.maxTop&&!placed.some(other=>overlap(box,other)))
        .sort((a,b)=>(a.left-item.baseLeft)**2+(a.top-item.baseTop)**2-((b.left-item.baseLeft)**2+(b.top-item.baseTop)**2));
      if(choices.length){item.left=choices[0].left;item.top=choices[0].top;}
    }
    placed.push(item);
  }
  // A narrow desktop can lack a free row around the fixed planner projection.
  // Pack only the six nameplates into nearby slots when greedy placement fails.
  if(labels.some((a,i)=>labels.slice(i+1).some(b=>overlap(a,b)))){
    const cellW=Math.max(...labels.map(x=>x.w)),cellH=Math.max(...labels.map(x=>x.h)),slotGap=5;
    let best=null,bestCost=Infinity;
    for(let cols=1;cols<=labels.length;cols++){
      const rows=Math.ceil(labels.length/cols),gridW=cols*cellW+(cols-1)*slotGap,gridH=rows*cellH+(rows-1)*slotGap;
      if(gridW>usableWidth-16||gridH>safeBottom-safeTop)continue;
      const left=(usableWidth-gridW)/2,top=safeTop+(safeBottom-safeTop-gridH)/2;
      const slots=Array.from({length:labels.length},(_,i)=>({left:left+(i%cols)*(cellW+slotGap),top:top+Math.floor(i/cols)*(cellH+slotGap)}));
      const visit=(index,used,result,cost)=>{
        if(cost>=bestCost)return;
        if(index===labels.length){bestCost=cost;best=result;return;}
        const item=labels[index];
        for(let i=0;i<slots.length;i++)if(!used.has(i)){
          const box={left:slots[i].left+(cellW-item.w)/2,top:slots[i].top};
          if(sheetBottom!=null&&item.id===selected&&box.top+item.h>sheetBottom)continue;
          const distance=(box.left-item.baseLeft)**2+(box.top-item.baseTop)**2;
          visit(index+1,new Set([...used,i]),[...result,box],cost+distance*(item.id==='overview'?1.5:1));
        }
      };
      visit(0,new Set(),[],0);
    }
    if(best)labels.forEach((item,i)=>Object.assign(item,best[i]));
  }
  return labels;
}

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
    ctx.fillStyle='#fbfcf8';ctx.fillRect(0,0,w,h);ctx.fillStyle='#253943';ctx.font='bold 28px sans-serif';ctx.fillText(kind==='blueprint'?'CONCEPT / 03':kind==='check'?'QUALITY CHECK':'CUSTOMER NEEDS',27,43);
    ctx.fillStyle='#f47732';ctx.fillRect(26,58,w-52,4);
    if(kind==='sticky'){
      const items=[['수납 · 정리','#e8f1b3'],['세척 불편','#f1dfb4'],['사용 조건','#bad7d0'],['모델 구분','#c9d5ec'],['잔여 불편','#f2c6c1'],['원문 연결','#d0e1cb']];
      items.forEach((a,i)=>{const x=25+(i%3)*158,y=83+Math.floor(i/3)*85;ctx.fillStyle=a[1];ctx.fillRect(x,y,145,71);ctx.fillStyle='#354849';ctx.font='bold 21px sans-serif';ctx.fillText(a[0],x+13,y+39);});
    }else if(kind==='check'){
      ['모델 · 기능 일치','원문 근거 확인','중복 후보 제외','요구사항 연결'].forEach((t,i)=>{ctx.fillStyle='#239a73';ctx.fillRect(29,81+i*40,21,21);ctx.fillStyle='#fff';ctx.font='bold 18px sans-serif';ctx.fillText('✓',31,98+i*40);ctx.fillStyle='#34464a';ctx.font='21px sans-serif';ctx.fillText(t,66,100+i*40);});
    }else{
      ctx.strokeStyle='#87a9ba';ctx.lineWidth=2;for(let j=0;j<3;j++){const x=42+j*159;ctx.strokeRect(x,91,101,133);ctx.strokeRect(x+9,101,83,45);ctx.strokeRect(x+9,158,83,55);ctx.beginPath();ctx.moveTo(x+48,92);ctx.lineTo(x+48,223);ctx.stroke();ctx.fillStyle='#bfccd1';ctx.fillRect(x+17,235,68,5);}
    }
  },512,280);
  const textures = { sticky:boardTexture('sticky'), check:boardTexture('check'), blueprint:boardTexture('blueprint') };
  const board = (group,kind,x,y,z,w=2.5,h=1.52) => {
    cube(group,w+.14,h+.14,.12,x,y,z,COLORS.steel,.05,.35);
    const material=new THREE.MeshStandardMaterial({map:textures[kind],roughness:.75});resources.push(material);
    const plane=new THREE.Mesh(new THREE.PlaneGeometry(w,h),material);resources.push(plane.geometry);plane.position.set(x,y,z+.072);group.add(plane);
    for(const dx of [-w*.38,w*.38]){cube(group,.065,y-h/2,.065,x+dx,(y-h/2)/2,z,COLORS.slate,.012,.4);cube(group,.38,.055,.36,x+dx,.12,z,COLORS.slate);}
  };
  const monitor = (group,x,y,z,scale=1) => {
    cube(group,.62*scale,.41*scale,.085*scale,x,y,z,COLORS.dark,.03);
    const material=new THREE.MeshStandardMaterial({map:screenTexture,emissive:'#1a6370',emissiveIntensity:.22,roughness:.5});resources.push(material);
    const g=new THREE.PlaneGeometry(.53*scale,.31*scale);resources.push(g);const s=new THREE.Mesh(g,material);s.position.set(x,y,z+.049*scale);group.add(s);
    cube(group,.05*scale,.22*scale,.05*scale,x,y-.29*scale,z,COLORS.slate);
    cube(group,.32*scale,.035*scale,.2*scale,x,y-.4*scale,z+.035,COLORS.slate);
  };
  const plant = (group,x,z,scale=1) => {
    cylinder(group,.18*scale,.42*scale,x,.32*scale,z,'#e4e2d4',.13*scale);
    cylinder(group,.019*scale,.57*scale,x,.75*scale,z,'#71866a',.019*scale,8);
    for(let i=0;i<7;i++){const a=i*2.4;sphere(group,.16*scale,x+Math.cos(a)*.18*scale,.91*scale+(i%3)*.1*scale,z+Math.sin(a)*.17*scale,i%2?'#708c5b':'#92a16d',[1.4,.65,1]);}
  };
  scene.add(new THREE.HemisphereLight('#fffdf5','#bdccc1',1.85));
  const sun = new THREE.DirectionalLight('#fff8e8',3.2);sun.position.set(-6,15,8);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-15;sun.shadow.camera.right=15;sun.shadow.camera.top=15;sun.shadow.camera.bottom=-15;sun.shadow.normalBias=.035;sun.shadow.bias=-.0001;sun.shadow.radius=3;scene.add(sun);
  const fill = new THREE.DirectionalLight('#e7eee4',.75);fill.position.set(10,7,-10);scene.add(fill);
  const floor=new THREE.Group();scene.add(floor);const fieldProps=[];
  const tiles=canvasTexture((ctx,w,h)=>{
    ctx.fillStyle='#e9ede4';ctx.fillRect(0,0,w,h);
    const size=w/4;
    for(let x=0;x<4;x++)for(let y=0;y<4;y++){
      ctx.fillStyle=(x+y)%3===0?'#eef0e7':'#e8ece3';ctx.fillRect(x*size+1,y*size+1,size-2,size-2);
      ctx.strokeStyle='#d3dacd';ctx.lineWidth=1;ctx.strokeRect(x*size+.5,y*size+.5,size,size);
      ctx.strokeStyle='#f8faf5';ctx.beginPath();ctx.moveTo(x*size+2,y*size+size-2);ctx.lineTo(x*size+size-2,y*size+size-2);ctx.stroke();
    }
  },512,512);
  tiles.wrapS=tiles.wrapT=THREE.RepeatWrapping;tiles.repeat.set(128,128);
  const groundMaterial=new THREE.MeshStandardMaterial({map:tiles,roughness:.93,color:'#fafbf5'});resources.push(groundMaterial);
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(512,512),groundMaterial);ground.rotation.x=-Math.PI/2;ground.position.y=-.012;ground.receiveShadow=true;floor.add(ground);
  // A narrow safety lane makes the miniature workstations feel like one factory.
  const lane=[[-8,-6],[-3,-7],[5,-6],[8,-1],[7,6],[0,8],[-7,6],[-8,-6]];
  lane.slice(0,-1).forEach((a,i)=>{const b=lane[i+1],len=Math.hypot(b[0]-a[0],b[1]-a[1]),n=Math.floor(len/.65);for(let j=0;j<n;j++){const t=j/n,u=Math.min((j+.5)/n,1);strip(floor,[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t],[a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u],.05,.065,'#e9ac41');}});
  const floorLabel=canvasTexture((ctx,w,h)=>{ctx.clearRect(0,0,w,h);ctx.fillStyle='#71817d';ctx.font='bold 56px sans-serif';ctx.textAlign='center';ctx.fillText('KITCHEN AX',w/2,90);ctx.font='20px sans-serif';ctx.fillText('PRODUCT PLANNING FACTORY',w/2,132);});
  const labelMaterial=new THREE.MeshBasicMaterial({map:floorLabel,transparent:true,depthWrite:false});resources.push(labelMaterial);const labelGeometry=new THREE.PlaneGeometry(4,2);resources.push(labelGeometry);const floorTitle=new THREE.Mesh(labelGeometry,labelMaterial);floorTitle.rotation.x=-Math.PI/2;floorTitle.position.set(3,.06,6.5);floor.add(floorTitle);
  const workshopTools={cube,cylinder,monitor,board,plant,mat,resources,canvasTexture};
  buildWorkshopBackdrop(scene,workshopTools);

  const stations = {};
  const stationRims=[];
  const platform=(s)=>{
    const group=new THREE.Group();group.position.set(s.x,0,s.z);group.userData.station=s.id;scene.add(group);stations[s.id]=group;
    cube(group,ZONE_FLOOR.halfX*2,.28,ZONE_FLOOR.halfZ*2,0,.22,0,'#70837e',.14,.1);
    cube(group,5.48,.13,4.68,0,.415,0,'#f7f4e9',.08);
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
  STATIONS.forEach(s=>buildWorkroom(s.id,platform(s),workshopTools));

  const center = new THREE.Group();center.userData.station='overview';scene.add(center);stations.overview=center;
  cube(center,3,.22,2.7,0,.22,0,'#617276',.17,.2);cube(center,2.82,.12,2.5,0,.4,0,'#faf8ee',.1);
  for(const x of [-1.18,1.18])cube(center,.23,.05,1.96,x,.49,0,'#e5b14e');
  cube(center,1.47,1.37,1.27,0,1.12,-.07,'#e6e9e2',.13,.1);
  cube(center,.97,.46,.055,0,1.39,.6,'#304b55',.025);
  monitor(center,.88,1.52,.2,.73);
  cube(center,.55,.23,.55,-.89,.72,.4,'#ced7d2',.05,.3);
  cylinder(center,.3,.1,-.89,.87,.4,'#e4ede9');
  const beacon=cylinder(center,.105,.23,0,1.96,-.09,'#ff8f30');const beaconMaterial=new THREE.MeshStandardMaterial({color:'#ff9f2f',emissive:'#ff6200',emissiveIntensity:1.3,roughness:.25});resources.push(beaconMaterial);beacon.material=beaconMaterial;cylinder(center,.17,.045,0,1.825,-.09,'#4f6269');
  cube(center,.54,.06,.15,-.22,1.81,.34,'#c5d4cf');
  cube(center,.44,.22,.04,0,.91,.62,'#f47b34');
  const packets=[],links=[];
  const addConveyor=(end,index)=>{
    const e=new THREE.Vector3(end.x,0,end.z),dir=e.clone().normalize(),start=dir.clone().multiplyScalar(1.7),finish=e.clone().addScaledVector(dir,-1.8),len=start.distanceTo(finish);
    const belt=new THREE.Group();belt.position.copy(start).add(finish).multiplyScalar(.5);belt.rotation.y=Math.atan2(dir.x,dir.z);scene.add(belt);
    cube(belt,.78,.10,len,0,.35,0,'#becabd',.025,.2);
    const glass=cube(belt,.65,.035,len,0,.422,0,'#c8dfd0',.012,.2);
    const glassMaterial=new THREE.MeshPhysicalMaterial({color:'#cce4d5',roughness:.12,metalness:.1,transparent:true,opacity:.74});glass.material=glassMaterial;resources.push(glassMaterial);
    for(const x of [-.35,.35])cube(belt,.035,.045,len,x,.45,0,'#f7f4dd',.008,.3);
    for(let j=0;j<Math.ceil(len/.62);j++){const dash=cube(belt,.20,.012,.06,0,.448,-len/2+(j+.5)*len/Math.ceil(len/.62),'#f5df9b',.005);dash.material=mat('#f5df9b',.25,.15);}
    for(let j=0;j<3;j++){const packet=new THREE.Group();const m=new THREE.MeshBasicMaterial({color:'#ffd17a',transparent:true,opacity:.9,depthWrite:false});resources.push(m);
     for(const side of [-1,1]){const arrow=cube(packet,.035,.013,.16,side*.045,0,0,'#ffd17a',.002);arrow.rotation.y=side*.55;arrow.material=m;}
     scene.add(packet);packets.push({mesh:packet,start,finish,phase:j/3+index*.11,id:end.id});}
    links.push({group:belt,baseLength:len,start,finish,id:end.id});
  };
  STATIONS.forEach(addConveyor);
  for(const [x,z] of [[-12,3],[12,13],[-16,-2],[16,-4],[5,16],[-17,12],[17,5],[-5,-16]]){
    const prop=new THREE.Group();prop.position.set(x,0,z);floor.add(prop);
    cube(prop,.56,.4,.49,0,.21,0,'#d9c7a2');cube(prop,.07,.42,.51,0,.22,0,'#e6d7b9');cube(prop,.17,.09,.018,.14,.27,.255,'#faf8ed');
    fieldProps.push({group:prop,x,z});
  }
  return {
    scene, stations, stationRims, packets, links, fieldProps, beaconMaterial,
    dispose(){scene.traverse(o=>{if(o.isMesh){if(o.geometry&&!Array.from(geometries.values()).includes(o.geometry))o.geometry.dispose();}});geometries.forEach(x=>x.dispose());materials.forEach(x=>x.dispose());resources.forEach(x=>x.dispose?.());},
  };
}

export default function FactoryScene({ selected='overview', onSelect, active=null, stepStates={}, reducedMotion=false, onHome, panelWidth=0, stationLabels={}, centerLabel=null, activeNodes=null, onFrame=null, sceneLabel=null, recording=false }) {
  const hostRef=useRef(null), labelsRef=useRef({}), dataRef=useRef({ selected, active, stepStates, reducedMotion, onSelect, onHome, panelWidth, activeNodes });
  const [unavailable,setUnavailable]=useState(false);
  dataRef.current={selected,active,stepStates,reducedMotion,onSelect,onHome,panelWidth,activeNodes,centerLabel,onFrame,recording};
  useEffect(()=>{
    const host=hostRef.current;if(!host)return;
    let renderer, factory, frame=0, recordingTimer=0, stopped=false, last=0;
    try{
      renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.6));renderer.setClearColor('#edf0ed',0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.02;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;
      renderer.domElement.className='factory-webgl';renderer.domElement.setAttribute('aria-hidden','true');host.prepend(renderer.domElement);
      factory=createFactory(renderer);
      host.dataset.researchers='loading';
      factory.researchers=createResearchers(factory.scene,state=>{host.dataset.researchers=state;},factory.stations);
    }catch(err){setUnavailable(true);renderer?.dispose();return;}
    const camera=new THREE.OrthographicCamera(-12,12,12,-12,.1,500),direction=new THREE.Vector3(13,17,18).normalize();
    const target=new THREE.Vector3(0,.35,0),desiredTarget=target.clone(),projection=new THREE.Vector3();
    let width=1,height=1,currentPanelWidth=0,currentExtent=12,layoutKey='',desiredLayout=null,lastShadow=0;
    let reflow=null,metricAt=0,metricFrames=0;
    const clampPanel=value=>Math.min(Math.max(0,Number(value)||0),Math.max(0,width-280));
    function resize(){const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;width=w;height=h;currentPanelWidth=clampPanel(currentPanelWidth);renderer.setSize(width,height,false);}
    const observer=new ResizeObserver(resize);observer.observe(host);resize();
    currentPanelWidth=clampPanel(dataRef.current.panelWidth);
    const raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2();let down=null;
    function locate(ev){const rect=renderer.domElement.getBoundingClientRect();pointer.set((ev.clientX-rect.left)/rect.width*2-1,-(ev.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hits=raycaster.intersectObjects(factory.scene.children,true);for(const hit of hits){let o=hit.object;while(o){if(o.userData.station)return o.userData.station;o=o.parent;}}return null;}
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
      const activeIds=[...new Set([...reportedIds,...(dataRef.current.centerLabel?.status==='working'?['overview']:[])])].filter(id=>ZONE_IDS.includes(id)),activeKey=[...activeIds].sort().join('|'),stateKey=JSON.stringify(states),elapsed=ms/1000;
      const smooth=reduce?1:1-Math.exp(-dt*6);
      currentPanelWidth+=(clampPanel(requestedPanelWidth)-currentPanelWidth)*smooth;
      if(Math.abs(currentPanelWidth-clampPanel(requestedPanelWidth))<.1)currentPanelWidth=clampPanel(requestedPanelWidth);
      const usableWidth=Math.max(240,width-currentPanelWidth),aspect=width/height;
      const nextKey=[Math.round(usableWidth/4),Math.round(height/4),activeKey].join(':');
      if(nextKey!==layoutKey){
        const nextLayout=factoryLayout({width,height,panelWidth:currentPanelWidth,activeIds});
        if(!desiredLayout||ZONE_IDS.some(id=>{const a=desiredLayout.zones[id],b=nextLayout.zones[id];return Math.abs(a.x-b.x)+Math.abs(a.z-b.z)+Math.abs(a.scale-b.scale)>.001;})){
          const from=desiredLayout?Object.fromEntries(Object.entries(factory.stations).map(([id,g])=>[id,{id,x:g.position.x,z:g.position.z,scale:g.scale.x}])):Object.fromEntries(Object.entries(nextLayout.zones).map(([id,g])=>[id,{...g,scale:.01}]));
          reflow={from,at:elapsed};
        }
        desiredLayout=nextLayout;layoutKey=nextKey;host.dataset.fieldLayout=desiredLayout.compact?'compact':'wide';
      }
      const moving=transitionFactory(reflow.from,desiredLayout.zones,elapsed-reflow.at,reduce);
      let changed=false;
      for(const [id,dest] of Object.entries(moving)){
        const group=factory.stations[id];if(!group)continue;
        changed=changed||Math.abs(group.position.x-dest.x)+Math.abs(group.position.z-dest.z)+Math.abs(group.scale.x-dest.scale)>.001;
        group.position.set(dest.x,0,dest.z);group.scale.setScalar(dest.scale);group.visible=dest.visible;
      }
      const currentShapes=Object.fromEntries(Object.entries(factory.stations).map(([id,g])=>[id,{id,x:g.position.x,z:g.position.z,scale:g.scale.x}]));
      const fitShapes={...currentShapes,...Object.fromEntries(Object.entries(desiredLayout.zones).map(([id,g])=>[id+'-target',g]))};
      const fit=fitFactory(fitShapes,{width,height,panelWidth:currentPanelWidth,top:width<600?72:76,bottom:height<500?54:72});
      desiredTarget.set(fit.x,.35,fit.z);target.lerp(desiredTarget,smooth);
      currentExtent=fit.extent>currentExtent?fit.extent:currentExtent+(fit.extent-currentExtent)*smooth;
      camera.zoom=1;camera.left=-currentExtent*aspect;camera.right=currentExtent*aspect;camera.top=currentExtent;camera.bottom=-currentExtent;
      camera.setViewOffset(width,height,currentPanelWidth/2,0,width,height);
      camera.position.copy(direction).multiplyScalar(Math.max(31,currentExtent*2.1)).add(target);camera.lookAt(target);camera.updateMatrixWorld();
      if(changed&&elapsed-lastShadow>.12){renderer.shadowMap.needsUpdate=true;lastShadow=elapsed;}
      const centerGroup=factory.stations.overview;
      factory.links.forEach(link=>{
        const end=factory.stations[link.id],dir=end.position.clone().sub(centerGroup.position),distance=dir.length();dir.normalize();
        const edge=(g,w,d)=>Math.min(Math.abs(dir.x)>.001?w*g.scale.x/Math.abs(dir.x):Infinity,Math.abs(dir.z)>.001?d*g.scale.x/Math.abs(dir.z):Infinity);
        link.start.copy(centerGroup.position).addScaledVector(dir,edge(centerGroup,1.5,1.35)+.12);
        link.finish.copy(end.position).addScaledVector(dir,-edge(end,ZONE_FLOOR.halfX,ZONE_FLOOR.halfZ)-.12);
        const len=distance-edge(centerGroup,1.5,1.35)-edge(end,ZONE_FLOOR.halfX,ZONE_FLOOR.halfZ)-.24;
        link.group.visible=len>.2;if(len<=.2)return;
        link.group.position.copy(link.start).add(link.finish).multiplyScalar(.5);link.group.rotation.y=Math.atan2(dir.x,dir.z);link.group.scale.z=len/link.baseLength;
      });
      factory.fieldProps.forEach(prop=>{prop.group.visible=!Object.values(currentShapes).some(z=>Math.hypot(z.x-prop.x,z.z-prop.z)<(z.id==='overview'?2.0:3.3)*z.scale+1.0);});
      host.style.setProperty('--zone-label-width',Math.min(width<600?146:174,Math.max(104,(usableWidth-24)/2))+'px');
      host.style.setProperty('--zone-active-label-width',Math.min(width<600?178:254,Math.max(110,(usableWidth-24)/2))+'px');
      if(sel!==oldSelected||activeKey!==oldActive||stateKey!==oldStates){
        factory.stationRims.forEach(r=>{const status=stageStatus(states[r.id]),isActive=activeIds.includes(r.id),isSelected=sel===r.id;r.material.color.set(isActive?COLORS.orange:isSelected?'#5bc6c4':status==='done'?COLORS.green:'#b6c1bf');r.material.emissive.set(isActive?COLORS.orange:isSelected?'#2b979d':COLORS.green);r.material.emissiveIntensity=isActive ? 1.5 : isSelected ? .15 : status==='done' ? .05 : 0;});oldSelected=sel;oldActive=activeKey;oldStates=stateKey;
      }
      factory.stationRims.forEach(r=>{r.glowMaterial.opacity=activeIds.includes(r.id)?(reduce?.24:.22+Math.sin(elapsed*2)*.035):0;});
      factory.researchers.update({activeIds,plannerWorking:dataRef.current.centerLabel ? dataRef.current.centerLabel.status==='working' : activeIds.length>0,reducedMotion:reduce,elapsed,dt,pausedIds:Object.keys(states).filter(id=>stageStatus(states[id])==='paused')});
      factory.packets.forEach(p=>{const t=reduce?p.phase%1:(elapsed*.105+p.phase)%1;p.mesh.position.copy(p.start).lerp(p.finish,t);p.mesh.position.y=.48;p.mesh.visible=activeIds.includes(p.id);});
      factory.beaconMaterial.emissiveIntensity=activeIds.length?(reduce?1:1.1+Math.sin(elapsed*4)*.45):.4;
      factory.scene.updateMatrixWorld(true);
      const app=host.closest('.fullscreen-app'),hostRect=host.getBoundingClientRect();
      const uiRect=selector=>{const element=app?.querySelector(selector);if(!element)return null;const rect=element.getBoundingClientRect();return rect.width&&rect.height?{top:rect.top-hostRect.top,bottom:rect.bottom-hostRect.top,left:rect.left-hostRect.left,right:rect.right-hostRect.left}:null;};
      const header=uiRect('.topbar'),footerControls=[uiRect('.scene-controls'),uiRect('.floating-run')].filter(rect=>rect&&rect.right>0&&rect.left<usableWidth&&rect.top>height*.45);
      const safeTop=header?Math.max(8,header.bottom+8):8,safeBottom=Math.max(safeTop+70,Math.min(height-8,...footerControls.map(rect=>rect.top-8)));
      const mobileReturn=width<=760?uiRect('.panel-return'):null,sheetBottom=mobileReturn?mobileReturn.top-8:null,projectedLabels=[];
      for(const s of [...STATIONS,{id:'overview',x:0,z:0,labelY:2.8}]){
        const el=labelsRef.current[s.id];if(!el)continue;const w=el.offsetWidth,h=el.offsetHeight;if(!w||!h)continue;
        const group=factory.stations[s.id];projection.set(0,s.labelY,s.labelZ||0);group.localToWorld(projection);projection.project(camera);const gutter=w/2+8,projectedX=(projection.x*.5+.5)*width,x=Math.min(Math.max(projectedX,gutter),Math.max(gutter,usableWidth-gutter)),y=(-projection.y*.5+.5)*height;
        el.style.opacity=Math.min(1,group.scale.x/desiredLayout.zones[s.id].scale*1.8);
        projectedLabels.push({id:s.id,el,w,h,left:x-w/2,top:y-h,visible:group.visible&&projection.z>-1&&projection.z<1});
      }
      for(const label of arrangeLabelRects(projectedLabels,usableWidth,safeTop,safeBottom,sel,sheetBottom)){
        label.el.style.transform=`translate3d(${label.left+label.w/2}px,${label.top+label.h}px,0) translate(-50%,-100%)`;label.el.style.visibility=label.visible?'visible':'hidden';
      }
      renderer.render(factory.scene,camera);
      metricFrames++;if(ms-metricAt>1000){host.dataset.renderFps=(metricFrames*1000/(ms-metricAt)).toFixed(1);host.dataset.drawCalls=String(renderer.info.render.calls);metricFrames=0;metricAt=ms;}
      dataRef.current.onFrame?.({canvas:renderer.domElement,host,labels:labelsRef.current,elapsed});
    }
    frame=requestAnimationFrame(render);
    return()=>{stopped=true;cancelAnimationFrame(frame);clearTimeout(recordingTimer);observer.disconnect();document.removeEventListener('visibilitychange',onVisibility);renderer.domElement.removeEventListener('pointerdown',pointerDown);renderer.domElement.removeEventListener('pointerup',pointerUp);renderer.domElement.removeEventListener('pointermove',pointerMove);renderer.domElement.removeEventListener('webglcontextlost',onLost);factory.researchers?.dispose();factory.dispose();renderer.dispose();renderer.domElement.remove();};
  },[]);
  return <div className={`factory-scene ${unavailable?'factory-no-webgl':''}`} ref={hostRef} style={{'--factory-panel-width':`${Math.max(0,Number(panelWidth)||0)}px`}} aria-label={sceneLabel||(centerLabel?'하네스 공장 3D 작업 공간':'상품기획 공장 3D 작업 공간')}>
    <div className="factory-scene-grain" aria-hidden="true" />
    <div className="factory-scene-corner"><span className="factory-isometric-mark" aria-hidden="true">◇</span><span>AX PLANNING FACTORY<small>작은 불편에서, 더 나은 일상으로</small></span></div>
    <div className="factory-label-layer">
      {STATIONS.map(base=>{const s={...base,...stationLabels[base.id]},status=stageStatus(stepStates[s.id]),stateLabel=s.statusLabel||statusText(status);return <button key={s.id} ref={el=>{labelsRef.current[s.id]=el;}} className={`factory-station-label ${selected===s.id?'is-selected':''} status-${status}`} onClick={()=>onSelect?.(s.id)} aria-pressed={selected===s.id} aria-label={`${s.no} ${s.title} · ${stateLabel}${selected===s.id?' · 선택됨':''}`} title={`${s.title} — ${s.caption}`}>
        <span className="factory-station-number">{s.no}</span><span className="factory-station-title"><strong>{s.title}</strong></span><span className="factory-station-state"><i/>{stateLabel}</span><span className="factory-station-caption">{s.caption}</span>
      </button>;})}
      <button ref={el=>{labelsRef.current.overview=el;}} className={`factory-planner-label ${centerLabel?.status==='working'?'status-running':''} ${selected==='overview'?'is-selected':''}`} onClick={()=>onHome?onHome():onSelect?.('overview')} aria-pressed={selected==='overview'}><span className="factory-planner-eyebrow"><i/> {centerLabel?.eyebrow||'ORCHESTRATOR'}</span><strong>{centerLabel?.title||'메인 기획 Agent'}</strong><span>{centerLabel?.caption||'다섯 Skill의 작업을 연결합니다'}</span></button>
    </div>
    {unavailable&&<p className="factory-fallback-message">3D 화면을 표시할 수 없습니다. 업무 공간 이름을 선택해 진행하세요.</p>}
    <div className="factory-scene-legend" aria-hidden="true"><span><i className="legend-active"/>실행 중</span><span><i className="legend-done"/>완료</span><span>업무 공간을 눌러 자세히 보기 <b>↗</b></span></div>
  </div>;
}
