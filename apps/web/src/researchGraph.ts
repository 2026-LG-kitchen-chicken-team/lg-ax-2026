import type { PlanningBrief, ResearchBundle, ResearchSource } from './research';
import { RESEARCH_TYPE_LABEL } from './research';

export type ResearchRelation = PlanningBrief['relations'][number];
export type RelationType = ResearchRelation['relation'];
export type RelationOrigin = 'all' | 'inferred' | 'recorded';
export const RELATION_LABEL: Record<RelationType, string> = {
  supports: '뒷받침', contradicts: '반대 근거', co_occurs: '함께 언급', addresses: '대응', proposes: '제안',
};
export interface ResearchGraphNode {
  id: string; kind: 'source' | 'problem' | 'concept' | 'comparison'; title: string; detail: string;
  source_ids: string[]; source_type?: ResearchSource['source_type']; x: number; y: number;
}
export interface ResearchGraphEdge extends ResearchRelation { id: string }
export interface ResearchGraph {
  nodes: ResearchGraphNode[]; edges: ResearchGraphEdge[]; height: number;
  local_relation_count: number; filtered_relation_count: number; hidden_relation_count: number;
  unresolved_relation_count: number;
}
export const GRAPH_NODE_WIDTH = 245;
export const GRAPH_NODE_HEIGHT = 66;

/** Draw only relations that the selected brief returned. Citation arrays never create an extra edge. */
export function buildResearchGraph(bundle: ResearchBundle, brief: PlanningBrief, problemId: string,
  relation: RelationType | 'all' = 'all', origin: RelationOrigin = 'all'): ResearchGraph {
  const empty: ResearchGraph = { nodes: [], edges: [], height: 160, local_relation_count: 0, filtered_relation_count: 0,
    hidden_relation_count: 0, unresolved_relation_count: 0 };
  if (bundle.bundle_id !== brief.bundle_id || !brief.problems.some(item => item.id === problemId)) return empty;
  type RawNode = Omit<ResearchGraphNode, 'x' | 'y'>;
  const catalog = new Map<string, RawNode>();
  const ambiguous = new Set<string>();
  function add(node: RawNode) { if (catalog.has(node.id)) ambiguous.add(node.id); else catalog.set(node.id, node); }
  for (const source of bundle.sources) add({ id: source.source_id, kind: 'source', title: source.title || RESEARCH_TYPE_LABEL[source.source_type],
    detail: source.text, source_ids: [source.source_id], source_type: source.source_type });
  for (const problem of brief.problems) add({ id: problem.id, kind: 'problem', title: problem.title, detail: problem.description,
    source_ids: [...new Set([...problem.source_ids, ...problem.counter_source_ids])] });
  for (const concept of brief.concepts) add({ id: concept.id, kind: 'concept', title: concept.title, detail: concept.mechanism, source_ids: concept.source_ids });
  for (const comparison of brief.comparisons) add({ id: comparison.id, kind: 'comparison', title: comparison.product,
    detail: `${comparison.existing_response}\n남은 부담: ${comparison.remaining_burden}`, source_ids: comparison.source_ids });
  const valid = brief.relations.map((item, index): ResearchGraphEdge => ({ ...item, id: `relation-${index}` }))
    .filter(item => catalog.has(item.from_id) && catalog.has(item.to_id) && !ambiguous.has(item.from_id) && !ambiguous.has(item.to_id));
  // Two hops around one selected problem keeps the view useful even when a shared document links many problems.
  const neighborhood = new Map<string, number>([[problemId, 0]]);
  for (let depth = 0; depth < 2; depth++) {
    for (const edge of valid) {
      if (neighborhood.get(edge.from_id) === depth && !neighborhood.has(edge.to_id)) neighborhood.set(edge.to_id, depth + 1);
      if (neighborhood.get(edge.to_id) === depth && !neighborhood.has(edge.from_id)) neighborhood.set(edge.from_id, depth + 1);
    }
  }
  const local = valid.filter(item => neighborhood.has(item.from_id) && neighborhood.has(item.to_id));
  const filtered = local.filter(item => (relation === 'all' || item.relation === relation)
    && (origin === 'all' || item.inferred === (origin === 'inferred')));
  const shownIds = new Set<string>([problemId]);
  const edges: ResearchGraphEdge[] = [];
  // A deterministic cap is stated in the UI; it is a display limit, never an importance or frequency score.
  for (const edge of filtered) {
    const nextIds = new Set([...shownIds, edge.from_id, edge.to_id]);
    if (edges.length >= 24 || nextIds.size > 18) continue;
    edges.push(edge); nextIds.forEach(id => shownIds.add(id));
  }
  const columnCounts = [0, 0, 0];
  const order = [...shownIds].sort((a, b) => (neighborhood.get(a) ?? 3) - (neighborhood.get(b) ?? 3));
  const nodes: ResearchGraphNode[] = order.flatMap(id => {
    const node = catalog.get(id); if (!node || ambiguous.has(id)) return [];
    const column = node.kind === 'source' ? 0 : node.kind === 'problem' ? 1 : 2;
    return [{ ...node, x: 35 + column * 335, y: 68 + columnCounts[column]++ * 100 }];
  });
  return { nodes, edges, height: Math.max(180, 68 + Math.max(...columnCounts) * 100),
    local_relation_count: local.length, filtered_relation_count: filtered.length,
    hidden_relation_count: filtered.length - edges.length, unresolved_relation_count: brief.relations.length - valid.length };
}

export function graphEdgePath(from: ResearchGraphNode, to: ResearchGraphNode): string {
  if (from.id === to.id) {
    const x = from.x + GRAPH_NODE_WIDTH; const y = from.y + GRAPH_NODE_HEIGHT / 2;
    return `M ${x} ${y - 10} C ${x + 60} ${y - 55}, ${x + 60} ${y + 55}, ${x} ${y + 10}`;
  }
  const forward = from.x < to.x;
  const sameColumn = from.x === to.x;
  const startX = sameColumn || forward ? from.x + GRAPH_NODE_WIDTH : from.x;
  const endX = sameColumn || !forward ? to.x + GRAPH_NODE_WIDTH : to.x;
  const startY = from.y + GRAPH_NODE_HEIGHT / 2; const endY = to.y + GRAPH_NODE_HEIGHT / 2;
  const bendX = sameColumn ? startX + 55 : (startX + endX) / 2;
  return `M ${startX} ${startY} C ${bendX} ${startY}, ${bendX} ${endY}, ${endX} ${endY}`;
}
