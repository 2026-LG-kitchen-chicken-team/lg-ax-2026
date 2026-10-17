import * as THREE from 'three';
import {workshopImages} from 'virtual:factory-assets';
import {ROOM_ORDER,fieldToWorld} from './factory-layout.js';

// The PNGs are visual layers only. Existing execution, people clocks, room
// selection and parallel scale calculations remain owned by their old modules.
function components(pixels,width,height,predicate){
 const used=new Uint8Array(width*height),queue=new Int32Array(width*height),found=[];
 for(let seed=0;seed<used.length;seed++){
  if(used[seed]||!predicate(seed))continue;
  let head=0,tail=1,minX=width,minY=height,maxX=0,maxY=0,sumX=0,sumY=0,sumXX=0,sumXY=0;queue[0]=seed;used[seed]=1;
  while(head<tail){const p=queue[head++],x=p%width,y=Math.floor(p/width);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);sumX+=x;sumY+=y;sumXX+=x*x;sumXY+=x*y;
   for(const n of [x>0?p-1:-1,x+1<width?p+1:-1,y>0?p-width:-1,y+1<height?p+width:-1])if(n>=0&&!used[n]&&predicate(n)){used[n]=1;queue[tail++]=n;}
  }
  if(tail>200)found.push({minX,minY,maxX,maxY,count:tail,cx:sumX/tail,cy:sumY/tail,slope:(sumXY-sumX*sumY/tail)/Math.max(1,sumXX-sumX*sumX/tail)});
 }
 return found.sort((a,b)=>b.count-a.count);
}
function displayOutline(data,w,{left,top,right,bottom},original){
 const shape=new THREE.Shape(),width=right-left,height=bottom-top,rows=[];
 if(original){
  // A vector viewport clips only the external white margin. Source PNG pixels are never edited.
  for(let y=top;y<bottom;y++){
   let lo=right,hi=left;
   for(let x=left;x<right;x++){const p=(y*w+x)*4;if(Math.min(data[p],data[p+1],data[p+2])<244){lo=Math.min(lo,x);hi=Math.max(hi,x);}}
   if(hi>lo)rows.push({y,lo:Math.max(left,lo-1),hi:Math.min(right,hi+2)});
  }
 }
 const points=rows.length?[...rows.map(r=>[r.lo,r.y]),...rows.toReversed().map(r=>[r.hi,r.y])]:[[left,top],[left,bottom],[right,bottom],[right,top]];
 points.forEach(([x,y],i)=>{const u=(x-left)/width-.5,v=1-(y-top)/height;i?shape.lineTo(u,v):shape.moveTo(u,v);});shape.closePath();
 const geometry=new THREE.ShapeGeometry(shape),positions=geometry.getAttribute('position'),uv=geometry.getAttribute('uv');
 for(let i=0;i<positions.count;i++)uv.setXY(i,positions.getX(i)+.5,positions.getY(i));return geometry;
}
function atlas(image,sourceIndex){
 const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);
 const {data}=ctx.getImageData(0,0,image.width,image.height),w=image.width,h=image.height;
 const isOriginal=sourceIndex===0;
 // UV viewports only: the user's PNG is stored byte-for-byte unchanged.
 const originalBounds=[[12,13,212,189],[212,21,405,183],[407,12,618,195],[12,196,213,378],[207,207,413,381],[412,197,618,376]];
 const rooms=isOriginal?originalBounds.map(([minX,minY,maxX,maxY])=>({minX,minY,maxX,maxY,cx:(minX+maxX)/2,cy:(minY+maxY)/2})):components(data,w,h,p=>data[p*4+3]>220).slice(0,6);
 if(rooms.length!==6)throw Error('작업실 이미지 영역을 확인하지 못했습니다.');
 rooms.sort((a,b)=>Number(a.cy>h/2)-Number(b.cy>h/2)||a.cx-b.cx);
 const fascia=components(data,w,h,p=>{const at=p*4;return data[at+3]>220&&data[at]<100&&data[at+1]<131&&data[at+2]<120&&data[at+1]>data[at]+4&&data[at+1]>data[at+2]+1;});
 return rooms.map(room=>{
  const left=Math.max(0,room.minX-(isOriginal?0:3)),top=Math.max(0,room.minY-(isOriginal?0:3)),right=Math.min(w,room.maxX+(isOriginal?0:4)),bottom=Math.min(h,room.maxY+(isOriginal?0:4)),width=right-left,height=bottom-top;
  const texture=new THREE.Texture(image);texture.colorSpace=THREE.SRGBColorSpace;texture.repeat.set(width/w,height/h);texture.offset.set(left/w,1-bottom/h);texture.needsUpdate=true;
  const sign=fascia.filter(p=>p.cx>left&&p.cx<right&&p.cy>top+height*.65&&p.cy<bottom&&p.maxX-p.minX>width*.40).sort((a,b)=>b.count-a.count)[0];
  const plate=sign?{x:(sign.cx-left)/width,y:(sign.cy-top)/height,width:(sign.maxX-sign.minX)/width*.88,height:Math.max(.055,sign.count/Math.max(1,sign.maxX-sign.minX)/height*.58),angle:Math.max(-15,Math.min(15,Math.atan(sign.slope)*180/Math.PI))}:{x:.5,y:.87,width:.6,angle:0};
  const foreground=texture.clone();foreground.repeat.y*=.48;foreground.needsUpdate=true;
  const geometry=displayOutline(data,w,{left,top,right,bottom},isOriginal);
  return {texture,foreground,geometry,original:isOriginal,aspect:width/height,plate,bounds:{left,top,right,bottom}};
 });
}
export function createWorkshopArtwork(stations){
 let disposed=false,ready=false,frames=null,error=false;
 const rooms=ROOM_ORDER.filter(id=>stations[id]).map((id,index)=>{
  const group=stations[id],legacy=[...group.children],material=new THREE.MeshBasicMaterial({transparent:true,alphaTest:.08,depthWrite:false,depthTest:false,toneMapped:false,side:THREE.DoubleSide});
  const blank=new THREE.PlaneGeometry(1,1);blank.translate(0,.5,0);const sprite=new THREE.Mesh(blank,material);sprite.name='workshop-art-'+id;sprite.visible=false;sprite.renderOrder=-1;
  sprite.quaternion.setFromRotationMatrix(new THREE.Matrix4().lookAt(new THREE.Vector3(13,17,18),new THREE.Vector3(),new THREE.Vector3(0,1,0)));
  const base=fieldToWorld(0,2.15);sprite.position.set(base.x,.07,base.z);group.add(sprite);
  const frontMaterial=material.clone(),front=new THREE.Mesh(blank,frontMaterial);front.quaternion.copy(sprite.quaternion);front.position.copy(sprite.position);front.renderOrder=1;front.visible=false;group.add(front);
  return {id,index,group,legacy,material,sprite,frontMaterial,front,frame:null,idle:true};
 });
 Promise.all(workshopImages.map(url=>new THREE.ImageLoader().loadAsync(url))).then(images=>{
  if(disposed)return;
  frames=images.map(atlas);ready=true;
 }).catch(()=>{error=true;});
 return {
  get ready(){return ready;},
  update({activeIds=[],pausedIds=[]}={}){
   const idleRooms=[];
   if(ready)for(const room of rooms){
    room.idle=!activeIds.includes(room.id)&&!pausedIds.includes(room.id);room.frame=frames[room.idle?0:1][room.index];
    if(room.idle)idleRooms.push(room.id);
    room.legacy.forEach(part=>{part.visible=false;});
    room.material.map=room.frame.texture;room.sprite.geometry=room.frame.geometry;room.sprite.scale.set(9.2,9.2/room.frame.aspect,1);room.sprite.visible=true;
    room.frontMaterial.map=room.frame.foreground;room.front.scale.set(room.sprite.scale.x,room.sprite.scale.y*.48,1);room.front.visible=!room.idle;
   }
   return {idleRooms,ready,error};
  },
  room(id){return ready?rooms.find(room=>room.id===id):null;},
  dispose(){disposed=true;for(const room of rooms){room.sprite.removeFromParent();room.front.removeFromParent();room.material.dispose();room.frontMaterial.dispose();room.front.geometry.dispose();}frames?.flat().forEach(frame=>{frame.texture.dispose();frame.foreground.dispose();frame.geometry.dispose();});},
 };
}
