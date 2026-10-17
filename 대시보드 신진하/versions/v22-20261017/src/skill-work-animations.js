import * as THREE from 'three';
import {createWorkshopActions} from './workshop-actions.js';

// Visual metaphors only. These objects never produce results or advance a run.
// Each clock advances only for that room's confirmed work (or labelled motion preview).
export function createSkillWorkAnimations(stations,t,parts={},artwork=null){
 const {cube,mat,canvasTexture,resources}=t,controllers={};
 const illustrated=artwork?createWorkshopActions(stations,artwork,resources):null;
 const add=(id,make)=>{const group=new THREE.Group();stations[id].add(group);const clock={time:0};controllers[id]={group,clock,...make(group)};};
 const paper=(g,x,y,z,color='#fff7e3')=>cube(g,.35,.025,.25,x,y,z,color,.006);
 add('retrieve',g=>{
  const sheets=[paper(g,.70,1.46,.75),paper(g,.73,1.49,.77)];
  const scanMat=new THREE.MeshBasicMaterial({color:'#ffb756',transparent:true,opacity:.65,depthWrite:false});resources.push(scanMat);
  const scan=cube(g,.34,.012,.025,1.02,1.435,.50,'#ffb756',.002);scan.material=scanMat;
  return {update(time,active){scan.visible=active;scan.position.z=.38+(Math.sin(time*3)+1)*.12;sheets.forEach((m,i)=>{m.position.z=.76-(active?(time*.2+i*.1)% .30:0);m.position.y=1.43+i*.025;});}};
 });
 add('structure',g=>{
  const cards=Array.from({length:6},(_,i)=>cube(g,.33,.23,.025,0,1.60,-.82,['#e5c98e','#a2b79c','#dcb7a5'][i%3],.012));
  return {update(time,active){const p=active?(Math.sin(time*.9)+1)/2:1;cards.forEach((m,i)=>{const x=(i%3-1)*.63,y=1.62+Math.floor(i/3)*.36;m.position.set(x*p,1.82+(y-1.82)*p,-.82);m.rotation.z=active?Math.sin(time*1.1+i)*.05:0;});}};
 });
 add('compare',g=>{
  const glowMat=new THREE.MeshBasicMaterial({color:'#f4b24d',transparent:true,opacity:.65,depthWrite:false});resources.push(glowMat);
  const shelf=cube(g,.67,.025,.40,-1.06,1.26,-.48,'#f4b24d',.005);shelf.material=glowMat;
  const slip=paper(g,-.28,1.35,.86,'#ffe5b4');
  return {update(time,active){const door=parts.compare?.door,angle=active?.90+Math.sin(time*.7)*.16:0;if(door)door.rotation.y=-angle;shelf.visible=active;glowMat.opacity=.32+(Math.sin(time*2)+1)*.2;slip.rotation.y=active?Math.sin(time)*.2:0;slip.position.y=1.35+(active?Math.sin(time*1.4)*.035:0);}};
 });
 add('concept',g=>{
  const pieces=[cube(g,.31,.13,.27,-.79,1.67,.47,'#e8d4ac',.02),cube(g,.31,.17,.27,-.01,1.76,.47,'#a2bda7',.02),cube(g,.31,.11,.27,.77,1.87,.47,'#f6efd9',.02)];
  return {update(time,active){pieces.forEach((m,i)=>{const cycle=(time*.28+i*.23)%1,offset=active?Math.max(0,Math.sin(cycle*Math.PI*2))*.32:0;m.position.y=[1.67,1.76,1.87][i]+offset;m.rotation.y=active?Math.sin(time*.65+i)*.15:0;});}};
 });
 add('validate',g=>{
  const stamp=cube(g,.19,.24,.18,-.55,1.49,.53,'#8b8d75',.02);cube(stamp,.26,.06,.23,0,-.15,0,'#baaa80',.01);
  const checkMap=canvasTexture((c,w,h)=>{c.clearRect(0,0,w,h);c.strokeStyle='#2a9266';c.lineWidth=20;c.lineCap='round';c.beginPath();c.moveTo(34,72);c.lineTo(65,101);c.lineTo(125,31);c.stroke();},160,128);
  const checkMat=new THREE.MeshBasicMaterial({map:checkMap,transparent:true,depthWrite:false}),checkGeo=new THREE.PlaneGeometry(.40,.32),check=new THREE.Mesh(checkGeo,checkMat);check.position.set(-.85,1.37,.55);check.rotation.x=-Math.PI/2;g.add(check);resources.push(checkMat,checkGeo);
  return {update(time,active){const phase=time%2.2;stamp.position.y=active?1.49-Math.max(0,1-Math.abs(phase-.8)/.25)*.18:1.49;check.visible=active&&phase>.85;}};
 });
 add('web',g=>{
  const globe=new THREE.Group();globe.position.set(-.92,1.62,-.28);g.add(globe);
  const globeMat=mat('#6c9a92',.44,.18),geo=new THREE.SphereGeometry(.36,14,10),ball=new THREE.Mesh(geo,globeMat);globe.add(ball);resources.push(geo);
  const wireGeo=new THREE.SphereGeometry(.37,10,6),wireMat=new THREE.MeshBasicMaterial({color:'#d4e7d7',wireframe:true,transparent:true,opacity:.5}),wire=new THREE.Mesh(wireGeo,wireMat);globe.add(wire);resources.push(wireGeo,wireMat);
  const slip=paper(g,.62,1.37,.65);return {update(time,active){globe.rotation.y=active?time*.36:0;slip.position.z=.65+(active?Math.sin(time)*.08:0);}};
 });
 return {update({activeIds=[],reducedMotion=false,dt=0}={}){
  illustrated?.update({activeIds,reducedMotion,dt});
  for(const [id,c] of Object.entries(controllers)){const active=activeIds.includes(id);c.group.visible=active&&!artwork?.ready;if(active&&!reducedMotion)c.clock.time+=Math.min(.1,Math.max(0,dt));c.update(c.clock.time,active);}
 }};
}
