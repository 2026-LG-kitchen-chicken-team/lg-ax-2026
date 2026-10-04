// @vitest-environment jsdom
import { createHash } from 'node:crypto';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { HistoryView } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import datasetSource from '../../../data/demo/dataset.json';
import planningRequestsSource from '../../../data/demo/planning_requests.json';
import * as api from './api';
import { parseBootstrap } from './api';
import type { BootstrapData, Evidence } from './domain';
import { FIXTURE_BOOTSTRAP, FIXTURE_DATASET_SHA256, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import {
  buildComparison, buildExport, buildRerunRequest, candidateChoicesFor, canonical, conceptChanges, conceptDetailChanges, contractErrors, draftRunFromRequest,
  draftRunWithCondition, exportCompleteness, exportMarkdown, heldItems, missingRequestQuestions, nextRequestRevision, requestChanges, splitConditions,
} from './planning';
import type { Feature, PlanningRequest, RunSnapshot } from './planning';

const dataset = datasetSource as unknown as BootstrapData;
const evidence = FIXTURE_BOOTSTRAP.evidence as Evidence[];
const features = FIXTURE_BOOTSTRAP.features as unknown as Feature[];
const [first, second] = FIXTURE_RUNS;

describe('fixture and live view scope', () => {
  let host: HTMLDivElement;
  let root: Root;
  const liveBootstrap: BootstrapData = { ...FIXTURE_BOOTSTRAP, ...dataset };

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  async function mount() { await act(async () => root.render(createElement(App))); }
  async function click(selector: string, label: string) {
    const button = [...host.querySelectorAll<HTMLButtonElement>(selector)].find(item => item.textContent?.includes(label));
    expect(button, label).toBeDefined();
    await act(async () => button!.click());
  }

  it('only permits the fixture refrigerator and never attaches its concepts to another appliance', async () => {
    const bootstrap = vi.spyOn(api, 'loadBootstrap').mockResolvedValue(liveBootstrap);
    await mount();
    await click('.mode-switch button', '계약 fixture');
    const [fridge, dishwasher, microwave] = host.querySelectorAll<HTMLButtonElement>('.scenario-card');
    expect(fridge.disabled).toBe(false);
    expect(dishwasher.disabled).toBe(true);
    expect(microwave.disabled).toBe(true);
    expect(dishwasher.textContent).toContain('fixture 미제공');
    await act(async () => { dishwasher.click(); microwave.click(); });
    expect(fridge.getAttribute('aria-pressed')).toBe('true');
    expect(host.querySelector<HTMLSelectElement>('#product-model')!.value).toBe('FRIDGE-A');
    await click('.nav-item', '콘셉트 검토');
    expect(host.textContent).toContain('오염 구획만 꺼내는 분리 청소 트레이');
    expect(bootstrap).toHaveBeenCalledTimes(1);
  });

  it('resets appliance, model and evidence filters when entering fixture and reloads live data on return', async () => {
    const bootstrap = vi.spyOn(api, 'loadBootstrap').mockResolvedValue(liveBootstrap);
    await mount();
    await click('.scenario-card', '식기세척기');
    expect(host.querySelector<HTMLSelectElement>('#product-model')!.value).toBe('DISHWASHER-A');
    await click('.evidence-types button', '제품 설명서');
    const input = host.querySelector<HTMLInputElement>('input[type="search"]')!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '없는검색어');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(host.querySelectorAll('.evidence-card')).toHaveLength(0);
    await click('.mode-switch button', '계약 fixture');
    expect(host.querySelector<HTMLSelectElement>('#product-model')!.value).toBe('FRIDGE-A');
    expect(host.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe('');
    expect(host.querySelector('.evidence-types button.active')!.textContent).toContain('전체');
    expect(host.querySelectorAll('.evidence-card').length).toBe(FIXTURE_BOOTSTRAP.evidence.length);
    expect(host.querySelector('[aria-label="선택한 근거 상세"]')!.textContent).toContain('FRIDGE-A');
    await click('.mode-switch button', '실제 서버');
    expect(bootstrap).toHaveBeenCalledTimes(2);
    expect([...host.querySelectorAll<HTMLButtonElement>('.scenario-card')].every(button => !button.disabled)).toBe(true);
    await click('.nav-item', '콘셉트 검토');
    expect(host.textContent).not.toContain('오염 구획만 꺼내는 분리 청소 트레이');
  });

  it('aborts an old bootstrap request and ignores its response after a newer live response', async () => {
    let finishOld!: (data: BootstrapData) => void;
    let finishNew!: (data: BootstrapData) => void;
    const bootstrap = vi.spyOn(api, 'loadBootstrap')
      .mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }))
      .mockImplementationOnce(() => new Promise(resolve => { finishNew = resolve; }));
    await mount();
    const oldSignal = bootstrap.mock.calls[0][0]!;
    await click('.mode-switch button', '계약 fixture');
    expect(oldSignal.aborted).toBe(true);
    expect(host.querySelector('.connection-status')!.textContent).toContain('공통 API 요청 안 함');
    await click('.mode-switch button', '실제 서버');
    expect(host.querySelector('.connection-status')!.textContent).toContain('API 연결 확인 중');
    await act(async () => finishNew(liveBootstrap));
    expect(host.querySelector('.hero-stats strong')!.textContent).toBe(String(liveBootstrap.products.length));
    // The mock deliberately ignores AbortSignal to verify the separate stale-response guard.
    await act(async () => finishOld(FIXTURE_BOOTSTRAP));
    expect(host.querySelector('.hero-stats strong')!.textContent).toBe(String(liveBootstrap.products.length));
    expect(host.querySelector('.connection-status')!.textContent).toContain('공통 API 연결됨');
  });

  it('shows no evidence when the selected appliance has no registered model', async () => {
    vi.spyOn(api, 'loadBootstrap').mockResolvedValue(FIXTURE_BOOTSTRAP);
    await mount();
    await click('.scenario-card', '식기세척기');
    expect(host.querySelector<HTMLSelectElement>('#product-model')!.value).toBe('');
    expect(host.querySelectorAll('.evidence-card')).toHaveLength(0);
    expect(host.querySelector('[aria-label="선택한 근거 상세"]')).toBeNull();
  });

  it('ends the authenticated live session when entering fixture, without making a workspace request', async () => {
    vi.spyOn(api, 'loadBootstrap').mockResolvedValue(liveBootstrap);
    const workspaceFetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true, data: { projects: [], contract_version: '0.1.0' },
    })));
    vi.stubGlobal('fetch', workspaceFetch);
    await mount();
    const token = host.querySelector<HTMLInputElement>('#workspace-token')!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(token, 'fixture-test-credential'.padEnd(48, 'x'));
      token.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => host.querySelector<HTMLFormElement>('.workspace-actions')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(host.querySelector('.workspace-state small')!.textContent).toContain('연결됨');
    expect(workspaceFetch).toHaveBeenCalledTimes(1);
    await click('.mode-switch button', '계약 fixture');
    await click('.mode-switch button', '실제 서버');
    expect(host.querySelector('.workspace-state small')!.textContent).toContain('미연결');
    expect(workspaceFetch).toHaveBeenCalledTimes(1);
  });
});

describe('contract fixture', () => {
  it('passes the shared bootstrap contract through the same parser as the live API', () => {
    expect(() => parseBootstrap({ ok: true, data: FIXTURE_BOOTSTRAP })).not.toThrow();
  });
  it('copies demo dataset entries verbatim so fixture text cannot drift from the source', () => {
    for (const key of ['products', 'reviews', 'features', 'evidence'] as const) {
      for (const item of FIXTURE_BOOTSTRAP[key] as { id?: string; model_id: string }[]) {
        const source = (dataset[key] as { id?: string; model_id: string }[]).find(entry => (entry.id ?? entry.model_id) === (item.id ?? item.model_id));
        expect(source, `${key} ${item.id ?? item.model_id}`).toEqual(item);
      }
    }
  });
  it('records the canonical dataset hash used by the workspace server', () => {
    expect(createHash('sha256').update(canonical(dataset), 'utf8').digest('hex')).toBe(FIXTURE_DATASET_SHA256);
  });
  it('validates every run, need, gap and concept against the shared schema', () => {
    for (const snapshot of FIXTURE_RUNS) {
      expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
      for (const need of snapshot.output!.needs) expect(contractErrors('Need', need)).toEqual([]);
      for (const gap of snapshot.output!.gaps) expect(contractErrors('Gap', gap)).toEqual([]);
      expect(snapshot.run.concepts.length).toBeLessThanOrEqual(3);
    }
  });
  it('only cites evidence and features present in the fixture bootstrap', () => {
    const ids = new Set(evidence.map(item => item.id));
    const featureIds = new Set(features.map(item => item.id));
    for (const snapshot of FIXTURE_RUNS) {
      const cited = [...snapshot.run.evidence_ids, ...snapshot.run.concepts.flatMap(item => item.evidence_ids), ...snapshot.output!.needs.flatMap(item => item.evidence_ids), ...snapshot.output!.gaps.flatMap(item => item.evidence_ids)];
      expect(cited.filter(id => !ids.has(id))).toEqual([]);
      expect(snapshot.output!.gaps.flatMap(item => item.feature_ids).filter(id => !featureIds.has(id))).toEqual([]);
    }
  });
});

describe('R02 request validation, questions and change requests', () => {
  it('asks a question for each missing field instead of filling defaults', () => {
    const questions = missingRequestQuestions({ ...FIXTURE_ORIGINAL_REQUEST, target_customer: '  ', use_situation: '', model_ids: [], dataset_version: '' });
    expect(questions.map(item => item.field)).toEqual(['target_customer', 'use_situation', 'model_ids', 'dataset_version']);
    expect(missingRequestQuestions(FIXTURE_ORIGINAL_REQUEST)).toEqual([]);
  });
  it('rejects requests outside the shared contract', () => {
    expect(contractErrors('PlanningRequest', FIXTURE_ORIGINAL_REQUEST)).toEqual([]);
    expect(contractErrors('PlanningRequest', { ...FIXTURE_ORIGINAL_REQUEST, product_group: 'oven' }).length).toBeGreaterThan(0);
  });
  it('lists field-level changes and follows the server request revision rule', () => {
    const changed: PlanningRequest = { ...FIXTURE_ORIGINAL_REQUEST, use_situation: '우유를 흘린 구역만 청소' };
    expect(requestChanges(FIXTURE_ORIGINAL_REQUEST, changed)).toEqual([{ field: 'use_situation', label: '사용 상황', before: FIXTURE_ORIGINAL_REQUEST.use_situation, after: '우유를 흘린 구역만 청소' }]);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, null, FIXTURE_ORIGINAL_REQUEST)).toBe(0);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, null, changed)).toBe(1);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, second, second.request)).toBe(1);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, second, changed)).toBe(2);
  });
});

describe('R14 comparison table', () => {
  it('joins needs, features, conditions, remaining pain and evidence', () => {
    const rows = buildComparison(first.output!, features, evidence);
    expect(rows).toHaveLength(2);
    expect(rows[0].features.map(item => item.id)).toEqual(['FEATURE-001']);
    expect(rows[0].conditions).toEqual(['선반 위 식품을 모두 이동']);
    expect(rows[0].gap?.support_status).toBe('unsupported');
    expect(rows[0].evidence.map(item => item.id)).toContain('MANUAL-001');
    expect(rows[1].gap?.support_status).toBe('insufficient_evidence');
    expect(rows.every(row => row.missingIds.length === 0)).toBe(true);
  });
  it('reports missing source IDs instead of dropping them silently', () => {
    const rows = buildComparison(first.output!, [], evidence.filter(item => item.id !== 'MANUAL-001'));
    expect(rows[0].missingIds).toEqual(['FEATURE-001', 'MANUAL-001']);
  });
});

describe('R21 additional condition creates a new linked run', () => {
  it('creates a contract-valid not_implemented draft without inventing concepts', () => {
    const draft = draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '1인 가구 소형 모델만', 'RUN-DRAFT-1', '2026-10-04T09:00:00.000Z');
    expect(draft.previous_run_id).toBe('RUN-FX-002');
    expect(draft.request_revision).toBe(2);
    expect(draft.request.exclusions.at(-1)).toBe('1인 가구 소형 모델만');
    expect(draft.run.status).toBe('not_implemented');
    expect(draft.run.concepts).toEqual([]);
    expect(draft.output).toBeNull();
    expect(second.request.exclusions).not.toContain('1인 가구 소형 모델만');
  });
  it('rejects empty or duplicate conditions', () => {
    expect(() => draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '  ', 'RUN-DRAFT-2', '2026-10-04T09:00:00.000Z')).toThrow(/추가할 조건/);
    expect(() => draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '실기기 제어', 'RUN-DRAFT-3', '2026-10-04T09:00:00.000Z')).toThrow(/이미 같은 조건/);
  });
  it('shows concept status changes between linked runs', () => {
    expect(conceptChanges(first, second)).toEqual([{ id: 'CONCEPT-FX-001', title: '오염 구획만 꺼내는 분리 청소 트레이', before: 'needs_review', after: 'rejected' }]);
    expect(conceptChanges(undefined, first).map(item => item.after)).toEqual(['needs_review', 'proposed']);
  });
});

describe('P2-WEB-003 candidate choices, condition correction and combined review', () => {
  const concepts = first.run.concepts;
  it('writes excluded and focused candidates into the request within the shared contract', () => {
    const next = buildRerunRequest(first.request, concepts, { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' }, ['실기기 제어', '1인 가구 소형 모델만']);
    expect(next.exclusions).toEqual(['실기기 제어', '1인 가구 소형 모델만', '후보 제외: 오염 구획만 꺼내는 분리 청소 트레이 (CONCEPT-FX-001)']);
    expect(next.improvement_task).toBe(`${first.request.improvement_task} [집중 검토: 청소 전 식품 이동 범위 안내 (CONCEPT-FX-002)]`);
    expect(next.model_ids).toEqual(first.request.model_ids);
    expect(contractErrors('PlanningRequest', next)).toEqual([]);
  });
  it('is idempotent across reruns: focus suffix and candidate exclusions are replaced, not stacked', () => {
    const once = buildRerunRequest(first.request, concepts, { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' }, splitConditions(first.request).conditions);
    const twice = buildRerunRequest(once, concepts, { 'CONCEPT-FX-001': 'keep', 'CONCEPT-FX-002': 'keep' }, splitConditions(once, concepts).conditions);
    expect(twice.improvement_task).toBe(first.request.improvement_task);
    expect(twice.exclusions).toEqual(first.request.exclusions);
    expect(splitConditions(once, concepts)).toEqual({ conditions: first.request.exclusions, excludedCandidates: ['후보 제외: 오염 구획만 꺼내는 분리 청소 트레이 (CONCEPT-FX-001)'] });
  });
  it('restores current focus/exclusion and leaves a no-change request exactly as it was', () => {
    const choices = { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' } as const;
    const once = buildRerunRequest(first.request, concepts, choices, first.request.exclusions);
    expect(candidateChoicesFor(once, concepts)).toEqual(choices);
    expect(buildRerunRequest(once, concepts, {}, splitConditions(once, concepts).conditions)).toEqual(once);
  });
  it('preserves candidate intent on a draft with no candidates, including another condition-only rerun', () => {
    const chosen = buildRerunRequest(first.request, concepts, { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' }, first.request.exclusions);
    const draft = draftRunFromRequest(first, FIXTURE_ORIGINAL_REQUEST, chosen, 'RUN-PRESERVE', '2026-10-04T10:00:00.000Z');
    expect(splitConditions(draft.request)).toEqual({ conditions: chosen.exclusions, excludedCandidates: [] });
    expect(buildRerunRequest(draft.request, [], {}, splitConditions(draft.request).conditions)).toEqual(chosen);
    const next = buildRerunRequest(draft.request, [], {}, [...splitConditions(draft.request).conditions, '1인 가구 조건']);
    expect(next.improvement_task).toBe(chosen.improvement_task);
    expect(next.exclusions).toEqual([...chosen.exclusions, '1인 가구 조건']);
  });
  it('does not delete user-authored prefixed text or unknown candidate markers', () => {
    const base = { ...first.request, improvement_task: `${first.request.improvement_task} [집중 검토: 사용자 작성 메모]`, exclusions: ['후보 제외: 사용자 원문', '  후보 제외: 과거 후보 (CONCEPT-OLD)  '] };
    expect(splitConditions(base, concepts)).toEqual({ conditions: base.exclusions, excludedCandidates: [] });
    const unchanged = buildRerunRequest(base, concepts, {}, splitConditions(base, concepts).conditions);
    expect(unchanged).toEqual(base);
    const focused = buildRerunRequest(base, concepts, { 'CONCEPT-FX-001': 'focus' }, base.exclusions);
    expect(focused.improvement_task.startsWith(base.improvement_task)).toBe(true);
    expect(buildRerunRequest(focused, concepts, {}, splitConditions(focused, concepts).conditions)).toEqual(focused);
  });
  it('handles brackets and punctuation in an exact current candidate label', () => {
    const unusual = [{ ...concepts[0], title: '트레이 [소형], (분리식)' }];
    const focused = buildRerunRequest(first.request, unusual, { 'CONCEPT-FX-001': 'focus' }, first.request.exclusions);
    expect(candidateChoicesFor(focused, unusual)).toEqual({ 'CONCEPT-FX-001': 'focus' });
    expect(buildRerunRequest(focused, unusual, {}, first.request.exclusions)).toEqual(focused);
    expect(buildRerunRequest(focused, unusual, { 'CONCEPT-FX-001': 'keep' }, first.request.exclusions).improvement_task).toBe(first.request.improvement_task);
  });
  it('corrects conditions: edits, removals and blanks are applied, duplicates collapse', () => {
    const next = buildRerunRequest(first.request, [], {}, ['실기기 제어', '  ', '실기기 제어', '제조용 CAD 제외']);
    expect(next.exclusions).toEqual(['실기기 제어', '제조용 CAD 제외']);
    expect(requestChanges(first.request, next).map(item => item.field)).toEqual(['exclusions']);
  });
  it('shows what changed inside each candidate between linked runs', () => {
    const changes = conceptDetailChanges(first, second);
    expect(changes).toHaveLength(1);
    expect(changes[0]).toMatchObject({ id: 'CONCEPT-FX-001', status: ['needs_review', 'rejected'] });
    expect(changes[0].added.assumptions).toEqual(['추가 조건에 따라 문서 2.0 FEATURE-006과 중복 가능성이 있어 제외']);
    expect(changes[0].removed).toEqual({ requirements: [], assumptions: [], evidence_ids: [] });
  });
  it('lists held items: insufficient-evidence gaps with their questions, then unresolved notes', () => {
    const held = heldItems(second);
    expect(held[0]).toMatchObject({ kind: 'insufficient_evidence', id: 'GAP-FX-002' });
    expect(held[0].questions[0]).toContain('임시 보관');
    expect(held.filter(item => item.kind === 'unresolved').map(item => item.text)).toEqual(second.run.unresolved);
  });
  it('creates a linked draft from a full rerun request in fixture mode', () => {
    const next = buildRerunRequest(second.request, second.run.concepts, { 'CONCEPT-FX-002': 'focus' }, splitConditions(second.request).conditions);
    const draft = draftRunFromRequest(second, FIXTURE_ORIGINAL_REQUEST, next, 'RUN-DRAFT-9', '2026-10-04T10:00:00.000Z');
    expect(draft).toMatchObject({ previous_run_id: 'RUN-FX-002', request_revision: 2, output: null });
    expect(draft.run.status).toBe('not_implemented');
  });
});

describe('candidate and condition rerun controls in the actual React DOM', () => {
  let host: HTMLDivElement;
  let root: Root;
  const onRerun = vi.fn().mockResolvedValue(undefined);
  const measure: MeasureControls = { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' };

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    onRerun.mockClear();
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });

  async function mount(selected: RunSnapshot) {
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'fixture', runs: [selected], selected, original: FIXTURE_ORIGINAL_REQUEST, onSelect: () => {},
      features, evidence, onRerun, measure,
    })));
  }
  async function type(input: HTMLInputElement, text: string) {
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, text);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

  it('keeps the same focused condition node while typing and when an earlier row is removed', async () => {
    await mount({ ...first, request: { ...first.request, exclusions: ['첫 번째 조건', '두 번째 조건'] } });
    const input = host.querySelectorAll<HTMLInputElement>('.condition-list input')[1];
    input.focus();
    for (const text of ['두 번째 조건 추', '두 번째 조건 추가', '두 번째 조건 추가됨']) {
      await type(input, text);
      expect(host.querySelectorAll('.condition-list input')[1]).toBe(input);
      expect(document.activeElement).toBe(input);
      expect(input.value).toBe(text);
    }
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="조건 1 삭제"]')!.click());
    expect(host.querySelector('.condition-list input')).toBe(input);
    expect(document.activeElement).toBe(input);
    await type(input, '남은 조건을 계속 입력');
    expect(input.value).toBe('남은 조건을 계속 입력');
    expect(document.activeElement).toBe(input);
  });

  it('restores the focused/excluded radio choices and does not silently create an edited request', async () => {
    const request = buildRerunRequest(first.request, first.run.concepts, { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' }, first.request.exclusions);
    await mount({ ...first, request });
    expect(host.querySelectorAll<HTMLInputElement>('input[name="choice-CONCEPT-FX-001"]')[2].checked).toBe(true);
    expect(host.querySelectorAll<HTMLInputElement>('input[name="choice-CONCEPT-FX-002"]')[1].checked).toBe(true);
    expect(host.querySelector('.condition-form')!.textContent).toContain('아직 바뀐 내용이 없습니다.');
    await act(async () => host.querySelector('.condition-form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(onRerun).not.toHaveBeenCalled();
    expect(host.querySelector('.condition-form')!.textContent).toContain('바뀐 조건이 없습니다.');
  });

  it('keeps prior intent visible on a no-candidate draft and sends it with an added condition', async () => {
    const request = buildRerunRequest(first.request, first.run.concepts, { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' }, first.request.exclusions);
    const draft = draftRunFromRequest(first, FIXTURE_ORIGINAL_REQUEST, request, 'RUN-DOM-DRAFT', '2026-10-04T10:00:00.000Z');
    await mount(draft);
    expect(host.querySelectorAll('input[type="radio"]')).toHaveLength(0);
    expect([...host.querySelectorAll<HTMLInputElement>('.condition-list input')].map(item => item.value)).toEqual(request.exclusions);
    expect(host.querySelector('.condition-form')!.textContent).toContain('아직 바뀐 내용이 없습니다.');
    await type(host.querySelector<HTMLInputElement>('#extra-condition')!, '1인 가구 조건');
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>('.condition-form button')].find(button => button.textContent === '조건 추가')!.click());
    await act(async () => host.querySelector('.condition-form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(onRerun).toHaveBeenCalledTimes(1);
    expect(onRerun.mock.calls[0][0]).toEqual({ ...request, exclusions: [...request.exclusions, '1인 가구 조건'] });
    expect(onRerun.mock.calls[0][1]).toEqual({ candidates_changed: 0, conditions_added: 1, conditions_removed: 0 });
  });
});

describe('R27 meeting export', () => {
  const doc = buildExport('fixture', second, features, evidence, '2026-10-04T09:00:00.000Z');
  const markdown = exportMarkdown(doc);
  it('includes every cited evidence text, requirement, assumption and unresolved item', () => {
    const cited = new Set([...second.run.evidence_ids, ...second.run.concepts.flatMap(item => item.evidence_ids), ...second.output!.needs.flatMap(item => item.evidence_ids), ...second.output!.gaps.flatMap(item => item.evidence_ids)]);
    expect(doc.evidence.map(item => item.id).sort()).toEqual([...cited].sort());
    for (const item of doc.evidence) expect(markdown).toContain(item.text);
    for (const concept of second.run.concepts) {
      for (const text of [...concept.requirements, ...concept.assumptions]) expect(markdown).toContain(text);
    }
    for (const text of [...second.run.unresolved, ...second.unconfirmed]) expect(markdown).toContain(text);
  });
  it('P2-WEB-004: includes held items and lineage, and its self-check passes', () => {
    const full = buildExport('fixture', second, features, evidence, '2026-10-04T09:00:00.000Z', FIXTURE_RUNS);
    expect(full.held.map(item => item.id)).toEqual(['GAP-FX-002']);
    expect(full.lineage.map(item => [item.run_id, item.request_revision])).toEqual([['RUN-FX-001', 0], ['RUN-FX-002', 1]]);
    expect(full.completeness).toEqual({ complete: true, missing_evidence: [], missing_concepts: [], missing_requirements: [], missing_assumptions: [], missing_unresolved: [], missing_held: [], mismatched_fields: [] });
    const md = exportMarkdown(full);
    expect(md).toContain('## 근거 부족으로 보류한 불편');
    expect(md).toContain('RUN-FX-001 · 요청 회차 0');
    expect(md).toContain('보류·계보가 모두 포함되었습니다');
  });
  it('P2-WEB-004: the self-check reports what an export would leave out', () => {
    const lossy = buildExport('fixture', second, features, evidence.filter(item => item.id !== 'MANUAL-001'), '2026-10-04T09:00:00.000Z');
    expect(lossy.completeness.complete).toBe(false);
    expect(lossy.completeness.missing_evidence).toEqual(['MANUAL-001']);
    const trimmed = { ...lossy, requirements: lossy.requirements.slice(1), assumptions: [], held: [] };
    const check = exportCompleteness(trimmed, second, features, evidence);
    expect(check.missing_requirements).toHaveLength(1);
    expect(check.missing_assumptions).toContain('문서 범위를 2.0으로 확대할지 기획자 결정 필요');
    expect(check.missing_held).toEqual(['GAP-FX-002']);
    expect(exportMarkdown(lossy)).toContain('누락이 있습니다');
  });
  it('rejects removed candidates and changed candidate fields even when the separate requirements remain', () => {
    const full = buildExport('fixture', second, features, evidence, '2026-10-04T09:00:00.000Z');
    const empty = exportCompleteness({ ...full, concepts: [] }, second, features, evidence);
    expect(empty.complete).toBe(false);
    expect(empty.missing_concepts).toEqual(second.run.concepts.map(item => item.id));
    expect(empty.mismatched_fields).toContain('콘셉트 후보');
    const changed = structuredClone(full);
    changed.concepts[0].title = '다른 후보';
    changed.concepts[0].requirements = [];
    expect(exportCompleteness(changed, second, features, evidence).complete).toBe(false);
    expect(second.run.concepts[0].title).not.toBe('다른 후보');
  });
  it('checks every cited source text and metadata against the actual source, including empty input', () => {
    const full = buildExport('fixture', second, features, evidence, '2026-10-04T09:00:00.000Z');
    for (const patch of [{ text: '' }, { text: '짧게 바뀐 원문' }, { document_version: '999' }, { source_id: 'OTHER-SOURCE' }, { model_id: 'FRIDGE-B' }]) {
      const changed = { ...full, evidence: full.evidence.map(item => ({ ...item, ...patch })) };
      const check = exportCompleteness(changed, second, features, evidence);
      expect(check.complete).toBe(false);
      expect(check.missing_evidence.length).toBe(full.evidence.length);
    }
    const blankSource = evidence.map(item => ({ ...item, text: '' }));
    expect(buildExport('fixture', second, features, blankSource, '2026-10-04T09:00:00.000Z').completeness.complete).toBe(false);
  });
  it('includes Skill-event and linked feature citations, and flags missing comparison inputs', () => {
    const eventSource = { ...evidence[0], id: 'EVIDENCE-EVENT-ONLY' };
    const featureSource = { ...evidence[0], id: 'EVIDENCE-FEATURE-ONLY' };
    const snapshot: RunSnapshot = { ...second, run: { ...second.run, events: [...second.run.events, { stage: 'retrieve', summary: '별도 원문 조회', tool: 'search', evidence_ids: [eventSource.id] }] } };
    const linkedFeatures = features.map(item => item.id === 'FEATURE-001' ? { ...item, evidence_ids: [...item.evidence_ids, featureSource.id] } : item);
    const full = buildExport('fixture', snapshot, linkedFeatures, [...evidence, eventSource, featureSource], '2026-10-04T09:00:00.000Z');
    expect(full.evidence.map(item => item.id)).toEqual(expect.arrayContaining([eventSource.id, featureSource.id]));
    expect(full.completeness.complete).toBe(true);
    const missingSources = buildExport('fixture', snapshot, linkedFeatures, evidence, '2026-10-04T09:00:00.000Z');
    expect(missingSources.completeness.missing_evidence).toEqual(expect.arrayContaining([eventSource.id, featureSource.id]));
    const missingFeatures = buildExport('fixture', second, [], evidence, '2026-10-04T09:00:00.000Z');
    expect(missingFeatures.completeness.complete).toBe(false);
    expect(missingFeatures.completeness.mismatched_fields.some(item => item.includes('FEATURE-001'))).toBe(true);
  });
  it('detects wrong request, lineage, comparison and assumption attribution', () => {
    const full = buildExport('fixture', second, features, evidence, '2026-10-04T09:00:00.000Z', FIXTURE_RUNS);
    const changed = structuredClone(full);
    changed.request.improvement_task = '다른 요청';
    changed.comparison[0].remaining_pain = '누락';
    changed.lineage = [];
    changed.assumptions = changed.assumptions.map(item => ({ ...item, source_id: 'OTHER-RUN' }));
    const check = exportCompleteness(changed, second, features, evidence, FIXTURE_RUNS);
    expect(check.complete).toBe(false);
    expect(check.mismatched_fields).toEqual(expect.arrayContaining(['기획 요청', '불편·기능 대조표', '가정·미확인', '실행 계보']));
    expect(check.missing_assumptions.length).toBeGreaterThan(0);
  });
  it('keeps the compared model on every comparison row', () => {
    expect(doc.comparison.every(row => row.model_id === 'FRIDGE-A')).toBe(true);
    expect(markdown).toContain('| 모델 | 불편 |');
    expect(markdown).toContain('| FRIDGE-A | NEED-FX-001');
  });
  it('accepts the shared multi-model sample requests', () => {
    const samples = planningRequestsSource as PlanningRequest[];
    expect(samples[0].model_ids).toEqual(['FRIDGE-A', 'FRIDGE-B', 'FRIDGE-C']);
    for (const sample of samples) {
      expect(contractErrors('PlanningRequest', sample)).toEqual([]);
      expect(missingRequestQuestions(sample)).toEqual([]);
    }
  });
  it('labels fixture exports so they are not mistaken for Agent output', () => {
    expect(doc.meta.mode).toBe('fixture');
    expect(markdown).toContain('Agent 출력이나 서버 응답이 아니며');
    expect(JSON.parse(JSON.stringify(doc)).meta.notice).toBe(doc.meta.notice);
  });
  it('keeps the export usable for a draft without results', () => {
    const draft = draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '추가 조건', 'RUN-DRAFT-4', '2026-10-04T09:00:00.000Z');
    const empty = exportMarkdown(buildExport('fixture', draft, features, evidence, '2026-10-04T09:00:00.000Z'));
    expect(empty).toContain('생성된 콘셉트가 없습니다.');
    expect(empty).toContain('not_implemented');
    expect(buildExport('fixture', draft, features, evidence, '2026-10-04T09:00:00.000Z').completeness.complete).toBe(true);
  });
});
