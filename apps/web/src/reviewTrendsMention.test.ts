// @vitest-environment jsdom
// PM decision 2026-10-06 on DATA #176 (record 최길웅-20261006-037): the trend contract has no polarity, so a topic share
// is a topic-MENTION ratio, never a complaint/sentiment ratio or seasonal demand, and the candidate topics stay a preview
// classification. The aggregate below is the one #176's collector actually returned through the workspace API in the
// pre-merge consumption check (record 036); the panel uses the synthetic fixture.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FIXTURE_TREND_MONTH } from './fixtures/reviewTrends.fixture';
import type { LiveWorkspace } from './liveWorkspace';
import { ReviewTrendsPanel } from './ReviewTrendsPanel';
import { MENTION_NOTE, taxonomyNote, topicLabel, topicsOf, trendSnapshotExport, trendSnapshotMarkdown } from './reviewTrends';
import type { TrendAggregate } from './reviewTrends';

const COLLECTED = (JSON.parse(readFileSync(resolve(process.cwd(), '../../evals/web/20261006/web-r3-pr176-precheck/web/web-snapshot.json'), 'utf-8')) as { aggregate: TrendAggregate }).aggregate;
const CANDIDATE_TOPICS = ['cleaning', 'temporary_storage', 'food_findability', 'manual_guidance', 'dish_loading_guidance', 'rotating_arm_clearance', 'heating_preset_management'];

describe('topic shares read as mentions, not complaints', () => {
  it('labels every candidate topic by name only, never as a complaint', () => {
    for (const id of CANDIDATE_TOPICS) {
      expect(topicLabel(id)).toMatch(new RegExp(`^.+ \\(${id}\\)$`));
      expect(topicLabel(id)).not.toContain('불편');
    }
    expect(topicLabel('cleaning')).toBe('청소 (cleaning)');
  });

  it('marks the collected candidate taxonomy as a preview and states the mention meaning in exports', () => {
    expect(COLLECTED.topic_taxonomy_version).toBe('kitchen-review-topics-candidate.v1');
    expect(taxonomyNote(COLLECTED.topic_taxonomy_version)).toContain('PM 승인 전 미리보기 분류');
    expect(taxonomyNote('kitchen-review-topics.v1')).toBe('주제 분류 kitchen-review-topics.v1');
    expect(taxonomyNote(undefined)).toBeNull();
    const doc = trendSnapshotExport(COLLECTED, { fixture: false, exportedAt: '2026-10-06T10:00:00.000Z', viewed: null });
    expect(doc.notices).toContain(MENTION_NOTE);
    expect(doc.notices.some(item => item.includes('미리보기 분류'))).toBe(true);
    const markdown = trendSnapshotMarkdown(doc);
    expect(markdown).toContain('언급한 리뷰의 비율');
    expect(markdown).not.toContain('불편');
    for (const id of topicsOf(COLLECTED)) expect(markdown).toContain(topicLabel(id));
  });
});

describe('panel heading and hint', () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

  it('names the chart a topic-mention trend and explains the ratio', async () => {
    const workspace = { connection: 'disconnected', scopeVersion: 0, project: null } as unknown as LiveWorkspace;
    await act(async () => root.render(createElement(ReviewTrendsPanel, { mode: 'fixture', workspace, data: undefined, modelId: FIXTURE_TREND_MONTH.filters.model_id, onUseInPlanning: vi.fn() })));
    expect(host.querySelector('.trends-head h3')?.textContent).toBe('월·계절별 리뷰 주제 언급 동향');
    expect(host.querySelector('.trends-head')?.textContent).toContain(MENTION_NOTE);
    expect(host.querySelector('.trends-head')?.textContent).not.toContain('불편');
  });
});
