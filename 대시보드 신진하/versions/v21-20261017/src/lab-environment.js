import * as THREE from 'three';
import {fieldToWorld,worldToField,ZONE_FLOOR,PLANNER_FLOOR} from './factory-layout.js';
import {warmLabWall} from 'virtual:factory-assets';

// A clean window wall is set dressing only; it never changes the run or room state.
export function createLabEnvironment(scene,{cube,resources}){
 const wall=new THREE.Group();scene.add(wall);wall.rotation.y=Math.atan2(13,18);
 const frame=cube(wall,1,5.7,.12,0,2.86,-.03,'#e8e7dc',.025);frame.castShadow=false;
 let artState='loading';
 const texture=new THREE.TextureLoader().load(warmLabWall,()=>{artState='ready';},undefined,()=>{artState='error';});texture.colorSpace=THREE.SRGBColorSpace;
 const material=new THREE.MeshBasicMaterial({map:texture}),geometry=new THREE.PlaneGeometry(1,5.7),picture=new THREE.Mesh(geometry,material);picture.position.set(0,2.86,.05);wall.add(picture);resources.push(texture,material,geometry);
 return {status:()=>artState,update(layout){
  let minV=Infinity;for(const zone of Object.values(layout.zones)){
   const f=zone.id==='overview'?PLANNER_FLOOR:ZONE_FLOOR;
   for(const x of [-f.halfX,f.halfX])for(const z of [-f.halfZ,f.halfZ]){const p=worldToField(zone.x+x*zone.scale,0,zone.z+z*zone.scale);minV=Math.min(minV,p.v);}
  }
  const width=layout.columns===2?29:48,at=fieldToWorld(0,minV-1.1);wall.position.set(at.x,0,at.z);picture.scale.x=width;frame.scale.x=width;
 }};
}
