// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { act, createElement, createRef } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ResearchSourcesPanel } from './ResearchSourcesPanel';
import manualSource from './fixtures/research-actual-manual-source.json';
import type { ResearchBundle, ResearchSource } from './research';
import * as views from './PlanningViews';

const source = manualSource as unknown as ResearchSource;
const bundle: ResearchBundle = { schema_version: '1.0', bundle_id: 'WEB-actual-manual-UI-check', product_group: 'microwave', analysis_scope: 'product_group',
  sources: [source], collection_manifest: { independent_evaluation_approved: false, limitations: ['Purposive UI sample'], review_count: 0 } };
const hosts: HTMLDivElement[] = []; const roots: ReturnType<typeof createRoot>[] = [];
afterEach(async () => { for (const root of roots.splice(0)) await act(async () => root.unmount()); hosts.splice(0).forEach(host => host.remove()); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function mount(inspectId = '', data: ResearchBundle = bundle) {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('fetch', vi.fn());
  const host = document.createElement('div'); document.body.append(host); hosts.push(host); const root = createRoot(host); roots.push(root);
  await act(async () => root.render(createElement(ResearchSourcesPanel, { bundle: data, brief: null, inspectId, onInspect: vi.fn(), onCloseInspect: vi.fn(), panelRef: createRef<HTMLElement>(), sourceBundleHash: 'c'.repeat(64) })));
  return host;
}
async function changeSelect(host: HTMLDivElement, label: string, value: string) {
  const field = [...host.querySelectorAll<HTMLLabelElement>('label')].find(item => item.textContent?.startsWith(label))!.querySelector<HTMLSelectElement>('select')!;
  await act(async () => { field.value = value; field.dispatchEvent(new Event('change', { bubbles: true })); });
}
async function click(host: HTMLDivElement, text: string) { await act(async () => [...host.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === text)!.click()); }

describe('source filters, plain-language limits and selection UI', () => {
  it('keeps unknown dates separately selectable and shows Korean source limits before the raw manifest', async () => {
    const host = await mount();
    expect(host.querySelectorAll('.research-source-row')).toHaveLength(1);
    expect(host.textContent).toContain('게시일 미확인'); expect(host.textContent).not.toContain('미확인 미확인');
    expect(host.querySelector('[aria-label="자료의 핵심 한계"]')?.textContent).toContain('일부 발췌 1건');
    expect(host.querySelector('[aria-label="자료의 핵심 한계"]')?.textContent).toContain('전체 시장');
    await changeSelect(host, '게시일 확인 여부', 'confirmed'); expect(host.querySelectorAll('.research-source-row')).toHaveLength(0);
    await changeSelect(host, '게시일 확인 여부', 'unknown'); expect(host.querySelectorAll('.research-source-row')).toHaveLength(1);
    expect([...host.querySelectorAll<HTMLInputElement>('input[type=date]')].every(input => input.disabled)).toBe(true);
    await changeSelect(host, '페이지 모델', source.page_model!); expect(host.querySelectorAll('.research-source-row')).toHaveLength(1);
  });
  it('retains a visible count for selections outside the filter and exports original facts without a planning POST', async () => {
    const downloaded: Array<{ content: string; type: string }> = [];
    vi.spyOn(views, 'download').mockImplementation((_name, type, content) => { downloaded.push({ content, type }); });
    const host = await mount();
    await click(host, '표시 자료 모두 선택'); await changeSelect(host, '원문 자료 유형', 'review');
    expect(host.textContent).toContain('현재 필터 밖 선택 1건');
    await click(host, '자료 파일 (.json)');
    await vi.waitFor(() => expect(downloaded).toHaveLength(1));
    const exported = JSON.parse(downloaded[0].content);
    expect(exported.sources[0]).toEqual(source); expect(exported.collection_manifest.planning_executed).toBe(false);
    expect(exported.collection_manifest.selection).toMatchObject({ source_bundle_id: bundle.bundle_id, review_text_edits: 0, facts_edits: 0, independent_evaluation_approved: false });
    expect(fetch).not.toHaveBeenCalled(); expect(host.textContent).toContain('원래 선택한 자료 묶음');
    await click(host, '전체 선택 해제'); expect(host.textContent).toContain('선택 0건');
  });
  it('shows where each original sits (page and section) in the row, the detail, its facts and the Markdown export', async () => {
    const downloaded: string[] = [];
    vi.spyOn(views, 'download').mockImplementation((_name, _type, content) => { downloaded.push(content); });
    const host = await mount(source.source_id);
    expect(host.querySelector('.research-source-row')?.textContent).toContain('위치 25쪽 · 항목 「출력 조절」');
    expect(host.querySelector('[data-source-locator]')?.textContent).toBe('원문 위치: 25쪽 · 항목 「출력 조절」');
    expect(host.querySelector('.research-source-detail li')?.textContent).toContain('위치 25쪽 · 항목 「출력 조절」');
    expect(host.querySelector('.research-locator-technical')).toBeNull();
    await click(host, '표시 자료 모두 선택'); await click(host, '자료 노트 (.md)');
    await vi.waitFor(() => expect(downloaded).toHaveLength(1));
    expect(downloaded[0]).toContain('원문 위치: 25쪽 · 항목 「출력 조절」');
    expect(downloaded[0]).toContain('(위치: 25쪽 · 항목 「출력 조절」)');
  });
  // O-R8-2 (DATA reply #6 6040922039): a review's document_version is the page model's linked reference material,
  // not the review's edition or the purchased SKU's manual, so it is not labelled as the review's document edition.
  it('labels a review version as the page model reference material and keeps a manual version as its edition', async () => {
    const manualHost = await mount(source.source_id);
    expect(manualHost.querySelector('[data-document-version]')?.textContent).toBe(`문서판: ${source.document_version}`);
    expect(manualHost.querySelector('[data-document-version-note]')).toBeNull();
    const review = { ...source, source_id: 'LGE-R8-REVIEW-TEST', source_type: 'review', source_role: 'customer_experience', coverage: 'full',
      document_version: 'MFL71959117 Rev.07_030626', facts: [], locator: { original_review_id: 'TEST' } } as ResearchSource;
    const reviewHost = await mount(review.source_id, { ...bundle, sources: [review] });
    expect(reviewHost.querySelector('[data-document-version]')?.textContent).toBe('페이지 모델의 연결 참고자료 버전: MFL71959117 Rev.07_030626');
    expect(reviewHost.querySelector('[data-document-version-note]')?.textContent).toContain('구매 당시 설명서 판을 확인한 값이 아닙니다');
    expect(reviewHost.querySelector('.research-source-detail')?.textContent).not.toContain('문서판');
  });
});
