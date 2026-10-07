import { describe, expect, it, vi } from 'vitest';
import { ResearchClient } from './researchClient';
import { exportResearchPlan, filterResearchSources, parseBundleList, parsePlanningBrief, parseResearchBundle } from './research';
import type { PlanningBrief } from './research';
import { heldBrief, REAL_RESEARCH_BUNDLE, REAL_RESEARCH_RECORD as record } from './fixtures/research-test-data';

describe('public research contract consumption', () => {
  it('keeps real text, unknown purchased model and posting date intact', () => {
    const parsed = parseResearchBundle(REAL_RESEARCH_BUNDLE);
    expect(parsed.sources[0].text).toBe(record.text);
    expect(parsed.sources[0].purchased_model).toBeNull();
    expect(parsed.sources[0].published_at).toBeNull();
    expect(parsePlanningBrief(heldBrief(), parsed).status).toBe('needs_sources');
    expect(parseBundleList({ bundles: [{ bundle_id: parsed.bundle_id, product_group: 'fridge', analysis_scope: 'product_group' }] })[0].review_count).toBeNull();
  });
  it('rejects synthetic origins, unsafe links, duplicate sources and missing reference IDs', () => {
    const payload = structuredClone(REAL_RESEARCH_BUNDLE) as unknown as Record<string, unknown>;
    const source = (payload.sources as Array<Record<string, unknown>>)[0];
    source.source_kind = 'synthetic'; expect(() => parseResearchBundle(payload)).toThrow('규격');
    source.source_kind = 'public'; source.url = 'javascript:alert(1)'; expect(() => parseResearchBundle(payload)).toThrow('규격');
    source.url = record.source_url; (payload.sources as unknown[]).push({ ...source }); expect(() => parseResearchBundle(payload)).toThrow('중복');
    const brief = heldBrief(); brief.summaries.positive[0].source_ids = ['missing']; expect(() => parsePlanningBrief(brief, REAL_RESEARCH_BUNDLE)).toThrow('인용');
    brief.bundle_id = 'different'; expect(() => parsePlanningBrief(brief, REAL_RESEARCH_BUNDLE)).toThrow('범위');
  });
  it('filters keywords in the original text and exports the selected revision with honest unknowns', () => {
    const word = record.text.split(/\s+/)[0];
    expect(filterResearchSources(REAL_RESEARCH_BUNDLE.sources, word, 'review')).toHaveLength(1);
    expect(filterResearchSources(REAL_RESEARCH_BUNDLE.sources, word, 'manual')).toHaveLength(0);
    const exported = exportResearchPlan(REAL_RESEARCH_BUNDLE, heldBrief());
    expect(JSON.parse(exported.json).brief.status).toBe('needs_sources');
    expect(JSON.parse(exported.json).bundle.sources[0].purchased_model).toBeNull();
    expect(exported.markdown).toContain('구매 모델: 미확인');
    expect(exported.markdown).toContain(record.text);
    expect(exported.markdown).toContain(record.source_url);
    expect(exported.markdown).toContain('불편·부정 요약');
  });
});

describe('authenticated research transport and revision links', () => {
  const credential = () => 'a'.repeat(40);
  const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  it('uses Bearer memory credentials and treats an unavailable API as pending, with no automatic POST retry', async () => {
    const transport = vi.fn().mockResolvedValue(response({ error: { code: 'NOT_IMPLEMENTED' } }, 501));
    const client = new ResearchClient(credential, transport);
    await expect(client.listBundles()).rejects.toThrow('연결 대기');
    expect(transport).toHaveBeenCalledOnce();
    expect(transport.mock.calls[0][1].headers.Authorization).toBe(`Bearer ${credential()}`);
    const unauthorized = new ResearchClient(() => 'short', transport);
    await expect(unauthorized.listBundles()).rejects.toThrow('토큰');
    expect(transport).toHaveBeenCalledOnce();
  });
  it('passes the captured previous run and refuses a different parent or returned condition', async () => {
    const previous = heldBrief();
    const next: PlanningBrief = { ...heldBrief(), run_id: 'TEST-revision-run', brief_id: 'TEST-revision-brief', revision: 1,
      previous_brief_id: previous.brief_id, constraints: [...previous.constraints, '하드웨어 변경 없이 개선'] };
    const transport = vi.fn().mockImplementation(() => Promise.resolve(response(next)));
    const client = new ResearchClient(credential, transport);
    const input = { bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, goal: next.goal, constraints: next.constraints, previous_run_id: previous.run_id };
    expect((await client.createPlan(REAL_RESEARCH_BUNDLE, input, previous)).revision).toBe(1);
    expect(JSON.parse(transport.mock.calls[0][1].body).previous_run_id).toBe(previous.run_id);
    next.previous_brief_id = null;
    await expect(client.createPlan(REAL_RESEARCH_BUNDLE, input, previous)).rejects.toThrow('수정 연결');
    await expect(client.createPlan(REAL_RESEARCH_BUNDLE, { ...input, previous_run_id: 'foreign' }, previous)).rejects.toThrow('기준 실행');
  });
  it('does not accept a saved plan from a different frozen bundle version', async () => {
    const hash = 'a'.repeat(64);
    const transport = vi.fn().mockImplementation((url: string) => Promise.resolve(response(url.endsWith('/bundles')
      ? { bundles: [{ bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, product_group: 'fridge', analysis_scope: 'product_group', bundle_sha256: hash }] }
      : heldBrief())));
    const client = new ResearchClient(credential, transport); await client.listBundles();
    await expect(client.getPlan(REAL_RESEARCH_BUNDLE, heldBrief().run_id)).rejects.toThrow('자료 버전');
    const brief = heldBrief(); brief.runtime.bundle_sha256 = hash;
    transport.mockResolvedValue(response(brief));
    expect((await client.getPlan(REAL_RESEARCH_BUNDLE, brief.run_id)).run_id).toBe(brief.run_id);
  });
});
