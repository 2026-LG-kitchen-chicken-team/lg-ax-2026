// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import * as api from './api';
import * as views from './PlanningViews';
import { FIXTURE_BOOTSTRAP, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import type { MeasurementExport } from './measurement';
import type { RunSnapshot } from './planning';
import { WorkspaceClient } from './workspace';
import type { WorkspaceProject, WorkspaceRun } from './workspace';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(yes => { resolve = yes; });
  return { promise, resolve };
}

function project(id: string, owner = 'planner'): WorkspaceProject {
  return {
    project: { id, name: id, request: FIXTURE_ORIGINAL_REQUEST as unknown as Record<string, unknown>, status: 'active', dataset_version: '0.1.0' },
    owner_id: owner, document_versions: { 'FRIDGE-A': '1.0' }, dataset_sha256: 'a'.repeat(64), created_at: '2026-10-04T09:00:00Z',
  };
}

function run(projectId: string, id: string, previous: string | null = null): RunSnapshot & WorkspaceRun {
  const source = FIXTURE_RUNS[0];
  return { ...source, request: { ...source.request }, output: source.output ? { ...source.output } : null, previous_run_id: previous,
    run: { ...source.run, id, project_id: projectId } };
}

let container: HTMLDivElement;
let root: Root;
let downloads: MeasurementExport[];
const a = project('project-a');
const b = project('project-b');
const firstId = 'run-a-1';
const baseId = 'run-a-2';

function button(label: string): HTMLButtonElement {
  const found = [...container.querySelectorAll('button')].find(item => item.textContent?.trim() === label);
  if (!found) throw new Error(`Missing test control: ${label}`);
  return found;
}

async function click(label: string) { await act(async () => { button(label).click(); }); }

async function input(selector: string, value: string) {
  const element = container.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
  expect(element).not.toBeNull();
  await act(async () => {
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(element, value);
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

async function connect() {
  await input('#workspace-token', 'test-token-not-a-credential');
  await click('연결');
  expect(container.textContent).toContain('연결됨 · 프로젝트 2개');
}

async function history() {
  const nav = [...container.querySelectorAll<HTMLButtonElement>('.nav-item')].find(item => item.textContent?.includes('수정 이력'))!;
  await act(async () => { nav.click(); });
}

async function requestView() {
  const nav = [...container.querySelectorAll<HTMLButtonElement>('.nav-item')].find(item => item.textContent?.includes('기획 요청'))!;
  await act(async () => { nav.click(); });
}

async function submitRequest() {
  await act(async () => { container.querySelector('form.request-form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
}

async function start(goal = '동일 목표 조건 교정') {
  await input('#measure-goal', goal);
  await click('수정 시간 측정 시작');
  expect(container.querySelector('.measure-bar.running')).not.toBeNull();
}

async function edit() {
  await input('#extra-condition', '1인 가구를 우선 검토');
  await click('조건 추가');
}

async function submitRerun() {
  await act(async () => { container.querySelector('form.condition-form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
}

async function selectRun(id: string) {
  const choice = [...container.querySelectorAll<HTMLButtonElement>('.timeline button')].find(item => item.querySelector('.id')?.textContent === id)!;
  expect(choice).not.toBeNull();
  await act(async () => { choice.click(); });
}

function selectedRunId() { return container.querySelector('.timeline button[aria-current="true"] .id')?.textContent; }

async function exportRecord() {
  await click('수정 시간 기록 내보내기(JSON)');
  return downloads[downloads.length - 1];
}

beforeEach(async () => {
  (globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div'); document.body.append(container); root = createRoot(container); downloads = [];
  vi.spyOn(api, 'loadBootstrap').mockResolvedValue(FIXTURE_BOOTSTRAP);
  vi.spyOn(WorkspaceClient.prototype, 'listProjects').mockResolvedValue({ projects: [b, a], contract_version: '0.1.0' });
  vi.spyOn(WorkspaceClient.prototype, 'getProject').mockImplementation(async id => id === a.project.id ? a : b);
  vi.spyOn(WorkspaceClient.prototype, 'listRuns').mockImplementation(async id => ({ runs: id === a.project.id ? [run(id, firstId), run(id, baseId, firstId)] : [run(id, 'run-b-1')], contract_version: '0.1.0' }));
  vi.spyOn(views, 'download').mockImplementation((_name, _type, content) => { downloads.push(JSON.parse(content) as MeasurementExport); });
  await act(async () => { root.render(createElement(App)); });
});

describe('App request form authentication boundaries', () => {
  it('discards the previous private prompt and customer after an automatic 401', async () => {
    await connect(); await requestView();
    await input('#planning-prompt', '이전 연결의 비공개 기획 요청');
    await input('#planning-customer', '이전 연결의 비공개 고객 조건');
    vi.spyOn(WorkspaceClient.prototype, 'createRun').mockRejectedValueOnce(new api.ApiError('UNAUTHORIZED', 'expired'));
    await submitRequest();
    expect(container.textContent).toContain('작업실 인증이 필요합니다');
    expect(container.querySelector<HTMLTextAreaElement>('#planning-prompt')!.value).not.toContain('이전 연결');
    expect(container.querySelector<HTMLInputElement>('#planning-customer')!.value).not.toContain('이전 연결');
    expect(container.querySelector<HTMLTextAreaElement>('#planning-prompt')!.value).toContain('냉장고를 청소');
    expect(container.querySelector<HTMLInputElement>('#planning-customer')!.value).toBe('일상에서 키친 가전을 사용하는 고객');
  });

  it('preserves entered fields and the successful save message when connected project creation changes the scope', async () => {
    vi.mocked(api.loadBootstrap).mockResolvedValue({ ...FIXTURE_BOOTSTRAP,
      products: [...FIXTURE_BOOTSTRAP.products, { model_id: 'FRIDGE-B', product_group: 'fridge', name: '추가 검토 모델', document_version: '1.0' }] });
    // Refresh the mounted App so the controlled bootstrap response includes the second valid model.
    await act(async () => { root.unmount(); }); root = createRoot(container);
    await act(async () => { root.render(createElement(App)); });
    await connect(); await requestView();
    await input('#planning-prompt', '저장 중에도 보존할 기획 요청');
    await input('#planning-customer', '저장 중에도 보존할 대상 고객');
    const otherModel = [...container.querySelectorAll<HTMLLabelElement>('.model-picker label')].find(item => item.textContent?.includes('FRIDGE-B'))!.querySelector<HTMLInputElement>('input')!;
    await act(async () => { otherModel.click(); });
    const created = deferred<WorkspaceProject>();
    vi.spyOn(WorkspaceClient.prototype, 'createProject').mockImplementationOnce(() => created.promise);
    vi.spyOn(WorkspaceClient.prototype, 'createRun').mockImplementationOnce(async (projectId, request) => ({ ...run(projectId, 'new-project-run'), request,
      output: null, run: { ...run(projectId, 'new-project-run').run, status: 'not_implemented', concepts: [] } }));
    await submitRequest();
    expect(container.querySelector<HTMLTextAreaElement>('#planning-prompt')!.value).toBe('저장 중에도 보존할 기획 요청');
    expect(container.querySelector<HTMLInputElement>('#planning-customer')!.value).toBe('저장 중에도 보존할 대상 고객');
    expect(container.textContent).toContain('서버 확인 중');
    const [name, request, versions] = vi.mocked(WorkspaceClient.prototype.createProject).mock.calls[0];
    const savedProject = project('new-project');
    await act(async () => { created.resolve({ ...savedProject, project: { ...savedProject.project, name, request }, document_versions: versions }); await created.promise; });
    expect(container.textContent).toContain('요청 저장 완료 · 분석 결과 아님');
    expect(container.textContent).toContain('새 프로젝트로 저장했습니다');
    expect(container.querySelector<HTMLTextAreaElement>('#planning-prompt')!.value).toBe('저장 중에도 보존할 기획 요청');
    expect(container.querySelector<HTMLInputElement>('#planning-customer')!.value).toBe('저장 중에도 보존할 대상 고객');
  });
});

afterEach(async () => {
  await act(async () => { root.unmount(); }); container.remove(); vi.restoreAllMocks();
});

describe('App modification measurements respect workspace and base-run boundaries', () => {
  it('cancels a running measurement when the selected base changes and never turns it into zero', async () => {
    await connect(); await history(); await start(); await selectRun(firstId);
    expect(container.querySelector('.measure-bar.running')).toBeNull();
    const doc = await exportRecord();
    expect(doc.records).toHaveLength(1);
    expect(doc.records[0]).toMatchObject({ status: 'cancelled', modification_seconds: null, result_run_id: null, base_run_id: baseId });
  });

  it('does not select or complete an old pending rerun after another base is selected', async () => {
    await connect(); await history(); await start(); await edit();
    const saved = deferred<WorkspaceRun>();
    vi.spyOn(WorkspaceClient.prototype, 'createRun').mockImplementationOnce(() => saved.promise);
    await submitRerun(); await selectRun(firstId);
    await act(async () => { saved.resolve(run(a.project.id, 'late-a', baseId)); await saved.promise; });
    expect(selectedRunId()).toBe(firstId);
    expect((await exportRecord()).records[0]).toMatchObject({ status: 'cancelled', modification_seconds: null, result_run_id: null });
  });

  it('clears session measurements and suppresses a pending live response after switching to fixture', async () => {
    await connect(); await history(); await start('이전 세션 목표'); await edit();
    const saved = deferred<WorkspaceRun>();
    vi.spyOn(WorkspaceClient.prototype, 'createRun').mockImplementationOnce(() => saved.promise);
    await submitRerun(); await click('계약 fixture');
    expect(container.textContent).not.toContain('이전 세션 목표');
    await start('fixture 목표');
    await act(async () => { saved.resolve(run(a.project.id, 'late-live', baseId)); await saved.promise; });
    expect(selectedRunId()).toBe(FIXTURE_RUNS[FIXTURE_RUNS.length - 1].run.id);
    const doc = await exportRecord();
    expect(doc.records).toHaveLength(1);
    expect(doc.records[0]).toMatchObject({ goal: 'fixture 목표', mode: 'fixture', execution_kind: 'fixture_browser', status: 'running', modification_seconds: null, result_run_id: null });
  });

  it('does not show or export another project measurement', async () => {
    await connect(); await history(); await start('project-a 목표');
    const picker = container.querySelector<HTMLSelectElement>('.workspace-bar select')!;
    await act(async () => { picker.value = b.project.id; picker.dispatchEvent(new Event('change', { bubbles: true })); });
    expect(container.textContent).not.toContain('project-a 목표');
    expect(container.textContent).toContain('수정 시간 측정 기록이 없습니다');
    await start('project-b 목표');
    const doc = await exportRecord();
    expect(doc.records).toHaveLength(1);
    expect(doc.records[0].scope?.project_id).toBe(b.project.id);
    expect(doc.records[0].goal).toBe('project-b 목표');
  });

  it('clears previous private goals on disconnect and reconnect even for the same project owner', async () => {
    await connect(); await history(); await start('previous connection goal'); await click('연결 해제');
    expect(container.textContent).not.toContain('previous connection goal');
    await connect();
    expect(container.textContent).not.toContain('previous connection goal');
    await start('new connection goal');
    const doc = await exportRecord();
    expect(doc.records).toHaveLength(1);
    expect(doc.records[0].goal).toBe('new connection goal');
  });

  it('finishes only the captured live base and labels a saved request without claiming human or Agent performance', async () => {
    await connect(); await history(); await start(); await edit();
    vi.spyOn(WorkspaceClient.prototype, 'createRun').mockResolvedValueOnce(run(a.project.id, 'saved-a', baseId));
    await submitRerun();
    expect(selectedRunId()).toBe('saved-a');
    const doc = await exportRecord();
    expect(doc.records).toHaveLength(1);
    expect(doc.records[0]).toMatchObject({ status: 'completed', base_run_id: baseId, result_run_id: 'saved-a', execution_kind: 'live_service', participant_kind: 'unconfirmed', scope: { project_id: a.project.id, project_owner_id: 'planner' } });
    expect(doc.records[0].modification_seconds).not.toBeNull();
    expect(doc.notice).toContain('Agent 실행 완료 시간은 아니다');
    expect(doc.notice).toContain('사람의 조작인지 자동화인지 확인하지 않았');
  });
});
