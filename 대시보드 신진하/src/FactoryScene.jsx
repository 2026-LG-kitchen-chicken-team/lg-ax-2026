import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import './factory-scene.css';

const STATIONS = [
  { id: 'retrieve', no: '01', title: '자료 조회', caption: '리뷰 · 제품 문서 수집', x: -5.9, z: .1, labelY: 3.4 },
  { id: 'structure', no: '02', title: '니즈 구조화', caption: '고객의 불편을 구조화', x: -2.9, z: -4.9, labelY: 3.55 },
  { id: 'compare', no: '03', title: '기능 대조', caption: '기존 기능과 남은 불편', x: 3.4, z: -4.05, labelY: 3.45 },
  { id: 'concept', no: '04', title: '콘셉트 작성', caption: '근거에서 새로운 가능성으로', x: 5.3, z: 1.9, labelY: 1.15 },
  { id: 'validate', no: '05', title: '검토 · 수정', caption: '근거와 요구사항 최종 점검', x: -1.05, z: 5.7, labelY: 1.15 },
];
const COLORS = { dark: '#293b45', slate: '#65747b', base: '#e9eceb', white: '#f7f7f2', steel: '#b9c4c8', orange: '#fc762c', green: '#219464', blue: '#3a98b9' };
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

// Two small label-only passes: try nearby horizontal space, then the next row.
// The camera, factory geometry and original world projections stay untouched.
function arrangeLabelRects(items, usableWidth, safeTop, safeBottom, selected, sheetBottom) {
  const gap=7,order=['structure','retrieve','compare','overview','validate','concept'];
  const overlap=(a,b)=>a.left<b.left+b.w+gap&&a.left+a.w+gap>b.left&&a.top<b.top+b.h+gap&&a.top+a.h+gap>b.top;
  const labels=items.map(item=>{
    const bottom=sheetBottom!=null&&item.id===selected?Math.min(safeBottom,sheetBottom):safeBottom;
    const maxTop=Math.max(safeTop,bottom-item.h);
    return {...item,baseLeft:item.left,top:Math.min(Math.max(item.top,safeTop),maxTop),maxTop};
  }).sort((a,b)=>(sheetBottom!=null&&a.id===selected?-1:sheetBottom!=null&&b.id===selected?1:order.indexOf(a.id)-order.indexOf(b.id)));
  const candidates=(item,others)=>others.flatMap(other=>[other.left-gap-item.w,other.left+other.w+gap])
    .filter(left=>left>=8&&left+item.w<=usableWidth-8&&Math.abs(left-item.baseLeft)<=80)
    .sort((a,b)=>Math.abs(a-item.baseLeft)-Math.abs(b-item.baseLeft));
  for(let pass=0;pass<2;pass++){
    const placed=[];
    for(const item of labels){
      if(placed.some(other=>overlap(item,other))){
        const positions=candidates(item,placed),clear=positions.find(left=>!placed.some(other=>overlap({...item,left},other)));
        if(clear!==undefined)item.left=clear;
        else if(pass===1){
          const rows=placed.map(other=>other.top+other.h+gap).filter(top=>top>=item.top&&top<=item.maxTop).sort((a,b)=>a-b);
          let found=false;
          for(const top of rows){
            for(const left of [item.left,...positions]){
              if(!placed.some(other=>overlap({...item,left,top},other))){item.left=left;item.top=top;found=true;break;}
            }
            if(found)break;
          }
        }
      }
      placed.push(item);
    }
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
  scene.add(new THREE.HemisphereLight('#fffdf3','#becad1',2.35));
  const sun = new THREE.DirectionalLight('#fff8e9',3.7);sun.position.set(-6,15,8);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-15;sun.shadow.camera.right=15;sun.shadow.camera.top=15;sun.shadow.camera.bottom=-15;sun.shadow.normalBias=.035;sun.shadow.bias=-.0001;sun.shadow.radius=3;scene.add(sun);
  const fill = new THREE.DirectionalLight('#d6e8f0',1.15);fill.position.set(10,7,-10);scene.add(fill);
  const floor=new THREE.Group();scene.add(floor);
  cube(floor,20.8,.34,19.6,0,-.24,0,'#aeb9bc',.15,.12);
  cube(floor,20.55,.1,19.35,0,-.025,0,'#d6dcda',.07);
  for(let x=-10;x<=10;x++){strip(floor,[x,-9.5],[x,9.5],.034,.017,x%3===0?'#bec8c5':'#c7d0cc');}
  for(let z=-9;z<=9;z++){strip(floor,[-10,z],[10,z],.035,.017,z%3===0?'#bec8c5':'#c7d0cc');}
  // A narrow safety lane makes the miniature workstations feel like one factory.
  const lane=[[-8,-6],[-3,-7],[5,-6],[8,-1],[7,6],[0,8],[-7,6],[-8,-6]];
  lane.slice(0,-1).forEach((a,i)=>{const b=lane[i+1],len=Math.hypot(b[0]-a[0],b[1]-a[1]),n=Math.floor(len/.65);for(let j=0;j<n;j++){const t=j/n,u=Math.min((j+.5)/n,1);strip(floor,[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t],[a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u],.05,.065,'#e9ac41');}});
  const floorLabel=canvasTexture((ctx,w,h)=>{ctx.clearRect(0,0,w,h);ctx.fillStyle='#71817d';ctx.font='bold 56px sans-serif';ctx.textAlign='center';ctx.fillText('KITCHEN AX',w/2,90);ctx.font='20px sans-serif';ctx.fillText('PRODUCT PLANNING FACTORY',w/2,132);});
  const labelMaterial=new THREE.MeshBasicMaterial({map:floorLabel,transparent:true,depthWrite:false});resources.push(labelMaterial);const labelGeometry=new THREE.PlaneGeometry(4,2);resources.push(labelGeometry);const floorTitle=new THREE.Mesh(labelGeometry,labelMaterial);floorTitle.rotation.x=-Math.PI/2;floorTitle.position.set(3,.06,6.5);floor.add(floorTitle);
  // Back-of-house architecture: a bright, open workshop, rather than a HUD backdrop.
  const architecture=new THREE.Group();scene.add(architecture);
  for(let i=0;i<4;i++){
    const x=-9+i*5.65;
    cube(architecture,.22,3.65,.24,x,1.84,-9.1,'#bbc5c5',.025,.2);
    cube(architecture,.38,.7,.37,x,.35,-9.1,'#d0b15f');
    if(i<3){cube(architecture,5.5,.55,.17,x+2.8,.3,-9.1,'#e1e5df');cube(architecture,5.5,.09,.19,x+2.8,2.85,-9.1,'#b0bfc1');cube(architecture,5.5,.14,.21,x+2.8,3.6,-9.1,'#c2cdcb');}
  }
  cube(architecture,18,.16,.2,-.5,3.85,-9.1,'#a9b5b4');
  for(let i=0;i<8;i++){const x=-8.6+i*2.28;cube(architecture,.055,2.75,.06,x,1.9,-9.13,'#becac8',.005);}
  for(let i=0;i<6;i++){plant(architecture,-9.2+i*3.5,-8.35,.78);}
  for(const [x,z] of [[-9,6],[8,7],[8,-6],[-8,-6]])plant(floor,x,z,1);

  const stations = {};
  const stationRims=[];
  const platform=(s)=>{
    const group=new THREE.Group();group.position.set(s.x,0,s.z);group.userData.station=s.id;scene.add(group);stations[s.id]=group;
    cube(group,3.8,.21,3.25,0,.19,0,'#536069',.1,.15);
    cube(group,3.66,.11,3.11,0,.35,0,'#f1f0e9',.05);
    const rimMaterial=new THREE.MeshStandardMaterial({color:'#b6c1bf',emissive:'#fc762c',emissiveIntensity:0,roughness:.4});resources.push(rimMaterial);
    const rim=new THREE.Group();
    for(const [w,d,x,z] of [[3.75,.045,0,1.64],[3.75,.045,0,-1.64],[.045,3.25,-1.9,0],[.045,3.25,1.9,0]]){const m=new THREE.Mesh(roundedGeo(w,.055,d,.01),rimMaterial);m.position.set(x,.35,z);rim.add(m);}group.add(rim);
    stationRims.push({id:s.id,material:rimMaterial,group});
    for(const x of [-1.55,1.55])for(const z of [-1.3,1.3])cube(group,.22,.23,.25,x,.13,z,'#637074');
    return group;
  };
  // 01 — source intake, books, storage cabinets, and a small scanner.
  let g=platform(STATIONS[0]);
  cube(g,2.2,1.45,.43,0,1.12,-1.08,COLORS.steel,.06,.2);
  for(let row=0;row<3;row++){
    cube(g,2.08,.045,.53,0,.53+row*.48,-.96,'#67787a');
    for(let i=0;i<8;i++){
      const h=.29+(i%3)*.035, x=-.88+i*.25;
      cube(g,.19,h,.36,x,.54+row*.48+h/2,-.94,['#e5e6d6','#8ba7b3','#b5c0bd','#d5a75d'][i%4],.013);
      cube(g,.115,.025,.018,x,.54+row*.48+h*.7,-.746,'#f7f8ef',.003);
    }
  }
  cube(g,.64,1.39,.68,-1.25,1.07,.14,'#9eafb1',.05,.4);cube(g,.4,.55,.02,-1.25,1.27,.493,'#314f59');cube(g,.04,.08,.025,-1.02,.99,.5,'#e6f1e7');
  cube(g,1.5,.13,.8,.48,1.02,.55,'#f9f9f1');for(const x of [-.1,1.06])cube(g,.075,.65,.075,x,.67,.55,COLORS.slate);
  cube(g,.72,.24,.5,.4,1.19,.53,'#c8cecc');cube(g,.53,.045,.3,.4,1.33,.53,COLORS.dark);
  cube(g,.4,.28,.37,1.16,.56,-.05,'#eba643');
  for(let i=0;i<4;i++)cube(g,.48,.035,.35,.2,1.08+i*.04,.93,i%2?'#e6e8e1':'#b9cfdb');
  monitor(g,-.67,1.5,.4,.7);

  // 02 — customer needs board, colored evidence cards, desk and sorted trays.
  g=platform(STATIONS[1]);board(g,'sticky',0,1.83,-.92,2.73,1.5);
  cube(g,2.8,.13,.76,0,.97,.52,'#f5f4ec');for(const x of [-1.17,1.17])cube(g,.1,.58,.54,x,.65,.52,'#aebcbd');
  for(let i=0;i<3;i++){cube(g,.55,.12,.4,-.88+i*.86,1.09,.46,['#f4c261','#86bdb8','#b4c2d5'][i]);for(let j=0;j<3;j++)cube(g,.37,.025,.24,-.88+i*.86,1.17+j*.032,.46,'#f7f7f1',.005);}
  cube(g,.32,.29,.4,1.28,.57,1.05,'#dba54b');plant(g,-1.5,-1.17,.6);

  // 03 — real solid miniature refrigerators on an inspection platform.
  g=platform(STATIONS[2]);
  const fridge=(x,z,scale,color)=>{
    const rg=new THREE.Group();rg.position.set(x,.42,z);rg.scale.setScalar(scale);g.add(rg);
    cube(rg,1.03,2.08,.84,0,1.04,0,color,.07,.5);
    cube(rg,.97,1.18,.085,0,1.48,.466,'#cbd4d7',.04,.55);
    cube(rg,.97,.73,.085,0,.47,.466,'#c3cdd0',.04,.55);
    cube(rg,.018,1.12,.018,0,1.48,.52,'#677e89',.005);
    cube(rg,.035,.47,.045,-.06,1.47,.539,'#657c89',.01,.7);cube(rg,.035,.47,.045,.06,1.47,.539,'#657c89',.01,.7);
    cube(rg,.36,.023,.04,0,.79,.534,'#6d838d',.005,.7);
    cube(rg,.23,.28,.018,.25,1.62,.522,'#264855',.01);cube(rg,.14,.018,.01,.25,1.66,.536,'#71c9d2',.002);
    cube(rg,.91,.08,.77,0,.03,.025,'#4e636c',.02,.2);
    cube(rg,.025,1.76,.025,-.525,1.11,.25,'#e9f1ef',.006);
  };
  fridge(-.88,-.35,1,'#9eadb5');fridge(.28,-.55,.76,'#6d9aaa');
  board(g,'check',1.15,1.8,-1.05,1.18,1.3);
  cube(g,.91,.12,.7,.95,.99,.7,'#f4f2e9');for(const x of [.6,1.3])cube(g,.065,.61,.48,x,.64,.7,'#a4b2b3');
  cube(g,.4,.45,.37,.95,1.27,.7,'#e0e3dc');cube(g,.21,.15,.025,.95,1.33,.901,'#244a53');cylinder(g,.06,.08,.95,1.54,.68,'#ed8a35');
  monitor(g,-1.38,1.09,1.0,.67);

  // 04 — engineering bench, blueprint board, modular product prototypes.
  g=platform(STATIONS[3]);board(g,'blueprint',0,1.89,-.97,2.75,1.57);
  cube(g,2.7,.16,1.07,0,1.08,.43,'#f6f6ee');for(const x of [-1.08,1.08]){cube(g,.17,.65,.75,x,.69,.43,'#b3c0c2');cube(g,.22,.25,.79,x,.51,.43,'#eba44a');}
  for(let i=0;i<3;i++){const x=-.84+i*.84;cube(g,.53,.11,.53,x,1.23,.48,'#728b95');cube(g,.36,.29+i*.12,.35,x,1.33+i*.06,.48,'#e8edea',.04);cube(g,.21,.018,.25,x,1.49+i*.12,.48,'#c0d2d6');}
  monitor(g,-1.15,1.62,.29,.58);plant(g,1.53,-1.16,.65);

  // 05 — checklist, magnifier and inspection tools.
  g=platform(STATIONS[4]);board(g,'check',-.33,1.9,-.95,2.35,1.55);
  cube(g,2.65,.14,1.03,0,.96,.47,'#f3f2e8');for(const x of [-1.1,1.1])cube(g,.13,.57,.7,x,.65,.47,'#aeb9b8');
  cylinder(g,.24,.06,.51,1.07,.35,'#617983');cube(g,.065,.67,.065,.51,1.42,.35,'#506973');
  const glassMaterial=new THREE.MeshPhysicalMaterial({color:'#b9e1e4',roughness:.12,metalness:.03,transparent:true,opacity:.42});resources.push(glassMaterial);
  const torusGeometry=new THREE.TorusGeometry(.35,.048,10,28);resources.push(torusGeometry);const magnifier=new THREE.Mesh(torusGeometry,mat('#4c6b77',.3,.6));magnifier.position.set(.51,1.89,.36);g.add(magnifier);
  const glassGeometry=new THREE.CircleGeometry(.32,28);resources.push(glassGeometry);const glass=new THREE.Mesh(glassGeometry,glassMaterial);glass.position.copy(magnifier.position);g.add(glass);
  for(let i=0;i<3;i++){cube(g,.35,.18,.34,-.94+i*.46,1.1,.55,i===1?'#d9b785':'#e4e8df');cube(g,.13,.035,.1,-.94+i*.46,1.21,.55,i===1?'#ed9b42':'#64a28b');}
  monitor(g,1.05,1.47,.26,.65);

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
  const packets=[];
  const addConveyor=(end,index)=>{
    const s=new THREE.Vector3(0,0,0),e=new THREE.Vector3(end.x,0,end.z),dir=e.clone().normalize(),length=e.length(),start=dir.clone().multiplyScalar(1.7),finish=e.clone().addScaledVector(dir,-1.8);
    const mid=start.clone().add(finish).multiplyScalar(.5),len=start.distanceTo(finish),angle=Math.atan2(dir.x,dir.z);if(len<.3)return;
    const belt=new THREE.Group();belt.position.copy(mid);belt.rotation.y=angle;scene.add(belt);
    cube(belt,.63,.16,len,0,.56,0,'#bdc7c4',.02,.3);cube(belt,.47,.035,len,0,.66,0,'#374e51',.006);
    for(const x of [-.29,.29])cube(belt,.045,.12,len+.1,x,.7,0,'#a6b6b6',.009,.6);
    const count=Math.ceil(len/.18);for(let j=0;j<count;j++){const roller=cylinder(belt,.044,.48,0,.68,-len/2+(j+.5)*len/count,'#8e9fa0',.044,10);roller.rotation.z=Math.PI/2;}
    for(const z of [-len*.37,len*.37]){for(const x of [-.22,.22])cube(belt,.045,.47,.045,x,.25,z,'#778c8d');cube(belt,.6,.055,.17,0,.085,z,'#a6b4b2');}
    for(let j=0;j<2;j++){
      const packet=new THREE.Group();cube(packet,.31,.12,.22,0,0,0,j%2?'#e9b356':'#eaf3ed',.012);cube(packet,.21,.018,.14,0,.07,0,'#fffdf0',.004);scene.add(packet);packets.push({mesh:packet,start,finish,phase:j*.5+index*.11,id:end.id});
    }
  };
  STATIONS.forEach(addConveyor);
  // Small shipping crates and architecture add believable scale without hiding the work.
  for(const [x,z] of [[-7.7,2.2],[7.45,-3.3],[-4,7.6]]){
    cube(floor,.56,.4,.49,x,.28,z,'#d9c7a2');cube(floor,.07,.42,.51,x,.29,z,'#e6d7b9');cube(floor,.17,.09,.018,x+.14,.34,z+.255,'#faf8ed');
  }
  return {
    scene, stations, stationRims, packets, beaconMaterial,
    dispose(){scene.traverse(o=>{if(o.isMesh){if(o.geometry&&!Array.from(geometries.values()).includes(o.geometry))o.geometry.dispose();}});geometries.forEach(x=>x.dispose());materials.forEach(x=>x.dispose());resources.forEach(x=>x.dispose?.());},
  };
}

export default function FactoryScene({ selected='overview', onSelect, active=null, stepStates={}, reducedMotion=false, onHome, panelWidth=0 }) {
  const hostRef=useRef(null), labelsRef=useRef({}), dataRef=useRef({ selected, active, stepStates, reducedMotion, onSelect, onHome, panelWidth });
  const [unavailable,setUnavailable]=useState(false);
  dataRef.current={selected,active,stepStates,reducedMotion,onSelect,onHome,panelWidth};
  useEffect(()=>{
    const host=hostRef.current;if(!host)return;
    let renderer, factory, frame=0, stopped=false, last=0;
    try{
      renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.6));renderer.setClearColor('#edf0ed',0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.08;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;
      renderer.domElement.className='factory-webgl';renderer.domElement.setAttribute('aria-hidden','true');host.prepend(renderer.domElement);
      factory=createFactory(renderer);
    }catch(err){setUnavailable(true);renderer?.dispose();return;}
    const camera=new THREE.OrthographicCamera(-12,12,12,-12,.1,100),direction=new THREE.Vector3(13,17,18).normalize();
    const target=new THREE.Vector3(0,.35,0),desiredTarget=target.clone(),projection=new THREE.Vector3();
    let width=1,height=1,currentPanelWidth=0;
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
      if(stopped)return;frame=requestAnimationFrame(render);if(document.hidden)return;
      const {selected:sel,active:activeId,stepStates:states,reducedMotion:reduce,panelWidth:requestedPanelWidth}=dataRef.current;
      const interval=reduce?120:1000/30;if(ms-last<interval)return;const dt=last?Math.min((ms-last)/1000,.08):.033;last=ms;
      const station=factory.stations[sel],selectedPos=station?.position;
      desiredTarget.set(selectedPos?.x*.075||0,.35,selectedPos?.z*.075||0);
      const desiredZoom=sel&&sel!=='overview'?1.035:1;
      const smooth=reduce?1:1-Math.exp(-dt*6);
      target.lerp(desiredTarget,smooth);camera.zoom+=(desiredZoom-camera.zoom)*smooth;
      currentPanelWidth+=(clampPanel(requestedPanelWidth)-currentPanelWidth)*smooth;
      if(Math.abs(currentPanelWidth-clampPanel(requestedPanelWidth))<.1)currentPanelWidth=clampPanel(requestedPanelWidth);
      // Keep the full canvas filled. An off-axis camera moves the factory left
      // by half the open drawer width; fitting uses the remaining work area.
      const usableWidth=Math.max(280,width-currentPanelWidth),aspect=width/height;
      const baseExtent=Math.max(8.0,9.5/(usableWidth/height));
      camera.left=-baseExtent*aspect;camera.right=baseExtent*aspect;camera.top=baseExtent;camera.bottom=-baseExtent;
      camera.setViewOffset(width,height,currentPanelWidth/2,0,width,height);
      camera.position.copy(direction).multiplyScalar(31).add(target);camera.lookAt(target);camera.updateMatrixWorld();
      const stateKey=JSON.stringify(states);
      if(sel!==oldSelected||activeId!==oldActive||stateKey!==oldStates){
        factory.stationRims.forEach(r=>{const status=stageStatus(states[r.id]),isActive=activeId===r.id,isSelected=sel===r.id;r.material.color.set(isActive?COLORS.orange:isSelected?'#5bc6c4':status==='done'?COLORS.green:'#b6c1bf');r.material.emissive.set(isActive?COLORS.orange:isSelected?'#2b979d':COLORS.green);r.material.emissiveIntensity=isActive ? .38 : isSelected ? .15 : status==='done' ? .05 : 0;});oldSelected=sel;oldActive=activeId;oldStates=stateKey;
      }
      const elapsed=ms/1000;
      factory.packets.forEach(p=>{const t=reduce?p.phase%1:(elapsed*.105+p.phase)%1;p.mesh.position.copy(p.start).lerp(p.finish,t);p.mesh.position.y=.84;p.mesh.visible=Boolean(activeId)&&activeId===p.id;});
      factory.beaconMaterial.emissiveIntensity=activeId?(reduce?1:1.1+Math.sin(elapsed*4)*.45):.4;
      const app=host.closest('.fullscreen-app'),hostRect=host.getBoundingClientRect();
      const uiRect=selector=>{const element=app?.querySelector(selector);if(!element)return null;const rect=element.getBoundingClientRect();return rect.width&&rect.height?{top:rect.top-hostRect.top,bottom:rect.bottom-hostRect.top,left:rect.left-hostRect.left,right:rect.right-hostRect.left}:null;};
      const header=uiRect('.topbar'),footerControls=[uiRect('.scene-controls'),uiRect('.floating-run')].filter(rect=>rect&&rect.right>0&&rect.left<usableWidth&&rect.top>height*.45);
      const safeTop=header?Math.max(8,header.bottom+8):8,safeBottom=Math.max(safeTop+70,Math.min(height-8,...footerControls.map(rect=>rect.top-8)));
      const mobileReturn=width<=760?uiRect('.panel-return'):null,sheetBottom=mobileReturn?mobileReturn.top-8:null,projectedLabels=[];
      for(const s of [...STATIONS,{id:'overview',x:0,z:0,labelY:1.12}]){
        const el=labelsRef.current[s.id];if(!el)continue;const w=el.offsetWidth,h=el.offsetHeight;if(!w||!h)continue;
        projection.set(s.x,s.labelY,s.z).project(camera);const gutter=w/2+8,projectedX=(projection.x*.5+.5)*width,x=Math.min(Math.max(projectedX,gutter),Math.max(gutter,usableWidth-gutter)),y=(-projection.y*.5+.5)*height;
        projectedLabels.push({id:s.id,el,w,h,left:x-w/2,top:y-h,visible:projection.z>-1&&projection.z<1});
      }
      for(const label of arrangeLabelRects(projectedLabels,usableWidth,safeTop,safeBottom,sel,sheetBottom)){
        label.el.style.transform=`translate3d(${label.left+label.w/2}px,${label.top+label.h}px,0) translate(-50%,-100%)`;label.el.style.visibility=label.visible?'visible':'hidden';
      }
      renderer.render(factory.scene,camera);
    }
    frame=requestAnimationFrame(render);
    return()=>{stopped=true;cancelAnimationFrame(frame);observer.disconnect();document.removeEventListener('visibilitychange',onVisibility);renderer.domElement.removeEventListener('pointerdown',pointerDown);renderer.domElement.removeEventListener('pointerup',pointerUp);renderer.domElement.removeEventListener('pointermove',pointerMove);renderer.domElement.removeEventListener('webglcontextlost',onLost);factory.dispose();renderer.dispose();renderer.domElement.remove();};
  },[]);
  return <div className={`factory-scene ${unavailable?'factory-no-webgl':''}`} ref={hostRef} style={{'--factory-panel-width':`${Math.max(0,Number(panelWidth)||0)}px`}} aria-label="상품기획 공장 3D 작업 공간">
    <div className="factory-scene-grain" aria-hidden="true" />
    <div className="factory-scene-corner"><span className="factory-isometric-mark" aria-hidden="true">◇</span><span>AX PLANNING FACTORY<small>작은 불편에서, 더 나은 일상으로</small></span></div>
    <div className="factory-label-layer">
      {STATIONS.map(s=>{const status=stageStatus(stepStates[s.id]);return <button key={s.id} ref={el=>{labelsRef.current[s.id]=el;}} className={`factory-station-label ${selected===s.id?'is-selected':''} status-${status}`} onClick={()=>onSelect?.(s.id)} aria-pressed={selected===s.id} aria-label={`${s.no} ${s.title} · ${statusText(status)}${selected===s.id?' · 선택됨':''}`} title={`${s.title} — ${s.caption}`}>
        <span className="factory-station-meta"><span className="factory-station-number">{s.no}<small>SKILL</small></span><span className="factory-station-badges">{selected===s.id&&<span className="factory-station-selected">선택</span>}<span className="factory-station-state"><i/>{statusText(status)}</span></span></span><span className="factory-station-title"><strong>{s.title}</strong></span><span className="factory-station-caption">{s.caption}</span>
      </button>;})}
      <button ref={el=>{labelsRef.current.overview=el;}} className={`factory-planner-label ${selected==='overview'?'is-selected':''}`} onClick={()=>onHome?onHome():onSelect?.('overview')} aria-pressed={selected==='overview'}><span className="factory-planner-eyebrow"><i/> ORCHESTRATOR</span><strong>메인 기획 Agent</strong><span>다섯 Skill의 작업을 연결합니다</span></button>
    </div>
    {unavailable&&<p className="factory-fallback-message">3D 화면을 표시할 수 없습니다. 업무 공간 이름을 선택해 진행하세요.</p>}
    <div className="factory-scene-legend" aria-hidden="true"><span><i className="legend-active"/>실행 중</span><span><i className="legend-done"/>완료</span><span>업무 공간을 눌러 자세히 보기 <b>↗</b></span></div>
  </div>;
}
