export const RESEARCHER_ROLES = ['overview', 'retrieve', 'structure', 'compare', 'concept', 'validate'];

// Selection never starts work. Only the execution state (or the explicitly
// labelled, separate motion preview) chooses an animated researcher.
export function researcherPose(id, { activeIds = [], plannerWorking = false, reducedMotion = false, elapsed = 0 } = {}) {
  const working = id === 'overview' ? plannerWorking : activeIds.includes(id);
  return { working, frame: working && !reducedMotion ? Math.floor(Math.max(0, elapsed) * 2.2) % 2 : 0 };
}

// This clock advances only while actual work is active; pause and reduced motion
// preserve each person's place on the route.
export function advanceResearcherClock(time,{working=false,reducedMotion=false,dt=0}={}){
  return time+(working&&!reducedMotion?Math.max(0,Math.min(.1,Number(dt)||0)):0);
}

// Isolated visual fixture. These groups never enter the execution store.
export function previewActiveNodes(elapsed,mode='parallel2'){
  const step=Math.floor(Math.max(0,elapsed)/30);
  if(mode==='all')return RESEARCHER_ROLES.slice(1);
  if(mode==='parallel4')return RESEARCHER_ROLES.slice(1,5);
  if(mode==='parallel3')return [['retrieve','structure','compare'],['concept','validate','structure']][step%2];
  if(mode==='parallel2')return [['structure','compare'],['concept','validate'],['retrieve','structure']][step%3];
  return [RESEARCHER_ROLES[step%RESEARCHER_ROLES.length]];
}
