import * as THREE from 'three';
import {SKILL_ACTIONS} from './skill-choreography.js';
// Moving props explain each Skill. These are illustrations, never task results or progress.
export function createWorkshopActions(stations,artwork,resources){
 const rooms={};
 function material(color){const m=new THREE.MeshBasicMaterial({color,transparent:true,depthWrite:false,depthTest:false,side:THREE.DoubleSide});resources.push(m);return m;}
 const sage=material('#537765'),gold=material('#f8b852'),cream=material('#fff9e9'),ink=material('#668074');
 function rect(parent,w,h,x,y,m=cream){const geo=new THREE.PlaneGeometry(w,h),mesh=new THREE.Mesh(geo,m);mesh.position.set(x,y,.01);mesh.renderOrder=2;parent.add(mesh);resources.push(geo);return mesh;}
 function outline(parent,w,h,x,y,m=gold){const group=new THREE.Group();group.position.set(x,y,.02);parent.add(group);rect(group,w,.009,0,-h/2,m);rect(group,w,.009,0,h/2,m);rect(group,.009,h,-w/2,0,m);rect(group,.009,h,w/2,0,m);return group;}
 function circle(parent,r,x,y,m=gold){const geo=new THREE.RingGeometry(r*.82,r,40),mesh=new THREE.Mesh(geo,m);mesh.position.set(x,y,.03);mesh.renderOrder=2.1;parent.add(mesh);resources.push(geo);return mesh;}
 for(const id of Object.keys(SKILL_ACTIONS)){
  const g=new THREE.Group();g.name='skill-action-'+id;stations[id].add(g);g.visible=false;
  const time={value:0};let animate=()=>{};
  if(id==='retrieve'){
   const pages=[0,1,2].map(i=>{const p=rect(g,.10,.13,-.12+i*.015,.34+i*.015);rect(p,.065,.008,0,.03,ink);rect(p,.065,.008,0,0,ink);return p;});
   const scanner=outline(g,.16,.16,.15,.35),beam=rect(scanner,.15,.012,0,0,gold);
   animate=t=>{pages.forEach((p,i)=>{p.position.x=-.20+((t*.07+i*.02)% .34);});beam.position.y=Math.sin(t*3)*.065;};
  }else if(id==='structure'){
   const cards=Array.from({length:6},(_,i)=>rect(g,.055,.065,0,0,material(['#eddba3','#c5d7c6','#e8c7b6'][i%3])));
   animate=t=>cards.forEach((p,i)=>{const a=(Math.sin(t*.8+i*.2)+1)/2;p.position.set((i%3-1)*.075+(1-a)*.10,.62+Math.floor(i/3)*.075,0);p.rotation.z=(1-a)*(i%2?-.15:.15);});
  }else if(id==='compare'){
   const fridge=outline(g,.18,.36,-.27,.61),table=outline(g,.24,.18,.25,.63),marker=rect(g,.20,.009,.25,.62,gold);
   animate=t=>{fridge.visible=Math.sin(t*.9)>-.4;table.visible=Math.sin(t*.9)<.4;marker.position.y=.57+(Math.sin(t*1.7)+1)*.05;};
  }else if(id==='concept'){
   const blocks=[0,1,2].map(i=>{const b=rect(g,.075,.09,-.12+i*.1,.34,material(['#c5d7c6','#f0d3a0','#f3ede0'][i]));outline(b,.075,.09,0,0,sage);return b;});
   animate=t=>blocks.forEach((p,i)=>{const a=(Math.sin(t*1.1-i*.8)+1)/2;p.position.y=.34+a*.065;p.rotation.z=Math.sin(t*.7+i)*.10;p.position.x=(-.12+i*.1)*(1-a*.35);});
  }else if(id==='validate'){
   const lens=circle(g,.06,-.15,.36);rect(lens,.014,.07,.045,-.06,sage).rotation.z=.5;
   const stamp=rect(g,.035,.05,.18,.42,sage),foot=rect(stamp,.09,.018,0,-.035,gold);outline(g,.13,.12,.16,.33,ink);
   animate=t=>{lens.position.x=-.18+Math.sin(t*1.2)*.08;lens.position.y=.37+Math.cos(t*1.2)*.02;stamp.position.y=.43-Math.max(0,Math.sin(t*2))*.07;foot.visible=true;};
  }else{
   const search=outline(g,.22,.14,-.19,.51),lens=circle(search,.027,-.06,.015);rect(lens,.009,.04,.026,-.03,sage).rotation.z=.6;
   const cursor=rect(search,.008,.065,.05,0,gold),file=rect(g,.07,.09,.15,.36);rect(file,.045,.007,0,.02,ink);rect(file,.045,.007,0,0,ink);
   animate=t=>{cursor.visible=Math.sin(t*4)>0;file.position.x=.05+(t*.05% .16);file.position.y=.40-(t*.025% .08);};
  }
  rooms[id]={g,time,animate};
 }
 return {update({activeIds=[],reducedMotion=false,dt=0}={}){for(const [id,r]of Object.entries(rooms)){
  const art=artwork.room(id);r.g.visible=Boolean(art?.frame&&activeIds.includes(id));if(!r.g.visible)continue;
  r.g.position.copy(art.sprite.position);r.g.quaternion.copy(art.sprite.quaternion);r.g.scale.set(art.sprite.scale.x,art.sprite.scale.y,1);
  if(!reducedMotion)r.time.value+=Math.max(0,Math.min(.1,dt));r.animate(r.time.value);
 }}};
}
