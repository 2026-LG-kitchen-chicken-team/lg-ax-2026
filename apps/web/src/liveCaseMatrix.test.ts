// Opt-in (same variables as liveWorkspace.test.ts): LGAX_WORKSPACE_URL plus LGAX_WORKSPACE_CREDENTIAL_FILE/LGAX_WORKSPACE_VIEWER_FILE.
// Sends the request of each of the six judgment cases to the actual workspace server, then the rerun request the
// candidate controls would build from that case's candidates. The server only stores requests (not_implemented):
// this checks the API input path, not planning-core judgment. Candidate labels come from the contract fixture.
import { readFileSync, writeFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { CASE_MATRIX } from './fixtures/caseMatrix.fixture';
import { FIXTURE_DATASET_SHA256 } from './fixtures/planning.fixture';
import { documentVersionsFor, projectName } from './liveWorkspace';
import type { Product } from './domain';
import { buildRerunRequest, canonical, contractErrors, splitConditions } from './planning';
import type { RunSnapshot } from './planning';
import { WorkspaceClient } from './workspace';

const live = process.env.LGAX_WORKSPACE_URL && process.env.LGAX_WORKSPACE_CREDENTIAL_FILE && process.env.LGAX_WORKSPACE_VIEWER_FILE;
const products = (JSON.parse(readFileSync(new URL('../../../data/demo/dataset.json', import.meta.url), 'utf8')) as { products: Product[] }).products;

describe.skipIf(!live)('six judgment case requests on the actual workspace server (explicit opt-in)', () => {
  const token = (path: string) => (JSON.parse(readFileSync(path, 'utf-8')) as { token: string }).token;
  const editor = () => new WorkspaceClient(process.env.LGAX_WORKSPACE_URL!, () => token(process.env.LGAX_WORKSPACE_CREDENTIAL_FILE!));

  it('stores each case request verbatim, links the candidate/condition rerun and leaves the first run unchanged', async () => {
    const client = editor();
    const proof: Record<string, unknown>[] = [];
    for (const { kind, snapshot } of CASE_MATRIX) {
      const request = snapshot.request;
      const versions = documentVersionsFor(products, request.model_ids);
      expect(versions).toEqual(snapshot.document_versions);
      const project = await client.createProject(projectName(request), request as unknown as Record<string, unknown>, versions);
      const first = await client.createRun(project.project.id, request as unknown as Record<string, unknown>, null, snapshot.unconfirmed) as unknown as RunSnapshot;
      expect(contractErrors('WorkspaceRunSnapshot', first)).toEqual([]);
      expect(first).toMatchObject({ request, previous_run_id: null, request_revision: 0, output: null, unconfirmed: snapshot.unconfirmed, document_versions: snapshot.document_versions, dataset_sha256: FIXTURE_DATASET_SHA256 });
      expect(first.run.status).toBe('not_implemented');

      const [a, b] = snapshot.run.concepts;
      const choices = a ? { [a.id]: 'exclude' as const, ...(b ? { [b.id]: 'focus' as const } : {}) } : {};
      const next = buildRerunRequest(request, snapshot.run.concepts, choices, [...splitConditions(request, snapshot.run.concepts).conditions, '1인 가구 소형 모델만 검토']);
      const second = await client.createRun(project.project.id, next as unknown as Record<string, unknown>, first.run.id) as unknown as RunSnapshot;
      expect(second).toMatchObject({ request: next, previous_run_id: first.run.id, request_revision: 1, output: null });
      expect(second.run.status).toBe('not_implemented');
      expect(canonical(await client.getRun(first.run.id))).toBe(canonical(first));

      proof.push({
        kind, project_id: project.project.id, document_versions: project.document_versions, dataset_sha256: project.dataset_sha256,
        runs: [first, second].map(item => ({ id: item.run.id, previous_run_id: item.previous_run_id, request_revision: item.request_revision, status: item.run.status, improvement_task: item.request.improvement_task, exclusions: item.request.exclusions, unconfirmed: item.unconfirmed })),
        first_run_unchanged: true,
      });
    }
    if (process.env.LGAX_CASE_PROOF_FILE) writeFileSync(process.env.LGAX_CASE_PROOF_FILE, `${JSON.stringify({ note: 'Requests stored by the workspace server; status not_implemented. Not planning-core output.', cases: proof }, null, 2)}\n`);
  });
});
