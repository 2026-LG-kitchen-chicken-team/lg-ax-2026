// Nameplates may move; the factory and researcher routes keep their real positions.
// All rectangles use CSS pixels in the factory viewport.
export function intersects(a,b,gap=0){
 return a.left<b.left+b.w+gap&&a.left+a.w+gap>b.left&&a.top<b.top+b.h+gap&&a.top+a.h+gap>b.top;
}
const area=(a,b)=>Math.max(0,Math.min(a.left+a.w,b.left+b.w)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.top+a.h,b.top+b.h)-Math.max(a.top,b.top));
const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
export function arrangeLabelRects(items,width,safeTop,safeBottom,selected,sheetBottom,protectedRects=[]){
 const gap=width<500?14:20,edge=8,obstacles=protectedRects.filter(b=>b.w>0&&b.h>0);
 const labels=items.filter(i=>i.visible!==false).map(item=>{
  const bottom=sheetBottom!=null&&item.id===selected?Math.min(safeBottom,sheetBottom):safeBottom;
  const maxTop=Math.max(safeTop,bottom-item.h);
  return {...item,baseLeft:clamp(item.left,edge,Math.max(edge,width-edge-item.w)),baseTop:clamp(item.top,safeTop,maxTop),maxTop};
 }).sort((a,b)=>Number(b.working)-Number(a.working)||(b.w*b.h-a.w*a.h));
 const boxes=labels.map(item=>({left:item.baseLeft,top:item.baseTop,w:item.w,h:item.h}));
 const options=labels.map(item=>{
  const xs=[item.baseLeft,edge,width-edge-item.w],ys=[item.baseTop,safeTop,item.maxTop];
  for(const b of [...obstacles,...boxes]){xs.push(b.left-gap-item.w,b.left+b.w+gap);ys.push(b.top-gap-item.h,b.top+b.h+gap);}
  const unique=values=>[...new Set(values.map(v=>Math.round(v*2)/2))];
  return unique(xs).flatMap(left=>unique(ys).map(top=>({left,top,w:item.w,h:item.h})))
   .filter(b=>b.left>=edge&&b.left+b.w<=width-edge+.5&&b.top>=safeTop&&b.top<=item.maxTop+.5&&!obstacles.some(p=>intersects(b,p,6)))
   .map(b=>({...b,cost:((b.left-item.baseLeft)**2+(b.top-item.baseTop)**2)*(item.working?1.3:1)})).sort((a,b)=>a.cost-b.cost).slice(0,64);
 });
 const order=labels.map((_,i)=>i).sort((a,b)=>options[a].length-options[b].length);
 let beam=[{cost:0,positions:[]}];
 for(const index of order){
  const next=[];
  for(const state of beam)for(const box of options[index])if(!state.positions.some(p=>intersects(box,p,gap)))next.push({cost:state.cost+box.cost,positions:[...state.positions,{...labels[index],...box,protectedClear:true}]});
  if(!next.length){beam=[];break;}beam=next.sort((a,b)=>a.cost-b.cost).slice(0,32);
 }
 if(beam.length)return beam[0].positions;
 const placed=[];
 for(const item of labels){
  const xs=[item.baseLeft,edge,width-edge-item.w],ys=[item.baseTop,safeTop,item.maxTop];
  for(const b of [...obstacles,...placed]){xs.push(b.left-gap-item.w,b.left+b.w+gap);ys.push(b.top-gap-item.h,b.top+b.h+gap);}
  const unique=values=>[...new Set(values.map(v=>Math.round(v*2)/2))];
  const choices=unique(xs).flatMap(left=>unique(ys).map(top=>({left,top,w:item.w,h:item.h}))).filter(b=>b.left>=edge&&b.left+b.w<=width-edge+.5&&b.top>=safeTop&&b.top<=item.maxTop+.5);
  const cost=b=>(b.left-item.baseLeft)**2+(b.top-item.baseTop)**2;
  const free=choices.filter(b=>!placed.some(p=>intersects(b,p,gap))&&!obstacles.some(p=>intersects(b,p,6))).sort((a,b)=>cost(a)-cost(b));
  // Prefer a free position. On very short screens, preserve all readable names
  // and minimize covered researcher area rather than dropping a room.
  const fallback=choices.filter(b=>!placed.some(p=>intersects(b,p,gap))).sort((a,b)=>obstacles.reduce((s,p)=>s+area(a,p),0)-obstacles.reduce((s,p)=>s+area(b,p),0)||cost(a)-cost(b));
  const chosen=free[0]||fallback[0]||{left:item.baseLeft,top:item.baseTop};
  placed.push({...item,...chosen,protectedClear:Boolean(free.length)});
 }
 // Extremely constrained views still keep the labels separate in a small grid.
 // This is used only when a full set of non-overlapping names was impossible.
 if(placed.some((a,i)=>placed.slice(i+1).some(b=>intersects(a,b,gap)))){
  const cw=Math.max(...placed.map(x=>x.w)),ch=Math.max(...placed.map(x=>x.h));
  const columns=Math.max(1,Math.floor((width-edge*2+gap)/(cw+gap)));
  placed.forEach((b,i)=>{b.left=edge+(i%columns)*(cw+gap);b.top=safeTop+Math.floor(i/columns)*(ch+gap);b.protectedClear=!obstacles.some(p=>intersects(b,p,6));});
 }
 return placed;
}
