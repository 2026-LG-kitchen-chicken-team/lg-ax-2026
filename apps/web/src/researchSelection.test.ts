import { describe, expect, it, vi } from 'vitest';
import { ResearchClient } from './researchClient';
import { normalizeSourceSelection, planningInputScope, planningInputScopeLabel } from './researchSelection';
import { heldBrief, REAL_RESEARCH_SELECTION_BUNDLE as bundle } from './fixtures/research-test-data';
import { exportResearchPlan } from './research';
import type { PlanningBrief, ResearchBundle, ResearchSource } from './research';
import manualSource from './fixtures/research-actual-manual-source.json';

const ids = bundle.sources.map(source => source.source_id);
const hash = 'a'.repeat(64);
const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
function selectedBrief(selection = ids.slice(1)): PlanningBrief {
  const sources = bundle.sources.filter(source => selection.includes(source.source_id));
  return { ...heldBrief({ ...bundle, sources }), source_facts: sources.map(source => ({ source_id: source.source_id, facts: source.facts })),
    runtime: { input_scope: 'user_selected_sources', user_selected_source_ids: selection, selected_source_ids: [], bundle_sha256: hash } };
}
const input = () => ({ bundle_id: bundle.bundle_id, goal: heldBrief().goal, constraints: heldBrief().constraints });
const client = (transport: typeof fetch) => new ResearchClient(() => 'a'.repeat(40), transport);

describe('selected original sources as planning input', () => {
  it('normalizes checkbox order and sends the frozen bundle hash independently of model sampling', async () => {
    expect(ids).toHaveLength(2);
    const transport = vi.fn().mockImplementation(async (url: string) => response(url.endsWith('/bundles')
      ? { bundles: [{ bundle_id: bundle.bundle_id, product_group: 'fridge', analysis_scope: 'product_group', bundle_sha256: hash }] }
      : selectedBrief(ids)));
    const api = client(transport); await api.listBundles();
    const result = await api.createPlan(bundle, { ...input(), selected_source_ids: [...ids].reverse() }, null);
    expect(JSON.parse(transport.mock.calls[1][1].body)).toMatchObject({ selected_source_ids: ids, bundle_sha256: hash });
    expect(result.runtime.selected_source_ids).toEqual([]);
    expect(planningInputScopeLabel(result)).toBe('기획 입력 범위: 사용자 선택 원문 2건');
  });

  it.each([{ selection: [] }, { selection: [ids[0], ids[0]] }, { selection: ['foreign-source'] }])('rejects an invalid selection before any POST: %j', async ({ selection }) => {
    const transport = vi.fn();
    await expect(client(transport).createPlan(bundle, { ...input(), selected_source_ids: selection }, null)).rejects.toThrow();
    expect(transport).not.toHaveBeenCalled();
  });

  it('rejects full-bundle substitution, missing scope, changed facts and out-of-selection references', async () => {
    const request = { ...input(), selected_source_ids: ids.slice(1) };
    const substituted = selectedBrief(ids); substituted.runtime.input_scope = 'full_bundle';
    const missing = selectedBrief(); delete missing.runtime.input_scope; delete missing.runtime.user_selected_source_ids;
    const expandedFacts = selectedBrief(); expandedFacts.source_facts.unshift({ source_id: ids[0], facts: [] });
    const outsideReference = selectedBrief(); outsideReference.summaries.positive[0].source_ids = [ids[0]];
    for (const result of [substituted, missing, expandedFacts, outsideReference]) {
      await expect(client(vi.fn().mockResolvedValue(response(result))).createPlan(bundle, request, null)).rejects.toThrow();
    }
  });

  it('omits a new selection on condition revisions and verifies the inherited range', async () => {
    const previous = selectedBrief();
    const next = { ...selectedBrief(), brief_id: 'TEST-next', run_id: 'TEST-next-run', previous_brief_id: previous.brief_id,
      revision: 1, constraints: [...previous.constraints, '하드웨어 변경 없이 개선'] };
    const transport = vi.fn().mockResolvedValue(response(next)); const api = client(transport);
    await api.createPlan(bundle, { ...input(), constraints: next.constraints, previous_run_id: previous.run_id }, previous);
    expect(JSON.parse(transport.mock.calls[0][1].body)).not.toHaveProperty('selected_source_ids');
    expect(planningInputScope(next, bundle)?.ids).toEqual(ids.slice(1));
    next.runtime.user_selected_source_ids = ids; next.source_facts = bundle.sources.map(source => ({ source_id: source.source_id, facts: [] }));
    transport.mockResolvedValue(response(next));
    await expect(api.createPlan(bundle, { ...input(), constraints: next.constraints, previous_run_id: previous.run_id }, previous)).rejects.toThrow('입력 근거 범위');
  });

  it('requires a new plan for changed selection and never guesses legacy scope from model sampling', async () => {
    const previous = selectedBrief(); const transport = vi.fn();
    await expect(client(transport).createPlan(bundle, { ...input(), selected_source_ids: ids, previous_run_id: previous.run_id }, previous)).rejects.toThrow('새 기획');
    expect(transport).not.toHaveBeenCalled();
    const legacy = heldBrief(bundle); legacy.runtime.selected_source_ids = ids;
    expect(planningInputScope(legacy, bundle)).toBeNull();
    expect(planningInputScopeLabel(legacy)).toContain('제공되지 않았습니다');
    expect(normalizeSourceSelection(bundle, [...ids].reverse())).toEqual(ids);
  });

  it('preserves original facts while accepting JSON object key reordering and rejects changed fact text', () => {
    const source = manualSource as unknown as ResearchSource;
    const manualBundle: ResearchBundle = { ...bundle, product_group: 'microwave', sources: [source] };
    const result = heldBrief(manualBundle);
    result.runtime = { input_scope: 'user_selected_sources', user_selected_source_ids: [source.source_id] };
    result.source_facts = [{ source_id: source.source_id, facts: source.facts.map(fact => Object.fromEntries(Object.entries(fact).reverse()) as typeof fact) }];
    expect(planningInputScope(result, manualBundle)?.ids).toEqual([source.source_id]);
    result.source_facts[0].facts[0].text += ' altered';
    expect(() => planningInputScope(result, manualBundle)).toThrow('원문 사실');
  });

  it('exports the actual input range and keeps the full original bundle as provenance', () => {
    const result = selectedBrief(); const exported = exportResearchPlan(bundle, result);
    expect(exported.markdown).toContain('입력: 사용자 선택 근거 1건');
    expect(exported.markdown).toContain(`입력 근거 ID: ${ids[1]}`);
    expect(exported.markdown).toContain(hash);
    expect(JSON.parse(exported.json).bundle.sources).toEqual(bundle.sources);
    expect(JSON.parse(exported.json).brief.runtime.user_selected_source_ids).toEqual(ids.slice(1));
  });
});
