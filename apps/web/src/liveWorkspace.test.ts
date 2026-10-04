import { readFileSync, writeFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { ApiError } from './api';
import type { Product } from './domain';
import { browserFetch, documentVersionsFor, errorView, parseEvidenceSearch, projectName, runStatusView, sameProjectScope } from './liveWorkspace';
import { contractErrors, nextRequestRevision, requestWithCondition } from './planning';
import type { PlanningRequest, RunSnapshot } from './planning';
import { WorkspaceClient } from './workspace';

const dataset = JSON.parse(readFileSync(new URL('../../../data/demo/dataset.json', import.meta.url), 'utf8'));
const products = dataset.products as Product[];
const request: PlanningRequest = {
  product_group: 'fridge', target_customer: '1인 가구', use_situation: '음료를 쏟은 뒤 선반 청소',
  improvement_task: '선반 청소 부담 감소', exclusions: [], model_ids: ['FRIDGE-A'], dataset_version: '0.1.0',
};

describe('workspace error presentation', () => {
  it('gives each server failure its own title and next action', () => {
    const codes = ['UNAUTHORIZED', 'FORBIDDEN', 'NOT_FOUND', 'DATASET_MISMATCH', 'INVALID_ARGUMENT', 'CONNECTION_FAILED', 'CONTRACT_MISMATCH', 'NOT_IMPLEMENTED'];
    const views = codes.map(code => errorView(new ApiError(code, 'server message')));
    expect(new Set(views.map(view => view.title)).size).toBe(codes.length);
    expect(views.map(view => view.code)).toEqual(codes);
    expect(errorView(new ApiError('NOT_IMPLEMENTED', 'x')).tone).toBe('notice');
    expect(errorView(new ApiError('FORBIDDEN', 'x')).tone).toBe('error');
  });
  it('has a dedicated message for every error code in the shared contract', () => {
    const schema = JSON.parse(readFileSync(new URL('../../../packages/contracts/schemas/lgax.schema.json', import.meta.url), 'utf8'));
    const codes = schema.$defs.Error.properties.code.enum as string[];
    const titles = codes.map(code => errorView(new ApiError(code, 'x')).title);
    expect(titles).not.toContain('요청을 처리하지 못했습니다');
    expect(errorView(new ApiError('INSUFFICIENT_EVIDENCE', 'x')).tone).toBe('notice');
  });
  it('keeps unknown failures visible with their message instead of hiding them', () => {
    expect(errorView(new ApiError('SOMETHING_NEW', '새 오류'))).toMatchObject({ code: 'SOMETHING_NEW', action: '새 오류', tone: 'error' });
    expect(errorView('broken').code).toBe('UNKNOWN_ERROR');
  });
});

describe('browser transport', () => {
  it('does not invoke fetch as a method of the client (browsers throw Illegal invocation)', async () => {
    const original = globalThis.fetch;
    const seen: unknown[] = [];
    // Simulate the browser rule: window.fetch must be called with the global object (or undefined) as this.
    globalThis.fetch = function (this: unknown) {
      seen.push(this);
      if (this !== undefined && this !== globalThis) throw new TypeError('Illegal invocation');
      return Promise.resolve(new Response(JSON.stringify({ ok: true, data: { projects: [], contract_version: '0.1.0' } })));
    } as typeof fetch;
    try {
      await expect(new WorkspaceClient('', () => 't'.repeat(48), browserFetch).listProjects()).resolves.toEqual({ projects: [], contract_version: '0.1.0' });
      await expect(new WorkspaceClient('', () => 't'.repeat(48)).listProjects()).resolves.toEqual({ projects: [], contract_version: '0.1.0' });
    } finally { globalThis.fetch = original; }
    expect(seen).toHaveLength(2);
  });
});

describe('source scope and run status', () => {
  it('takes document versions from the selected products and rejects unknown models', () => {
    expect(documentVersionsFor(products, ['FRIDGE-A', 'FRIDGE-B'])).toEqual({ 'FRIDGE-A': '1.0', 'FRIDGE-B': '1.0' });
    expect(() => documentVersionsFor(products, ['FRIDGE-Z'])).toThrow(/FRIDGE-Z/);
  });
  it('names projects from the request and fits the server name limit', () => {
    const name = projectName({ ...request, improvement_task: '가'.repeat(100) });
    expect(name.startsWith('FRIDGE-A · ')).toBe(true);
    expect(name.length).toBeLessThanOrEqual(120);
    expect(contractErrors('WorkspaceProjectCreateRequest', { name, request, document_versions: { 'FRIDGE-A': '1.0' } })).toEqual([]);
  });
  it('labels not_implemented runs as saved requests, not analysis results', () => {
    expect(runStatusView('not_implemented')).toMatchObject({ label: '요청만 저장됨', tone: 'notice' });
    expect(runStatusView('held').label).toBe('보류');
    expect(runStatusView('failed').tone).toBe('error');
    expect(runStatusView('completed').tone).toBe('done');
  });
  it('reads the contract search envelope including an empty result', () => {
    const empty = parseEvidenceSearch({ project_id: 'p', dataset_sha256: 'a'.repeat(64), contract_version: '0.1.0',
      search: { ok: true, data: { query: '없는말', model_id: 'FRIDGE-A', document_version: '1.0', items: [], total: 0, contract_version: '0.1.0', search_method: 'literal_token_count' } } });
    expect(empty).toMatchObject({ total: 0, items: [], documentVersion: '1.0', method: 'literal_token_count' });
  });
  it('continues a project only for the same product group and model set', () => {
    const multi = { ...request, model_ids: ['FRIDGE-A', 'FRIDGE-B'] };
    expect(sameProjectScope(multi, { ...multi, model_ids: ['FRIDGE-B', 'FRIDGE-A'], use_situation: '다른 상황' })).toBe(true);
    expect(sameProjectScope(multi, request)).toBe(false);
    expect(sameProjectScope(request, { ...request, product_group: 'dishwasher', model_ids: ['DISHWASHER-A'] })).toBe(false);
  });
  it('builds condition requests that stay inside the project scope', () => {
    const next = requestWithCondition(request, '1인 가구 소형 모델만');
    expect(next.model_ids).toEqual(request.model_ids);
    expect(next.product_group).toBe(request.product_group);
    expect(contractErrors('PlanningRequest', next)).toEqual([]);
  });
});

// Opt-in: LGAX_WORKSPACE_URL=http://127.0.0.1:18869 plus editor/viewer credential files from scripts/init_workspace.py.
const live = process.env.LGAX_WORKSPACE_URL && process.env.LGAX_WORKSPACE_CREDENTIAL_FILE && process.env.LGAX_WORKSPACE_VIEWER_FILE;
describe.skipIf(!live)('actual workspace server flow used by the web live mode (explicit opt-in)', () => {
  const token = (path: string) => (JSON.parse(readFileSync(path, 'utf-8')) as { token: string }).token;
  const url = process.env.LGAX_WORKSPACE_URL!;
  it('saves a request, links a condition run, searches the fixed scope and reports each failure code', async () => {
    const editor = new WorkspaceClient(url, () => token(process.env.LGAX_WORKSPACE_CREDENTIAL_FILE!));
    const viewer = new WorkspaceClient(url, () => token(process.env.LGAX_WORKSPACE_VIEWER_FILE!));
    const wrong = new WorkspaceClient(url, () => 'x'.repeat(48));
    const versions = documentVersionsFor(products, request.model_ids);

    const project = await editor.createProject(projectName(request), request as unknown as Record<string, unknown>, versions);
    const first = await editor.createRun(project.project.id, request as unknown as Record<string, unknown>) as unknown as RunSnapshot;
    const conditioned = requestWithCondition(first.request, '1인 가구 소형 모델만');
    const second = await editor.createRun(project.project.id, conditioned as unknown as Record<string, unknown>, first.run.id) as unknown as RunSnapshot;
    expect(first.run.status).toBe('not_implemented');
    expect(first.request_revision).toBe(0);
    expect(second.previous_run_id).toBe(first.run.id);
    expect(second.request_revision).toBe(nextRequestRevision(request, first, conditioned));
    expect(second.request_revision).toBe(1);
    expect(second.run.concepts).toEqual([]);
    expect(second.output).toBeNull();
    expect((await editor.listRuns(project.project.id)).runs.map(item => item.run.id)).toEqual([first.run.id, second.run.id]);

    const hit = parseEvidenceSearch(await editor.search(project.project.id, '청소', 'FRIDGE-A'));
    const miss = parseEvidenceSearch(await editor.search(project.project.id, '존재하지않는검색어', 'FRIDGE-A'));
    expect(hit.total).toBeGreaterThan(0);
    expect(hit.items.every(item => item.model_id === 'FRIDGE-A' && item.document_version === '1.0')).toBe(true);
    expect(miss).toMatchObject({ total: 0, items: [] });

    const failures: Record<string, string> = {};
    const capture = async (name: string, work: () => Promise<unknown>) => {
      try { await work(); failures[name] = 'NO_ERROR'; } catch (error) { failures[name] = error instanceof ApiError ? error.code : String(error); }
    };
    await capture('wrong_token', () => wrong.listProjects());
    await capture('viewer_write', () => viewer.createRun(project.project.id, request as unknown as Record<string, unknown>));
    await capture('missing_run', () => editor.getRun('run-does-not-exist'));
    await capture('scope_change', () => editor.createRun(project.project.id, { ...request, model_ids: ['FRIDGE-B'] } as unknown as Record<string, unknown>));
    await capture('model_outside_project', () => editor.search(project.project.id, '청소', 'FRIDGE-B'));
    await capture('unreachable', () => new WorkspaceClient('http://127.0.0.1:1', () => 'x'.repeat(48)).listProjects());
    expect(failures).toEqual({
      wrong_token: 'UNAUTHORIZED', viewer_write: 'FORBIDDEN', missing_run: 'NOT_FOUND',
      scope_change: 'INVALID_ARGUMENT', model_outside_project: 'INVALID_ARGUMENT', unreachable: 'CONNECTION_FAILED',
    });
    expect(Object.values(failures).map(code => errorView(new ApiError(code, '')).title)).not.toContain('요청을 처리하지 못했습니다');

    if (process.env.LGAX_WORKSPACE_PROOF_FILE) {
      writeFileSync(process.env.LGAX_WORKSPACE_PROOF_FILE, JSON.stringify({
        project_id: project.project.id, document_versions: project.document_versions, dataset_sha256: project.dataset_sha256,
        runs: [first, second].map(item => ({ id: item.run.id, previous_run_id: item.previous_run_id, request_revision: item.request_revision, status: item.run.status, client: item.client, actor_id: item.actor_id, exclusions: item.request.exclusions, unresolved: item.run.unresolved })),
        search: { hit: { query: hit.query, total: hit.total, ids: hit.items.map(item => item.id), document_version: hit.documentVersion, method: hit.method }, miss: { query: miss.query, total: miss.total } },
        failures,
      }, null, 2) + '\n');
    }
  });
});
