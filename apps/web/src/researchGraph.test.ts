// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ResearchRelationsGraph } from './ResearchRelationsGraph';
import { buildResearchGraph, GRAPH_NODE_HEIGHT, graphEdgePath } from './researchGraph';
import { heldBrief, REAL_RESEARCH_BUNDLE } from './fixtures/research-test-data';
import type { PlanningBrief } from './research';

// Relation structure only, using a real public source. No fabricated customer text or model-quality claim.
function relationBrief(): PlanningBrief {
  const brief = heldBrief(); const sourceId = REAL_RESEARCH_BUNDLE.sources[0].source_id;
  brief.problems = [{ id: 'problem-structure-check', title: '관계 구조 검사', description: '관계 ID와 필터의 UI 검사이며 제품 문제 판단이 아닙니다.',
    source_ids: [sourceId], counter_source_ids: [], scope_caveat: '실모델 평가 아님' }];
  brief.concepts = [{ id: 'concept-structure-check', title: '연결 구조 검사', problem_ids: [brief.problems[0].id], target_user: 'UI 검사',
    use_context: '관계 구조 검증', before_steps: ['기준 구조'], after_steps: ['연결 구조'], mechanism: 'UI 계약 검사',
    proposed_changes: [], source_ids: [sourceId], assumptions: [], validation_questions: [],
    visual_scenes: [{ title: '구조 검사', before: '기준', after: '연결' }], status: 'needs_sources' }];
  brief.relations = [
    { from_id: sourceId, to_id: brief.problems[0].id, relation: 'supports', source_ids: [sourceId], inferred: true },
    { from_id: brief.problems[0].id, to_id: brief.concepts[0].id, relation: 'proposes', source_ids: [sourceId], inferred: true },
  ];
  return brief;
}

describe('bounded graph of returned research relations', () => {
  it('uses only original relation IDs/directions and never adds an edge from a citation alone', () => {
    const brief = relationBrief(); const graph = buildResearchGraph(REAL_RESEARCH_BUNDLE, brief, brief.problems[0].id);
    expect(graph.nodes.map(node => node.kind).sort()).toEqual(['concept', 'problem', 'source']);
    expect(graph.edges.map(({ id: _id, ...edge }) => edge)).toEqual(brief.relations);
    brief.relations = []; expect(buildResearchGraph(REAL_RESEARCH_BUNDLE, brief, brief.problems[0].id).edges).toHaveLength(0);
  });
  it('filters relation type and inference status without converting co-occurrence into cause or frequency', () => {
    const brief = relationBrief(); brief.relations.push({ ...brief.relations[0], relation: 'co_occurs', inferred: false });
    const graph = buildResearchGraph(REAL_RESEARCH_BUNDLE, brief, brief.problems[0].id, 'co_occurs', 'recorded');
    expect(graph.edges).toHaveLength(1); expect(graph.edges[0].relation).toBe('co_occurs'); expect(graph.edges[0].inferred).toBe(false);
    expect(buildResearchGraph(REAL_RESEARCH_BUNDLE, brief, brief.problems[0].id, 'co_occurs', 'inferred').edges).toHaveLength(0);
  });
  it('reports unresolved nodes and caps dense relationships, without drawing a whole product graph', () => {
    const brief = relationBrief(); brief.relations.push({ ...brief.relations[0], from_id: 'unresolved-original-node' });
    const checked = buildResearchGraph(REAL_RESEARCH_BUNDLE, brief, brief.problems[0].id);
    expect(checked.unresolved_relation_count).toBe(1); expect(checked.edges).toHaveLength(2);
    brief.relations = Array.from({ length: 40 }, () => ({ ...brief.relations[0] }));
    const graph = buildResearchGraph(REAL_RESEARCH_BUNDLE, brief, brief.problems[0].id);
    expect(graph.edges).toHaveLength(24); expect(graph.hidden_relation_count).toBe(16); expect(graph.nodes.length).toBeLessThanOrEqual(18);
    expect(graphEdgePath(graph.nodes.find(node => node.kind === 'source')!, graph.nodes.find(node => node.kind === 'problem')!)).toContain(` ${68 + GRAPH_NODE_HEIGHT / 2}`);
  });
  it('keeps nodes beyond two hops out of the selected problem view', () => {
    const brief = relationBrief();
    brief.problems.push({ ...brief.problems[0], id: 'problem-two-hops' });
    brief.concepts.push({ ...brief.concepts[0], id: 'concept-three-hops', problem_ids: ['problem-two-hops'] });
    brief.relations.push({ ...brief.relations[1], from_id: brief.concepts[0].id, to_id: 'problem-two-hops' },
      { ...brief.relations[1], from_id: 'problem-two-hops', to_id: 'concept-three-hops' });
    const graph = buildResearchGraph(REAL_RESEARCH_BUNDLE, brief, brief.problems[0].id);
    expect(graph.nodes.some(node => node.id === 'problem-two-hops')).toBe(true);
    expect(graph.nodes.some(node => node.id === 'concept-three-hops')).toBe(false);
    expect(graph.edges).toHaveLength(3);
  });
});

describe('accessible research graph interactions', () => {
  const hosts: HTMLDivElement[] = []; const roots: ReturnType<typeof createRoot>[] = [];
  afterEach(async () => { for (const root of roots.splice(0)) await act(async () => root.unmount()); hosts.splice(0).forEach(host => host.remove()); vi.unstubAllGlobals(); });
  async function mount(brief = relationBrief()) {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); const host = document.createElement('div'); document.body.append(host); hosts.push(host);
    const root = createRoot(host); roots.push(root); const onInspect = vi.fn(); const onReuseProblem = vi.fn();
    await act(async () => root.render(createElement(ResearchRelationsGraph, { bundle: REAL_RESEARCH_BUNDLE, brief, onInspect, onReuseProblem })));
    return { host, onInspect, onReuseProblem, brief };
  }
  it('offers keyboard source inspection and reuses only the chosen problem without a model request', async () => {
    const { host, onInspect, onReuseProblem, brief } = await mount();
    const source = host.querySelector<SVGGElement>('.graph-node-source')!;
    expect(source.getAttribute('tabindex')).toBe('0');
    await act(async () => source.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })));
    expect(onInspect).toHaveBeenCalledWith(REAL_RESEARCH_BUNDLE.sources[0].source_id);
    expect(host.querySelector('.research-graph-list')?.textContent).toContain('AI 추론');
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>('button')].find(item => item.textContent === '이 문제로 기획 조건 검토')!.click());
    expect(onReuseProblem).toHaveBeenCalledWith(brief.problems[0]);
    expect(host.textContent).toContain('원인 관계나 발생 빈도를 뜻하지 않습니다');
  });
  it('shows no invented graph for a held result with no recorded problems', async () => {
    const { host } = await mount(heldBrief()); expect(host.querySelector('svg')).toBeNull();
    expect(host.textContent).toContain('연결할 문제를 아직 확인하지 못했습니다');
  });
});
