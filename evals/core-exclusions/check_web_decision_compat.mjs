/** Replay the fixed PR61 consumer over immutable authored fixtures; no browser or model calls. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from '../../apps/web/node_modules/vite/dist/node/index.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const folder = path.join(root, 'harness/phase2/runs/core002-decision-compat-20261005');
const source = await fs.readFile(path.join(folder, 'pr61-judgement-source.ts'), 'utf8');
const originalPath = path.join(root, 'apps/web/src/judgement.ts').replaceAll('\\', '/');
const server = await createServer({
  root: path.join(root, 'apps/web'), configFile: false, appType: 'custom',
  server: { middlewareMode: true, hmr: false },
  optimizeDeps: { noDiscovery: true, include: [] },
  plugins: [{ name: 'read-fixed-pr61-consumer', enforce: 'pre',
    load(id) { if (id.replaceAll('\\', '/') === originalPath) return source; } }],
});
try {
  const consumer = await server.ssrLoadModule('/src/judgement.ts');
  const old = JSON.parse(await fs.readFile(path.join(root,
    'harness/phase2/runs/core002-semantic-draft-20261005/fixture-flow-traces.json'), 'utf8'));
  const previous = ['uncertain', 'persistent_violation'].map(name => ({
    name, errors: consumer.judgementDecisionErrors(old.flows[name].decision),
  }));
  if (previous.some(row => !row.errors.length)) throw new Error('Original compatibility failure was not reproduced');
  const current = JSON.parse(await fs.readFile(path.join(folder, 'current-fixture-snapshots.json'), 'utf8'));
  const after = Object.entries(current.flows).map(([name, flow]) => {
    const view = consumer.planningExecutionView(flow.snapshot);
    return { name, decision_errors: consumer.judgementDecisionErrors(flow.decision),
      view_kind: view.kind, view_problems: view.kind === 'ok' ? view.problems : view.errors,
      status: flow.snapshot.run.status, revision_count: flow.decision.revision_count,
      model_calls: view.kind === 'ok' ? view.model_calls : null };
  });
  if (after.some(row => row.decision_errors.length || row.view_kind !== 'ok' || row.view_problems.length)) {
    throw new Error(JSON.stringify(after));
  }
  console.log(JSON.stringify({ execution_kind: 'fixture', new_live_model_calls: 0,
    consumer_pr: 61, consumer_head: '963d3b8c87ac62bea71880279ad116864075b6a7',
    original_failures: previous, current: after,
    limitation: 'Actual fixed-source functions and fixture persistence, no browser or live-model execution.' }));
} finally {
  await server.close();
}
