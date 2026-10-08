// @vitest-environment jsdom
import { act, createElement, StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ResearchPlanningView } from './ResearchPlanningView';
import App from './App';
import { heldBrief, REAL_RESEARCH_BUNDLE } from './fixtures/research-test-data';
import * as views from './PlanningViews';
import type { PlanningBrief } from './research';
import { createSharedSessionLoader } from './sharedSession';
import { ResearchClient } from './researchClient';
import type { ResearchPlanProgress } from './researchClient';

describe('accepted research jobs use a single POST and bounded authenticated status reads', () => {
  const jobId = '1'.repeat(32);
  const credential = () => 'a'.repeat(40);
  const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  const input = () => ({ bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, goal: heldBrief().goal, constraints: heldBrief().constraints, previous_run_id: null });
  const queued = () => ({ job_id: jobId, status: 'queued', queue_position: 2, poll_after_ms: 1000 });
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  it('reports queued, running and validated completion while preserving memory Bearer and POST1', async () => {
    const reads = [
      { ...queued(), queue_position: 1 },
      { ...queued(), status: 'running', queue_position: 0 },
      { ...queued(), status: 'completed', queue_position: null, result: heldBrief() },
    ];
    const transport = vi.fn().mockImplementation((_url: string, options?: RequestInit) => Promise.resolve(response(options?.method === 'POST' ? queued() : reads.shift(), options?.method === 'POST' ? 202 : 200)));
    const states: ResearchPlanProgress[] = [];
    const pending = new ResearchClient(credential, transport).createPlan(REAL_RESEARCH_BUNDLE, input(), null, undefined, state => states.push(state));
    await vi.advanceTimersByTimeAsync(0);
    expect(states.map(state => state.status)).toEqual(['queued']);
    await vi.advanceTimersByTimeAsync(3000);
    expect(await pending).toEqual(heldBrief());
    expect(states.map(state => state.status)).toEqual(['queued', 'queued', 'running', 'completed']);
    expect(transport.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
    expect(transport.mock.calls.slice(1).every(call => call[0] === `/api/prototype/jobs/${jobId}` && call[1]?.method === 'GET')).toBe(true);
    expect(transport.mock.calls.every(call => new Headers(call[1]?.headers).get('Authorization') === `Bearer ${credential()}`)).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });
  it('returns the backend failure message without a completed callback, retry or remaining timer', async () => {
    const transport = vi.fn().mockImplementation((_url: string, options?: RequestInit) => Promise.resolve(response(options?.method === 'POST' ? queued()
      : { ...queued(), status: 'failed', queue_position: null, error: { code: 'MODEL_UNAVAILABLE', message: '모델 요청을 완료하지 못했습니다.' } }, options?.method === 'POST' ? 202 : 200)));
    const states: ResearchPlanProgress[] = [];
    const pending = new ResearchClient(credential, transport).createPlan(REAL_RESEARCH_BUNDLE, input(), null, undefined, state => states.push(state));
    const checked = expect(pending).rejects.toThrow('모델 요청을 완료하지 못했습니다');
    await vi.advanceTimersByTimeAsync(1000); await checked;
    expect(states.map(state => state.status)).toEqual(['queued', 'failed']);
    expect(transport).toHaveBeenCalledTimes(2); expect(vi.getTimerCount()).toBe(0);
  });
  it('applies the existing exact input-scope check to the completed result before reporting completion', async () => {
    const result = heldBrief();
    result.source_facts = REAL_RESEARCH_BUNDLE.sources.map(source => ({ source_id: source.source_id, facts: source.facts }));
    result.runtime = { input_scope: 'full_bundle', user_selected_source_ids: REAL_RESEARCH_BUNDLE.sources.map(source => source.source_id) };
    const transport = vi.fn().mockImplementation((_url: string, options?: RequestInit) => Promise.resolve(response(options?.method === 'POST' ? queued()
      : { ...queued(), status: 'completed', queue_position: null, result }, options?.method === 'POST' ? 202 : 200)));
    const states: ResearchPlanProgress[] = [];
    const pending = new ResearchClient(credential, transport).createPlan(REAL_RESEARCH_BUNDLE, { ...input(), selected_source_ids: REAL_RESEARCH_BUNDLE.sources.map(source => source.source_id) }, null, undefined, state => states.push(state));
    const checked = expect(pending).rejects.toThrow('입력 근거 범위');
    await vi.advanceTimersByTimeAsync(1000); await checked;
    expect(states.map(state => state.status)).toEqual(['queued']);
    expect(transport).toHaveBeenCalledTimes(2); expect(vi.getTimerCount()).toBe(0);
  });
  it('rejects another job ID from the polling route and never resubmits the request', async () => {
    const transport = vi.fn().mockImplementation((_url: string, options?: RequestInit) => Promise.resolve(response(options?.method === 'POST' ? queued()
      : { ...queued(), job_id: '2'.repeat(32) }, options?.method === 'POST' ? 202 : 200)));
    const pending = new ResearchClient(credential, transport).createPlan(REAL_RESEARCH_BUNDLE, input(), null);
    const checked = expect(pending).rejects.toThrow('상태 응답');
    await vi.advanceTimersByTimeAsync(1000); await checked;
    expect(transport).toHaveBeenCalledTimes(2); expect(vi.getTimerCount()).toBe(0);
  });
  it('aborts a pending GET, cleans its timers and ignores a late completed response', async () => {
    const controller = new AbortController(); let finish!: (value: Response) => void;
    const transport = vi.fn().mockImplementation((_url: string, options?: RequestInit) => options?.method === 'POST' ? Promise.resolve(response(queued(), 202)) : new Promise<Response>(resolve => { finish = resolve; }));
    const states: ResearchPlanProgress[] = [];
    const pending = new ResearchClient(credential, transport).createPlan(REAL_RESEARCH_BUNDLE, input(), null, controller.signal, state => states.push(state));
    const checked = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    await vi.advanceTimersByTimeAsync(1000); controller.abort(); await checked;
    finish(response({ ...queued(), status: 'completed', queue_position: null, result: heldBrief() }));
    await vi.advanceTimersByTimeAsync(0);
    expect(transport.mock.calls[1][1]?.signal?.aborted).toBe(true);
    expect(states.map(state => state.status)).toEqual(['queued']);
    expect(transport).toHaveBeenCalledTimes(2); expect(vi.getTimerCount()).toBe(0);
  });
  it('stops after 25 minutes even when transport ignores abort, without a blind POST retry', async () => {
    const transport = vi.fn().mockImplementation(() => new Promise<Response>(() => {}));
    const pending = new ResearchClient(credential, transport).createPlan(REAL_RESEARCH_BUNDLE, input(), null);
    const checked = expect(pending).rejects.toThrow('25분');
    await vi.advanceTimersByTimeAsync(25 * 60 * 1000); await checked;
    expect(transport).toHaveBeenCalledTimes(1);
    expect(transport.mock.calls[0][1]?.signal?.aborted).toBe(true); expect(vi.getTimerCount()).toBe(0);
  });
  it('finds the current principal job without an accepted job ID and treats no job as an explicit 404', async () => {
    const transport = vi.fn().mockResolvedValue(response(queued()));
    const client = new ResearchClient(credential, transport);
    expect((await client.getCurrentJobStatus()).job_id).toBe(jobId);
    expect(transport.mock.calls[0][0]).toBe('/api/prototype/jobs/current');
    expect(transport.mock.calls[0][1]?.method).toBe('GET');
    transport.mockResolvedValue(response({ error: { code: 'NOT_FOUND' } }, 404));
    await expect(client.getCurrentJobStatus()).rejects.toThrow('접수한 기획 요청을 찾지 못했습니다');
    expect(transport.mock.calls.every(call => call[1]?.method === 'GET')).toBe(true); expect(vi.getTimerCount()).toBe(0);
  });
});

describe('actual-source research screen state and revision flow', () => {
  let host: HTMLDivElement; let root: Root;
  const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); sessionStorage.clear(); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { if (host.isConnected) await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); });
  const enter = async (selector: string, value: string) => { await act(async () => {
    const input = host.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
    const prototype = input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }); };
  const click = async (text: string) => { await act(async () => {
    const button = [...host.querySelectorAll<HTMLButtonElement>('button')].find(item => item.textContent === text);
    if (!button) throw new Error(`missing ${text}`); button.click();
  }); };
  const connect = async () => { await enter('#research-token', 'x'.repeat(40)); await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))); };
  const choose = async () => { await act(async () => { const select = host.querySelector<HTMLSelectElement>('#research-bundle')!; select.value = REAL_RESEARCH_BUNDLE.bundle_id; select.dispatchEvent(new Event('change', { bubbles: true })); }); };
  function api() {
    return vi.fn().mockImplementation(async (url: string, options?: RequestInit) => {
      if (url.endsWith('/bundles')) return response({ bundles: [{ bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, product_group: 'fridge', analysis_scope: 'product_group', source_count: 1, review_count: 1 }] });
      if (url.includes('/bundles/')) return response(REAL_RESEARCH_BUNDLE);
      if (url.endsWith('/planning-runs') && options?.method === 'POST') return response(heldBrief());
      return response({ error: { code: 'NOT_FOUND' } }, 404);
    });
  }
  it('opens the new flow independently of legacy bootstrap or synthetic example controls', async () => {
    const fetch = vi.fn().mockResolvedValue(response({}, 404)); vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(App)));
    expect(host.querySelector('[aria-label="실제 자료 작업실 연결"]')).not.toBeNull();
    expect(host.textContent).not.toContain('계약 fixture'); expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe('/api/prototype/session');
    expect(host.querySelector('#research-token')).not.toBeNull();
    expect(host.querySelectorAll('nav[aria-label="기획 작업 영역"] button')).toHaveLength(6);
  });
  it('connects a shared link once in StrictMode and retains the real-source planning flow without a token form or legacy menus', async () => {
    const token = 's'.repeat(48);
    const fetch = vi.fn().mockImplementation(async (url: string, options?: RequestInit) => {
      if (url === '/api/prototype/session') return response({ shared_prototype: true, token });
      if (url.endsWith('/bundles')) return response({ bundles: [{ bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, product_group: 'fridge', analysis_scope: 'product_group', source_count: 1, review_count: 1 }] });
      if (url.includes('/bundles/')) return response(REAL_RESEARCH_BUNDLE);
      if (url.endsWith('/planning-runs') && options?.method === 'POST') return response(heldBrief());
      return response({}, 404);
    });
    vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(StrictMode, null, createElement(App))));
    expect(fetch.mock.calls.filter(call => call[0] === '/api/prototype/session')).toHaveLength(1);
    expect(fetch.mock.calls.filter(call => call[0].endsWith('/bundles'))).toHaveLength(1);
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store' });
    expect(host.querySelector('#research-token')).toBeNull();
    expect(host.querySelectorAll('nav[aria-label="기획 작업 영역"] button')).toHaveLength(1);
    expect(host.textContent).toContain('공유 프로토타입 연결됨');
    expect(host.textContent).not.toContain(token); expect(host.textContent).not.toContain('계약 fixture');
    await choose(); expect(host.textContent).toContain(REAL_RESEARCH_BUNDLE.sources[0].text);
    await click('새 기획 생성');
    const writes = fetch.mock.calls.filter(call => call[1]?.method === 'POST');
    expect(writes).toHaveLength(1);
    expect(new Headers(writes[0][1]?.headers).get('Authorization')).toBe(`Bearer ${token}`);
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).not.toBeNull();
    expect(fetch.mock.calls.some(call => call[0] === '/api/bootstrap' || call[0].startsWith('/api/workspace'))).toBe(false);
  });
  it('does not connect or update the screen from a shared-session response arriving after unmount', async () => {
    let finish!: (value: Response) => void;
    const fetch = vi.fn().mockImplementation(() => new Promise<Response>(resolve => { finish = resolve; }));
    vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(StrictMode, null, createElement(App))));
    expect(fetch).toHaveBeenCalledTimes(1);
    await act(async () => root.unmount()); host.remove();
    await act(async () => finish(response({ shared_prototype: true, token: 's'.repeat(48) })));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(host.textContent).toBe('');
  });
  it('shows accepted queue and running states while original-text filters remain usable, with only job_id stored', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(ResearchPlanningView))); await connect(); await choose();
    const jobId = '3'.repeat(32);
    const states = [
      { job_id: jobId, status: 'running', queue_position: 0, poll_after_ms: 1000 },
      { job_id: jobId, status: 'completed', queue_position: null, poll_after_ms: 1000, result: heldBrief() },
    ];
    fetch.mockImplementation(async (url: string, options?: RequestInit) => {
      if (options?.method === 'POST') return response({ job_id: jobId, status: 'queued', queue_position: 1, poll_after_ms: 1000 }, 202);
      if (url === `/api/prototype/jobs/${jobId}`) return response(states.shift());
      return response({}, 404);
    });
    vi.useFakeTimers(); await click('새 기획 생성');
    expect(host.querySelector('[aria-label="접수한 기획 요청 상태"]')?.textContent).toContain('대기 순서 1');
    expect(Object.keys(sessionStorage)).toEqual(['lgax.research.pending-job']);
    expect(sessionStorage.getItem('lgax.research.pending-job')).toBe(jobId);
    expect(host.querySelector<HTMLInputElement>('#research-keyword')!.disabled).toBe(false);
    await enter('#research-keyword', 'no-matching-original-for-this-test'); expect(host.querySelectorAll('.research-source-row')).toHaveLength(0);
    await enter('#research-keyword', ''); expect(host.querySelectorAll('.research-source-row')).toHaveLength(1);
    await act(async () => vi.advanceTimersByTimeAsync(1000));
    expect(host.querySelector('[aria-label="접수한 기획 요청 상태"]')?.textContent).toContain('기획 생성 실행 중');
    await act(async () => vi.advanceTimersByTimeAsync(1000));
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).not.toBeNull();
    expect(host.querySelector('[aria-label="접수한 기획 요청 상태"]')?.textContent).toContain('처리 완료');
    expect(sessionStorage.getItem('lgax.research.pending-job')).toBeNull();
    expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
  });
  it('shows a queued job failure with its message while preserving original-source browsing', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(ResearchPlanningView))); await connect(); await choose();
    const jobId = '4'.repeat(32);
    fetch.mockImplementation(async (_url: string, options?: RequestInit) => response(options?.method === 'POST'
      ? { job_id: jobId, status: 'queued', queue_position: 1, poll_after_ms: 1000 }
      : { job_id: jobId, status: 'failed', queue_position: null, poll_after_ms: 1000, error: { code: 'MODEL_UNAVAILABLE', message: '모델 실행을 완료하지 못했습니다.' } }, options?.method === 'POST' ? 202 : 200));
    vi.useFakeTimers(); await click('새 기획 생성'); await act(async () => vi.advanceTimersByTimeAsync(1000));
    expect(host.querySelector('[aria-label="접수한 기획 요청 상태"]')?.textContent).toContain('기획 생성 실패');
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('모델 실행을 완료하지 못했습니다');
    expect(host.textContent).toContain(REAL_RESEARCH_BUNDLE.sources[0].text);
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).toBeNull();
    expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
    expect(sessionStorage.getItem('lgax.research.pending-job')).toBeNull();
  });
  it('restores only a saved job status through the current principal and does not retry its original POST', async () => {
    const jobId = '5'.repeat(32); sessionStorage.setItem('lgax.research.pending-job', jobId);
    const fetch = api(); vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(ResearchPlanningView))); await connect();
    expect(fetch.mock.calls.some(call => String(call[0]).includes('/api/prototype/jobs/'))).toBe(false);
    fetch.mockImplementation(async () => response({ job_id: jobId, status: 'completed', queue_position: null, poll_after_ms: 1000, result: heldBrief() }));
    await click('접수한 요청 상태 확인');
    expect(host.textContent).toContain('이 상태 조회만으로 자료 선택·기획 결과를 복원하지 않습니다');
    expect(host.textContent).toContain(REAL_RESEARCH_BUNDLE.bundle_id); expect(host.textContent).toContain(heldBrief().run_id);
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).toBeNull();
    const reads = fetch.mock.calls.filter(call => call[0] === `/api/prototype/jobs/${jobId}`);
    expect(reads).toHaveLength(1); expect(reads[0][1]?.method).toBe('GET');
    expect(new Headers(reads[0][1]?.headers).get('Authorization')).toBe(`Bearer ${'x'.repeat(40)}`);
    expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0);
    expect(Object.keys(sessionStorage)).toEqual(['lgax.research.pending-job']);
  });
  it('recovers an owner job through GET current after the first accepted response is lost, without POST replay', async () => {
    const jobId = '6'.repeat(32);
    const fetch = api(); vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement<NonNullable<Parameters<typeof ResearchPlanningView>[0]>>(ResearchPlanningView, { sharedSession: { shared_prototype: true, token: 's'.repeat(48) } }))); await choose();
    fetch.mockImplementation(async (url: string, options?: RequestInit) => {
      if (options?.method === 'POST') throw new Error('transport response lost');
      if (url === '/api/prototype/jobs/current') return response({ job_id: jobId, status: 'running', queue_position: 0, poll_after_ms: 1000 });
      return response({}, 404);
    });
    await click('새 기획 생성');
    expect(sessionStorage.getItem('lgax.research.pending-job')).toBeNull();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('연결할 수 없습니다');
    await click('접수한 요청 상태 확인');
    expect(host.querySelector('[aria-label="접수한 기획 요청 상태"]')?.textContent).toContain('기획 생성 실행 중');
    expect(fetch.mock.calls.filter(call => call[0] === '/api/prototype/jobs/current')).toHaveLength(1);
    expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
    expect(sessionStorage.getItem('lgax.research.pending-job')).toBe(jobId);
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).toBeNull();
  });
  it('keeps shared-session failures explicit and does not silently expose the manual or legacy interface', async () => {
    const fetch = vi.fn().mockResolvedValue(response({}, 503)); vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(App)));
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('공유 프로토타입 연결을 확인하지 못했습니다');
    expect(host.querySelector('#research-token')).toBeNull();
    expect(host.querySelectorAll('nav[aria-label="기획 작업 영역"] button')).toHaveLength(1);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('rejects a malformed shared credential without persisting it or automatically repeating the session request', async () => {
    const transport = vi.fn().mockResolvedValue(response({ shared_prototype: true, token: 'invalid session value' }));
    const load = createSharedSessionLoader(transport);
    await expect(load()).rejects.toThrow('공유 프로토타입 연결을 확인하지 못했습니다');
    await expect(load()).rejects.toThrow('공유 프로토타입 연결을 확인하지 못했습니다');
    expect(transport).toHaveBeenCalledTimes(1);
  });
  it('does not fetch or offer invented results before authentication, and clearly shows endpoint pending', async () => {
    const fetch = vi.fn().mockResolvedValue(response({ error: { code: 'NOT_IMPLEMENTED' } }, 501)); vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(ResearchPlanningView)));
    expect(fetch).not.toHaveBeenCalled(); expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).toBeNull();
    await connect(); expect(host.textContent).toContain('연결 대기'); expect(host.textContent).not.toContain('기획 초안 생성 완료');
    expect(host.querySelector<HTMLInputElement>('#research-token')!.value).toBe('');
  });
  it('uses actual source text, keeps absent negative summaries and creates a captured condition revision', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(ResearchPlanningView)));
    await connect(); await choose();
    expect(host.textContent).toContain(REAL_RESEARCH_BUNDLE.sources[0].text);
    expect(host.textContent).toContain('구매 모델 미확인');
    expect(host.querySelector('[required]')).toBeNull();
    await click('새 기획 생성');
    expect(host.textContent).toContain('추가 자료 필요');
    expect(host.querySelector('.summary-negative')!.textContent).toContain('확인된 요약 없음');
    await click('현재 결과에서 조건 변경'); expect(host.textContent).toContain('목적이나 조건을 바꾼 뒤');
    expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
    await enter('#research-extra-constraints', '하드웨어 변경 없이 개선');
    fetch.mockImplementation(async (url: string, options?: RequestInit) => {
      if (url.endsWith('/planning-runs') && options?.method === 'POST') {
        const input = JSON.parse(String(options.body));
        return response({ ...heldBrief(), brief_id: 'TEST-next', run_id: 'TEST-next-run', revision: 1, previous_brief_id: heldBrief().brief_id, constraints: input.constraints });
      }
      return response({}, 404);
    });
    await click('현재 결과에서 조건 변경');
    const writes = fetch.mock.calls.filter(call => call[1]?.method === 'POST');
    expect(JSON.parse(String(writes[1][1].body)).previous_run_id).toBe(heldBrief().run_id);
    expect(host.querySelectorAll('#research-run-choice option')).toHaveLength(3);
    await click('연결 해제'); expect(host.textContent).not.toContain(REAL_RESEARCH_BUNDLE.sources[0].text);
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).toBeNull();
  });
  it('does not duplicate a pending POST or show its delayed result after disconnect', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(ResearchPlanningView))); await connect(); await choose();
    let finish!: (value: Response) => void;
    fetch.mockImplementation(() => new Promise<Response>(resolve => { finish = resolve; }));
    await act(async () => { const button = [...host.querySelectorAll<HTMLButtonElement>('button')].find(item => item.textContent === '새 기획 생성')!; button.click(); button.click(); });
    expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
    await click('연결 해제'); await act(async () => finish(response(heldBrief())));
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).toBeNull(); expect(host.textContent).toContain('자료 연결을 기다리고');
  });
  it('navigates to sources and saved results without a request or changing the planning selection', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch);
    await act(async () => root.render(createElement(ResearchPlanningView))); await connect(); await choose();
    const navigation = host.querySelector('nav[aria-label="실제 자료 작업실 바로가기"]')!;
    expect(navigation.querySelector('a[href="#research-results"]')).toBeNull();
    const select = host.querySelector<HTMLInputElement>('.research-source-check input')!;
    await act(async () => select.click());
    const beforeNavigation = fetch.mock.calls.length;
    await act(async () => navigation.querySelector<HTMLAnchorElement>('a[href="#research-sources"]')!.click());
    expect(document.activeElement?.id).toBe('research-sources');
    expect(fetch.mock.calls).toHaveLength(beforeNavigation);
    expect(select.checked).toBe(true);
    await click('새 기획 생성');
    expect(document.activeElement?.id).toBe('research-results');
    expect(navigation.querySelector('a[href="#research-concepts"]')).not.toBeNull();
    expect(host.querySelector('[aria-label="첫 문제의 기획 연결 요약"]')?.textContent).toContain('명시적으로 연결된 개선안이 없습니다');
    const beforeResultNavigation = fetch.mock.calls.length;
    await act(async () => navigation.querySelector<HTMLAnchorElement>('a[href="#research-relations"]')!.click());
    expect(document.activeElement?.id).toBe('research-relations');
    expect(fetch.mock.calls).toHaveLength(beforeResultNavigation);
    expect(select.checked).toBe(true);
  });
  it('keeps actual source browsing available when model generation is not activated', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(ResearchPlanningView))); await connect(); await choose();
    fetch.mockImplementation(() => Promise.resolve(response({ error: { code: 'NOT_IMPLEMENTED' } }, 501)));
    await click('새 기획 생성');
    expect(host.textContent).toContain('실제 자료 조회는 연결됐습니다. 모델 실행 활성화를 기다리고 있습니다.');
    expect(host.querySelectorAll('.research-source-row')).toHaveLength(1);
    expect(host.textContent).toContain(REAL_RESEARCH_BUNDLE.sources[0].text);
    expect(host.querySelector('[aria-label="실제 자료 기획 결과"]')).toBeNull();
  });
  // V1 first stage (record 최길웅-20261008-060). The brief is a hand-written contract object, not model output.
  it('exports a concept as a future-concept storyboard from the result card without another request', async () => {
    const source = REAL_RESEARCH_BUNDLE.sources[0].source_id;
    const withConcept: PlanningBrief = { ...heldBrief(), status: 'complete',
      problems: [{ id: 'PROBLEM-T1', title: '안쪽 식품 확인', description: '깊은 칸 안쪽이 잘 보이지 않는다', source_ids: [source], counter_source_ids: [], scope_caveat: '제품군 탐색' }],
      concepts: [{ id: 'CONCEPT-T1', title: '깊은 칸 안쪽 보기', problem_ids: ['PROBLEM-T1'], target_user: '맞벌이 가구', use_context: '주말 장보기 뒤 정리',
        before_steps: ['안쪽 식품을 꺼내 확인한다'], after_steps: ['문을 열면 안쪽 칸을 비춘다'], mechanism: '문 열림 감지로 안쪽 조명을 켠다', proposed_changes: [],
        source_ids: [source], assumptions: [], validation_questions: ['안쪽 확인 빈도는?'], status: 'draft',
        visual_scenes: [{ title: '장면 1', before: '안쪽을 들여다본다', after: '조명으로 바로 보인다' }] }] };
    const downloads: Array<{ name: string; content: string }> = [];
    vi.spyOn(views, 'download').mockImplementation((name, _type, content) => { downloads.push({ name, content }); });
    const fetch = vi.fn().mockImplementation(async (url: string, options?: RequestInit) => {
      if (url.endsWith('/bundles')) return response({ bundles: [{ bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, product_group: 'fridge', analysis_scope: 'product_group', source_count: 1, review_count: 1 }] });
      if (url.includes('/bundles/')) return response(REAL_RESEARCH_BUNDLE);
      if (url.endsWith('/planning-runs') && options?.method === 'POST') return response(withConcept);
      return response({ error: { code: 'NOT_FOUND' } }, 404);
    });
    vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(ResearchPlanningView)));
    await connect(); await choose(); await click('새 기획 생성');
    expect(host.querySelector('[aria-label="깊은 칸 안쪽 보기 콘셉트 스토리보드"]')?.textContent).toContain('실제 성능 증거가 아닙니다');
    const requests = fetch.mock.calls.length;
    await click('스토리보드 Markdown');
    expect(fetch.mock.calls).toHaveLength(requests);
    expect(downloads).toHaveLength(1);
    expect(downloads[0].name).toBe('storyboard-TEST-held-run-r0-CONCEPT-T1.md');
    expect(downloads[0].content).toContain('미래 콘셉트 시안입니다');
    expect(downloads[0].content).toContain("개선안 상태가 '제안 초안'입니다");
    expect(downloads[0].content).toContain('| S02 | 지금 | 장면 1 |');
    vi.restoreAllMocks();
  });
  // A11Y-1 (record 최길웅-20261008-061): the detail opens above the list, so keyboard and screen-reader users must be
  // taken to it, and brought back to the citation they came from when it closes.
  it('moves focus into an opened source detail and back to the citation when it closes', async () => {
    // jsdom has no scrollIntoView; the screen scrolls the source panel into view when a citation opens.
    const scroll = vi.fn(); Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { value: scroll, configurable: true, writable: true });
    vi.stubGlobal('fetch', api()); await act(async () => root.render(createElement(ResearchPlanningView)));
    await connect(); await choose();
    const cite = host.querySelector<HTMLButtonElement>('.research-source-row .research-citations button')!;
    await act(async () => { cite.focus(); cite.click(); });
    const detail = host.querySelector('[aria-label="인용 원문 상세"]')!;
    expect(detail).not.toBeNull();
    expect(document.activeElement).toBe(detail.querySelector('h3'));
    await click('상세 닫기');
    expect(host.querySelector('[aria-label="인용 원문 상세"]')).toBeNull();
    expect(document.activeElement).toBe(cite);
    expect(scroll).toHaveBeenCalledTimes(1);
    delete (HTMLElement.prototype as unknown as { scrollIntoView?: unknown }).scrollIntoView;
  });
  it('plans from an explicit source selection and inherits that range after the current checkboxes change', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(ResearchPlanningView))); await connect(); await choose();
    const selectedButton = () => [...host.querySelectorAll<HTMLButtonElement>('button')].find(item => item.textContent?.startsWith('선택 근거로 새 기획 생성'))!;
    expect(selectedButton().disabled).toBe(true);
    await click('표시 자료 모두 선택'); expect(selectedButton().disabled).toBe(false);
    const first = heldBrief(); first.source_facts = REAL_RESEARCH_BUNDLE.sources.map(source => ({ source_id: source.source_id, facts: source.facts }));
    first.runtime = { input_scope: 'user_selected_sources', user_selected_source_ids: REAL_RESEARCH_BUNDLE.sources.map(source => source.source_id), selected_source_ids: [] };
    fetch.mockResolvedValue(response(first));
    await act(async () => selectedButton().click());
    const firstRequest = JSON.parse(String(fetch.mock.calls.filter(call => call[1]?.method === 'POST')[0][1].body));
    expect(firstRequest.selected_source_ids).toEqual(first.runtime.user_selected_source_ids);
    expect(host.querySelector('[data-planning-input-scope]')?.textContent).toContain('사용자 선택 원문 1건');
    await click('전체 선택 해제'); expect(selectedButton().disabled).toBe(true);
    await enter('#research-extra-constraints', '하드웨어 변경 없이 개선');
    const next = { ...first, run_id: 'TEST-selected-next-run', brief_id: 'TEST-selected-next', revision: 1, previous_brief_id: first.brief_id,
      constraints: [...first.constraints, '하드웨어 변경 없이 개선'] };
    fetch.mockResolvedValue(response(next)); await click('현재 결과에서 조건 변경');
    const revisionRequest = JSON.parse(String(fetch.mock.calls.filter(call => call[1]?.method === 'POST')[1][1].body));
    expect(revisionRequest).not.toHaveProperty('selected_source_ids'); expect(revisionRequest.previous_run_id).toBe(first.run_id);
    expect(host.querySelector('[data-planning-input-scope]')?.textContent).toContain('사용자 선택 원문 1건');
    expect(host.querySelector('#research-run-choice')?.textContent).toContain(next.run_id);
  });
  // Record 최길웅-20261008-067: summary citation coverage is shown only from a consistent runtime block; absent stays absent.
  it('shows summary citation coverage from the brief and says so when it is not provided', async () => {
    const source = REAL_RESEARCH_BUNDLE.sources[0].source_id;
    const coverage = { basis: 'returned_summary_references_on_successful_discovery', sample_unit: 'unique_deduplicated_customer_source',
      summary_item_counts: { positive: 1, negative: 0, mixed: 0 }, polarity_source_counts: { positive: 1, negative: 0, mixed: 0 },
      polarity_source_ids: { positive: [source], negative: [], mixed: [] }, input_customer_source_count: 1, denominator_customer_source_count: 1,
      denominator_source_ids: [source], covered_customer_source_count: 1, covered_source_ids: [source], unreferenced_processed_source_count: 0,
      unprocessed_input_source_count: 0, overlapping_polarity_source_count: 0, coverage_ratio: 1, classification_approved: false, market_frequency_estimated: false };
    const withCoverage: PlanningBrief = { ...heldBrief(), source_facts: [{ source_id: source, facts: [] }], runtime: { summary_reference_coverage: coverage } };
    const fetch = vi.fn().mockImplementation(async (url: string, options?: RequestInit) => {
      if (url.endsWith('/bundles')) return response({ bundles: [{ bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, product_group: 'fridge', analysis_scope: 'product_group', source_count: 1, review_count: 1 }] });
      if (url.includes('/bundles/')) return response(REAL_RESEARCH_BUNDLE);
      if (url.endsWith('/planning-runs') && options?.method === 'POST') return response(withCoverage);
      return response({ error: { code: 'NOT_FOUND' } }, 404);
    });
    vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(ResearchPlanningView)));
    await connect(); await choose(); await click('새 기획 생성');
    expect(host.querySelector('[data-summary-coverage="ok"]')?.textContent).toContain('처리된 고객 원문 1건 중 1건 인용(인용률 100%)');
    expect(host.querySelector('[data-summary-polarity-coverage="positive"]')?.textContent).toBe('고객 원문 1건 인용 · 요약 1개');
    await act(async () => root.render(createElement('div')));
    vi.stubGlobal('fetch', api()); await act(async () => root.render(createElement(ResearchPlanningView)));
    await connect(); await choose(); await click('새 기획 생성');
    expect(host.querySelector('[data-summary-coverage="not_provided"]')?.textContent).toContain('제공되지 않았습니다');
    expect(host.querySelector('[data-summary-polarity-coverage]')).toBeNull();
  });
});
