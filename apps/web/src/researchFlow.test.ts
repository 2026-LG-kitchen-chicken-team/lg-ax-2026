// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ResearchPlanningView } from './ResearchPlanningView';
import App from './App';
import { heldBrief, REAL_RESEARCH_BUNDLE } from './fixtures/research-test-data';

describe('actual-source research screen state and revision flow', () => {
  let host: HTMLDivElement; let root: Root;
  const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
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
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); await act(async () => root.render(createElement(App)));
    expect(host.querySelector('[aria-label="실제 자료 작업실 연결"]')).not.toBeNull();
    expect(host.textContent).not.toContain('계약 fixture'); expect(fetch).not.toHaveBeenCalled();
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
});
