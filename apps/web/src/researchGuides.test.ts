// @vitest-environment jsdom
// Existing public document/review captures; mock HTTP exports test transport/UI, not model quality or browser Save As.
import { act, createElement, createRef } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import manualPack from '../../../data/research/r9-public-runtime-20261008/microwave.manual-reference.research-bundle.json';
import microwavePack from '../../../data/research/r9-public-runtime-20261008/microwave.research-bundle.json';
import factBearingManual from './fixtures/research-actual-manual-source.json';
import { ResearchClient } from './researchClient';
import { ResearchSourcesPanel } from './ResearchSourcesPanel';
import { ResearchPlanningView } from './ResearchPlanningView';
import type { ResearchBundle, ResearchGuideExport } from './research';
import * as views from './PlanningViews';

const bundle = manualPack as unknown as ResearchBundle;
const microwave = microwavePack as unknown as ResearchBundle;
const ids = bundle.sources.map(source => source.source_id); const hash = 'b'.repeat(64);
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
function guideResponse(selected = ids): ResearchGuideExport {
  return { bundle_id: bundle.bundle_id, bundle_sha256: hash, source_ids: selected,
    guide: { guide_version: '1.0', guide_kind: 'official_reference', bundle_id: bundle.bundle_id,
      title: '공식 참고자료 발췌 안내', notice: '공식 원문 참고자료입니다. 전체 정식 설명서를 대체하지 않습니다.',
      sources: structuredClone(bundle.sources.filter(source => selected.includes(source.source_id))), proposal: null, exact_sku_applicability_confirmed: false },
    markdown: '# 공식 참고자료 발췌 안내\n전체 정식 설명서를 대체하지 않습니다.\n',
    html: '<!doctype html><html lang="ko"><body><article id="guide-export-only">공식 원문 참고자료</article></body></html>' };
}
function transportFor(result: ResearchGuideExport = guideResponse()) {
  return vi.fn().mockImplementation(async (url: string) => response(url.endsWith('/bundles')
    ? { bundles: [{ bundle_id: bundle.bundle_id, product_group: 'microwave', analysis_scope: bundle.analysis_scope, bundle_sha256: hash }] } : result));
}
const clientFor = (transport: typeof fetch) => new ResearchClient(() => 'a'.repeat(40), transport);
const hosts: HTMLDivElement[] = []; const roots: ReturnType<typeof createRoot>[] = [];
afterEach(async () => { for (const root of roots.splice(0)) await act(async () => root.unmount()); hosts.splice(0).forEach(host => host.remove()); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function panel(transport: typeof fetch) {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const api = clientFor(transport); await api.listBundles();
  const host = document.createElement('div'); document.body.append(host); hosts.push(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => root.render(createElement(ResearchSourcesPanel, { bundle, brief: null, inspectId: '', onInspect: vi.fn(),
    onCloseInspect: vi.fn(), panelRef: createRef<HTMLElement>(), sourceBundleHash: hash, guideClient: api })));
  return { host, root };
}
async function click(host: HTMLElement, text: string) {
  await act(async () => [...host.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === text)!.click());
}

describe('official reference guide export', () => {
  it('normalizes explicit official sources and checks original sources/facts plus the frozen hash', async () => {
    const selected = ids.slice(0, 2); const result = guideResponse(selected); const transport = transportFor(result);
    const api = clientFor(transport); await api.listBundles();
    expect(await api.createGuide(bundle, [...selected].reverse())).toEqual(result);
    expect(JSON.parse(transport.mock.calls[1][1].body)).toEqual({ bundle_id: bundle.bundle_id, source_ids: selected, bundle_sha256: hash });
    expect(transport.mock.calls[1][0]).toBe('/api/research/guides');
    expect(transport.mock.calls[1][1].headers.Authorization).toBe(`Bearer ${'a'.repeat(40)}`);
  });

  it('refuses a review or customer question mixed into official selection without a POST or silent omission', async () => {
    const official = microwave.sources.find(source => source.source_type === 'manual')!;
    const review = microwave.sources.find(source => source.source_type === 'review')!;
    const question = microwave.sources.find(source => source.source_role === 'customer_question');
    const transport = vi.fn(); const api = clientFor(transport);
    await expect(api.createGuide(microwave, [official.source_id, review.source_id])).rejects.toThrow('자동으로 누락하지 않습니다');
    if (question) await expect(api.createGuide(microwave, [official.source_id, question.source_id])).rejects.toThrow('공식 답변만');
    const misleadingHost = structuredClone(bundle); misleadingHost.sources[0].url = 'https://lge.com.example.invalid/manual';
    await expect(api.createGuide(misleadingHost, ids.slice(0, 1))).rejects.toThrow('공식 설명서');
    expect(transport).not.toHaveBeenCalled();
  });

  it('rejects changed bundle version, selected IDs, original facts and an asserted SKU approval', async () => {
    const selected = ids.slice(0, 1); const valid = guideResponse(selected);
    const wrongHash = structuredClone(valid); wrongHash.bundle_sha256 = 'c'.repeat(64);
    const wrongIds = structuredClone(valid); wrongIds.source_ids = ids.slice(1, 2);
    // This new excerpt has no extracted facts; an extra fact copied from another real manual is also corruption.
    const wrongFacts = structuredClone(valid); wrongFacts.guide.sources[0].facts = structuredClone(factBearingManual.facts) as ResearchBundle['sources'][number]['facts'];
    const approved = structuredClone(valid) as unknown as { guide: { exact_sku_applicability_confirmed: boolean } }; approved.guide.exact_sku_applicability_confirmed = true;
    for (const value of [wrongHash, wrongIds, wrongFacts, approved]) {
      const transport = transportFor(); const api = clientFor(transport); await api.listBundles(); transport.mockResolvedValue(response(value));
      await expect(api.createGuide(bundle, selected)).rejects.toThrow();
    }
  });

  it('exports HTML/Markdown as files and keeps the HTML outside the application DOM', async () => {
    const result = guideResponse(); const transport = transportFor(result); const saved: Array<{ name: string; content: string }> = [];
    vi.spyOn(views, 'download').mockImplementation((name, _type, content) => { saved.push({ name, content }); });
    const { host } = await panel(transport);
    const htmlButton = [...host.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === '선택 공식자료 안내서 HTML')!;
    expect(htmlButton.disabled).toBe(true);
    await click(host, '표시 자료 모두 선택'); await click(host, '선택 공식자료 안내서 HTML'); await click(host, '선택 공식자료 안내서 Markdown');
    expect(saved).toEqual([{ name: `official-guide-${bundle.bundle_id}.html`, content: result.html }, { name: `official-guide-${bundle.bundle_id}.md`, content: result.markdown }]);
    expect(host.querySelector('#guide-export-only')).toBeNull();
    expect(host.querySelector('iframe')).toBeNull(); expect(host.textContent).toContain('구매 SKU의 적용을 확정하지 않습니다');
    expect(transport.mock.calls.filter(call => call[0] === '/api/research/guides')).toHaveLength(2);
    expect(transport.mock.calls.some(call => String(call[0]).includes('planning-runs'))).toBe(false);
  });

  it('locks a pending export, avoids duplicate requests and drops late results after the source view closes', async () => {
    const transport = transportFor(); const { host, root } = await panel(transport); await click(host, '표시 자료 모두 선택');
    let finish!: (value: Response) => void; transport.mockImplementation(() => new Promise<Response>(resolve => { finish = resolve; }));
    const save = vi.spyOn(views, 'download').mockImplementation(() => {});
    await act(async () => { const button = [...host.querySelectorAll<HTMLButtonElement>('button')].find(item => item.textContent === '선택 공식자료 안내서 HTML')!; button.click(); button.click(); });
    expect(transport.mock.calls.filter(call => call[0] === '/api/research/guides')).toHaveLength(1);
    expect(host.querySelector('[role="status"]')?.textContent).toContain('모델은 호출하지 않습니다');
    expect([...host.querySelectorAll<HTMLInputElement>('.research-source-check input')].every(item => item.disabled)).toBe(true);
    await act(async () => root.render(null)); await act(async () => finish(response(guideResponse())));
    expect(save).not.toHaveBeenCalled();
  });

  it('labels default, preserved and document-only bundles, and keeps originals after an export error', async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    const host = document.createElement('div'); document.body.append(host); hosts.push(host); const root = createRoot(host); roots.push(root);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ bundles: [
      { bundle_id: microwave.bundle_id, product_group: 'microwave', analysis_scope: 'product_group', source_count: 53, review_count: 45 },
      { bundle_id: 'LGE-R8-microwave-development-20261007-official-v1', product_group: 'microwave', analysis_scope: 'product_group', source_count: 51, review_count: 45 },
      { bundle_id: bundle.bundle_id, product_group: 'microwave', analysis_scope: bundle.analysis_scope, source_count: 5, review_count: 0 },
    ] })));
    await act(async () => root.render(createElement(ResearchPlanningView)));
    await act(async () => { const token = host.querySelector<HTMLInputElement>('#research-token')!; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(token, 'a'.repeat(40)); token.dispatchEvent(new Event('input', { bubbles: true })); });
    await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    const options = host.querySelector('#research-bundle')!.textContent!;
    expect(options).toContain('R9 기본 자료'); expect(options).toContain('이전 보존 자료'); expect(options).toContain('설명서 참고 · 리뷰 없음'); expect(options).toContain('자료 5 / 리뷰 0');
    const transport = transportFor(); const mounted = await panel(transport); await click(mounted.host, '표시 자료 모두 선택');
    transport.mockResolvedValue(response({ error: { code: 'DATASET_MISMATCH', message: '자료 버전을 다시 확인해 주세요.' } }, 409));
    const save = vi.spyOn(views, 'download').mockImplementation(() => {}); await click(mounted.host, '선택 공식자료 안내서 HTML');
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toContain('자료 버전');
    expect(mounted.host.querySelectorAll('.research-source-row')).toHaveLength(5); expect(save).not.toHaveBeenCalled();
    expect(mounted.host.querySelector('[role="status"]')).toBeNull();
  });
});
