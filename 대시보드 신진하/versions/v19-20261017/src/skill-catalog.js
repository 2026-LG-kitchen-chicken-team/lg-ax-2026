// Audited release definitions, not a claim that these tools or helpers are running.
export const VERIFIED_PRODUCT = Object.freeze({
  version:'product-v0.18.0', commit:'f599731b8d740b32d43d84de2b1589311696a88a',
  url:'https://github.com/2026-LG-kitchen-chicken-team/lg-ax-agent/releases/tag/product-v0.18.0',
  checked:'2026-10-17', mainCount:1,
});
export const PRODUCT_SKILLS = Object.freeze([
  {id:'evidence-retrieval',node:'retrieve',no:'01',label:'자료 조회',verb:'모아 둔 자료를 찾아요',description:'이미 모아 둔 고객 리뷰와 제품 설명서를 찾아 확인해요.',object:'자료 선반·스캐너'},
  {id:'needs-structuring',node:'structure',no:'02',label:'니즈 구조화',verb:'비슷한 불편을 모아요',description:'사람들이 무엇을 불편해하는지 비슷한 내용끼리 정리해요.',object:'불편 메모 보드'},
  {id:'feature-comparison',node:'compare',no:'03',label:'기능 대조',verb:'지금 기능과 비교해요',description:'지금 제품에 있는 기능으로 불편을 해결할 수 있는지 비교해요.',object:'제품·기능 대조판'},
  {id:'concept-writing',node:'concept',no:'04',label:'콘셉트 작성',verb:'새 아이디어를 만들어요',description:'아직 남은 불편을 해결할 새 제품이나 기능 아이디어를 만들어요.',object:'아이디어 모형'},
  {id:'review-and-revise',node:'validate',no:'05',label:'검토 · 수정',verb:'빠진 것이 없는지 살펴요',description:'아이디어에 근거가 있는지 확인하고 잘못된 부분을 고쳐요.',object:'검사표·확인 도장'},
  {id:'web-evidence-collection',node:'web',no:'06',label:'웹 근거 수집',verb:'인터넷에서 자료를 찾아요',description:'부족한 고객 리뷰와 공식 제품 자료를 인터넷에서 찾아요.',object:'웹 검색 화면·지구본'},
].map(Object.freeze));
export const PRODUCT_ROLES = Object.freeze([
  {id:'product_official_researcher',label:'공식 자료 조사자',simple:'제품 설명서를 찾아보는 도우미',home:'web'},
  {id:'product_review_researcher',label:'후기 조사·분석자',simple:'고객 후기를 찾아 읽는 도우미',home:'web'},
  {id:'product_evidence_reviewer',label:'근거 검토자',simple:'아이디어의 근거를 확인하는 도우미',home:'validate'},
].map(Object.freeze));
export const SKILL_BY_ID = Object.freeze(Object.fromEntries(PRODUCT_SKILLS.map(s=>[s.id,s])));
export const SKILL_BY_ROOM = Object.freeze(Object.fromEntries(PRODUCT_SKILLS.map(s=>[s.node,s])));
export const ROLE_BY_ID = Object.freeze(Object.fromEntries(PRODUCT_ROLES.map(r=>[r.id,r])));
export const PRODUCT_ROOM_IDS = Object.freeze(PRODUCT_SKILLS.map(s=>s.node));
export const actorLabel = actor => actor==='main'?'메인 기획 AI':ROLE_BY_ID[actor]?.label||'역할 미확인 도우미';
