// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ResearchPlanningView } from './ResearchPlanningView';
import App from './App';
import { heldBrief, REAL_RESEARCH_BUNDLE } from './fixtures/research-test-data';
import * as views from './PlanningViews';
import type { PlanningBrief } from './research';

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
  });
});
