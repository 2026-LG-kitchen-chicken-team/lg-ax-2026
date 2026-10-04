// Explicit, private opt-in: invokes the real planning backend, not a mocked fetch.
import { readFileSync, writeFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { WorkspaceClient } from './workspace';

const enabled = process.env.LGAX_LIVE_PLANNING === 'true';
it.skipIf(!enabled)('stores real model results and changed requests without rewriting the first run', async () => {
  const credentialFile = process.env.LGAX_WORKSPACE_CREDENTIAL_FILE!;
  const credential = () => JSON.parse(readFileSync(credentialFile, 'utf8')).token as string;
  const client = new WorkspaceClient(process.env.LGAX_WORKSPACE_URL!, credential);
  const fixture = (name: string) => JSON.parse(readFileSync(new URL(`../../../evals/core-planning/examples/${name}`, import.meta.url), 'utf8'));
  const original = fixture('fridge.input.json');
  const changed = fixture('fridge-changed.input.json');
  const project = await client.createProject('PM real planning integration', original.request,
    { [original.product.model_id]: original.product.document_version });
  const first = await client.createRun(project.project.id, original.request);
  const proof: Record<string, unknown> = { execution_kind: 'live_model', client: 'web_typescript_http',
    project, first, first_run_unchanged: null,
    limitations: ['Synthetic development example; no browser screen or external ChatGPT/Claude workspace proof.'] };
  const save = () => { if (process.env.LGAX_PLANNING_PROOF_FILE) writeFileSync(process.env.LGAX_PLANNING_PROOF_FILE,
    `${JSON.stringify(proof, null, 2)}\n`); };
  save();
  expect(first.run.status).toBe('completed');
  expect(first.run.concepts.length).toBeGreaterThan(0);
  expect(first.output?.needs).toBeInstanceOf(Array);
  expect(first.output?.gaps).toBeInstanceOf(Array);
  const execution = first.output?.planning_execution as { execution_kind: string; model_calls: unknown[]; decision: { valid: boolean } };
  expect(execution.execution_kind).toBe('live_model');
  expect(execution.model_calls.length).toBeGreaterThanOrEqual(3);
  expect(execution.decision.valid).toBe(true);
  const second = await client.createRun(project.project.id, changed.request, first.run.id);
  proof.second = second;
  save();
  expect(second.request).toEqual(changed.request);
  expect(second.previous_run_id).toBe(first.run.id);
  expect(second.request_revision).toBe(1);
  expect(second.run.status).toBe('completed');
  expect(await client.getRun(first.run.id)).toEqual(first);
  expect((await client.listRuns(project.project.id)).runs).toEqual([first, second]);
  proof.first_run_unchanged = true;
  save();
}, 360_000);
