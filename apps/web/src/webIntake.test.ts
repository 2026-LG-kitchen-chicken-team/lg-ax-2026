// @vitest-environment jsdom
// Actual App wiring with synthetic contract examples. No network or model execution is used.
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { enterLegacyEvidence, installManualSessionFixture } from './fixtures/legacy-test-navigation';
import { HistoryView } from './PlanningViews';
import { FIXTURE_BOOTSTRAP, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import type { Feature } from './planning';

describe('PM integrated planner screens', () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline fixture test')));
    host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
  const click = async (label: string) => { await act(async () => {
    const button = [...host.querySelectorAll<HTMLButtonElement>('button')].find(item => item.textContent?.includes(label));
    if (!button) throw new Error(`missing button ${label}`);
    button.click();
  }); };
  it('App reaches the evidence trace and separated revision/clarification panels', async () => {
    installManualSessionFixture(); await act(async () => root.render(createElement(App))); await act(async () => { enterLegacyEvidence(host); });
    await click('계약 fixture'); await click('콘셉트 검토');
    expect(host.querySelector('[aria-label="근거 추적"]')).not.toBeNull();
    expect(host.textContent).toContain('합성 자료');
    await click('수정 이력');
    expect(host.querySelector('[data-revision-timeline]')).not.toBeNull();
    expect([...host.querySelectorAll('.timeline-panel .run-picker option')].map(item => item.getAttribute('value'))).toEqual(FIXTURE_RUNS.map(item => item.run.id));
    expect(host.textContent).toContain('사용자 조건 변경');
    expect(host.querySelector('[aria-label="추가 질문에 답변"]')).not.toBeNull();
    expect(host.querySelector('[aria-label="이전 실행과 결과 비교"]')).not.toBeNull();
  });
  it('keeps the selected candidate original citation list distinct from judgment trace quotations', async () => {
    installManualSessionFixture(); await act(async () => root.render(createElement(App))); await act(async () => { enterLegacyEvidence(host); });
    await click('계약 fixture'); await click('콘셉트 검토');
    const inspect = [...host.querySelectorAll<HTMLButtonElement>('button')].filter(item => item.textContent?.includes('원문·판단 함께 보기'));
    await act(async () => inspect[1].click());
    const review = host.querySelector('[aria-label="후보 상세 검토"]')!;
    expect(review.querySelectorAll('.quote-list')).toHaveLength(2);
    const cited = review.querySelectorAll('ul[aria-label="후보 인용 원문"]');
    expect(cited).toHaveLength(1);
    expect(cited[0].textContent).toContain('선반 분리 방법이 설명서 어디 있는지 모르겠어요.');
    expect(review.querySelector('[aria-label="근거 추적"] ul[aria-label="판단 근거 추적 원문"]')).not.toBeNull();
  });
  it('a cross-project parent cannot leak its candidate or question into comparisons', () => {
    const foreign = structuredClone(FIXTURE_RUNS[0]);
    foreign.run.project_id = 'UNRELATED-PROJECT';
    foreign.run.concepts[0].title = '외부 프로젝트 비공개 후보';
    const selected = FIXTURE_RUNS[1];
    const markup = renderToStaticMarkup(createElement(HistoryView, {
      mode: 'fixture', runs: [foreign, selected], selected, onSelect: () => {}, original: FIXTURE_ORIGINAL_REQUEST,
      features: FIXTURE_BOOTSTRAP.features as unknown as Feature[], evidence: FIXTURE_BOOTSTRAP.evidence,
      onRerun: async () => {}, measure: { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' },
    }));
    expect(markup).toContain('비교를 보류합니다');
    expect(markup).not.toContain('외부 프로젝트 비공개 후보');
    expect(markup).not.toContain('이전 실행과 결과 비교');
  });
  it('holds before/after results if a parent has an invalid Agent-internal revision count', () => {
    const before = structuredClone(FIXTURE_RUNS[0]);
    before.run.revision_count = 3;
    const selected = FIXTURE_RUNS[1];
    const markup = renderToStaticMarkup(createElement(HistoryView, {
      mode: 'fixture', runs: [before, selected], selected, onSelect: () => {}, original: FIXTURE_ORIGINAL_REQUEST,
      features: FIXTURE_BOOTSTRAP.features as unknown as Feature[], evidence: FIXTURE_BOOTSTRAP.evidence,
      onRerun: async () => {}, measure: { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' },
    }));
    expect(markup).toContain('0~2 범위를 벗어납니다');
    expect(markup).toContain('비교를 보류합니다');
    expect(markup).not.toContain('이전 실행과 결과 비교');
  });
  it.each(['pending', 'running'] as const)('does not describe a %s result as removing candidates or resolving questions', status => {
    const waiting = { ...FIXTURE_RUNS[1], output: null, unconfirmed: [], run: { ...FIXTURE_RUNS[1].run, status, concepts: [], unresolved: [] } };
    const markup = renderToStaticMarkup(createElement(HistoryView, {
      mode: 'fixture', runs: [FIXTURE_RUNS[0], waiting], selected: waiting, onSelect: () => {}, original: FIXTURE_ORIGINAL_REQUEST,
      features: FIXTURE_BOOTSTRAP.features as unknown as Feature[], evidence: FIXTURE_BOOTSTRAP.evidence,
      onRerun: async () => {}, measure: { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' },
    }));
    expect(markup).toContain('후보 변화를 비교하지 않습니다');
    expect(markup).toContain('보류·실패·질문을 비교하지 않습니다');
    expect(markup).not.toContain('class="detail-change"');
    expect(markup).not.toContain('이전 실행과 결과 비교');
  });
});
