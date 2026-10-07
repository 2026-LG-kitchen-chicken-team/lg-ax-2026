import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseResearchBundle } from './research';

// Optional intake check uses frozen DATA outputs, without a network call or model execution.
const intake = process.env.LGAX_RESEARCH_INTAKE_DIR;
describe.skipIf(!intake)('frozen public DATA research intake', () => {
  for (const group of ['dishwasher', 'microwave', 'fridge']) it(`consumes ${group} without losing original holds or unknowns`, () => {
    const raw = JSON.parse(readFileSync(join(intake!, `${group}.development.research-bundle.json`), 'utf8'));
    const bundle = parseResearchBundle(raw);
    expect(bundle.product_group).toBe(group);
    expect(bundle.analysis_scope).toBe('product_group');
    expect(bundle.sources.every(source => source.source_kind === 'public')).toBe(true);
    expect(bundle.sources.filter(source => source.source_type === 'review').length).toBe(bundle.collection_manifest.review_count);
    expect(bundle.collection_manifest.synthetic_review_count).toBe(0);
    expect(bundle.collection_manifest.original_exact_model_holds_preserved).toBe(true);
    expect(bundle.sources.filter(source => source.purchased_model === null).length).toBe(raw.sources.filter((source: { purchased_model: unknown }) => source.purchased_model === null).length);
    expect(bundle.sources.filter(source => source.published_at === null).length).toBe(raw.sources.filter((source: { published_at: unknown }) => source.published_at === null).length);
  });
});
