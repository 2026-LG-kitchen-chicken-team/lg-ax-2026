import * as THREE from 'three';
import { RESEARCHER_ROLES, researcherPose, advanceResearcherClock } from './researcher-motion.js';
import {patrolPosition,VIEW} from './factory-layout.js';
import {characters} from 'virtual:factory-assets';

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
  const people = RESEARCHER_ROLES.flatMap((id,roleIndex) => Array.from({length:id==='overview'?0:3},(_,worker)=>{
    const appearance=(roleIndex+worker)%RESEARCHER_ROLES.length;
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
  Promise.all(characters.map(url=>loader.loadAsync(url))).then(([idle, work, walk]) => {
    if (disposed) return;
    frames = { idle: atlasFrames(idle, 3, 2), work: atlasFrames(work, 6, 2), walk:atlasFrames(walk,6,2) };
    textures.push(...Object.values(frames).flat().flatMap(f=>[f.texture,f.mirror]));
    onLoadState?.('ready');
  }).catch(() => { if (!disposed) onLoadState?.('error'); });
  return {
    update(options) {
      if (!frames || disposed) return;
      people.forEach(person => {
        const index=person.appearance;
        const pose = researcherPose(person.id, options);
        person.time=advanceResearcherClock(person.time,{working:pose.working,reducedMotion:options.reducedMotion,dt:options.dt});
        const route=patrolPosition(person.time,{planner:person.id==='overview',worker:person.worker});
        const walking=pose.working&&!options.reducedMotion&&route.walking;
        if(walking){const direction=VIEW.rx*route.dx+VIEW.rz*route.dz;if(Math.abs(direction)>.08)person.flipped=direction<0;}
        const kind=!pose.working?'idle':walking?'walk':'work';
        const indexInAtlas=kind==='idle'?index:index+(walking?Math.floor(person.time*4)%2:pose.frame)*6;
        const frame=frames[kind][indexInAtlas],map=person.flipped?frame.mirror:frame.texture;
        if(person.current!==map){
          person.material.map=map;person.material.needsUpdate=true;
          const height=person.worker?1.60:1.72;person.sprite.scale.set(height*frame.aspect,height,1);
          person.sprite.center.set(person.flipped?1-frame.anchor:frame.anchor,0);person.current=map;
        }
        person.group.position.set(route.x,route.y,route.z);
        person.group.visible=Boolean(person.worker===0||pose.working||options.pausedIds?.includes(person.id)||options.reducedMotion&&person.time>0);
        person.sprite.visible=true;person.ring.visible=pose.working;
        person.sprite.position.y=walking?Math.abs(Math.sin(person.time*9))*.045:0;
        person.shadowMaterial.opacity=walking?.11:.16;
      });
    },
    dispose() { disposed = true; people.forEach(p => { p.group.parent?.remove(p.group); p.material.dispose(); p.ringMaterial.dispose();p.shadow.geometry.dispose();p.shadowMaterial.dispose(); }); ringGeometry.dispose(); textures.forEach(t => t.dispose()); },
  };
}
