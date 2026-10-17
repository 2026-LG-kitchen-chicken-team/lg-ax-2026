import * as THREE from 'three';
import { RESEARCHER_ROLES, researcherPose, advanceResearcherClock } from './researcher-motion.js';
import {VIEW,worldToField,fieldToWorld} from './factory-layout.js';
import {characters} from 'virtual:factory-assets';
import {illustratedWorkPose} from './skill-choreography.js';
import {skillResearcherRoute} from './skill-researcher-route.js';
import {SEATED_DOCKS,researcherPresence} from './researcher-presence.js';

// The original generated PNGs remain intact. UV regions select each figure;
// alpha bounds and the feet anchor keep the two work poses registered.
function atlasFrames(image, columns, rows) {
  const canvas = document.createElement('canvas');
  canvas.width = image.width; canvas.height = image.height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(image, 0, 0);
  const pixels = ctx.getImageData(0, 0, image.width, image.height).data;
  return Array.from({ length: columns * rows }, (_, index) => {
    const column = index % columns, row = Math.floor(index / columns);
    const x0 = Math.round(column * image.width / columns), x1 = Math.round((column + 1) * image.width / columns);
    const y0 = Math.round(row * image.height / rows), y1 = Math.round((row + 1) * image.height / rows);
    const xs = new Uint16Array(x1 - x0), ys = new Uint16Array(y1 - y0);
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
      if (pixels[(y * image.width + x) * 4 + 3] > 220) { xs[x - x0]++; ys[y - y0]++; }
    }
    const occupiedX = Array.from(xs.keys()).filter(x => xs[x] > 6);
    const occupiedY = Array.from(ys.keys()).filter(y => ys[y] > 8);
    if (!occupiedX.length || !occupiedY.length) throw Error('연구원 이미지 영역을 찾지 못했습니다.');
    const left = x0 + Math.max(0, occupiedX[0] - 3), right = x0 + Math.min(xs.length, occupiedX.at(-1) + 4);
    const top = y0 + Math.max(0, occupiedY[0] - 3), bottom = y0 + Math.min(ys.length, occupiedY.at(-1) + 4);
    let footSum = 0, footCount = 0;
    for (let y = Math.round(bottom - (bottom - top) * .12); y < bottom; y++) for (let x = left; x < right; x++) {
      if (pixels[(y * image.width + x) * 4 + 3] > 220) { footSum += x; footCount++; }
    }
    const texture = new THREE.Texture(image);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.repeat.set((right - left) / image.width, (bottom - top) / image.height);
    texture.offset.set(left / image.width, 1 - bottom / image.height);
    texture.needsUpdate = true;
    const mirror=texture.clone();mirror.offset.x+=mirror.repeat.x;mirror.repeat.x*=-1;mirror.needsUpdate=true;
    return { texture, mirror, aspect: (right - left) / (bottom - top), anchor: ((footCount ? footSum / footCount : (left + right) / 2) - left) / (right - left) };
  });
}

export function createResearchers(scene, onLoadState, stations={}) {
  let disposed = false, frames = null;
  const loader = new THREE.ImageLoader(), textures = [];
  const ringGeometry = new THREE.RingGeometry(.30, .35, 28);
  const workSeats=Object.fromEntries(Object.entries(stations).map(([id,g])=>{const seats=[];g.traverse(o=>{if(o.userData.workSeat)seats.push(o);});return [id,seats];}));
  const people = Object.keys(stations).flatMap((id,roleIndex) => Array.from({length:id==='overview'?0:4},(_,worker)=>{
    const appearance=((RESEARCHER_ROLES.indexOf(id)>=0?RESEARCHER_ROLES.indexOf(id):0)+worker)%6;
    const group = new THREE.Group(); group.userData.station = id;
    (stations[id]||scene).add(group);
    group.name='researcher-'+id+'-'+worker;
    const material = new THREE.SpriteMaterial({ transparent: true, alphaTest: .55, depthWrite: false, toneMapped: false });
    const sprite = new THREE.Sprite(material); sprite.visible = false; group.add(sprite);
    const ringMaterial = new THREE.MeshBasicMaterial({ color: '#f69646', transparent: true, opacity: .65, depthWrite: false, side: THREE.DoubleSide });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial); ring.rotation.x = -Math.PI / 2; ring.position.y = .018; ring.visible = false; group.add(ring);
    const shadowMaterial=new THREE.MeshBasicMaterial({color:'#344d40',transparent:true,opacity:.14,depthWrite:false});
    const shadow=new THREE.Mesh(new THREE.CircleGeometry(.30,20),shadowMaterial);shadow.rotation.x=-Math.PI/2;shadow.position.y=.008;shadow.scale.set(1,.7,1);group.add(shadow);
    return {id,worker,appearance,group,sprite,material,ring,ringMaterial,shadow,shadowMaterial,current:null,time:0,flipped:false};
  }));
  Promise.all(characters.map(url=>loader.loadAsync(url))).then(([idle, work, walk, seated]) => {
    if (disposed) return;
    frames = { idle: atlasFrames(idle, 3, 2), work: atlasFrames(work, 6, 2), walk:atlasFrames(walk,6,2),seated:atlasFrames(seated,3,2) };
    textures.push(...Object.values(frames).flat().flatMap(f=>[f.texture,f.mirror]));
    onLoadState?.('ready');
  }).catch(() => { if (!disposed) onLoadState?.('error'); });
  return {
    update(options) {
      if (!frames || disposed) return;
      people.forEach(person => {
        const index=person.appearance;
        const pose = researcherPose(person.id, options);person.working=pose.working;
        const presence=researcherPresence({working:pose.working,paused:options.pausedIds?.includes(person.id),worker:person.worker,workerCount:options.assignments?.[person.id]?.workerCount??3,hasWorkPose:person.kind==='work'||person.kind==='walk'});
        person.illustratedIdle=presence.mode==='seated'&&options.illustratedIdle?.includes(person.id);
        person.group.visible=presence.visible&&!person.illustratedIdle;person.ring.visible=pose.working;
        if(person.worker===0)workSeats[person.id].forEach(seat=>{seat.visible=presence.showWorkSeat;});
        if(presence.mode==='frozen')return;
        person.time=advanceResearcherClock(person.time,{working:pose.working,reducedMotion:options.reducedMotion,dt:options.dt});
        const route=skillResearcherRoute(person.id,person.time,{worker:person.worker});
        const illustrated=options.illustratedRooms?.includes(person.id),action=illustratedWorkPose(person.id,person.time,{worker:person.worker});
        const walking=pose.working&&!options.reducedMotion&&(illustrated?action.walking:route.walking);
        if(walking){const direction=illustrated?action.dx:VIEW.rx*route.dx+VIEW.rz*route.dz;if(Math.abs(direction)>.08)person.flipped=direction<0;}
        const kind=!pose.working?'seated':walking?'walk':'work';person.kind=kind;
        const indexInAtlas=kind==='seated'?index:(illustrated&&!walking?action.pose:index)+(walking?Math.floor(person.time*4)%2:Math.floor(person.time*1.8)%2)*6;
        const frame=frames[kind][indexInAtlas],map=person.flipped?frame.mirror:frame.texture;
        if(person.current!==map){
          person.material.map=map;person.material.needsUpdate=true;
          const height=kind==='seated'?1.43:illustrated?(person.worker?2.35:2.65):person.worker?1.60:1.72;person.sprite.scale.set(height*frame.aspect,height,1);
          person.sprite.center.set(person.flipped?1-frame.anchor:frame.anchor,0);person.current=map;
        }
        const dock=SEATED_DOCKS[person.id];
        person.group.position.set(kind==='seated'?dock[0]:route.x,route.y,kind==='seated'?dock[1]:route.z);
        if(kind!=='seated'&&options.illustratedRooms?.includes(person.id)){
          // Visual registration inside the wider illustration; route timing and work state are unchanged.
          const art=options.artwork?.room(person.id),artH=art?.sprite.scale.y||8,registered=fieldToWorld(action.u*9.2,2.15-artH*action.foot+VIEW.uy*(route.y-.07));
          person.group.position.set(registered.x,route.y,registered.z);
        }
        person.sprite.visible=true;person.ring.visible=pose.working;
        person.sprite.renderOrder=.5;person.material.depthTest=!illustrated;
        person.sprite.position.y=walking?Math.abs(Math.sin(person.time*9))*.06:0;
        person.sprite.material.rotation=pose.working&&!walking&&illustrated?Math.sin(person.time*2.5)*.025:0;
        person.shadowMaterial.opacity=walking?.11:.16;
      });
    },
    status(){return {seated:people.filter(p=>p.worker===0&&stations[p.id].visible&&p.kind==='seated'&&(p.illustratedIdle||p.group.visible&&p.sprite.visible)).length,moving:people.filter(p=>p.group.visible&&p.working).length};},
    protectedRegions({precise=false}={}){
      return Object.keys(stations).filter(id=>id!=='overview'&&stations[id].visible).flatMap(id=>{
        const visible=people.filter(p=>p.id===id&&p.group.visible&&p.sprite.visible);if(!visible.length)return [];
        if(!precise&&visible.some(p=>p.working))return [{id,minX:-2.65,maxX:2.65,minZ:-2.2,maxZ:2.2}];
        return [{id,billboards:visible.map(p=>({x:p.group.position.x,y:p.group.position.y,z:p.group.position.z,width:p.sprite.scale.x,height:p.sprite.scale.y,anchor:p.sprite.center.x}))}];
      });
    },
    dispose() { disposed = true; people.forEach(p => { p.group.parent?.remove(p.group); p.material.dispose(); p.ringMaterial.dispose();p.shadow.geometry.dispose();p.shadowMaterial.dispose(); }); ringGeometry.dispose(); textures.forEach(t => t.dispose()); },
  };
}
