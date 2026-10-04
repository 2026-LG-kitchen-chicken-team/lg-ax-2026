import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

/** Strict opt-in evidence checks; execution success never implies semantic quality. */
export function requireLiveModelProof(value: unknown, modelId: string | undefined, digest: string | undefined): number {
  assert.ok(modelId?.trim(), 'Strict live-model verification requires an explicit expected model ID');
  assert.match(digest ?? '', /^[0-9a-f]{64}$/, 'Strict live-model verification requires an explicit expected digest');
  assert.ok(value && typeof value === 'object', 'Planning execution record missing');
  const record = value as Record<string, unknown>;
  assert.equal(record.execution_kind, 'live_model', 'Fixture records cannot satisfy live-model verification');
  assert.ok(Array.isArray(record.model_calls) && record.model_calls.length > 0, 'No recorded model generation');
  for (const value of record.model_calls) {
    assert.ok(value && typeof value === 'object', 'Invalid model-call record');
    const call = value as Record<string, unknown>;
    assert.equal(call.execution_kind, 'live_model', 'Call must be a live-model execution');
    assert.equal(call.model_id, modelId, 'Unexpected generation model');
    assert.equal(call.model_digest, digest, 'Unexpected generation digest');
    const metadata = call.metadata as Record<string, unknown> | undefined;
    assert.ok(metadata && typeof metadata === 'object', 'Generation metadata missing');
    assert.equal(metadata.model_id, modelId, 'Metadata model does not match the expected model');
    assert.equal(metadata.revision, digest, 'Metadata pin does not match the expected digest');
    assert.equal(metadata.pin_verification, 'before_and_after_generation', 'Generation pin verification missing');
    assert.ok(typeof metadata.elapsed_ms === 'number' && Number.isFinite(metadata.elapsed_ms) && metadata.elapsed_ms >= 0,
      'Measured generation duration missing');
    assert.ok(typeof call.formatted_prompt === 'string' && call.formatted_prompt.trim(), 'Generated prompt missing');
    assert.equal(createHash('sha256').update(call.formatted_prompt).digest('hex'), call.formatted_prompt_sha256,
      'Recorded generation prompt hash does not match');
    assert.ok(typeof call.raw_response === 'string' && call.raw_response.trim(), 'Recorded generation output missing');
    const generated = call.generated as { data?: unknown; metadata?: Record<string, unknown> } | undefined;
    assert.ok(generated?.data && generated.metadata?.locally_validated === true, 'Validated generation result missing');
    assert.equal(generated.metadata.model_id, modelId, 'Validated result model does not match');
    assert.equal(generated.metadata.revision, digest, 'Validated result pin does not match');
  }
  return record.model_calls.length;
}
