// @vitest-environment jsdom
// PM-20261006-WEB-MANUAL-FLOW-R1 (record 025): gaps found by walking the real planning workspace with qwen3:8b.
// 1) a save/rerun waits minutes with only a disabled button; 2) core questions embed raw check codes; 3) plain-object
// label tables must not turn inherited keys ("constructor") into functions. Display only — stored data is unchanged.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { reasonText, runSources, violationText } from './judgement';
import { stageLabel } from './liveWorkspace';
import { elapsedText, PendingJudgement } from './PendingJudgement';
import { HistoryView } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import type { RunSnapshot } from './planning';

describe('reasonText labels codes written inside core sentences', () => {
  it('labels a known code in place and keeps the code', () => {
    // Exact question stored by the live run run-e47f242b… (record 025).
    const stored = '판단 근거의 REVIEW_UNCERTAIN 조건을 확인할 수 있는 자료가 있나요?';
    expect(reasonText(stored)).toBe("판단 근거의 '불편인지 불확실한 리뷰를 근거로 썼습니다'(REVIEW_UNCERTAIN) 조건을 확인할 수 있는 자료가 있나요?");
  });

  it('leaves unknown tokens, plain text and already-labelled codes as they are (no stacking)', () => {
    expect(reasonText('판단 근거의 NEW_CORE_CODE 조건')).toBe('판단 근거의 NEW_CORE_CODE 조건');
    expect(reasonText('REVIEW-EVIDENCE-004는 설명서 위치 질문')).toBe('REVIEW-EVIDENCE-004는 설명서 위치 질문');
    const once = reasonText('판단 근거의 SUPPORT_UNKNOWN 조건');
    expect(reasonText(once)).toBe(once);
    const violation = violationText({ code: 'DUPLICATE_CONCEPT', stage: 'concepts' });
    expect(reasonText(violation)).toBe(violation);
  });

  it('never resolves inherited object keys as labels (PM P3 on PR85)', () => {
    for (const key of ['constructor', 'toString', '__proto__', 'hasOwnProperty']) {
      expect(reasonText(key)).toBe(key);
      expect(violationText({ code: key, stage: 'needs' })).toBe(`${key} (${key} · needs 단계)`);
    }
    expect(stageLabel('constructor')).toBe('constructor 단계');
  });
});

describe('stage labels', () => {
  it('names stored stages in planner words and keeps an unknown stage visible', () => {
    expect(stageLabel('review')).toBe('검토·수정 단계');
    expect(stageLabel('compare')).toBe('기능 대조 단계');
    expect(stageLabel('mystery')).toBe('mystery 단계');
  });
});

describe('PendingJudgement', () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.useRealTimers(); });

  it('formats elapsed time', () => {
    expect(elapsedText(0)).toBe('0초');
    expect(elapsedText(59_900)).toBe('59초');
    expect(elapsedText(125_000)).toBe('2분 5초');
  });

  it('shows nothing when idle, then an honest in-flight status with a running clock', async () => {
    await act(async () => root.render(createElement(PendingJudgement, { active: false, action: '요청 저장과 판단 실행' })));
    expect(host.textContent).toBe('');
    await act(async () => root.render(createElement(PendingJudgement, { active: true, action: '요청 저장과 판단 실행' })));
    const status = host.querySelector('[role="status"]');
    expect(status?.getAttribute('aria-live')).toBe('polite');
    expect(status?.textContent).toContain('요청 저장과 판단 실행 · 서버 응답 대기 중');
    expect(status?.textContent).toContain('(0초)');
    expect(status?.textContent).toContain('자동으로 다시 보내지 않습니다');
    // It does not claim a stage the server never reported.
    expect(status?.textContent).not.toMatch(/니즈 구조화 중|기능 대조 중|콘셉트 작성 중/);
    await act(async () => { vi.advanceTimersByTime(65_000); });
    expect(host.textContent).toContain('(1분 5초)');
    await act(async () => root.render(createElement(PendingJudgement, { active: false, action: '요청 저장과 판단 실행' })));
    expect(host.textContent).toBe('');
  });
});

describe('rerun submits once even when two submits arrive before the re-render', () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

  it('locks synchronously, shows the in-flight notice and unlocks after the server answers', async () => {
    // A real held run stored by PM through the API with Qwen3:8B (round2), replayed as data.
    const record = JSON.parse(readFileSync(resolve(process.cwd(), '../..', 'evals/pm-review/20261005-round2/api-live/workspace-live.json'), 'utf-8'));
    const held: RunSnapshot = record.first;
    let finish: () => void = () => {};
    const onRerun = vi.fn(() => new Promise<void>(done => { finish = done; }));
    const measure: MeasureControls = { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' };
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'live', runs: [held], selected: held, original: held.request, onSelect: () => {}, ...runSources(held, [], []), onRerun, measure,
    })));
    const form = host.querySelector('form[aria-label="후보·조건 선택 후 재실행"]') as HTMLFormElement;
    const input = host.querySelector('#extra-condition') as HTMLInputElement;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '1인 가구 소형 냉장고 기준');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => ([...form.querySelectorAll('button')].find(item => item.textContent === '조건 추가') as HTMLButtonElement).click());
    await act(async () => { form.requestSubmit(); form.requestSubmit(); });
    expect(onRerun).toHaveBeenCalledTimes(1);
    expect(form.querySelector('.pending-judgement')?.textContent).toContain('새 실행 저장과 판단 실행 · 서버 응답 대기 중');
    await act(async () => { finish(); });
    expect(form.querySelector('.pending-judgement')).toBeNull();
    await act(async () => form.requestSubmit());
    expect(onRerun).toHaveBeenCalledTimes(2);
  });
});
