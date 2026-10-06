// @vitest-environment jsdom
// review-trends-20261006.md "집계 스냅샷 내보내기" (WEB005/#149): the downloaded snapshot carries the aggregate exactly
// as received, the evidence page actually opened (same aggregate/bucket/topic), its source and the reading cautions.
// Synthetic fixture only: a real collector snapshot waits for DATA #148 / PM #152.
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FIXTURE_TREND_MONTH, FIXTURE_TREND_SEASON, fixtureTrendEvidence } from './fixtures/reviewTrends.fixture';
import type { LiveWorkspace } from './liveWorkspace';
import { ReviewTrendsPanel } from './ReviewTrendsPanel';
import { topicsOf, trendCells, trendSnapshotExport, trendSnapshotMarkdown } from './reviewTrends';

const MONTH = FIXTURE_TREND_MONTH;
const TOPIC = topicsOf(MONTH)[0];
const CELLS = trendCells(MONTH, TOPIC);

describe('trend snapshot document', () => {
  it('keeps the aggregate byte-identical and does not share it with the caller', () => {
    const before = JSON.stringify(MONTH);
    const doc = trendSnapshotExport(MONTH, { fixture: true, exportedAt: '2026-10-06T06:30:00.000Z', viewed: null });
    expect(JSON.stringify(doc.aggregate)).toBe(before);
    expect(doc.aggregate).not.toBe(MONTH);
    doc.aggregate.counts.eligible_unique_review_count = -1;
    expect(JSON.stringify(MONTH)).toBe(before);
    expect(doc).toMatchObject({ kind: 'review_trend_snapshot', source: 'synthetic_fixture', aggregate_id: MONTH.aggregate_id, consistency_problems: [], viewed_evidence: null });
    expect(doc.notices[0]).toContain('합성 fixture');
    expect(trendSnapshotExport(MONTH, { fixture: false, exportedAt: 'x', viewed: null }).notices.join(' ')).not.toContain('합성 fixture');
  });

  it('writes denominators, empty periods, 0%, partial periods and cautions into Markdown', () => {
    const md = trendSnapshotMarkdown(trendSnapshotExport(MONTH, { fixture: true, exportedAt: '2026-10-06T06:30:00.000Z', viewed: null }));
    expect(md).toContain(MONTH.aggregate_id);
    expect(md).toContain(`분모(유효 고유 리뷰) ${MONTH.counts.eligible_unique_review_count}건`);
    expect(md).toContain(`날짜 없음 제외 ${MONTH.counts.excluded_undated_count}건`);
    expect(md).toContain('합성 fixture(실제 집계 아님)');
    const empty = CELLS.find(cell => cell.state === 'empty')!;
    expect(md).toMatch(new RegExp(`\\| ${empty.bucket.label}[^\\n]*\\| 자료 없음`));
    const zero = MONTH.buckets.flatMap(bucket => bucket.topics.filter(topic => topic.topic_review_count === 0 && bucket.total_reviews > 0).map(() => bucket));
    if (zero.length) expect(md).toContain('(0.0%)');
    const partial = MONTH.buckets.find(bucket => bucket.partial_period);
    if (partial) expect(md).toContain(`${partial.label} (부분 구간)`);
    expect(md).toContain('판매량이나 수요 증가를 뜻하지 않습니다');
    expect(md).not.toMatch(/NaN|Infinity|undefined/);
  });

  it('keeps winter as one season with its own year in the seasonal snapshot', () => {
    const md = trendSnapshotMarkdown(trendSnapshotExport(FIXTURE_TREND_SEASON, { fixture: true, exportedAt: 'x', viewed: null }));
    expect(md).toContain('2025년 겨울');
    expect(md).toContain('계절별');
  });

  it('records an inconsistent aggregate as such instead of hiding the problem', () => {
    const broken = structuredClone(MONTH);
    broken.counts.eligible_unique_review_count += 1;
    const doc = trendSnapshotExport(broken, { fixture: true, exportedAt: 'x', viewed: null });
    expect(doc.consistency_problems.length).toBeGreaterThan(0);
    expect(trendSnapshotMarkdown(doc)).toContain('## 숫자 불일치');
  });
});

describe('snapshot export from the panel', () => {
  let host: HTMLDivElement;
  let root: Root;
  let files: { name: string; text: string }[];
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    files = [];
    // jsdom's Blob cannot be read back; a minimal stand-in keeps the exact string handed to download().
    class TextBlob { constructor(readonly parts: string[]) {} }
    let blob: TextBlob | null = null;
    vi.stubGlobal('Blob', TextBlob);
    vi.stubGlobal('URL', Object.assign(Object.create(URL), { createObjectURL: (value: TextBlob) => { blob = value; return 'blob:test'; }, revokeObjectURL: () => undefined }));
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { files.push({ name: this.download, text: blob!.parts.join('') }); });
    host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  const workspace = { connection: 'disconnected', scopeVersion: 0, project: null } as unknown as LiveWorkspace;
  const exportAs = async (label: string) => {
    await act(async () => [...host.querySelectorAll<HTMLButtonElement>('.trend-export button')].find(node => node.textContent === label)!.click());
    const file = files.at(-1)!;
    return file;
  };

  it('downloads the fixture snapshot with the opened page of the selected bucket only', async () => {
    await act(async () => root.render(createElement(ReviewTrendsPanel, { mode: 'fixture', workspace, data: undefined, modelId: MONTH.filters.model_id, onUseInPlanning: vi.fn() })));
    const before = JSON.parse((await exportAs('JSON')).text);
    expect(before.viewed_evidence).toBeNull();
    expect(before.aggregate).toEqual(MONTH);

    const index = CELLS.findIndex(cell => cell.state === 'value');
    await act(async () => host.querySelectorAll<HTMLButtonElement>('.trend-bar')[index].click());
    const file = await exportAs('JSON');
    const doc = JSON.parse(file.text);
    expect(file.name).toMatch(/^review-trend-.+\.json$/);
    const expected = fixtureTrendEvidence(MONTH, CELLS[index].bucket.bucket_id, TOPIC);
    expect(doc.viewed_evidence).toEqual({ bucket_id: CELLS[index].bucket.bucket_id, topic_id: TOPIC, total: expected.total, evidence_ids: expected.evidence.map(item => String(item.id)) });
    expect(doc.source).toBe('synthetic_fixture');

    const md = await exportAs('문서(Markdown)');
    expect(md.name).toMatch(/\.md$/);
    expect(md.text).toContain('## 열어 본 원문');
    expect(md.text).toContain(String(expected.evidence[0].id));
  });
});
