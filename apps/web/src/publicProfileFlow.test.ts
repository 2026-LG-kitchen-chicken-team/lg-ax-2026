// @vitest-environment jsdom
// Synthetic contract examples with real-SKU-shaped IDs. This is UI regression evidence, not collected reviews,
// actual API/model execution, accepted recommendations, or a usability study.
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import * as api from './api';
import type { BootstrapData } from './domain';
import { FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import type { PlanningRequest, RunSnapshot } from './planning';
import { WorkspaceClient } from './workspace';
import type { WorkspaceProject, WorkspaceRun } from './workspace';

const VERSION = 'public-profile-test.r5';
const MODEL = 'T876MEE1H1';
const DOC = 'manual-capture-test.r5';
const BOOTSTRAP: BootstrapData = {
  contract_version: '0.1.0', manifest: { version: VERSION, source_kind: 'public' }, evidence: [], features: [], reviews: [],
  products: Array.from({ length: 18 }, (_, index) => ({ model_id: index === 0 ? MODEL : `SKU-TEST-${index}`, name: '계약 시험 모델',
    product_group: (['fridge', 'dishwasher', 'microwave'] as const)[Math.floor(index / 6)], document_version: DOC, source_kind: 'public' })),
};
const request = (version = VERSION): PlanningRequest => ({ ...FIXTURE_ORIGINAL_REQUEST, model_ids: [MODEL], dataset_version: version });
function project(id: string, input: PlanningRequest): WorkspaceProject {
  return { project: { id, name: id, request: { ...input }, status: 'active', dataset_version: input.dataset_version },
    owner_id: 'test-planner', document_versions: { [MODEL]: DOC }, dataset_sha256: 'a'.repeat(64), created_at: '2026-10-07T00:00:00Z' };
}
function snapshot(projectId: string, input: PlanningRequest, status: 'held' | 'failed', previous: string | null = null): RunSnapshot & WorkspaceRun {
  return { ...FIXTURE_RUNS[0], request: { ...input }, run: { ...FIXTURE_RUNS[0].run, id: previous ? 'run-changed-test' : 'run-new-test', project_id: projectId,
    dataset_version: input.dataset_version, status, stage: 'finished', concepts: [], evidence_ids: [], unresolved: ['시험용 판단 확인 필요'], events: [] },
  previous_run_id: previous, request_revision: previous ? 1 : 0, actor_id: 'test-planner', client: 'web', document_versions: { [MODEL]: DOC }, output: null };
}

let host: HTMLDivElement; let root: Root;
async function setValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  await act(async () => {
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(element, value);
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
async function click(text: string) {
  const button = [...host.querySelectorAll('button')].find(item => item.textContent?.trim() === text)!;
  expect(button).toBeDefined();
  await act(async () => button.click());
}
async function mountAndConnect() {
  await act(async () => root.render(createElement(App)));
  await setValue(host.querySelector<HTMLInputElement>('#workspace-token')!, 'test-token-not-a-credential');
  await click('연결');
  await click('01기획 요청');
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  vi.spyOn(api, 'loadBootstrap').mockResolvedValue(BOOTSTRAP);
  vi.spyOn(WorkspaceClient.prototype, 'listProjects').mockResolvedValue({ projects: [], contract_version: '0.1.0' });
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('new public profile uses registered SKU, document and dataset boundaries', () => {
  it.each(['held', 'failed'] as const)('sends once while waiting, preserves %s, then links changed conditions to the same data', async status => {
    const createProject = vi.spyOn(WorkspaceClient.prototype, 'createProject').mockImplementation(async (_name, input) => project('project-new-test', input as unknown as PlanningRequest));
    let finish: (value: WorkspaceRun) => void = () => {};
    const createRun = vi.spyOn(WorkspaceClient.prototype, 'createRun').mockImplementationOnce(() => new Promise(done => { finish = done; }))
      .mockImplementation(async (id, input, previous) => snapshot(id, input as unknown as PlanningRequest, status, previous));
    await mountAndConnect();
    expect(host.querySelector('.hero-stats')?.textContent).toContain(`공개자료 · 자료 ${VERSION}`);
    expect(host.querySelector('.hero-stats')?.textContent).not.toContain('시연용 합성자료');
    expect(host.querySelector('.hero-stats')?.textContent).toContain('18');
    expect([...host.querySelectorAll('.model-picker input:checked')].map(input => input.parentElement?.textContent)).toEqual([expect.stringContaining(MODEL)]);
    const form = host.querySelector<HTMLFormElement>('.request-form')!;
    await act(async () => { form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
    expect(createProject).toHaveBeenCalledTimes(1);
    expect(createProject.mock.calls[0].slice(1)).toEqual([expect.objectContaining({ model_ids: [MODEL], dataset_version: VERSION }), { [MODEL]: DOC }]);
    expect(createRun).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain('서버 응답 대기 중');
    expect(host.textContent).toContain('자동으로 다시 보내지 않습니다');
    const sent = createRun.mock.calls[0][1] as unknown as PlanningRequest;
    await act(async () => finish(snapshot('project-new-test', sent, status)));
    expect(host.querySelector('[data-code]')?.getAttribute('data-code')).toBe(status === 'held' ? 'SAVED_HELD' : 'SAVED_FAILED');
    await click('03콘셉트 검토');
    expect(host.querySelectorAll('.concept-card')).toHaveLength(0);
    expect(host.textContent).toContain('JSON');
    expect(host.textContent).toContain('문서(Markdown)');
    await click('01기획 요청');
    await setValue(host.querySelector<HTMLTextAreaElement>('#planning-excluded')!, '기존 기능 재제안 제외\n자동 세척 장치 제외');
    await act(async () => host.querySelector<HTMLFormElement>('.request-form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(createProject).toHaveBeenCalledTimes(1);
    expect(createRun).toHaveBeenCalledTimes(2);
    expect(createRun.mock.calls[1]).toEqual(['project-new-test', expect.objectContaining({ model_ids: [MODEL], dataset_version: VERSION,
      exclusions: ['기존 기능 재제안 제외', '자동 세척 장치 제외'] }), 'run-new-test']);
  });

  it('starts a separate project for a new dataset version even if the SKU is unchanged', async () => {
    const old = project('project-old-test', request('public-profile-test.r4'));
    vi.mocked(WorkspaceClient.prototype.listProjects).mockResolvedValue({ projects: [old], contract_version: '0.1.0' });
    vi.spyOn(WorkspaceClient.prototype, 'getProject').mockResolvedValue(old);
    vi.spyOn(WorkspaceClient.prototype, 'listRuns').mockResolvedValue({ runs: [snapshot(old.project.id, request('public-profile-test.r4'), 'held')], contract_version: '0.1.0' });
    const createProject = vi.spyOn(WorkspaceClient.prototype, 'createProject').mockImplementation(async (_name, input) => project('project-r5-test', input as unknown as PlanningRequest));
    const createRun = vi.spyOn(WorkspaceClient.prototype, 'createRun').mockImplementation(async (id, input, previous) => snapshot(id, input as unknown as PlanningRequest, 'held', previous));
    await mountAndConnect();
    expect(host.querySelector('[data-dataset-change]')?.textContent).toContain('public-profile-test.r4');
    expect(host.querySelector('[data-dataset-change]')?.textContent).toContain(VERSION);
    await click('새 프로젝트로 저장');
    expect(createProject).toHaveBeenCalledTimes(1);
    expect(createRun.mock.calls[0]).toEqual(['project-r5-test', expect.objectContaining({ dataset_version: VERSION, model_ids: [MODEL] })]);
    expect(old.project.dataset_version).toBe('public-profile-test.r4');
  });
});
