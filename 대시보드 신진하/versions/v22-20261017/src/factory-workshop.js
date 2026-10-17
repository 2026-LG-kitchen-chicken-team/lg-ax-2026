import * as THREE from 'three';

// All furniture stays inside the original room footprint and its perimeter
// walking lane. The execution/layout modules do not depend on this decoration.
export function buildWorkroom(id,g,t){
 const parts={}, {cube,cylinder,monitor,board,plant,lab}=t,ivory='#fff6e7',sage='#748b72',oak='#cbb48b',steel='#a3afa0';
 const desk=(x,z,w=2.5,d=.76)=>{
  cube(g,w,.12,d,x,1.04,z,ivory,.05);lab.wood(cube(g,w,.045,d,x,.965,z,oak,.02));
  for(const dx of [-w*.39,w*.39]){cube(g,.09,.57,d*.72,x+dx,.69,z,steel);cube(g,.28,.045,d*.78,x+dx,.415,z,'#738a7e');}
 };
 const papers=(x,y,z)=>{for(let i=0;i<4;i++)cube(g,.31,.018,.23,x+i*.012,y+i*.021,z,i%2?'#fffdf3':'#d5ded0',.005);cube(g,.22,.005,.012,x,y+.085,z+.02,'#b1c0b6',.001);};
 const stool=(x,z)=>{const seat=new THREE.Group();seat.userData.live=true;seat.userData.workSeat=true;g.add(seat);cylinder(seat,.23,.075,x,.75,z,sage);cylinder(seat,.04,.31,x,.56,z,steel);for(let i=0;i<3;i++){const a=i*Math.PI*2/3;cube(seat,.045,.12,.045,x+Math.cos(a)*.16,.44,z+Math.sin(a)*.16,steel);}};
 const drawers=(x,z,w=.65,h=.77)=>{
  cube(g,w,h,.48,x,.40+h/2,z,ivory,.035);
  for(let i=0;i<3;i++){const y=.43+(i+.5)*(h-.06)/3;cube(g,w-.06,(h-.10)/3,.035,x,y,z+.255,'#e3e7dc',.015);cube(g,w*.35,.028,.022,x,y+.03,z+.28,steel,.005);}
  lab.wood(cube(g,w+.03,.045,.51,x,.42+h,z,oak,.012));
 };
 const laptop=(x,y,z)=>{
  cube(g,.40,.025,.28,x,y,z,'#7f9690',.01);cube(g,.34,.009,.17,x,y+.018,z+.02,'#c5d0c4',.004);monitor(g,x,y+.23,z-.105,.55);
 };
 const bookcase=(x,z,w=2.3)=>{
  lab.wood(cube(g,w,1.66,.37,x,1.23,z,'#d6c5a1',.025));
  for(let row=0;row<3;row++){
   const y=.49+row*.49;cube(g,w-.08,.055,.43,x,y,z+.04,ivory,.012);
   for(let i=0;i<9;i++){const h=.31+(i%3)*.045,bx=x-w*.42+i*w*.105;cube(g,w*.078,h,.29,bx,y+h/2+.03,z+.08,['#b1bba7','#f0e7cd','#6c8e8e','#d7b46e'][i%4],.008);cube(g,w*.045,.018,.008,bx,y+h*.7,z+.23,'#f9f8e8',.001);}
  }
  cube(g,w,.055,.43,x,2.08,z+.02,ivory);
 };
 const fridge=(x,z,scale=1)=>{
  const f=new THREE.Group();f.position.set(x,.41,z);f.scale.setScalar(scale);g.add(f);
  const animated=id==='compare'&&scale===.91;
  if(animated){
   f.userData.live=true;
   cube(f,.92,2.02,.055,0,1.01,-.33,'#bac6c3',.025,.4);
   for(const side of [-1,1])cube(f,.055,2.02,.72,side*.435,1.01,0,'#bac6c3',.02,.4);
   for(const y of [.03,1.99])cube(f,.87,.06,.72,0,y,0,'#dbe3d6',.015);
   cube(f,.80,1.88,.018,0,1.01,-.294,'#f9faef',.008);
   for(const y of [.38,.82,1.26,1.7]){cube(f,.79,.035,.61,0,y,.015,'#d6e5d5',.008);cube(f,.16,.20,.15,.20,y+.12,.04,'#e1c78e',.012);}
   const door=new THREE.Group();door.position.set(-.435,0,.398);f.add(door);
   for(const [y,h] of [[1.43,1.10],[.43,.73]]){cube(door,.87,h,.075,.435,y,0,'#e4e8de',.035,.25);cube(door,.036,h*.60,.04,.745,y,.052,'#8c9e95',.008,.6);}
   cube(door,.17,.21,.016,.20,1.60,.049,'#4b685f',.008);parts.door=door;
  }else{
   cube(f,.92,2.02,.72,0,1.01,0,'#bac6c3',.06,.4);
   for(const [y,h] of [[1.43,1.10],[.43,.73]]){cube(f,.87,h,.075,0,y,.398,'#e4e8de',.035,.25);cube(f,.036,h*.60,.04,.31,y,.45,'#8c9e95',.008,.6);}
   cube(f,.018,1.01,.012,0,1.43,.445,'#a8b5aa',.004);cube(f,.17,.21,.016,-.23,1.60,.446,'#4b685f',.008);cube(f,.10,.016,.006,-.23,1.62,.46,'#c3ddd2',.001);
  }
  cube(f,.82,.045,.65,0,.025,.02,'#597268');
 };
 const appliance=(x,z,type)=>{
  cube(g,.73,.78,.65,x,.80,z,ivory,.035,.15);cube(g,.64,.57,.04,x,.76,z+.35,'#869d93',.018,.4);cube(g,.53,.45,.015,x,.76,z+.377,type==='oven'?'#344b44':'#d1ded3',.01);cube(g,.43,.028,.04,x,1.01,z+.39,'#bec9bd',.008,.5);
  for(let i=0;i<3;i++)cylinder(g,.025,.025,x-.17+i*.17,1.22,z+.20,steel,.025,8);
 };
 if(id==='retrieve'){
  bookcase(-.20,-1.04,2.55);drawers(-1.39,.78,.54,.91);desk(.55,.54,1.69,.76);
  monitor(g,.12,1.47,.39,.8);cube(g,.48,.20,.36,1.02,1.20,.50,'#c8d1c4');cube(g,.34,.022,.20,1.02,1.31,.50,'#667e74');papers(.45,1.12,.77);stool(.65,1.26);plant(g,1.42,-1.04,.62);
 }else if(id==='web'){
  board(g,'web',.20,1.90,-1.05,2.36,1.40);desk(.2,.46,2.40,.84);laptop(.68,1.13,.52);papers(-.28,1.13,.77);stool(.45,1.27);plant(g,1.44,-1.05,.60);
 }else if(id==='structure'){
  board(g,'sticky',0,1.83,-1.05,2.6,1.40);desk(0,.42,2.54,.76);drawers(-1.40,-.07,.46,.76);
  laptop(.42,1.13,.44);papers(-.75,1.13,.49);papers(.94,1.13,.51);stool(-.62,1.19);stool(.72,1.19);plant(g,1.43,-1.08,.64);
 }else if(id==='compare'){
  fridge(-1.06,-.71,.91);fridge(-.15,-.63,.51);board(g,'compare',.56,1.92,-1.05,1.75,1.37);appliance(1.10,.64,'oven');desk(-.58,.73,1.40,.61);
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
 lab.roomProps(id,g);
 return parts;
}

export function buildWorkshopBackdrop(scene,t,fieldProps=[]){
 const {cube,cylinder,canvasTexture,resources,lab}=t,a=new THREE.Group();a.position.z=-13.8;scene.add(a);
 cube(a,31,1.10,.28,0,.55,0,'#dcd7c7',.04);lab.wood(cube(a,31,.15,.48,0,1.13,.02,'#d8c5a0',.025));
 const landscape=canvasTexture((c,w,h)=>{
  let seed=31;const r=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
  const sky=c.createLinearGradient(0,0,0,h);sky.addColorStop(0,'#f5f0db');sky.addColorStop(.48,'#e4ebd1');sky.addColorStop(1,'#b3c399');c.fillStyle=sky;c.fillRect(0,0,w,h);
  for(let i=0;i<34;i++){
   const x=r()*w,y=h*(.3+r()*.58),size=55+r()*110;
   c.fillStyle='#83925e35';c.fillRect(x-4,y,6,h-y);
   const halo=c.createRadialGradient(x,y,0,x,y,size);halo.addColorStop(0,'#bccc91cc');halo.addColorStop(.6,'#8fa26999');halo.addColorStop(1,'#a6bc7700');c.fillStyle=halo;c.fillRect(x-size,y-size,size*2,size*2);
   for(let j=0;j<70;j++){const angle=r()*Math.PI*2,rr=Math.sqrt(r())*size;c.fillStyle=['#758945aa','#b5c686bb','#e3e6b0cc','#879e5aaa'][j%4];c.beginPath();c.ellipse(x+Math.cos(angle)*rr,y+Math.sin(angle)*rr*.62,3+r()*9,2+r()*5,r(),0,Math.PI*2);c.fill();}
  }
  const haze=c.createLinearGradient(0,0,w,h);haze.addColorStop(0,'#fff7dc2b');haze.addColorStop(.5,'#fff9e52b');haze.addColorStop(1,'#fff9e500');c.fillStyle=haze;c.fillRect(0,0,w,h);
 },2048,768);
 const viewMat=new THREE.MeshBasicMaterial({map:landscape}),viewGeo=new THREE.PlaneGeometry(30,5.2),outside=new THREE.Mesh(viewGeo,viewMat);outside.position.set(0,3.72,-.23);a.add(outside);resources.push(viewGeo,viewMat);
 const glassMat=new THREE.MeshPhysicalMaterial({color:'#f8f2df',transparent:true,opacity:.08,roughness:.15,metalness:.03});resources.push(glassMat);
 for(let i=0;i<8;i++){
  const x=-15+i*4.28;cube(a,.13,6.3,.25,x,3.18,.16,'#bcc0ac',.018,.28);cube(a,.30,.62,.32,x,.33,.16,'#b8a06c',.02,.24);
  if(i<7){cube(a,4.15,.11,.25,x+2.14,3.65,.15,'#c8ccb9',.012,.2);cube(a,4.15,.15,.28,x+2.14,6.22,.15,'#d4d3bd',.018,.2);
   const pg=new THREE.PlaneGeometry(4.09,4.87),pane=new THREE.Mesh(pg,glassMat);pane.position.set(x+2.14,3.69,.22);a.add(pane);resources.push(pg);}
 }
 const logo=canvasTexture((c,w,h)=>{c.clearRect(0,0,w,h);c.fillStyle='#6c806d';c.font='600 58px sans-serif';c.textAlign='center';c.fillText('KITCHEN AX',w/2,105);},768,180);
 const logoMat=new THREE.MeshBasicMaterial({map:logo,transparent:true,depthWrite:false}),logoGeo=new THREE.PlaneGeometry(4.8,1.12),brand=new THREE.Mesh(logoGeo,logoMat);brand.position.set(9.5,2.20,.25);a.add(brand);resources.push(logoMat,logoGeo);
 for(const x of [-13.8,-7.6,2.5,13.5])lab.pot(a,x,.68);
 // Peripheral display furniture retreats when an enlarged workspace approaches.
 const perimeter=(x,z,radius,make)=>{const g=new THREE.Group();g.position.set(x,0,z);scene.add(g);make(g);fieldProps.push({group:g,x,z,radius,detail:true});return g;};
 perimeter(-15,-5.6,2.2,g=>{
  cube(g,3.8,1.22,.85,0,.65,0,'#e8dfcc',.045);lab.wood(cube(g,3.95,.10,.97,0,1.30,0,'#c9b18b',.03));
  for(let i=0;i<4;i++){const x=-1.43+i*.95;cube(g,.88,1.07,.04,x,.70,.46,'#f4ecde',.025);cube(g,.26,.035,.035,x,1.06,.49,'#9ca58e',.006,.4);}
  cube(g,.80,.02,.58,-.88,1.37,0,'#a5b2a3',.018,.4);cube(g,.58,.025,.37,-.88,1.38,0,'#7a897c',.025,.4);
  cylinder(g,.18,.20,.32,1.46,0,'#b9c0ad',.18,16);cylinder(g,.20,.025,.32,1.57,0,'#d8daca',.20,16);lab.pot(g,1.30,-.13);
 });
 const cart=(x,z)=>perimeter(x,z,1.5,g=>{
  for(const y of [.40,1.04]){cube(g,1.65,.065,.79,0,y,0,'#b5bbaa',.018,.3);lab.wood(cube(g,1.53,.025,.68,0,y+.043,0,'#d7c5a0',.008));}
  for(const x of [-.77,.77])for(const z of [-.33,.33]){cube(g,.04,1.15,.04,x,.67,z,'#a1ad9c',.008,.4);cylinder(g,.07,.05,x,.14,z,'#5d7064',.07,10);}
  cube(g,.61,.33,.51,-.40,.62,0,'#d4bf96',.02);cube(g,.57,.27,.47,.34,.59,0,'#e4d6b8',.02);lab.plant(g,.52,-.08,.44);lab.book(g,-.34,1.12,.08,'#8a9b7e');lab.book(g,-.32,1.16,.08,'#d9c49e');
 });
 cart(14.8,4.5);cart(-12.3,10.8);
 return a;
}
