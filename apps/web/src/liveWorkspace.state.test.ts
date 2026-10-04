// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './api';
import { FIXTURE_BOOTSTRAP, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import { ServerEvidenceSearch } from './PlanningViews';
import { useLiveWorkspace } from './liveWorkspace';
import type { EvidenceSearch, LiveWorkspace } from './liveWorkspace';
import type { RunSnapshot } from './planning';
import { WorkspaceClient } from './workspace';
import type { WorkspaceProject, WorkspaceRun } from './workspace';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function project(id: string, owner = 'planner'): WorkspaceProject {
  return {
    project: { id, name: id, request: FIXTURE_ORIGINAL_REQUEST as unknown as Record<string, unknown>, status: 'active', dataset_version: '0.1.0' },
    owner_id: owner, document_versions: { 'FRIDGE-A': '1.0', 'FRIDGE-B': '1.0' },
    dataset_sha256: 'a'.repeat(64), created_at: '2026-10-04T09:00:00Z',
  };
}

function run(projectId: string, id = `run-${projectId}`): RunSnapshot & WorkspaceRun {
  const source = FIXTURE_RUNS[0];
  return { ...source, request: { ...source.request }, output: source.output ? { ...source.output } : null,
    run: { ...source.run, id, project_id: projectId } };
}

let container: HTMLDivElement;
let root: Root;
let live: LiveWorkspace;
const a = project('project-a');
const b = project('project-b');

function Probe() {
  live = useLiveWorkspace();
  return createElement('output', null, JSON.stringify({ connection: live.connection, project: live.project?.project.id,
    runs: live.runs.map(item => item.run.id), busy: live.busy, error: live.error?.code }));
}

async function connect() {
  await act(async () => { await live.connect('editor-token'.repeat(4)); });
  expect(live.project?.project.id).toBe(a.project.id);
}

beforeEach(async () => {
  (globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  vi.spyOn(WorkspaceClient.prototype, 'listProjects').mockResolvedValue({ projects: [a], contract_version: '0.1.0' });
  vi.spyOn(WorkspaceClient.prototype, 'getProject').mockImplementation(async id => id === a.project.id ? a : b);
  vi.spyOn(WorkspaceClient.prototype, 'listRuns').mockImplementation(async id => ({ runs: [run(id)], contract_version: '0.1.0' }));
  await act(async () => { root.render(createElement(Probe)); });
});

afterEach(async () => {
  await act(async () => { root.unmount(); });
  container.remove();
  vi.restoreAllMocks();
});

describe('actual React workspace state boundaries', () => {
  it('does not pair the new project with old runs when its run lookup fails', async () => {
    await connect();
    const lookup = deferred<{ runs: WorkspaceRun[]; contract_version: string }>();
    vi.mocked(WorkspaceClient.prototype.listRuns).mockImplementationOnce(() => lookup.promise);
    let selection!: Promise<void>;
    await act(async () => { selection = live.selectProject(b.project.id); });
    expect(live.project).toBeNull();
    expect(live.runs).toEqual([]);
    await act(async () => { lookup.reject(new ApiError('CONNECTION_FAILED', 'offline')); await selection; });
    expect(live.project).toBeNull();
    expect(live.runs).toEqual([]);
    expect(live.error?.code).toBe('CONNECTION_FAILED');
    expect(live.busy).toBe(false);
  });

  it('ignores a project lookup that completes after disconnect', async () => {
    await connect();
    const lookup = deferred<{ runs: WorkspaceRun[]; contract_version: string }>();
    vi.mocked(WorkspaceClient.prototype.listRuns).mockImplementationOnce(() => lookup.promise);
    let selection!: Promise<void>;
    await act(async () => { selection = live.selectProject(b.project.id); });
    await act(async () => { live.disconnect(); });
    await act(async () => { lookup.resolve({ runs: [run(b.project.id)], contract_version: '0.1.0' }); await selection; });
    expect(live.connection).toBe('disconnected');
    expect(live.project).toBeNull();
    expect(live.runs).toEqual([]);
    expect(live.projects).toEqual([]);
    expect(live.busy).toBe(false);
  });

  it('keeps the newer login when an older connection responds later', async () => {
    const old = deferred<{ projects: WorkspaceProject[]; contract_version: string }>();
    vi.mocked(WorkspaceClient.prototype.listProjects).mockImplementationOnce(() => old.promise)
      .mockResolvedValueOnce({ projects: [b], contract_version: '0.1.0' });
    let first!: Promise<void>;
    await act(async () => { first = live.connect('first-token'.repeat(4)); });
    await act(async () => { await live.connect('second-token'.repeat(4)); });
    await act(async () => { old.resolve({ projects: [a], contract_version: '0.1.0' }); await first; });
    expect(live.project?.project.id).toBe(b.project.id);
    expect(live.runs.map(item => item.run.project_id)).toEqual([b.project.id]);
    expect(live.connection).toBe('connected');
  });

  it('clears protected cached records after authorization expires', async () => {
    await connect();
    vi.spyOn(WorkspaceClient.prototype, 'search').mockRejectedValueOnce(new ApiError('UNAUTHORIZED', 'expired'));
    await act(async () => { await live.search('청소', 'FRIDGE-A'); });
    expect(live.connection).toBe('error');
    expect(live.project).toBeNull();
    expect(live.projects).toEqual([]);
    expect(live.runs).toEqual([]);
    expect(live.error?.code).toBe('UNAUTHORIZED');
    expect(live.busy).toBe(false);
  });

  it('does not retain the previous account records after a failed reconnect', async () => {
    await connect();
    vi.mocked(WorkspaceClient.prototype.listProjects).mockRejectedValueOnce(new ApiError('UNAUTHORIZED', 'wrong account'));
    await act(async () => { await live.connect('wrong-token'.repeat(4)); });
    expect(live.connection).toBe('error');
    expect(live.project).toBeNull();
    expect(live.projects).toEqual([]);
    expect(live.runs).toEqual([]);
    expect(live.error?.code).toBe('UNAUTHORIZED');
  });

  it('does not let a late authorization failure clear the newer login', async () => {
    await connect();
    const response = deferred<Record<string, unknown>>();
    vi.spyOn(WorkspaceClient.prototype, 'search').mockImplementationOnce(() => response.promise);
    let search!: Promise<EvidenceSearch | null>;
    await act(async () => { search = live.search('청소', 'FRIDGE-A'); });
    vi.mocked(WorkspaceClient.prototype.listProjects).mockResolvedValueOnce({ projects: [b], contract_version: '0.1.0' });
    await act(async () => { await live.connect('new-token'.repeat(5)); });
    await act(async () => { response.reject(new ApiError('UNAUTHORIZED', 'expired old token')); await search; });
    expect(live.connection).toBe('connected');
    expect(live.project?.project.id).toBe(b.project.id);
    expect(live.error).toBeNull();
  });

  it('keeps busy until all current-scope operations finish', async () => {
    await connect();
    const first = deferred<Record<string, unknown>>();
    const second = deferred<Record<string, unknown>>();
    vi.spyOn(WorkspaceClient.prototype, 'search').mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);
    let one!: Promise<EvidenceSearch | null>;
    let two!: Promise<EvidenceSearch | null>;
    await act(async () => { one = live.search('청소', 'FRIDGE-A'); two = live.search('다른검색', 'FRIDGE-A'); });
    expect(live.busy).toBe(true);
    await act(async () => { second.resolve(searchPayload(a)); await two; });
    expect(live.busy).toBe(true);
    await act(async () => { first.resolve(searchPayload(a)); await one; });
    expect(live.busy).toBe(false);
  });

  it('rejects a response that cites another fixed document or project scope', async () => {
    await connect();
    vi.spyOn(WorkspaceClient.prototype, 'search').mockResolvedValueOnce(searchPayload(b));
    let result!: EvidenceSearch | null;
    await act(async () => { result = await live.search('청소', 'FRIDGE-A'); });
    expect(result).toBeNull();
    expect(live.error?.code).toBe('CONTRACT_MISMATCH');
    expect(live.project?.project.id).toBe(a.project.id);
  });

  it('does not append a delayed write to another selected project', async () => {
    await connect();
    const write = deferred<WorkspaceRun>();
    vi.spyOn(WorkspaceClient.prototype, 'createRun').mockImplementationOnce(() => write.promise);
    let saved!: Promise<RunSnapshot | null>;
    await act(async () => { saved = live.addRun(FIXTURE_ORIGINAL_REQUEST, 'run-project-a'); });
    await act(async () => { await live.selectProject(b.project.id); });
    let result: RunSnapshot | null = run('unexpected');
    await act(async () => { write.resolve(run(a.project.id, 'late-write')); result = await saved; });
    expect(result).toBeNull();
    expect(live.project?.project.id).toBe(b.project.id);
    expect(live.runs.map(item => item.run.project_id)).toEqual([b.project.id]);
  });

  it('does not issue the second write with a new credential after disconnect', async () => {
    await connect();
    const creation = deferred<WorkspaceProject>();
    vi.spyOn(WorkspaceClient.prototype, 'createProject').mockImplementationOnce(() => creation.promise);
    const createRun = vi.spyOn(WorkspaceClient.prototype, 'createRun');
    let saved!: Promise<RunSnapshot | null>;
    await act(async () => { saved = live.saveRequest(FIXTURE_ORIGINAL_REQUEST, FIXTURE_BOOTSTRAP.products); });
    await act(async () => { live.disconnect(); await live.connect('new-token'.repeat(5)); });
    await act(async () => { creation.resolve(b); await saved; });
    expect(createRun).not.toHaveBeenCalled();
    expect(live.project?.project.id).toBe(a.project.id);
  });

  it('keeps a newly created project selected when its first run save fails, so a retry continues it', async () => {
    await connect();
    const created = project('project-new');
    vi.spyOn(WorkspaceClient.prototype, 'createProject').mockResolvedValue(created);
    const createRun = vi.spyOn(WorkspaceClient.prototype, 'createRun').mockRejectedValueOnce(new ApiError('CONNECTION_FAILED', 'lost'));
    let saved: RunSnapshot | null = null;
    await act(async () => { saved = await live.saveRequest(FIXTURE_ORIGINAL_REQUEST, FIXTURE_BOOTSTRAP.products); });
    expect(saved).toBeNull();
    expect(live.error?.code).toBe('CONNECTION_FAILED');
    expect(live.project?.project.id).toBe('project-new');
    expect(live.runs).toEqual([]);
    expect(live.projects.map(item => item.project.id)).toEqual([a.project.id, 'project-new']);
    createRun.mockResolvedValueOnce(run('project-new', 'run-retry'));
    await act(async () => { saved = await live.addRun(FIXTURE_ORIGINAL_REQUEST, null); });
    expect((saved as RunSnapshot | null)?.run.id).toBe('run-retry');
    expect(createRun).toHaveBeenLastCalledWith('project-new', FIXTURE_ORIGINAL_REQUEST, null);
  });
  it('rejects a run list from a different project even when the payload has the right shape', async () => {
    await connect();
    vi.mocked(WorkspaceClient.prototype.listRuns).mockResolvedValueOnce({ runs: [run(a.project.id)], contract_version: '0.1.0' });
    await act(async () => { await live.selectProject(b.project.id); });
    expect(live.project).toBeNull();
    expect(live.runs).toEqual([]);
    expect(live.error?.code).toBe('CONTRACT_MISMATCH');
  });
});

function searchResult(modelId = 'FRIDGE-A'): EvidenceSearch {
  return { query: '청소', modelId, documentVersion: '1.0', items: [], total: 0, method: 'literal_token_count' };
}

function searchPayload(scope: WorkspaceProject): Record<string, unknown> {
  return { project_id: scope.project.id, dataset_sha256: scope.dataset_sha256,
    search: { data: { query: '청소', model_id: 'FRIDGE-A', document_version: '1.0', items: [], total: 0, search_method: 'literal_token_count' } } };
}

async function submitSearch() {
  const input = container.querySelector<HTMLInputElement>('input[type="search"]')!;
  const valueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
  await act(async () => {
    valueSetter.call(input, '청소');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  const form = container.querySelector('form')!;
  await act(async () => { form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
}

describe('actual React fixed-scope evidence search', () => {
  it('removes the previous search result when the model or project changes', async () => {
    await connect();
    const search = vi.fn().mockResolvedValue(searchResult());
    await act(async () => { root.render(createElement(ServerEvidenceSearch, { workspace: { ...live, search }, modelId: 'FRIDGE-A' })); });
    await submitSearch();
    expect(search).toHaveBeenCalledWith('청소', 'FRIDGE-A');
    expect(container.textContent).toContain('검색 결과가 없습니다');
    await act(async () => { root.render(createElement(ServerEvidenceSearch, { workspace: { ...live, search }, modelId: 'FRIDGE-B' })); });
    expect(container.textContent).not.toContain('검색 결과가 없습니다');
    expect(container.textContent).toContain('FRIDGE-B · 문서 1.0로 고정');
    await act(async () => { root.render(createElement(ServerEvidenceSearch, { workspace: { ...live, project: b, search }, modelId: 'FRIDGE-A' })); });
    expect(container.textContent).not.toContain('검색 결과가 없습니다');
  });

  it('ignores the pending result from a scope that was replaced', async () => {
    await connect();
    const response = deferred<EvidenceSearch | null>();
    const search = vi.fn().mockImplementationOnce(() => response.promise);
    await act(async () => { root.render(createElement(ServerEvidenceSearch, { workspace: { ...live, search }, modelId: 'FRIDGE-A' })); });
    await submitSearch();
    await act(async () => { root.render(createElement(ServerEvidenceSearch, { workspace: { ...live, project: b, search }, modelId: 'FRIDGE-A' })); });
    await act(async () => { response.resolve(searchResult()); });
    expect(container.textContent).not.toContain('검색 결과가 없습니다');
  });

  it('does not restore a previous credential session result for the same project ID', async () => {
    await connect();
    const response = deferred<EvidenceSearch | null>();
    const search = vi.fn().mockImplementationOnce(() => response.promise);
    const previous = { ...live, search };
    await act(async () => { root.render(createElement(ServerEvidenceSearch, { workspace: previous, modelId: 'FRIDGE-A' })); });
    await submitSearch();
    await act(async () => { root.render(createElement(ServerEvidenceSearch, { workspace: { ...previous, scopeVersion: previous.scopeVersion + 1 }, modelId: 'FRIDGE-A' })); });
    await act(async () => { response.resolve(searchResult()); });
    expect(container.textContent).not.toContain('검색 결과가 없습니다');
  });
});
