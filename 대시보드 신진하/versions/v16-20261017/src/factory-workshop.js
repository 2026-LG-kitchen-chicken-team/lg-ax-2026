import * as THREE from 'three';

// All furniture stays inside the original room footprint and its perimeter
// walking lane. The execution/layout modules do not depend on this decoration.
export function buildWorkroom(id,g,t){
 const {cube,cylinder,monitor,board,plant}=t,ivory='#f6f3e9',sage='#789487',oak='#c7ad7e',steel='#9eafa7';
 const desk=(x,z,w=2.5,d=.76)=>{
  cube(g,w,.12,d,x,1.04,z,ivory,.05);cube(g,w,.045,d,x,.965,z,oak,.02);
  for(const dx of [-w*.39,w*.39]){cube(g,.09,.57,d*.72,x+dx,.69,z,steel);cube(g,.28,.045,d*.78,x+dx,.415,z,'#738a7e');}
 };
 const papers=(x,y,z)=>{for(let i=0;i<4;i++)cube(g,.31,.018,.23,x+i*.012,y+i*.021,z,i%2?'#fffdf3':'#d5ded0',.005);cube(g,.22,.005,.012,x,y+.085,z+.02,'#b1c0b6',.001);};
 const stool=(x,z)=>{cylinder(g,.23,.075,x,.75,z,sage);cylinder(g,.04,.31,x,.56,z,steel);for(let i=0;i<3;i++){const a=i*Math.PI*2/3;cube(g,.045,.12,.045,x+Math.cos(a)*.16,.44,z+Math.sin(a)*.16,steel);}};
 const drawers=(x,z,w=.65,h=.77)=>{
  cube(g,w,h,.48,x,.40+h/2,z,ivory,.035);
  for(let i=0;i<3;i++){const y=.43+(i+.5)*(h-.06)/3;cube(g,w-.06,(h-.10)/3,.035,x,y,z+.255,'#e3e7dc',.015);cube(g,w*.35,.028,.022,x,y+.03,z+.28,steel,.005);}
  cube(g,w+.03,.045,.51,x,.42+h,z,oak,.012);
 };
 const laptop=(x,y,z)=>{
  cube(g,.40,.025,.28,x,y,z,'#7f9690',.01);cube(g,.34,.009,.17,x,y+.018,z+.02,'#c5d0c4',.004);monitor(g,x,y+.23,z-.105,.55);
 };
 const bookcase=(x,z,w=2.3)=>{
  cube(g,w,1.66,.37,x,1.23,z,'#d6c5a1',.025);
  for(let row=0;row<3;row++){
   const y=.49+row*.49;cube(g,w-.08,.055,.43,x,y,z+.04,ivory,.012);
   for(let i=0;i<9;i++){const h=.31+(i%3)*.045,bx=x-w*.42+i*w*.105;cube(g,w*.078,h,.29,bx,y+h/2+.03,z+.08,['#b1bba7','#f0e7cd','#6c8e8e','#d7b46e'][i%4],.008);cube(g,w*.045,.018,.008,bx,y+h*.7,z+.23,'#f9f8e8',.001);}
  }
  cube(g,w,.055,.43,x,2.08,z+.02,ivory);
 };
 const fridge=(x,z,scale=1)=>{
  const f=new THREE.Group();f.position.set(x,.41,z);f.scale.setScalar(scale);g.add(f);
  cube(f,.92,2.02,.72,0,1.01,0,'#bac6c3',.06,.4);
  for(const [y,h] of [[1.43,1.10],[.43,.73]]){cube(f,.87,h,.075,0,y,.398,'#e4e8de',.035,.25);cube(f,.036,h*.60,.04,.31,y,.45,'#8c9e95',.008,.6);}
  cube(f,.018,1.01,.012,0,1.43,.445,'#a8b5aa',.004);cube(f,.17,.21,.016,-.23,1.60,.446,'#4b685f',.008);cube(f,.10,.016,.006,-.23,1.62,.46,'#c3ddd2',.001);cube(f,.82,.045,.65,0,.025,.02,'#597268');
 };
 const appliance=(x,z,type)=>{
  cube(g,.73,.78,.65,x,.80,z,ivory,.035,.15);cube(g,.64,.57,.04,x,.76,z+.35,'#869d93',.018,.4);cube(g,.53,.45,.015,x,.76,z+.377,type==='oven'?'#344b44':'#d1ded3',.01);cube(g,.43,.028,.04,x,1.01,z+.39,'#bec9bd',.008,.5);
  for(let i=0;i<3;i++)cylinder(g,.025,.025,x-.17+i*.17,1.22,z+.20,steel,.025,8);
 };
 if(id==='retrieve'){
  bookcase(-.20,-1.04,2.55);drawers(-1.39,.78,.54,.91);desk(.55,.54,1.69,.76);
  monitor(g,.12,1.47,.39,.8);cube(g,.48,.20,.36,1.02,1.20,.50,'#c8d1c4');cube(g,.34,.022,.20,1.02,1.31,.50,'#667e74');papers(.45,1.12,.77);stool(.65,1.26);plant(g,1.42,-1.04,.62);
 }else if(id==='structure'){
  board(g,'sticky',0,1.83,-1.05,2.6,1.40);desk(0,.42,2.54,.76);drawers(-1.40,-.07,.46,.76);
  laptop(.42,1.13,.44);papers(-.75,1.13,.49);papers(.94,1.13,.51);stool(-.62,1.19);stool(.72,1.19);plant(g,1.43,-1.08,.64);
 }else if(id==='compare'){
  fridge(-1.06,-.71,.91);fridge(-.15,-.63,.51);board(g,'check',.56,1.92,-1.05,1.75,1.37);appliance(1.10,.64,'oven');desk(-.58,.73,1.40,.61);
  laptop(-.89,1.13,.72);papers(-.14,1.13,.76);stool(-.47,1.31);cube(g,.45,.32,.36,.01,.59,-.62,'#d2be95');plant(g,1.48,-1.18,.6);
 }else if(id==='concept'){
  board(g,'blueprint',-.12,1.87,-1.06,2.52,1.43);desk(0,.44,2.56,.92);drawers(1.42,-.24,.43,.70);
  for(let i=0;i<3;i++){const x=-.79+i*.78;cube(g,.53,.055,.46,x,1.14,.47,'#829b8e');cube(g,.36,.27+i*.09,.30,x,1.30+i*.045,.47,ivory,.035);cube(g,.26,.025,.016,x,1.34+i*.07,.63,'#d3b779',.004);}
  monitor(g,-1.06,1.52,.11,.54);papers(.79,1.13,.83);stool(-.21,1.26);plant(g,1.41,-1.06,.61);
 }else{
  board(g,'check',-.24,1.88,-1.04,2.30,1.45);desk(0,.44,2.53,.82);drawers(-1.41,-.05,.47,.77);monitor(g,1.02,1.51,.24,.65);
  cylinder(g,.18,.045,.15,1.14,.40,'#647f73');cube(g,.045,.52,.045,.15,1.41,.40,steel);
  const ringGeo=new THREE.TorusGeometry(.25,.027,8,24),ring=new THREE.Mesh(ringGeo,t.mat('#65877b',.3,.5));ring.position.set(.15,1.78,.40);g.add(ring);t.resources.push(ringGeo);
  const glassGeo=new THREE.CircleGeometry(.225,24),glassMat=new THREE.MeshPhysicalMaterial({color:'#c3e5d4',transparent:true,opacity:.24,roughness:.08}),glass=new THREE.Mesh(glassGeo,glassMat);glass.position.copy(ring.position);g.add(glass);t.resources.push(glassGeo,glassMat);
  papers(-.85,1.13,.51);papers(.66,1.13,.81);stool(.30,1.25);plant(g,1.43,-1.09,.58);
 }
}

export function buildWorkshopBackdrop(scene,t){
 const {cube,plant,canvasTexture,resources}=t,a=new THREE.Group();a.position.z=-13.8;scene.add(a);
 cube(a,29,1.12,.28,0,.56,0,'#dedfd3',.04);cube(a,29,.15,.46,0,1.13,.02,'#f3f0df',.025);
 const landscape=canvasTexture((ctx,w,h)=>{
  const sky=ctx.createLinearGradient(0,0,0,h);sky.addColorStop(0,'#dfebe7');sky.addColorStop(.65,'#eef1dc');sky.addColorStop(1,'#ccd7b9');ctx.fillStyle=sky;ctx.fillRect(0,0,w,h);
  ctx.fillStyle='#b9cbaa';for(let i=0;i<17;i++){ctx.beginPath();ctx.ellipse(i*w/16,h*.84+Math.sin(i*2)*h*.04,w*.09,h*.15,0,0,Math.PI*2);ctx.fill();}
 },1024,256);
 const viewMat=new THREE.MeshBasicMaterial({map:landscape}),viewGeo=new THREE.PlaneGeometry(28,4.8),outside=new THREE.Mesh(viewGeo,viewMat);outside.position.set(0,3.64,-.20);a.add(outside);resources.push(viewGeo,viewMat);
 const glassMat=new THREE.MeshPhysicalMaterial({color:'#e3eee4',transparent:true,opacity:.17,roughness:.12,metalness:.08});resources.push(glassMat);
 for(let i=0;i<7;i++){
  const x=-14+i*4.65;cube(a,.14,6.15,.24,x,3.09,.16,'#a6b4a9',.018,.2);cube(a,.32,.64,.32,x,.34,.16,'#bda46c',.02,.15);
  if(i<6){cube(a,4.52,.12,.27,x+2.32,3.65,.15,'#b8c4b7',.012);cube(a,4.52,.16,.28,x+2.32,6.07,.15,'#bec7bc',.018);
   const pg=new THREE.PlaneGeometry(4.45,4.75),pane=new THREE.Mesh(pg,glassMat);pane.position.set(x+2.32,3.60,.22);a.add(pane);resources.push(pg);}
 }
 const logo=canvasTexture((ctx,w,h)=>{ctx.clearRect(0,0,w,h);ctx.fillStyle='#657b72';ctx.font='bold 56px sans-serif';ctx.textAlign='center';ctx.fillText('KITCHEN AX',w/2,80);ctx.fillStyle='#9a957a';ctx.font='18px sans-serif';ctx.fillText('GOOD IDEAS. BETTER PRODUCTS.',w/2,121);},768,180);
 const logoMat=new THREE.MeshBasicMaterial({map:logo,transparent:true,depthWrite:false}),logoGeo=new THREE.PlaneGeometry(5.3,1.24),brand=new THREE.Mesh(logoGeo,logoMat);brand.position.set(9.4,2.5,.25);a.add(brand);resources.push(logoMat,logoGeo);
 for(const x of [-12.8,-7.9,2.4,12.6])plant(a,x,.60,.83);
}
