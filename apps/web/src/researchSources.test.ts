import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import records from '../../../data/research/r5-public-reviews-20261007/fixed18/records.json';
import manualSource from './fixtures/research-actual-manual-source.json';
import { REAL_RESEARCH_BUNDLE } from './fixtures/research-test-data';
import { confirmedPostingDay, DEFAULT_SOURCE_FILTERS, expandedKeywords, exportResearchSelection, koreanSourceLimitations, selectFilteredSources, sourceDateDisplay } from './researchSources';
import type { ResearchBundle, ResearchSource } from './research';
import { ResearchClient } from './researchClient';

describe('confirmed dates and explicit keyword expansion', () => {
  it('separates observed purchase dates from unknown posting dates without duplicated unknown wording', () => {
    const source = { ...REAL_RESEARCH_BUNDLE.sources[0], date_kind: 'purchase' as const, metadata: { purchase_date: '2026-10-07' } };
    expect(confirmedPostingDay(source)).toBeNull(); expect(sourceDateDisplay(source)).toBe('게시일 미확인 · 구매일 2026-10-07');
    expect(sourceDateDisplay({ ...source, metadata: {} })).toBe('게시일 미확인 · 원문 날짜 기준 구매일');
    expect(sourceDateDisplay(REAL_RESEARCH_BUNDLE.sources[0])).toBe('게시일 미확인');
  });
  it('uses only structurally confirmed posting dates for an inclusive range, with unknowns separately selectable', () => {
    // Dates below are shape checks, not claimed historical posting dates of the real review.
    const base = REAL_RESEARCH_BUNDLE.sources[0];
    const dated: ResearchSource = { ...base, source_id: 'date-shape-check', date_kind: 'posting', published_at: '2026-10-07T00:00:00Z' };
    const purchase: ResearchSource = { ...base, source_id: 'purchase-shape-check', date_kind: 'purchase', published_at: '2026-10-07' };
    const filters = { ...DEFAULT_SOURCE_FILTERS, start_date: '2026-10-07', end_date: '2026-10-07' };
    expect(selectFilteredSources([dated, purchase, base], filters)).toEqual([dated]);
    expect(selectFilteredSources([dated, purchase, base], { ...DEFAULT_SOURCE_FILTERS, posting_date_mode: 'unknown' })).toEqual([purchase, base]);
    expect(confirmedPostingDay({ ...dated, published_at: '2026-02-30' })).toBeNull();
    expect(selectFilteredSources([dated], { ...filters, start_date: '2026-10-08' })).toHaveLength(0);
    expect(selectFilteredSources([base], { ...DEFAULT_SOURCE_FILTERS, page_model: 'different-page-model' })).toHaveLength(0);
  });
  it('matches actual quiet-review text through a visible rule group, without a model call', () => {
    const record = records.find(item => item.text.includes('조용'))!; expect(record).toBeDefined();
    const source: ResearchSource = { ...REAL_RESEARCH_BUNDLE.sources[0], source_id: record.original_review_id, text: record.text, page_model: record.displayed_model_id };
    const exact = { ...DEFAULT_SOURCE_FILTERS, query: '시끄럽' };
    expect(selectFilteredSources([source], exact)).toHaveLength(0);
    expect(selectFilteredSources([source], { ...exact, expand_terms: true })).toEqual([source]);
    expect(expandedKeywords({ ...exact, expand_terms: true })).toContain('조용');
  });
});

describe('selected public source export and manifest meaning', () => {
  beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals());
  const actualManual = manualSource as unknown as ResearchSource;
  const bundle: ResearchBundle = { schema_version: '1.0', bundle_id: 'WEB-actual-manual-selection-check', product_group: 'microwave', analysis_scope: 'product_group',
    sources: [actualManual], collection_manifest: { independent_evaluation_approved: false, limitations: ['Purposive UI sample'], review_count: 0 } };
  it('copies full original facts/locator/text exactly and explicitly records no execution or evaluation approval', async () => {
    const before = structuredClone(bundle); const hash = 'b'.repeat(64);
    const exported = await exportResearchSelection(bundle, [actualManual.source_id], DEFAULT_SOURCE_FILTERS, hash, '2026-10-07T00:00:00Z');
    expect(exported.bundle.sources[0]).toEqual(actualManual); expect(bundle).toEqual(before);
    expect(exported.bundle.sources[0].facts[0].text).toContain('200 W');
    expect(exported.bundle.sources[0].facts[0].locator).toEqual({ page: 25, section: '출력 조절' });
    expect(exported.bundle.collection_manifest.independent_evaluation_approved).toBe(false);
    expect(exported.bundle.collection_manifest.planning_executed).toBe(false);
    expect(exported.bundle.collection_manifest.selection).toMatchObject({ source_bundle_id: bundle.bundle_id, source_bundle_sha256: hash, review_text_edits: 0, facts_edits: 0, server_subset_planning_supported: false });
    expect(JSON.parse(exported.json)).toEqual(exported.bundle); expect(exported.markdown).toContain(actualManual.text);
    expect(exported.markdown).toContain(JSON.stringify(actualManual.facts, null, 2)); expect(exported.markdown).toContain('새 기획 실행 결과가 아닙니다');
  });
  it('rejects empty/stale selection and calculates an explicit fallback fingerprint instead of inventing a server hash', async () => {
    await expect(exportResearchSelection(bundle, [], DEFAULT_SOURCE_FILTERS, null)).rejects.toThrow('하나 이상');
    await expect(exportResearchSelection(bundle, ['missing'], DEFAULT_SOURCE_FILTERS, null)).rejects.toThrow('하나 이상');
    const selected = await exportResearchSelection(bundle, [actualManual.source_id], DEFAULT_SOURCE_FILTERS, null);
    expect(selected.bundle.collection_manifest.selection).toMatchObject({ source_hash_basis: 'browser_canonical_json' });
    expect((selected.bundle.collection_manifest.selection as Record<string, unknown>).source_bundle_sha256).toMatch(/^[a-f0-9]{64}$/);
    expect(koreanSourceLimitations(selected.bundle).join(' ')).toContain('선택한 파일');
    expect(koreanSourceLimitations(bundle).join(' ')).toContain('전체 시장');
  });
  it('separates model activation waiting from an unavailable source-list API', async () => {
    const transport = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ error: { code: 'NOT_IMPLEMENTED' } }), { status: 501 })));
    const client = new ResearchClient(() => 'a'.repeat(40), transport);
    await expect(client.listBundles()).rejects.toThrow('API 연결 대기');
    await expect(client.createPlan(bundle, { bundle_id: bundle.bundle_id, goal: '형식 검사', constraints: [], previous_run_id: null }, null)).rejects.toThrow('모델 실행 활성화');
  });
});
