// Locator shapes copied from the committed R8 bundles (data/research/*/bundles), one per kind of source.
import { describe, expect, it } from 'vitest';
import { locatorView } from './researchLocator';

describe('locatorView', () => {
  it('turns each real R8 locator shape into a readable position', () => {
    expect(locatorView({ page: 20, section: '식기 배열' }).text).toBe('20쪽 · 항목 「식기 배열」');
    expect(locatorView({ paragraphs: [1, 2], section: '올바른 식기 수납' }).text).toBe('항목 「올바른 식기 수납」 · 문단 1–2');
    expect(locatorView({ paragraph: 1, section: '컵 수납하기 / 동영상 자막' }).text).toBe('항목 「컵 수납하기 / 동영상 자막」 · 1번째 문단');
    expect(locatorView({ section: '빌트인 설치 일반 걸레받이용(150mm)', table: '싱크대 깊이', unit: 'mm' }).text)
      .toBe('항목 「빌트인 설치 일반 걸레받이용(150mm)」 · 표 「싱크대 깊이」 · 단위 mm');
    expect(locatorView({ before_heading: '매뉴얼 & 다운로드', section: '제품명 및 모델번호' }).text).toBe('항목 「제품명 및 모델번호」 · 「매뉴얼 & 다운로드」 제목 앞');
    expect(locatorView({ model_pattern: 'DUE6***', section: '린스 레벨 설정', step: 1 }).text).toBe('항목 「린스 레벨 설정」 · 1단계 · 적용 모델 DUE6***');
    expect(locatorView({ date_label: '작성일', page_model_id: 'MD08039646', question_no: '473510', section: '질문 제목 및 본문' }).text)
      .toBe('항목 「질문 제목 및 본문」 · 질문 번호 473510 · 페이지 모델 ID MD08039646 · 날짜 항목 「작성일」');
  });

  it('keeps the review page selector as a technical detail instead of the readable text', () => {
    const view = locatorView({ original_review_id: '767844', selector: '#divReviewList > li[data-review-id="767844"] .message' });
    expect(view.text).toBe('리뷰 번호 767844');
    expect(view.technical).toEqual(['페이지 내 선택자: #divReviewList > li[data-review-id="767844"] .message']);
    expect(locatorView({ selector: '#a' }).text).toBe('페이지 안 위치만 기록됨');
  });

  it('shows unknown keys instead of dropping them and says when there is no position', () => {
    expect(locatorView({ page: 3, line: 7, range: { start: 10, end: 42 } }).text).toBe('3쪽 · line: 7 · range: {"start":10,"end":42}');
    expect(locatorView({ paragraphs: [1, 3] }).text).toBe('문단 1, 3');
    expect(locatorView({}).text).toBe('위치 정보 없음');
    expect(locatorView(undefined).text).toBe('위치 정보 없음');
    expect(locatorView({ page: null, section: '' }).text).toBe('위치 정보 없음');
  });
});
