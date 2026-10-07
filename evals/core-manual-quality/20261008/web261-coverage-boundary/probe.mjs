import fs from 'node:fs';
import assert from 'node:assert/strict';
import { summaryCoverageView } from './researchCoverage.before.ts';

// Protocol-only coverage metadata with an existing real source ID. No new
// review, model response, sentiment assignment, or actual stored brief.
const id = 'LGE-R8-REVIEW-752651';
function block(covered, ratio, m = 1) {
  return {
    basis: 'returned_summary_references_on_successful_discovery',
    sample_unit: 'unique_deduplicated_customer_source',
    summary_item_counts: { positive: covered, negative: 0, mixed: 0 },
    polarity_source_counts: { positive: covered, negative: 0, mixed: 0 },
    polarity_source_ids: { positive: covered ? [id] : [], negative: [], mixed: [] },
    input_customer_source_count: 1,
    denominator_customer_source_count: m,
    denominator_source_ids: m ? [id] : [],
    covered_customer_source_count: covered,
    covered_source_ids: covered ? [id] : [],
    unreferenced_processed_source_count: m - covered,
    unprocessed_input_source_count: 1 - m,
    overlapping_polarity_source_count: 0,
    coverage_ratio: ratio,
    classification_approved: false,
    market_frequency_estimated: false,
  };
}
const rows = [];
function check(name, runtime, required, observed) {
  const result = summaryCoverageView({ source_facts: [{ source_id: id, facts: [] }], runtime });
  rows.push({ name, runtime, required_state: required, actual_state: result.state, result });
  assert.equal(result.state, observed, name);
}
check('valid_zero_ratio', { summary_reference_coverage: block(0, 0) }, 'ok', 'ok');
check('negative_near_zero', { summary_reference_coverage: block(0, -5e-10) }, 'malformed', 'ok');
check('valid_one_ratio', { summary_reference_coverage: block(1, 1) }, 'ok', 'ok');
check('above_one_near_one', { summary_reference_coverage: block(1, 1 + 5e-10) }, 'malformed', 'ok');
check('negative_outside_tolerance', { summary_reference_coverage: block(0, -1e-8) }, 'malformed', 'malformed');
check('above_one_outside_tolerance', { summary_reference_coverage: block(1, 1 + 1e-8) }, 'malformed', 'malformed');
check('valid_zero_denominator_null', { summary_reference_coverage: block(0, null, 0) }, 'ok', 'ok');
check('metadata_absent', {}, 'not_provided', 'not_provided');
check('invalid_inherited_metadata', { summary_reference_coverage: block(1, 1), summary_reference_coverage_inheritance: 'invalid_previous_metadata' }, 'not_provided', 'not_provided');
check('boolean_count', { summary_reference_coverage: { ...block(1, 1), input_customer_source_count: true } }, 'malformed', 'malformed');
const output = { kind: 'actual_fixed_WEB_module_protocol_boundary',
  head: 'eed222989abd74156fe3ccb01514470a9a2073bc', module_sha256: 'e8d6298dde15c677e652b6d6f8806e3c2398cffa17c8af1cf2baace7693ac2d2',
  node: process.version, new_model_calls: 0, actual_UI_HTTP_MCP_run_verified: false,
  cases: rows, strict_range_mismatch_count: rows.filter(row => row.required_state !== row.actual_state).length };
assert.equal(output.strict_range_mismatch_count, 2);
fs.writeFileSync('/out/probe.json', JSON.stringify(output, null, 2) + '\n');
process.stdout.write(JSON.stringify({ cases: rows.length, strict_range_mismatches: output.strict_range_mismatch_count, node: process.version }) + '\n');
