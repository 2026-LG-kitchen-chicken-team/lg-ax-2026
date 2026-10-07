// Hand-written briefs (not model output). The coverage block follows CORE's definition on #234 (comment 6045972338) and
// public_planning.summary_reference_coverage in PR #251; the public API does not pass it yet.
import { describe, expect, it } from 'vitest';
import { coverageText, summaryCoverageView } from './researchCoverage';
import { heldBrief } from './fixtures/research-test-data';
import type { PlanningBrief } from './research';

const IDS = ['S-A', 'S-B', 'S-C', 'S-D', 'S-E'];
function block(patch: Record<string, unknown> = {}) {
  return { basis: 'returned_summary_references_on_successful_discovery', sample_unit: 'unique_deduplicated_customer_source',
    summary_item_counts: { positive: 2, negative: 1, mixed: 0 }, polarity_source_counts: { positive: 2, negative: 2, mixed: 0 },
    polarity_source_ids: { positive: ['S-A', 'S-B'], negative: ['S-B', 'S-C'], mixed: [] },
    input_customer_source_count: 5, denominator_customer_source_count: 4, denominator_source_ids: ['S-A', 'S-B', 'S-C', 'S-D'],
    covered_customer_source_count: 3, covered_source_ids: ['S-A', 'S-B', 'S-C'], unreferenced_processed_source_count: 1,
    unprocessed_input_source_count: 1, overlapping_polarity_source_count: 1, coverage_ratio: 0.75,
    classification_approved: false, market_frequency_estimated: false, ...patch };
}
function brief(runtime: Record<string, unknown>): PlanningBrief {
  return { ...heldBrief(), source_facts: IDS.map(source_id => ({ source_id, facts: [] })), runtime };
}

describe('summaryCoverageView', () => {
  it('reads a consistent block as N/M/C with unreferenced, unprocessed and overlaps kept apart', () => {
    const view = summaryCoverageView(brief({ summary_reference_coverage: block() }));
    expect(view).toEqual({ state: 'ok', value: { input: 5, denominator: 4, covered: 3, unreferenced: 1, unprocessed: 1, ratio: 0.75, overlapping: 1,
      polaritySources: { positive: 2, negative: 2, mixed: 0 }, summaryItems: { positive: 2, negative: 1, mixed: 0 } } });
    expect(coverageText(view)).toContain('처리된 고객 원문 4건 중 3건 인용(인용률 75%) · 미인용 1건 · 처리되지 않은 입력 1건(입력 5건)');
  });

  it('keeps M=0 with a null ratio as a valid state, separate from a missing block', () => {
    const empty = block({ summary_item_counts: { positive: 0, negative: 0, mixed: 0 }, polarity_source_counts: { positive: 0, negative: 0, mixed: 0 },
      polarity_source_ids: { positive: [], negative: [], mixed: [] }, denominator_customer_source_count: 0, denominator_source_ids: [],
      covered_customer_source_count: 0, covered_source_ids: [], unreferenced_processed_source_count: 0, unprocessed_input_source_count: 5,
      overlapping_polarity_source_count: 0, coverage_ratio: null });
    const view = summaryCoverageView(brief({ summary_reference_coverage: empty }));
    expect(view.state).toBe('ok');
    expect(coverageText(view)).toContain('인용률 없음(처리된 원문 0건)');
    expect(summaryCoverageView(brief({}))).toEqual({ state: 'not_provided', reason: 'absent' });
    expect(summaryCoverageView(brief({ summary_reference_coverage: block(), summary_reference_coverage_inheritance: 'invalid_previous_metadata' })))
      .toEqual({ state: 'not_provided', reason: 'inheritance_invalid' });
  });

  it.each([
    ['approval flag', { classification_approved: true }],
    ['basis', { basis: 'other' }],
    ['boolean count', { input_customer_source_count: true }],
    ['ratio not C/M', { coverage_ratio: 0.5 }],
    ['non-finite ratio', { coverage_ratio: Number.NaN }],
    ['unsorted ids', { denominator_source_ids: ['S-B', 'S-A', 'S-C', 'S-D'] }],
    ['unknown denominator id', { denominator_source_ids: ['S-A', 'S-B', 'S-C', 'S-Z'] }],
    ['polarity id outside denominator', { polarity_source_ids: { positive: ['S-A', 'S-E'], negative: ['S-B', 'S-C'], mixed: [] } }],
    ['covered is not the union', { covered_source_ids: ['S-A', 'S-B'], covered_customer_source_count: 2, unreferenced_processed_source_count: 2, coverage_ratio: 0.5 }],
    ['unreferenced is not M-C', { unreferenced_processed_source_count: 2 }],
    ['M larger than N', { input_customer_source_count: 3, unprocessed_input_source_count: -1 }],
    ['overlap count', { overlapping_polarity_source_count: 0 }],
    ['polarity count vs ids', { polarity_source_counts: { positive: 3, negative: 2, mixed: 0 } }],
  ])('rejects an inconsistent block: %s', (_name, patch) => {
    const view = summaryCoverageView(brief({ summary_reference_coverage: block(patch) }));
    expect(view.state).toBe('malformed');
    expect(coverageText(view)).toContain('형식 불일치');
  });

  // CORE boundary review on #234 (comment 6046183340): a ratio within 1e-9 of C/M but outside 0–1 must still be rejected.
  it.each([
    ['below 0 (C=0, M=1)', { covered: [] as string[], ratio: -5e-10 }],
    ['above 1 (C=M=1)', { covered: ['S-A'], ratio: 1 + 5e-10 }],
  ])('rejects a ratio just outside 0–1: %s', (_name, { covered, ratio }) => {
    const single = block({ summary_item_counts: { positive: covered.length, negative: 0, mixed: 0 }, polarity_source_counts: { positive: covered.length, negative: 0, mixed: 0 },
      polarity_source_ids: { positive: covered, negative: [], mixed: [] }, input_customer_source_count: 1, denominator_customer_source_count: 1,
      denominator_source_ids: ['S-A'], covered_customer_source_count: covered.length, covered_source_ids: covered,
      unreferenced_processed_source_count: 1 - covered.length, unprocessed_input_source_count: 0, overlapping_polarity_source_count: 0, coverage_ratio: ratio });
    expect(summaryCoverageView(brief({ summary_reference_coverage: single })).state).toBe('malformed');
    expect(summaryCoverageView(brief({ summary_reference_coverage: { ...single, coverage_ratio: covered.length } })).state).toBe('ok');
  });
});
