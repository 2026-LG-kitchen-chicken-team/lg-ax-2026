import { afterEach, describe, expect, it, vi } from 'vitest';
import dataset from '../../../data/demo/dataset.json';
import { ApiError, loadBootstrap, parseBootstrap, requestPlanning } from './api';

const response = () => ({ ok: true, data: { ...structuredClone(dataset), contract_version: '0.1.0' } });
const request = { product_group: 'fridge', target_customer: '냉장고 사용자', use_situation: '선반 청소', improvement_task: '청소 부담 검토', exclusions: ['기존 기능 중복'], model_ids: ['FRIDGE-A'], dataset_version: dataset.manifest.version };
afterEach(() => vi.unstubAllGlobals());

describe('canonical Draft2020-12 계약과 실패 표시', () => {
  it('공통 fixture를 정식 response schema로 검증한다', () => {
    const result = parseBootstrap(response());
    expect(result.products.length).toBe(5);
    expect(result.reviews.length).toBe(dataset.manifest.review_count);
    expect(result.manifest.analysis_implemented).toBe(false);
  });
  it('문서 버전 타입이 어긋난 응답을 거부한다', () => {
    const malformed = response();
    Object.assign(malformed.data.evidence[0], { document_version: 123 });
    expect(() => parseBootstrap(malformed)).toThrow(ApiError);
    expect(() => parseBootstrap(malformed)).toThrow('규격');
  });
  it('알 수 없는 제품군이 들어온 응답을 거부한다', () => {
    const malformed = response();
    Object.assign(malformed.data.products[0], { product_group: 'unknown-device' });
    expect(() => parseBootstrap(malformed)).toThrow();
  });
  it('네트워크 실패를 자료 없는 정상 화면으로 바꾸지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network failure')));
    await expect(loadBootstrap()).rejects.toMatchObject({ code: 'API_UNAVAILABLE' });
  });
  it('HTTP 오류는 실패 상태를 유지한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('upstream failure', { status: 502 })));
    await expect(loadBootstrap()).rejects.toMatchObject({ code: 'API_ERROR' });
  });
  it('분석 미구현을 성공·가짜 콘셉트로 표시하지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ok: false, error: { code: 'NOT_IMPLEMENTED', message: 'Agent 실행 미구현', details: {} } }, { status: 501 })));
    await expect(requestPlanning(request)).rejects.toMatchObject({ code: 'NOT_IMPLEMENTED' });
  });
  it('공통 입력 규격 위반이면 API를 호출하지 않는다', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(requestPlanning({ ...request, model_ids: [] })).rejects.toMatchObject({ code: 'INVALID_REQUEST' });
    expect(fetch).not.toHaveBeenCalled();
  });
});
