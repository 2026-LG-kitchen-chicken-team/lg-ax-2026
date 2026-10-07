// @vitest-environment jsdom
// PM-20261006-WEB-INTEGRATION-R4 (record 최길웅-20261006-041): selecting a live microwave project left the screen on the
// default fridge group and FRIDGE-A, so the evidence, trend and request views read another product's scope. The
// bootstrap here is the real demo dataset (5 models); projects and runs are stubbed like the other App tests.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import * as api from './api';
import type { BootstrapData } from './domain';
import { FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import type { RunSnapshot } from './planning';
import { WorkspaceClient } from './workspace';
import type { WorkspaceProject, WorkspaceRun } from './workspace';

const dataset = JSON.parse(readFileSync(resolve(process.cwd(), '../../data/demo/dataset.json'), 'utf-8'));
const BOOTSTRAP = { ...dataset, contract_version: '0.1.0' } as unknown as BootstrapData;

function project(id: string, group: string, model: string): WorkspaceProject {
  return {
    project: { id, name: id, request: { ...FIXTURE_ORIGINAL_REQUEST, product_group: group, model_ids: [model] } as unknown as Record<string, unknown>, status: 'active', dataset_version: '0.1.0' },
    owner_id: 'planner', document_versions: { [model]: '1.0' }, dataset_sha256: 'a'.repeat(64), created_at: '2026-10-06T09:00:00Z',
  };
}
const FRIDGE = project('project-fridge', 'fridge', 'FRIDGE-A');
const MICROWAVE = project('project-microwave', 'microwave', 'MICROWAVE-A');

function run(projectId: string): RunSnapshot & WorkspaceRun {
  const source = FIXTURE_RUNS[0];
  return { ...source, request: { ...source.request }, output: source.output ? { ...source.output } : null, previous_run_id: null, run: { ...source.run, id: `run-${projectId}`, project_id: projectId } };
}

let container: HTMLDivElement;
let root: Root;

async function setValue(element: HTMLInputElement | HTMLSelectElement, value: string) {
  await act(async () => {
    const prototype = element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(element, value);
    element.dispatchEvent(new Event(element instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }));
  });
}
const modelSelect = () => container.querySelector<HTMLSelectElement>('#product-model')!;
const projectSelect = () => [...container.querySelectorAll<HTMLLabelElement>('label.run-picker')].find(label => label.textContent?.startsWith('프로젝트'))!.querySelector('select')!;

beforeEach(async () => {
  (globalThis as unknown as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
  vi.spyOn(api, 'loadBootstrap').mockResolvedValue(BOOTSTRAP);
  vi.spyOn(WorkspaceClient.prototype, 'bootstrap').mockResolvedValue(BOOTSTRAP);
  vi.spyOn(WorkspaceClient.prototype, 'listProjects').mockResolvedValue({ projects: [FRIDGE, MICROWAVE], contract_version: '0.1.0' });
  vi.spyOn(WorkspaceClient.prototype, 'getProject').mockImplementation(async id => id === MICROWAVE.project.id ? MICROWAVE : FRIDGE);
  vi.spyOn(WorkspaceClient.prototype, 'listRuns').mockImplementation(async id => ({ runs: [run(id)], contract_version: '0.1.0' }));
  await act(async () => { root.render(createElement(App)); });
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks(); });

describe('a selected workspace project fixes the product group and review model', () => {
  it('switching to the microwave project shows MICROWAVE-A, and back to the fridge project shows FRIDGE-A', async () => {
    await setValue(container.querySelector<HTMLInputElement>('#workspace-token')!, 'test-token-not-a-credential');
    await act(async () => { [...container.querySelectorAll('button')].find(item => item.textContent?.trim() === '연결')!.click(); });
    expect(container.textContent).toContain('연결됨');
    await setValue(projectSelect(), MICROWAVE.project.id);
    expect(projectSelect().value).toBe(MICROWAVE.project.id);
    expect(modelSelect().value).toBe('MICROWAVE-A');
    expect([...modelSelect().options].map(option => option.value)).toEqual(['MICROWAVE-A']);
    await setValue(projectSelect(), FRIDGE.project.id);
    expect(modelSelect().value).toBe('FRIDGE-A');
    // The planner can still pick another model of the same group afterwards; the sync runs only on a project change.
    await setValue(modelSelect(), 'FRIDGE-B');
    expect(modelSelect().value).toBe('FRIDGE-B');
  });
});
