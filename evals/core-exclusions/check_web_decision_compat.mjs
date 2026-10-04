/** Replay a pinned PR61 consumer over immutable authored fixtures; no browser or model calls. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createServer } from '../../apps/web/node_modules/vite/dist/node/index.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const folder = path.join(root, 'harness/phase2/runs/core002-decision-compat-20261005');
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--consumer-commit' || !/^[a-f0-9]{40}$/.test(args[1]))) {
  throw new Error('Usage: node check_web_decision_compat.mjs [--consumer-commit FULL_COMMIT_SHA]');
}
const consumerHead = args[1] ?? '963d3b8c87ac62bea71880279ad116864075b6a7';
const readPinned = relative => execFileSync('git', ['show', `${consumerHead}:${relative}`], { cwd: root, encoding: 'utf8' });
const source = args.length ? readPinned('apps/web/src/judgement.ts')
  : await fs.readFile(path.join(folder, 'pr61-judgement-source.ts'), 'utf8');
const originalPath = path.join(root, 'apps/web/src/judgement.ts').replaceAll('\\', '/');
const viewsPath = path.join(root, 'apps/web/src/JudgementViews.tsx').replaceAll('\\', '/');
const viewsSource = args.length ? readPinned('apps/web/src/JudgementViews.tsx') : null;
const server = await createServer({
  root: path.join(root, 'apps/web'), configFile: false, appType: 'custom',
  esbuild: { jsx: 'automatic' },
  server: { middlewareMode: true, hmr: false },
  optimizeDeps: { noDiscovery: true, include: [] },
  plugins: [{ name: 'read-fixed-pr61-consumer', enforce: 'pre',
    load(id) {
      const normalized = id.replaceAll('\\', '/');
      if (normalized === originalPath) return source;
      if (normalized === viewsPath && viewsSource !== null) return viewsSource;
    } }],
});
try {
  const consumer = await server.ssrLoadModule('/src/judgement.ts');
  const old = JSON.parse(await fs.readFile(path.join(root,
    'harness/phase2/runs/core002-semantic-draft-20261005/fixture-flow-traces.json'), 'utf8'));
  const previous = ['uncertain', 'persistent_violation'].map(name => ({
    name, errors: consumer.judgementDecisionErrors(old.flows[name].decision),
  }));
  if (!args.length && previous.some(row => !row.errors.length)) throw new Error('Original compatibility failure was not reproduced');
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
  const rendered = [];
  if (viewsSource !== null) {
    const { createElement } = await import('../../apps/web/node_modules/react/index.js');
    const { renderToStaticMarkup } = await import('../../apps/web/node_modules/react-dom/server.node.js');
    const { ExecutionPanel } = await server.ssrLoadModule('/src/JudgementViews.tsx');
    for (const [name, flow] of Object.entries(current.flows)) {
      const html = renderToStaticMarkup(createElement(ExecutionPanel, { snapshot: flow.snapshot }));
      const execution = flow.snapshot.output.planning_execution;
      const semantic = Boolean(execution.semantic_reviews?.length);
      const rejected = Boolean(execution.rejected_output?.concepts?.length);
      if ((semantic && !html.includes('aria-label="의미 검토 기록"'))
        || (rejected && !html.includes('aria-label="거절된 후보"'))
        || !html.includes('aria-label="판단 계약 검사 결과"')) throw new Error(`Missing core record panel: ${name}`);
      rendered.push({ name, semantic_review_panel: semantic, rejected_candidates_panel: rejected, render_ok: true });
    }
  }
  console.log(JSON.stringify({ execution_kind: 'fixture', new_live_model_calls: 0,
    consumer_pr: 61, consumer_head: consumerHead,
    consumer_source_sha256: createHash('sha256').update(source).digest('hex'),
    view_source_sha256: viewsSource === null ? null : createHash('sha256').update(viewsSource).digest('hex'),
    original_failures: previous, current: after, rendered,
    limitation: 'Pinned source functions, persisted fixtures and optional static HTML rendering; no browser or live-model execution.' }));
} finally {
  await server.close();
}
