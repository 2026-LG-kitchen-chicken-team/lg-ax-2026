import { describe, expect, it } from 'vitest';
import dataset from '../../../data/demo/dataset.json';
import { evidenceLocation, filterEvidence } from './domain';

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
