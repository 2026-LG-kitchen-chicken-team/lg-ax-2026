// A seated figure is set dressing, not an additional executing agent.
export const SEATED_DOCKS={retrieve:[.65,1.26],structure:[-.62,1.19],compare:[-.47,1.31],concept:[-.21,1.26],validate:[.30,1.25],web:[.45,1.27]};
export function researcherPresence({working=false,paused=false,worker=0,workerCount=3,hasWorkPose=false}={}){
 const freeze=paused&&!working&&hasWorkPose;
 return {mode:working?'work':freeze?'frozen':'seated',visible:working||freeze?worker<workerCount:worker===0,animate:working,showWorkSeat:working||freeze};
}
