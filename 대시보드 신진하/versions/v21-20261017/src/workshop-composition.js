import {ROOM_ORDER,fieldToWorld} from './factory-layout.js';
// Presentation only: use the same run-derived room sizes in the approved two-row lab composition.
export function composeWorkshopLayout(layout){
 if(layout.columns!==3)return layout;
 const depth=[-5.25,-7.5,-5.25,7,9,7];
 const zones=Object.fromEntries(Object.entries(layout.zones).map(([id,z])=>{
  const index=ROOM_ORDER.indexOf(id);return [id,index<0?z:{...z,...fieldToWorld((index%3-1)*13,depth[index])}];
 }));
 return {...layout,zones};
}
