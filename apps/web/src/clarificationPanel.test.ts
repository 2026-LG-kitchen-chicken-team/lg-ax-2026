// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { buildClarificationRequest, clarificationQuestions, ClarificationPanel } from './ClarificationPanel';
import { FIXTURE_RUNS } from './fixtures/planning.fixture';
import type { RunSnapshot } from './planning';

const SNAPSHOT = FIXTURE_RUNS[0];
describe('clarification preserves the stored run and scope', () => {
  it('returns a new common request with the answer and exact originating question/run', () => {
    const before = structuredClone(SNAPSHOT);
    const question = clarificationQuestions(SNAPSHOT)[0];
    const next = buildClarificationRequest(SNAPSHOT, { [question]: '문서 1.0 범위를 유지하며 검토하겠습니다.' });
    expect(next.improvement_task).toContain(SNAPSHOT.request.improvement_task);
    expect(next.improvement_task).toContain(SNAPSHOT.run.id);
    expect(next.improvement_task).toContain(question);
    expect(next.improvement_task).toContain('답변: 문서 1.0 범위를 유지하며 검토하겠습니다.');
    expect(next.model_ids).toEqual(SNAPSHOT.request.model_ids);
    expect(next.exclusions).toEqual(SNAPSHOT.request.exclusions);
    expect(next.dataset_version).toBe(SNAPSHOT.request.dataset_version);
    expect(SNAPSHOT).toEqual(before);
  });
  it('rejects empty, stale and overlong answers instead of sending a silent condition', () => {
    const question = clarificationQuestions(SNAPSHOT)[0];
    expect(() => buildClarificationRequest(SNAPSHOT, {})).toThrow('답변을 하나 이상');
    expect(() => buildClarificationRequest(SNAPSHOT, { [question]: '  ' })).toThrow('답변을 하나 이상');
    expect(() => buildClarificationRequest(SNAPSHOT, { '다른 실행의 질문': '예' })).toThrow('현재 실행에 없는');
    expect(() => buildClarificationRequest(SNAPSHOT, { [question]: 'x'.repeat(2001) })).toThrow('2,000자');
  });
});

describe('clarification input, cancellation and failed submission', () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
  const mount = async (onSubmit = vi.fn().mockResolvedValue(undefined), snapshot: RunSnapshot = SNAPSHOT) => {
    await act(async () => root.render(createElement(ClarificationPanel, { snapshot, mode: 'fixture', onSubmit })));
    return onSubmit;
  };
  const enter = async (value: string) => { await act(async () => {
    const input = host.querySelector('textarea')!;
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }); };
  const submit = async () => { await act(async () => { host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); }); };

  it('shows no-answer questions, cancels without a write, and links an answered request', async () => {
    const onSubmit = await mount();
    expect(host.textContent).toContain('화면 확인용 합성 예시');
    await submit(); expect(onSubmit).not.toHaveBeenCalled(); expect(host.textContent).toContain('답변을 하나 이상');
    await enter('초기 입력');
    await act(async () => host.querySelector<HTMLButtonElement>('button[type="button"]')!.click());
    expect(host.querySelector<HTMLTextAreaElement>('textarea')!.value).toBe(''); expect(onSubmit).not.toHaveBeenCalled();
    await enter('문서 1.0만 사용'); await submit();
    expect(onSubmit).toHaveBeenCalledOnce(); expect(onSubmit.mock.calls[0][0].improvement_task).toContain('문서 1.0만 사용');
    expect(host.querySelector<HTMLTextAreaElement>('textarea')!.value).toBe('');
  });
  it('keeps typed answers when saving fails, and does not alter the current held state', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('저장 실패'));
    const held = { ...SNAPSHOT, run: { ...SNAPSHOT.run, status: 'held' as const, concepts: [] } };
    await mount(onSubmit, held); await enter('조건 보완'); await submit();
    expect(host.querySelector<HTMLTextAreaElement>('textarea')!.value).toBe('조건 보완');
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('저장 실패');
    expect(held.run.status).toBe('held'); expect(held.run.concepts).toEqual([]);
  });
  it('does not invent a question or submit a request for a run without questions', async () => {
    const none = { ...SNAPSHOT, output: null, unconfirmed: [], run: { ...SNAPSHOT.run, unresolved: [], concepts: [] } };
    const onSubmit = await mount(undefined, none);
    expect(host.textContent).toContain('저장된 추가 질문이 없습니다'); expect(host.querySelector('textarea')).toBeNull();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
