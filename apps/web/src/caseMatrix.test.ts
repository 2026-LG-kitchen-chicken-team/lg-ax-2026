// @vitest-environment jsdom
// Six judgment cases × three proposal products (PM-20261004-WEB-003-CORE-INTEGRATION, core-waiting stage).
// These are contract fixtures, not planning-core output: passing here shows the screens and export keep what a
// contract-shaped result carries; it says nothing about how the actual core will judge these cases.
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CASE_EVIDENCE, CASE_FEATURES, CASE_MATRIX } from './fixtures/caseMatrix.fixture';
import { ConceptsView, HistoryView } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import {
  buildComparison, buildExport, buildRerunRequest, candidateExclusion, contractErrors, draftRunFromRequest, exportCompleteness, exportMarkdown,
  heldItems, scopeWarnings, splitConditions,
} from './planning';
import type { PlanningRequest, RunSnapshot } from './planning';

const evidenceById = new Map(CASE_EVIDENCE.map(item => [item.id, item]));

describe('six judgment cases across the three proposal products (contract fixtures)', () => {
  it('covers every case type and all three proposal usage examples', () => {
    expect(CASE_MATRIX.map(item => item.kind)).toEqual(['normal', 'supported', 'duplicate', 'insufficient_evidence', 'conflict', 'document_update']);
    expect(new Set(CASE_MATRIX.map(item => item.snapshot.request.product_group))).toEqual(new Set(['fridge', 'dishwasher', 'microwave']));
    expect(CASE_MATRIX.flatMap(item => item.proposal_example ?? [])).toEqual(['식기세척기 안내 서비스', '전자레인지 기능 중복 제외', '냉장고 구조 개선']);
  });

  describe.each(CASE_MATRIX)('$label ($kind)', ({ snapshot, expect: want }) => {
    it('matches the shared contract as a stored run and as an API run request', () => {
      expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
      for (const need of snapshot.output!.needs) expect(contractErrors('Need', need)).toEqual([]);
      for (const gap of snapshot.output!.gaps) expect(contractErrors('Gap', gap)).toEqual([]);
      expect(contractErrors('WorkspaceRunCreateRequest', { request: snapshot.request, previous_run_id: null, unconfirmed: snapshot.unconfirmed })).toEqual([]);
    });

    it('cites only real source entries and keeps each judgment on the comparison table', () => {
      const rows = buildComparison(snapshot.output!, CASE_FEATURES, CASE_EVIDENCE);
      expect(rows.flatMap(row => row.missingIds)).toEqual([]);
      expect(Object.fromEntries(rows.map(row => [row.need.id, row.gap?.support_status]))).toEqual(want.statuses);
      expect(Object.fromEntries(snapshot.run.concepts.map(item => [item.id, item.status]))).toEqual(want.concept_statuses);
      expect(snapshot.run.evidence_ids.filter(id => !evidenceById.has(id))).toEqual([]);
      expect(rows.filter(row => row.need.uncertainties.length).map(row => row.need.id)).toEqual(want.uncertain_need_ids);
      expect(heldItems(snapshot).filter(item => item.kind === 'insufficient_evidence').map(item => item.id)).toEqual(want.held_gap_ids);
      expect(scopeWarnings(snapshot, CASE_FEATURES, CASE_EVIDENCE).map(item => item.id)).toEqual(want.out_of_scope_ids);
    });

    it('exports the same candidates, source text, document versions, holds and scope warnings without loss', () => {
      const doc = buildExport('fixture', snapshot, CASE_FEATURES, CASE_EVIDENCE, '2026-10-04T13:30:00.000Z');
      expect(doc.completeness).toMatchObject({ complete: true, mismatched_fields: [] });
      expect(doc.meta.document_versions).toEqual(snapshot.document_versions);
      expect(doc.concepts).toEqual(snapshot.run.concepts);
      for (const item of doc.evidence) expect(item.text).toBe(evidenceById.get(item.id)!.text);
      expect(doc.scope_warnings.map(item => item.id)).toEqual(want.out_of_scope_ids);
      const markdown = exportMarkdown(doc);
      for (const concept of snapshot.run.concepts) expect(markdown).toContain(`${concept.id} — ${concept.title}`);
      for (const text of [...snapshot.run.unresolved, ...snapshot.unconfirmed]) expect(markdown).toContain(text);
      for (const id of want.held_gap_ids) expect(markdown).toContain(`- ${id}:`);
      // A dropped scope warning is reported by the completeness check, never silently accepted.
      if (want.out_of_scope_ids.length) {
        expect(markdown).toContain('검토 범위 밖 문서 버전');
        const tampered = exportCompleteness({ ...doc, scope_warnings: [] }, snapshot, CASE_FEATURES, CASE_EVIDENCE);
        expect(tampered.complete).toBe(false);
        expect(tampered.missing_scope_warnings).toEqual(want.out_of_scope_ids);
      }
    });

    it('turns candidate choices and a corrected condition into a new linked run without touching the original', () => {
      const before = structuredClone(snapshot);
      const [first, second] = snapshot.run.concepts;
      const choices = first ? { [first.id]: 'exclude' as const, ...(second ? { [second.id]: 'focus' as const } : {}) } : {};
      const conditions = [...splitConditions(snapshot.request, snapshot.run.concepts).conditions, '1인 가구 소형 모델만 검토'];
      const next = buildRerunRequest(snapshot.request, snapshot.run.concepts, choices, conditions);
      const draft = draftRunFromRequest(snapshot, snapshot.request, next, `${snapshot.run.id}-NEXT`, '2026-10-04T13:40:00.000Z');
      expect(snapshot).toEqual(before);
      expect(draft).toMatchObject({ previous_run_id: snapshot.run.id, request_revision: 1, output: null, document_versions: snapshot.document_versions, dataset_sha256: snapshot.dataset_sha256 });
      expect(draft.run.status).toBe('not_implemented');
      expect(draft.request.improvement_task.startsWith(snapshot.request.improvement_task)).toBe(true);
      expect(draft.request.use_situation).toBe(snapshot.request.use_situation);
      for (const item of snapshot.request.exclusions) expect(draft.request.exclusions).toContain(item);
      expect(draft.request.exclusions).toContain('1인 가구 소형 모델만 검토');
      if (first) expect(draft.request.exclusions).toContain(candidateExclusion(first));
      if (second) expect(draft.request.improvement_task).toContain(`[집중 검토: ${second.title} (${second.id})]`);
    });
  });
});

describe('six judgment cases in the actual React DOM', () => {
  let host: HTMLDivElement;
  let root: Root;
  const onRerun = vi.fn<(request: PlanningRequest) => Promise<void>>().mockResolvedValue(undefined);
  const measure: MeasureControls = { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' };

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    onRerun.mockClear();
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });

  async function showConcepts(snapshot: RunSnapshot) {
    await act(async () => root.render(createElement(ConceptsView, { mode: 'fixture', runs: [snapshot], selected: snapshot, onSelect: () => {}, features: CASE_FEATURES, evidence: CASE_EVIDENCE })));
  }

  it.each(CASE_MATRIX)('$label: shows judgment, source text with document version, assumptions and holds', async ({ snapshot, expect: want }) => {
    await showConcepts(snapshot);
    const text = host.textContent ?? '';
    expect(host.querySelectorAll('.comparison-table tbody tr')).toHaveLength(snapshot.output!.needs.length);
    for (const need of snapshot.output!.needs) expect(text).toContain(need.pain);
    for (const status of Object.values(want.statuses)) expect(host.querySelector(`.comparison-table .status-pill.${status}`)).not.toBeNull();
    for (const need of snapshot.output!.needs) for (const item of need.uncertainties) expect(text).toContain(item);
    for (const item of snapshot.run.unresolved) expect(text).toContain(item);
    expect(text).toContain(snapshot.run.concepts.length ? `${snapshot.run.concepts.length} / 3` : '생성된 후보가 없습니다.');
    for (const concept of snapshot.run.concepts) {
      const card = [...host.querySelectorAll('.concept-card')].find(item => item.textContent?.includes(concept.id))!;
      expect(card.classList.contains(concept.status)).toBe(true);
      for (const item of concept.assumptions) expect(card.textContent).toContain(item);
      await act(async () => (card.querySelector('.review-button') as HTMLButtonElement).click());
      const review = host.querySelector('[aria-label="후보 상세 검토"]')!.textContent ?? '';
      for (const id of concept.evidence_ids) {
        const source = evidenceById.get(id)!;
        expect(review).toContain(source.text);
        expect(review).toContain(`${source.model_id} · 문서 ${source.document_version}`);
      }
      if (want.held_gap_ids.length) expect(review).toContain('근거 부족·보류');
    }
    const notice = host.querySelector('.scope-notice');
    if (want.out_of_scope_ids.length) {
      expect(notice?.textContent).toContain(`검토 범위 밖 문서 버전 ${want.out_of_scope_ids.length}건`);
      for (const id of want.out_of_scope_ids) expect(notice?.textContent).toContain(`${id}: ${evidenceById.get(id)!.model_id} 문서 ${evidenceById.get(id)!.document_version}`);
    } else {
      expect(notice).toBeNull();
    }
  });

  it.each(CASE_MATRIX.filter(item => item.snapshot.run.concepts.length))('$label: excluding a candidate sends a rerun that keeps the original request text', async ({ snapshot }) => {
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'fixture', runs: [snapshot], selected: snapshot, original: snapshot.request, onSelect: () => {},
      features: CASE_FEATURES, evidence: CASE_EVIDENCE, onRerun, measure,
    })));
    const concept = snapshot.run.concepts[0];
    const group = host.querySelector(`[aria-label="${concept.title} 처리"]`)!;
    const exclude = [...group.querySelectorAll('label')].find(item => item.textContent === '제외')!.querySelector('input')!;
    await act(async () => exclude.click());
    await act(async () => (host.querySelector('form[aria-label="후보·조건 선택 후 재실행"]') as HTMLFormElement).requestSubmit());
    expect(onRerun).toHaveBeenCalledTimes(1);
    const sent = onRerun.mock.calls[0][0];
    expect(sent).toEqual({ ...snapshot.request, exclusions: [...snapshot.request.exclusions, candidateExclusion(concept)] });
  });

  it('insufficient-evidence case has no candidate to choose and still allows a condition-only rerun', async () => {
    const held = CASE_MATRIX.find(item => item.kind === 'insufficient_evidence')!.snapshot;
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'fixture', runs: [held], selected: held, original: held.request, onSelect: () => {},
      features: CASE_FEATURES, evidence: CASE_EVIDENCE, onRerun, measure,
    })));
    expect(host.textContent).toContain('이 실행에는 고를 후보가 없습니다.');
    expect(host.querySelectorAll('.choice-group')).toHaveLength(0);
  });
});
