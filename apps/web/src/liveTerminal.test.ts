// Explicit opt-in: real private API and model; records held/failed without treating them as quality success.
import { readFileSync, writeFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { WorkspaceClient } from './workspace';
import { planningExecutionView } from './judgement';
import type { RunSnapshot } from './planning';

it.skipIf(process.env.LGAX_LIVE_TERMINAL !== 'true')('keeps real terminal runs, raw trace and changed request history', async () => {
 const token = () => JSON.parse(readFileSync(process.env.LGAX_WORKSPACE_CREDENTIAL_FILE!, 'utf8')).token as string;
 const client = new WorkspaceClient(process.env.LGAX_WORKSPACE_URL!, token);
 const fixture = (name: string) => JSON.parse(readFileSync(new URL(`../../../evals/core-planning/examples/${name}`, import.meta.url), 'utf8'));
 const original = fixture('fridge.input.json'), changed = fixture('fridge-changed.input.json');
 const project = await client.createProject('PM real terminal integration', original.request, { [original.product.model_id]: original.product.document_version });
 const first = await client.createRun(project.project.id, original.request);
 const second = await client.createRun(project.project.id, changed.request, first.run.id);
 const snapshots = [first, second];
 for (const run of snapshots) {
  expect(['completed','held','failed']).toContain(run.run.status);
  // WorkspaceClient has already validated the shared run envelope; its public type is intentionally broad.
  const record = planningExecutionView(run as unknown as RunSnapshot);
  expect(record.kind).toBe('ok');
  if (record.kind === 'ok') {
   expect(record.execution.execution_kind).toBe('live_model');
   expect(record.execution.model_calls.length).toBeGreaterThan(0);
   expect(record.execution.input!.revision_count).toBeLessThanOrEqual(2);
  }
 }
 expect(second.previous_run_id).toBe(first.run.id);
 expect(second.request_revision).toBe(1);
 expect(await client.getRun(first.run.id)).toEqual(first);
 expect((await client.listRuns(project.project.id)).runs).toEqual(snapshots);
 const proof = { execution_kind:'live_model', client:'real_typescript_http', project, first, second, first_run_unchanged:true,
  agent_quality_passed: null, limitation:'Transport, storage and UI contract verification; successful quality is not asserted.' };
 writeFileSync(process.env.LGAX_TERMINAL_PROOF_FILE!, JSON.stringify(proof,null,2)+'\n');
}, 480_000);
