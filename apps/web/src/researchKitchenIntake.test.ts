// @vitest-environment jsdom
// Frozen actual public excerpts. HTTP/download mocks verify UI scope, never model quality or native Save As.
import { webcrypto } from 'node:crypto';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import kimchiPack from '../../../data/research/r9-kitchen-intake-20261008/kimchi_refrigerator.research-bundle.json';
import ovenPack from '../../../data/research/r9-kitchen-intake-20261008/lightwave_oven.research-bundle.json';
import { ResearchPlanningView } from './ResearchPlanningView';
import { researchGroupLabel } from './research';
import type { ResearchBundle } from './research';
import { koreanSourceLimitations } from './researchSources';
import * as views from './PlanningViews';

const kimchi = kimchiPack as unknown as ResearchBundle;
const oven = ovenPack as unknown as ResearchBundle;
const packs = [kimchi, oven];
let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  host?.remove(); root = null; host = null; vi.restoreAllMocks(); vi.unstubAllGlobals();
});
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
async function click(view: HTMLElement, text: string) {
  await act(async () => [...view.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === text)!.click());
}
async function choose(view: HTMLElement, selector: string, value: string) {
  await act(async () => { const field = view.querySelector<HTMLSelectElement>(selector)!; field.value = value; field.dispatchEvent(new Event('change', { bubbles: true })); });
}

describe('actual kitchen public intake labels and scope', () => {
  it('uses each bundle’s actual review scope, retains missing identity/dates/SKU, and separates official-only material', () => {
    const before = JSON.stringify(packs);
    expect(researchGroupLabel(kimchi.product_group)).toBe('김치냉장고');
    expect(researchGroupLabel(oven.product_group)).toBe('광파오븐');
    const kimchiLimits = koreanSourceLimitations(kimchi).join('\n');
    expect(kimchiLimits).toContain('후기 미리보기 발췌 3건');
    expect(kimchiLimits).toContain('전체 후기 본문·전체 후기 수와 독립적인 후기 수는 확인되지 않았습니다');
    expect(kimchiLimits).toContain('후기 3/3건의 사이트 원 후기 ID가 미확인');
    expect(kimchiLimits).toContain('후기 3/3건의 게시일이 미확인');
    expect(kimchiLimits).toContain('후기 3/3건의 구매 모델이 미확인');
    expect(kimchiLimits).toContain('시연용 자료 사용은 아직 승인되지 않았습니다');
    const ovenLimits = koreanSourceLimitations(oven).join('\n');
    expect(ovenLimits).toContain('고객 후기 0건');
    expect(ovenLimits).toContain('공식 제품 기능·참고 설명만');
    expect(ovenLimits).toContain('고객의 불편이나 불편 해결을 확인·승인한 근거가 아닙니다');
    expect(ovenLimits).not.toContain('후기 미리보기 발췌 3건');
    expect(ovenLimits).toContain('독립평가용 사용은 승인되지 않았습니다');
    expect(JSON.stringify(packs)).toBe(before);
  });

  it('connects with the real client, labels R9 intake before defaults and reuses original filtering/selection without any POST', async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); vi.stubGlobal('crypto', webcrypto);
    const originals = structuredClone(packs);
    const transport = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (init?.method !== 'GET') throw new Error('TEST ONLY: no planning or guide POST in source intake inspection');
      if (url === '/api/research/bundles') return response({ bundles: packs.map(pack => ({
        bundle_id: pack.bundle_id, product_group: pack.product_group, analysis_scope: pack.analysis_scope,
        source_count: pack.sources.length, review_count: pack.sources.filter(source => source.source_type === 'review').length,
      })) });
      const pack = packs.find(item => url === `/api/research/bundles/${encodeURIComponent(item.bundle_id)}`);
      return response(pack ?? { error: { code: 'NOT_FOUND' } }, pack ? 200 : 404);
    });
    vi.stubGlobal('fetch', transport);
    const saved: string[] = []; vi.spyOn(views, 'download').mockImplementation((_name, _type, content) => { saved.push(content); });
    const view = document.createElement('div'); host = view; document.body.append(view); root = createRoot(view);
    await act(async () => root!.render(createElement(ResearchPlanningView)));
    await act(async () => {
      const token = view.querySelector<HTMLInputElement>('#research-token')!;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(token, 'TEST-ONLY-kitchen-intake-credential-20261008');
      token.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => view.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    const options = [...view.querySelectorAll<HTMLOptionElement>('#research-bundle option')].filter(option => option.value);
    expect(options).toHaveLength(2);
    expect(options.every(option => option.textContent?.includes('추가 수집 자료'))).toBe(true);
    expect(options.some(option => option.textContent?.includes('리뷰·제품 문서'))).toBe(false);
    expect(options[0].textContent).toContain('김치냉장고'); expect(options[1].textContent).toContain('광파오븐');
    await choose(view, '#research-bundle', kimchi.bundle_id);
    expect(view.querySelectorAll('.research-source-row')).toHaveLength(6);
    expect(view.querySelector('[aria-label="자료의 핵심 한계"]')?.textContent).toContain('사이트 원 후기 ID가 미확인');
    await choose(view, '#research-source-type', 'review');
    expect(view.querySelectorAll('.research-source-row')).toHaveLength(3);
    const selected = kimchi.sources.find(source => source.source_type === 'review')!;
    await act(async () => view.querySelector<HTMLInputElement>('.research-source-check input')!.click());
    await click(view, '자료 파일 (.json)'); await vi.waitFor(() => expect(saved).toHaveLength(1));
    const exported = JSON.parse(saved[0]);
    expect(exported.sources).toEqual([selected]);
    expect(exported.collection_manifest.planning_executed).toBe(false);
    expect(exported.collection_manifest.demonstration_approved).toBe(false);
    await choose(view, '#research-bundle', oven.bundle_id);
    expect(view.querySelectorAll('.research-source-row')).toHaveLength(4);
    expect(view.querySelector('[aria-label="자료의 핵심 한계"]')?.textContent).toContain('고객 후기 0건');
    expect(view.textContent).toContain('선택 0건');
    expect(transport.mock.calls.every(call => call[1]?.method === 'GET')).toBe(true);
    expect(packs).toEqual(originals);
  });
});
