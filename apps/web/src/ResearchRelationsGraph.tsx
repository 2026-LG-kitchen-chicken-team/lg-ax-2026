import { useId, useMemo, useState } from 'react';
import { buildResearchGraph, GRAPH_NODE_HEIGHT, GRAPH_NODE_WIDTH, graphEdgePath, RELATION_LABEL } from './researchGraph';
import type { RelationOrigin, RelationType, ResearchGraphNode } from './researchGraph';
import type { PlanningBrief, ResearchBundle, ResearchProblem } from './research';

const KIND_LABEL = { source: '원문', problem: '문제', concept: '개선안', comparison: '제품 대조' };
function originLabel(inferred: boolean): string { return inferred ? 'AI 추론' : '기록된 연결 · 추론 표시 없음'; }
function shorten(text: string, limit: number): string { return text.length > limit ? `${text.slice(0, limit)}…` : text; }

export function ResearchRelationsGraph({ bundle, brief, onInspect, onReuseProblem }: {
  bundle: ResearchBundle; brief: PlanningBrief; onInspect: (sourceId: string) => void;
  onReuseProblem: (problem: ResearchProblem) => void;
}) {
  const graphicId = useId().replace(/:/g, '');
  const [problemChoice, setProblemChoice] = useState(brief.problems[0]?.id ?? '');
  const [relation, setRelation] = useState<RelationType | 'all'>('all');
  const [origin, setOrigin] = useState<RelationOrigin>('all');
  const [nodeChoice, setNodeChoice] = useState('');
  const problem = brief.problems.find(item => item.id === problemChoice) ?? brief.problems[0];
  const graph = useMemo(() => buildResearchGraph(bundle, brief, problem?.id ?? '', relation, origin), [bundle, brief, problem?.id, relation, origin]);
  const nodeById = new Map(graph.nodes.map(node => [node.id, node]));
  const selectedNode = nodeById.get(nodeChoice);
  function selectNode(node: ResearchGraphNode) {
    setNodeChoice(node.id);
    if (node.kind === 'source') onInspect(node.id);
    if (node.kind === 'problem') setProblemChoice(node.id);
  }
  return <section className="research-relations research-card" aria-label="문제 주변 관계 그래프">
    <div className="research-card-title"><h3>문제 주변의 근거 연결</h3><span className="research-chip">선택한 실행의 관계 기록</span></div>
    <p>반대 근거와 제안의 연결을 좁혀 보고, 기존 대응 비교와 다음 기획 조건에 활용하세요. 화살표는 저장된 연결 방향입니다.</p>
    <p className="research-note">점선은 AI 추론입니다. 실선도 사실·효과가 검증됐다는 뜻은 아닙니다. ‘함께 언급’은 원인 관계나 발생 빈도를 뜻하지 않습니다.</p>
    {!problem ? <p className="research-muted">연결할 문제를 아직 확인하지 못했습니다. 기획 결과의 추가 자료 필요 사항을 확인해 주세요.</p> : <>
      <div className="research-graph-filters"><label>중심 문제<select value={problem.id} onChange={event => { setProblemChoice(event.target.value); setNodeChoice(''); }}>{brief.problems.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label><label>관계 유형<select value={relation} onChange={event => { setRelation(event.target.value as typeof relation); setNodeChoice(''); }}><option value="all">모든 관계 유형</option>{Object.entries(RELATION_LABEL).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>추론 표시<select value={origin} onChange={event => { setOrigin(event.target.value as RelationOrigin); setNodeChoice(''); }}><option value="all">모두 보기</option><option value="inferred">AI 추론</option><option value="recorded">추론 표시 없는 기록</option></select></label></div>
      <div className="research-graph-caption"><span>주변 관계 {graph.local_relation_count}건 · 필터 결과 {graph.filtered_relation_count}건 · 화면 표시 {graph.edges.length}건</span><button type="button" className="secondary-button" onClick={() => onReuseProblem(problem)}>이 문제로 기획 조건 검토</button></div>
      {graph.hidden_relation_count ? <p className="research-note">선택 문제의 두 단계 이내 관계만 살펴봅니다. 최대 18개 노드·24개 관계 표시 제한으로 {graph.hidden_relation_count}개 관계가 생략됐습니다. 중심 문제나 관계 유형을 좁혀 확인해 주세요.</p> : <p className="research-muted">선택 문제에서 두 단계 이내의 연결을 표시합니다. 개수는 현재 자료의 관계 기록 수입니다.</p>}
      {graph.unresolved_relation_count ? <p className="research-note">현재 실행 전체에서 연결 노드를 확인하지 못한 관계 {graph.unresolved_relation_count}건은 그리지 않았습니다.</p> : null}
      {!graph.edges.length ? <p className="research-note">선택한 조건에 맞는 관계 기록이 없습니다. 인용 목록으로 그래프 연결을 임의로 만들지 않습니다.</p> : <div className="research-graph-scroll"><svg role="group" aria-labelledby={`${graphicId}-title ${graphicId}-description`} viewBox={`0 0 1010 ${graph.height}`} width="1010" height={graph.height}>
        <title id={`${graphicId}-title`}>{problem.title} 주변 원문·문제·개선안 관계</title><desc id={`${graphicId}-description`}>같은 관계를 아래 접근 가능한 목록에서도 확인할 수 있습니다. 점선은 추론이며 함께 언급은 인과나 빈도가 아닙니다.</desc>
        <defs><marker id={`${graphicId}-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#728863" /></marker></defs>
        <text x="35" y="30" className="research-graph-column">원문</text><text x="370" y="30" className="research-graph-column">관찰한 문제</text><text x="705" y="30" className="research-graph-column">기획·대조</text>
        {graph.edges.map(edge => <path key={edge.id} d={graphEdgePath(nodeById.get(edge.from_id)!, nodeById.get(edge.to_id)!)} fill="none" stroke={edge.relation === 'contradicts' ? '#ab765a' : '#728863'} strokeWidth="2" strokeDasharray={edge.inferred ? '6 4' : undefined} markerEnd={`url(#${graphicId}-arrow)`} data-relation={edge.relation}><title>{RELATION_LABEL[edge.relation]} · {originLabel(edge.inferred)}</title></path>)}
        {graph.nodes.map(node => <g key={`${node.kind}:${node.id}`} className={`research-graph-node graph-node-${node.kind}`} role="button" tabIndex={0} aria-label={`${KIND_LABEL[node.kind]}: ${node.title}`} transform={`translate(${node.x},${node.y})`} onClick={() => selectNode(node)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectNode(node); } }}><rect width={GRAPH_NODE_WIDTH} height={GRAPH_NODE_HEIGHT} rx="9" /><text x="12" y="20" className="research-graph-node-kind">{KIND_LABEL[node.kind]} · {shorten(node.id, 24)}</text><text x="12" y="44">{shorten(node.title, 20)}</text><title>{node.title}</title></g>)}
      </svg></div>}
      {selectedNode ? <div className="research-graph-detail" aria-label="선택한 관계 노드"><strong>{KIND_LABEL[selectedNode.kind]} · {selectedNode.title}</strong><p>{selectedNode.detail}</p><div className="research-citations">{[...new Set(selectedNode.source_ids)].map(id => <button type="button" key={id} onClick={() => onInspect(id)}>{id} 원문 확인</button>)}</div></div> : null}
      <details className="research-graph-list" open><summary>관계를 목록으로 확인 · {graph.edges.length}건</summary><ul>{graph.edges.map(edge => <li key={edge.id}><div><button type="button" onClick={() => selectNode(nodeById.get(edge.from_id)!)}>{nodeById.get(edge.from_id)!.title}</button><span>→ {RELATION_LABEL[edge.relation]} →</span><button type="button" onClick={() => selectNode(nodeById.get(edge.to_id)!)}>{nodeById.get(edge.to_id)!.title}</button></div><p>{originLabel(edge.inferred)} · 연결 출처 {edge.source_ids.length}건</p><div className="research-citations">{edge.source_ids.length ? [...new Set(edge.source_ids)].map(id => <button type="button" key={id} onClick={() => onInspect(id)}>{id} 원문 확인</button>) : <span>연결 출처 미제공</span>}</div></li>)}</ul></details>
    </>}
  </section>;
}
