/** Python and Ajv consume identical synthetic shape fixtures; no collector is simulated here. */
import Ajv2020 from 'ajv/dist/2020';
import { describe, expect, it } from 'vitest';
import schema from '../../../packages/contracts/schemas/lgax.schema.json';
import fixture from '../../../packages/contracts/fixtures/review-trends.v1.json';

type Edit = { path: (string | number)[]; value?: unknown; remove?: boolean };
type Case = { id: string; definition: string; template: string; changes: Edit[] };
const templates = fixture.templates as Record<string, unknown>;

function fixtureValue(testCase: Case): unknown {
  const value = structuredClone(templates[testCase.template]);
  for (const edit of testCase.changes) {
    let target = value as Record<string | number, unknown>;
    for (const part of edit.path.slice(0, -1)) target = target[part] as Record<string | number, unknown>;
    const key = edit.path[edit.path.length - 1];
    if (edit.remove) delete target[key];
    else target[key] = structuredClone(edit.value);
  }
  return value;
}

// Check the schema's strict Gregorian patterns even when optional format
// validators are unavailable. Date.parse would normalize 2026-02-30.
const ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: false });
ajv.addSchema(schema, 'trend-shared');
function check(definition: string, value: unknown): boolean {
  const validator = ajv.compile({ $ref: `trend-shared#/$defs/${definition}` });
  return Boolean(validator(value));
}

describe('shared review trend contracts', () => {
  for (const testCase of fixture.cases) {
    it(testCase.id, () => {
      expect(check(testCase.definition, fixtureValue(testCase))).toBe(testCase.valid);
    });
  }

  for (const testCase of fixture.semantic_cases) {
    it(`shape alone cannot certify ${testCase.id}`, () => {
      expect(check(testCase.definition, fixtureValue(testCase))).toBe(testCase.schema_valid);
      expect(['INVALID_INPUT', 'FORBIDDEN', 'CONTRACT_MISMATCH']).toContain(testCase.semantic_error);
    });
  }

  it('uses a distinct success envelope and keeps unimplemented responses as errors', () => {
    const success = { ok: true, data: { aggregate: templates.aggregate, contract_version: '0.1.0' } };
    const failure = { ok: false, error: { code: 'NOT_IMPLEMENTED', message: 'Collector is not connected.', details: {} } };
    expect(check('WorkspaceReviewTrendResponse', success)).toBe(true);
    expect(check('ErrorResponse', failure)).toBe(true);
    expect(check('WorkspaceReviewTrendResponse', failure)).toBe(false);
  });

  it('enforces the notes limit without changing canonical Review or PlanningRequest', () => {
    const testCase = { template: 'aggregate', changes: [{ path: ['notes'], value: 'n'.repeat(801) }], id: 'notes-bound', definition: 'ReviewTrendAggregate' };
    expect(check(testCase.definition, fixtureValue(testCase))).toBe(false);
    expect(schema.$defs.Review.additionalProperties).toBe(false);
    expect(schema.$defs.Review.properties).not.toHaveProperty('published_at');
    expect(schema.$defs.PlanningRequest.properties).not.toHaveProperty('aggregate_id');
    expect(schema['x-contract-version']).toBe('0.1.0');
  });
});
