import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { requireLiveModelProof } from '../e2e/live-model-proof';

// Replay only: this validates the proof gate against a saved real run, without a new model invocation.
const saved = JSON.parse(readFileSync(resolve(process.cwd(), '../..', 'evals/pm-review/20261005-round2/api-live/workspace-live.json'), 'utf8'));
const execution = saved.first.output.planning_execution;
const modelId: string = execution.model_calls[0].model_id;
const digest: string = execution.model_calls[0].model_digest;

describe('strict live-model E2E proof', () => {
  it('accepts recorded generation with the exact expected pin, without asserting quality', () => {
    expect(execution.status).toBe('held');
    expect(requireLiveModelProof(execution, modelId, digest)).toBe(execution.model_calls.length);
  });

  it('rejects a run that failed before a generation', () => {
    expect(() => requireLiveModelProof({ execution_kind: 'live_model', model_calls: [] }, modelId, digest)).toThrow('No recorded model generation');
  });

  it('rejects fixture records even if they copy model call metadata', () => {
    expect(() => requireLiveModelProof({ ...execution, execution_kind: 'fixture' }, modelId, digest)).toThrow('Fixture records');
  });

  it('requires an explicit expected model and digest', () => {
    expect(() => requireLiveModelProof(execution, undefined, digest)).toThrow('expected model ID');
    expect(() => requireLiveModelProof(execution, modelId, undefined)).toThrow('expected digest');
  });

  it.each(['model', 'digest', 'metadata', 'prompt', 'output', 'validation'] as const)('rejects inconsistent or absent %s evidence', kind => {
    const changed = structuredClone(execution);
    const call = changed.model_calls[0];
    if (kind === 'model') call.model_id = 'OTHER-MODEL';
    if (kind === 'digest') call.model_digest = '0'.repeat(64);
    if (kind === 'metadata') call.metadata.revision = '0'.repeat(64);
    if (kind === 'prompt') call.formatted_prompt += ' changed';
    if (kind === 'output') call.raw_response = '';
    if (kind === 'validation') call.generated.metadata.locally_validated = false;
    expect(() => requireLiveModelProof(changed, modelId, digest)).toThrow();
  });
});
