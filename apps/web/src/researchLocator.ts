// Readable source position for the R8 research flow (record 최길웅-20261007-058). The bundle's `locator` is a free-form
// object; the keys below are the ones the committed R8 bundles use. Every other key is still shown as "key: value" so no
// position is silently dropped. A page selector is technical, so it is kept apart for an expandable detail.

export interface LocatorView { text: string; technical: string[] }

const quoted = (value: unknown) => `「${String(value)}」`;
const FORMAT: [string, (value: unknown) => string][] = [
  ['page', value => `${value}쪽`],
  ['section', value => `항목 ${quoted(value)}`],
  ['table', value => `표 ${quoted(value)}`],
  ['unit', value => `단위 ${value}`],
  ['paragraph', value => `${value}번째 문단`],
  ['paragraphs', value => paragraphRange(value)],
  ['step', value => `${value}단계`],
  ['before_heading', value => `${quoted(value)} 제목 앞`],
  ['paragraph_topic', value => `문단 주제 ${quoted(value)}`],
  ['model_pattern', value => `적용 모델 ${value}`],
  ['question_no', value => `질문 번호 ${value}`],
  ['page_model_id', value => `페이지 모델 ID ${value}`],
  ['date_label', value => `날짜 항목 ${quoted(value)}`],
  ['original_review_id', value => `리뷰 번호 ${value}`],
];
const TECHNICAL: Record<string, string> = { selector: '페이지 내 선택자' };

function paragraphRange(value: unknown): string {
  if (!Array.isArray(value) || !value.length) return `문단 ${plain(value)}`;
  const numbers = value.every(item => Number.isInteger(item)) ? (value as number[]) : null;
  if (numbers && numbers.length > 1 && numbers.every((item, index) => index === 0 || item === numbers[index - 1] + 1)) {
    return `문단 ${numbers[0]}–${numbers[numbers.length - 1]}`;
  }
  return `문단 ${value.map(plain).join(', ')}`;
}

function plain(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : JSON.stringify(value);
}

const present = (value: unknown) => value !== undefined && value !== null && value !== '';

export function locatorView(locator: Record<string, unknown> | null | undefined): LocatorView {
  const entries = locator && typeof locator === 'object' && !Array.isArray(locator) ? locator : {};
  const parts: string[] = [];
  for (const [key, format] of FORMAT) if (present(entries[key])) parts.push(format(entries[key]));
  const known = new Set([...FORMAT.map(([key]) => key), ...Object.keys(TECHNICAL)]);
  for (const [key, value] of Object.entries(entries)) if (!known.has(key) && present(value)) parts.push(`${key}: ${plain(value)}`);
  const technical = Object.entries(TECHNICAL).filter(([key]) => present(entries[key])).map(([key, label]) => `${label}: ${plain(entries[key])}`);
  return { text: parts.length ? parts.join(' · ') : technical.length ? '페이지 안 위치만 기록됨' : '위치 정보 없음', technical };
}
