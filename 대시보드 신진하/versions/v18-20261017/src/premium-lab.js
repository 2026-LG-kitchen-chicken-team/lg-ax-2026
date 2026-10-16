import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// Visual materials and set dressing only. These props never read or advance a run.
export function createPremiumLab(t){
  const {cube,cylinder,canvasTexture,resources}=t;
  const random=(seed=73)=>()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
  const oak=canvasTexture((c,w,h)=>{
    c.fillStyle='#cdb58c';c.fillRect(0,0,w,h);const r=random(34);
    for(let i=0;i<170;i++){const y=r()*h;c.strokeStyle=i%3?'#ab875322':'#fff4d44d';c.lineWidth=.5+r()*2;c.beginPath();c.moveTo(0,y);c.bezierCurveTo(w*.3,y+r()*9,w*.65,y-r()*8,w,y+2);c.stroke();}
  },512,128);
  const tile=canvasTexture((c,w,h)=>{
    const r=random(8),s=w/4;
    c.fillStyle='#d6cbb8';c.fillRect(0,0,w,h);
    for(let x=0;x<4;x++)for(let y=0;y<4;y++){
      const v=Math.floor(r()*4);c.fillStyle=['#eee7d9','#ebe3d5','#f0e9dc','#ede5d7'][v];c.fillRect(x*s+1,y*s+1,s-2,s-2);
      const sheen=c.createLinearGradient(x*s,y*s,(x+1)*s,(y+1)*s);sheen.addColorStop(0,'#ffffff25');sheen.addColorStop(1,'#beaa8908');c.fillStyle=sheen;c.fillRect(x*s+1,y*s+1,s-2,s-2);
      c.fillStyle='#aa947c0a';for(let n=0;n<110;n++)c.fillRect(x*s+r()*s,y*s+r()*s,1+r()*2,.6);
      c.strokeStyle='#fffaf033';c.lineWidth=1;c.strokeRect(x*s+2,y*s+2,s-4,s-4);
    }
  },512,512);
  tile.wrapS=tile.wrapT=THREE.RepeatWrapping;tile.repeat.set(64,64);
  const material=new THREE.MeshStandardMaterial({map:oak,roughness:.60,color:'#fff6e7'});resources.push(material);
  const shadow=canvasTexture((c,w,h)=>{const r=c.createRadialGradient(w/2,h/2,w*.20,w/2,h/2,w*.49);r.addColorStop(0,'#53412f42');r.addColorStop(.70,'#53412f21');r.addColorStop(1,'#53412f00');c.fillStyle=r;c.fillRect(0,0,w,h);},256,256);
  const shadowMat=new THREE.MeshBasicMaterial({map:shadow,transparent:true,depthWrite:false,toneMapped:false});resources.push(shadowMat);
  const leafGeo=new THREE.SphereGeometry(1,8,5),leafMat=new THREE.MeshStandardMaterial({color:'#ffffff',roughness:.8});resources.push(leafGeo,leafMat);
  const wood=mesh=>{mesh.material=material;return mesh;};
  const shade=(g,w,d,y=.012)=>{const geo=new THREE.PlaneGeometry(w,d),m=new THREE.Mesh(geo,shadowMat);m.rotation.x=-Math.PI/2;m.position.y=y;m.raycast=()=>{};g.add(m);resources.push(geo);};
  const plant=(g,x,z,s=1)=>{
    cylinder(g,.17*s,.34*s,x,.26*s,z,'#f5f0e4',.135*s,16);
    cylinder(g,.148*s,.015*s,x,.438*s,z,'#5c5140',.148*s,16);
    const leaves=new THREE.InstancedMesh(leafGeo,leafMat,36),dummy=new THREE.Object3D(),r=random(91);
    cylinder(g,.014*s,.69*s,x,.76*s,z,'#667c47',.014*s,7);
    for(let i=0;i<36;i++){
      const a=i*2.399,reach=(.10+r()*.20)*s,y=(.57+i/36*.65)*s;
      dummy.position.set(x+Math.cos(a)*reach,y,z+Math.sin(a)*reach);dummy.rotation.set(Math.sin(a)*.9,a,Math.cos(a)*.65);dummy.scale.set(.105*s,(.17+r()*.045)*s,.045*s);dummy.updateMatrix();leaves.setMatrixAt(i,dummy.matrix);leaves.setColorAt(i,new THREE.Color(['#657b42','#849859','#a5b071','#748e4d'][i%4]));
    }
    leaves.castShadow=true;g.add(leaves);
  };
  const pot=(g,x,z)=>{cube(g,.55,.72,.55,x,.37,z,'#f6f1e5',.045);const p=new THREE.Group();p.position.set(x,.44,z);g.add(p);plant(p,0,0,1.1);};
  const mug=(g,x,y,z)=>{cylinder(g,.065,.13,x,y+.065,z,'#f2eada',.055,12);cylinder(g,.052,.009,x,y+.132,z,'#7c6245',.052,12);cube(g,.06,.065,.03,x+.072,y+.07,z,'#e8dcc5',.012);};
  const book=(g,x,y,z,color='#9aab92')=>{cube(g,.23,.032,.30,x,y,z,color,.006);cube(g,.21,.018,.28,x,y+.018,z,'#fffaf0',.003);};
  const lamp=(g,x,z)=>{
    cylinder(g,.12,.025,x,1.14,z,'#8a9a88');cylinder(g,.018,.40,x,1.35,z,'#a3aa95',.018,8);
    const arm=cube(g,.31,.025,.03,x+.12,1.56,z,'#a3aa95',.006);arm.rotation.z=-.15;
    cylinder(g,.12,.11,x+.25,1.50,z,'#e4d7b9',.075,16);cylinder(g,.09,.008,x+.25,1.442,z,'#ffeac0',.09,16);
  };
  const roomProps=(id,g)=>{
    // Keep x=+/-2.10 and z=+/-1.75 clear for the existing three-researcher patrol.
    if(id==='retrieve'){
      for(let i=0;i<3;i++){book(g,-1.42,.98+i*.045,.76,i%2?'#cfb98f':'#9ba88e');}
      cube(g,.35,.10,.30,1.02,1.37,.50,'#f3eee0',.018);cube(g,.28,.006,.20,1.02,1.424,.50,'#c3cbb4',.004);
      for(let i=0;i<3;i++)cube(g,.45,.075,.37,-.95+i*.51,.49,-.92,['#8d9d83','#d3bf99','#eee7d7'][i],.012);
      mug(g,.96,1.11,.81);
    }else if(id==='structure'){
      mug(g,-1.01,1.11,.25);book(g,-.77,1.13,.63,'#ccb489');lamp(g,1.02,.18);
      cube(g,.18,.09,.18,.91,1.15,.67,'#b8c4ae',.015);
      for(let i=0;i<4;i++){const p=cube(g,.012,.22,.012,.86+i*.03,1.29,.67,'#b69d6e',.002);p.rotation.z=(i-1.5)*.09;}
    }else if(id==='compare'){
      // A physical removable shelf sample complements the full-sized appliances.
      cube(g,.51,.025,.32,-.19,1.14,.67,'#a8b8ae',.008,.35);
      for(let i=0;i<6;i++)cube(g,.012,.025,.28,-.40+i*.08,1.165,.67,'#e2e8dc',.002,.3);
      cube(g,.18,.11,.16,-.18,1.22,.67,'#f6f1e4',.015);
      for(let i=0;i<3;i++)book(g,1.02,1.23+i*.04,.63,['#e0ccaa','#8fa68f','#f3ead6'][i]);
    }else if(id==='concept'){
      for(const x of [-.79,-.01,.77]){cylinder(g,.10,.02,x,1.50,.47,'#d8c19a',.10,16);cube(g,.17,.025,.07,x,1.52,.47,'#eee2cb',.004);}
      book(g,-.81,1.15,.78,'#adba9d');mug(g,1.10,1.12,.63);
      for(let i=0;i<3;i++)cube(g,.10,.045,.10,-.10+i*.16,1.16,.83,['#99b4a8','#e3c692','#c9d1b5'][i],.005);
    }else{
      lamp(g,-1.03,.15);book(g,-.82,1.15,.76,'#e1c69c');mug(g,.96,1.12,.77);
      cube(g,.38,.06,.24,.65,1.14,.36,'#c4b18c',.012);cube(g,.31,.01,.18,.65,1.18,.36,'#fff7e6',.003);
      for(let i=0;i<3;i++)cube(g,.20,.005,.010,.65,1.187,.32+i*.04,'#9baa92',.001);
    }
  };
  return {wood,tile,shade,plant,pot,mug,book,lamp,roomProps};
}

// Static furniture can share a draw call while each room remains independently
// selectable and animated. Transparent props, live rims and researchers stay separate.
export function batchLabFurniture(group,resources){
  group.updateWorldMatrix(true,true);const inverse=group.matrixWorld.clone().invert(),buckets=new Map();
  group.traverse(mesh=>{let parent=mesh;while(parent&&parent!==group){if(parent.userData.live)return;parent=parent.parent;}if(!mesh.isMesh||mesh.isInstancedMesh||Array.isArray(mesh.material)||mesh.material.transparent)return;const list=buckets.get(mesh.material)||[];list.push(mesh);buckets.set(mesh.material,list);});
  for(const [material,meshes] of buckets){
    if(meshes.length<2)continue;
    const copies=meshes.map(mesh=>{const g=mesh.geometry.index?mesh.geometry.toNonIndexed():mesh.geometry.clone();return g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inverse,mesh.matrixWorld));});
    const merged=mergeGeometries(copies,false);copies.forEach(g=>g.dispose());if(!merged)continue;
    const result=new THREE.Mesh(merged,material);result.castShadow=true;result.receiveShadow=true;group.add(result);resources.push(merged);meshes.forEach(mesh=>mesh.removeFromParent());
  }
}
