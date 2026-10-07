import { describe, expect, it } from 'vitest';
import dataset from '../../../data/demo/dataset.json';
import { bootstrapSourceSummary, evidenceLocation, filterEvidence } from './domain';
import type { BootstrapData } from './domain';

describe('근거 필터의 모델·자료 경계', () => {
  it('같은 제품 모델의 리뷰만 선택해 다른 제품 근거를 섞지 않는다', () => {
    const result = filterEvidence(dataset.evidence, { modelId: 'FRIDGE-A', query: '', type: 'review' });
    expect(result.length).toBeGreaterThan(0);
    expect(result.every(item => item.model_id === 'FRIDGE-A' && item.source_type === 'review')).toBe(true);
  });
  it('검색어가 일치하지 않으면 근거 없는 빈 결과를 반환한다', () => {
    expect(filterEvidence(dataset.evidence, { modelId: 'FRIDGE-A', query: 'NO_MATCH_67291', type: 'all' })).toEqual([]);
  });
  it('문서 근거는 한국어 검색어와 유형 필터를 함께 적용한다', () => {
    const manual = dataset.evidence.find(item => item.source_type === 'manual')!;
    const result = filterEvidence(dataset.evidence, { modelId: manual.model_id, query: manual.text.slice(0, 6), type: 'manual' });
    expect(result.map(item => item.id)).toContain(manual.id);
    expect(result.every(item => item.source_type === 'manual')).toBe(true);
  });
  it('원문 위치의 페이지·행을 보존한다', () => {
    const review = dataset.evidence.find(item => item.source_type === 'review')!;
    const manual = dataset.evidence.find(item => item.source_type === 'manual')!;
    expect(evidenceLocation(review)).toContain('행');
    expect(evidenceLocation(manual)).toContain('쪽');
  });
});

describe('connected dataset provenance', () => {
  const bootstrap = { ...dataset, contract_version: '0.1.0' } as BootstrapData;
  it('labels synthetic origins and the exact data version', () => {
    expect(bootstrapSourceSummary(bootstrap)).toBe('합성자료 · 자료 0.1.0');
  });
  it('labels a public profile without claiming market demand or Agent quality', () => {
    const example = { ...bootstrap, manifest: { version: 'public-profile-test.v1', source_kind: 'public' }, evidence: bootstrap.evidence.map(item => ({ ...item, source_kind: 'public' })) };
    expect(bootstrapSourceSummary(example)).toBe('공개자료 · 자료 public-profile-test.v1');
  });
  it('keeps mixed evidence visible even when a manifest claims public sources', () => {
    const example = { ...bootstrap, manifest: { version: 'mixed-test.v1', source_kind: 'public' } };
    expect(bootstrapSourceSummary(example)).toContain('혼합자료');
    expect(bootstrapSourceSummary(example)).toContain('합성자료');
  });
  it('does not resolve inherited labels or invent an unknown version', () => {
    expect(bootstrapSourceSummary({ ...bootstrap, manifest: { source_kind: 'constructor' }, evidence: [] })).toBe('출처 미확인 · 자료 버전 미확인');
  });
});
