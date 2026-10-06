// @vitest-environment jsdom
// Record 최길웅-20261006-034: PM's real model-study runs (qwen3.5:27b held ×2, qwen3:8b failed ×2, synthetic data,
// evals/pm-prototype/20261006/finite-model-study) stored through the actual workspace HTTP API and read back over HTTP
// and MCP (evals/web/20261006/web-real-replay/tools/replay_model_study.py). The repository keeps only each HTTP
// snapshot's envelope; its planning_execution is PM's recording, byte-pinned by SHA-256. No model is called here, and
// none of this is planning quality: it checks that held/failed runs never read as accepted or successful.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { exportJudgement, judgementView, planningExecutionView, rejectedCandidateCount, rerunBaseNotice, runSources, selectableConcepts, terminalReason } from './judgement';
import type { PlanningExecution } from './judgement';
import { runStatusView } from './liveWorkspace';
import { ConceptsView, HistoryView } from './PlanningViews';
import type { MeasureControls } from './PlanningViews';
import { buildComparison, buildExport, contractErrors, exportCompleteness, exportMarkdown } from './planning';
import type { PlanningRequest, RunSnapshot } from './planning';

const ROOT = resolve(process.cwd(), '../..');
const REPLAY = 'evals/web/20261006/web-real-replay';
interface Row { case: string; run_id: string; envelope: string; recording: string; recording_sha256: string; recorded_status: string; decision_action: string; historical_model_calls: number }
const SUMMARY = JSON.parse(readFileSync(resolve(ROOT, REPLAY, 'replay-summary.json'), 'utf-8')) as { new_model_calls: number; cases: Row[] };

/** Envelope + PM recording = the snapshot the HTTP API returned; a recording whose bytes changed is refused. */
function replayed(row: Row): RunSnapshot {
  const envelope = JSON.parse(readFileSync(resolve(ROOT, REPLAY, row.envelope), 'utf-8'));
  const ref = envelope.output.planning_execution as { $replay_record: string; sha256: string };
  const bytes = readFileSync(resolve(ROOT, ref.$replay_record));
  const digest = createHash('sha256').update(bytes).digest('hex');
  if (ref.$replay_record !== row.recording || digest !== ref.sha256 || digest !== row.recording_sha256) throw new Error(`recording changed: ${row.case}`);
  envelope.output.planning_execution = JSON.parse(bytes.toString('utf-8'));
  return envelope as RunSnapshot;
}

const RUNS = SUMMARY.cases.map(row => ({ row, snapshot: replayed(row) }));
const execution = (snapshot: RunSnapshot) => (snapshot.output as unknown as { planning_execution: PlanningExecution }).planning_execution;
const HELD = RUNS.filter(item => item.row.recorded_status === 'held');
const FAILED = RUNS.filter(item => item.row.recorded_status === 'failed');
// Facts of the recordings themselves (read once from the files, not from the code under test).
const VIOLATIONS: Record<string, { hold: string[]; unrevised: string[] }> = {
  '27b-enum-guide/fridge-normal': { hold: ['SUPPORT_UNKNOWN'], unrevised: ['CONCEPT_WITHOUT_CONFIRMED_GAP'] },
  '27b-bounded12/fridge-normal': { hold: ['SUPPORT_UNKNOWN'], unrevised: ['NON_COMPLAINT_AS_NEED', 'SUPPORT_BASIS_MISMATCH', 'CONCEPT_WITHOUT_CONFIRMED_GAP', 'DUPLICATE_CONCEPT'] },
};

describe('real 27B held / 8B failed runs replayed from the workspace HTTP API (record 034)', () => {
  it('are the four stored runs, unchanged recordings, valid snapshots and readable core records', () => {
    expect(SUMMARY.new_model_calls).toBe(0);
    expect(RUNS.map(item => [item.row.case, item.row.recorded_status])).toEqual([
      ['27b-enum-guide/fridge-normal', 'held'], ['27b-bounded12/fridge-normal', 'held'],
      ['8b-bounded12/fridge-normal', 'failed'], ['8b-bounded12/microwave-normal', 'failed'],
    ]);
    for (const { row, snapshot } of RUNS) {
      expect(snapshot.run.id).toBe(row.run_id);
      expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
      const view = planningExecutionView(snapshot);
      if (view.kind !== 'ok') throw new Error(`${row.case}: ${JSON.stringify(view)}`);
      expect(view.problems).toEqual([]);
      expect(view.execution.execution_kind).toBe('live_model');
      expect(view.model_calls).toBe(row.historical_model_calls);
      expect([snapshot.run.status, view.execution.status, view.execution.decision?.action]).toEqual([row.recorded_status, row.recorded_status, row.decision_action]);
      expect(snapshot.run.concepts).toEqual([]);
    }
  });

  it('offer nothing to select, and a rerun never inherits them as success', () => {
    for (const { snapshot } of RUNS) {
      expect(selectableConcepts(snapshot)).toEqual([]);
      expect(rerunBaseNotice(snapshot)).toContain(`${snapshot.run.status === 'held' ? '보류' : '실패'}로 끝나 채택된 후보가 없습니다`);
    }
  });

  it('a failed run that used both revisions is not described as an execution error', () => {
    for (const { snapshot } of FAILED) {
      expect(terminalReason(snapshot)).toBe('revision_limit');
      const view = runStatusView(snapshot.run.status, terminalReason(snapshot));
      expect([view.label, view.tone]).toEqual(['실패', 'error']);
      expect(view.detail).toContain('내부 수정 한도(2회)');
      expect(view.detail).not.toContain('실행 중 오류');
    }
    for (const { snapshot } of HELD) expect([runStatusView(snapshot.run.status, terminalReason(snapshot)).tone, terminalReason(snapshot)]).toEqual(['notice', 'hold']);
    // Without a recorded reason the old generic wording stays.
    expect(runStatusView('failed').detail).toBe('실행 중 오류가 발생했습니다. 미해결 항목을 확인해 주세요.');
  });

  it('a hold separates the evidence problem that caused it from the judgement errors it left unrevised', () => {
    for (const { row, snapshot } of HELD) {
      const record = execution(snapshot);
      const view = judgementView(record.input, record.output!, record.decision!);
      const expected = VIOLATIONS[row.case];
      expect(view.hold_causes).toHaveLength(expected.hold.length);
      expected.hold.forEach((code, index) => expect(view.hold_causes[index]).toContain(code));
      expect(view.unrevised_errors).toHaveLength(expected.unrevised.length);
      for (const code of expected.unrevised) expect(view.unrevised_errors.some(item => item.includes(code))).toBe(true);
      expect(view.detail).toContain(`판단 오류 ${expected.unrevised.length}건`);
      expect(view.detail).toContain('자료 부족만의 문제가 아님');
    }
    for (const { snapshot } of FAILED) {
      const record = execution(snapshot);
      const view = judgementView(record.input, record.output!, record.decision!);
      expect([view.label, view.hold_causes, view.unrevised_errors]).toEqual(['미해결 종료', [], []]);
    }
  });

  it('exports keep held/failed, the end reason, the hold split and the turned-down candidates; never "accepted"', () => {
    for (const { row, snapshot } of RUNS) {
      const record = execution(snapshot);
      const scoped = runSources(snapshot, [], []);
      const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-06T10:00:00.000Z', [snapshot]);
      const judgement = exportJudgement(snapshot)!;
      if (!judgement.record_valid) throw new Error('expected a valid record');
      expect(doc.concepts).toEqual([]);
      expect(doc.execution_record).toEqual(record);
      expect(judgement.terminal_reason).toBe(record.correction_budget!.terminal_reason);
      expect(judgement.rejected_candidates.map(item => item.id)).toEqual((record.rejected_output?.concepts ?? []).map(item => item.id));
      const markdown = exportMarkdown(doc);
      expect(markdown).toContain(`- 실행 상태: ${row.recorded_status}`);
      expect(markdown).not.toContain('계약 검사 통과');
      const rejected = rejectedCandidateCount(snapshot);
      if (rejected) {
        expect(markdown).toContain(`채택된 콘셉트가 없습니다. 모델이 만든 후보 ${rejected}개`);
        expect(markdown).not.toContain('생성된 콘셉트가 없습니다.');
        expect(markdown).toContain('보류를 일으킨 문제(근거 확인 필요):');
        expect(markdown).toContain('함께 발견된 판단 오류(보류로 내부 수정하지 않음):');
      } else {
        expect(markdown).toContain('생성된 콘셉트가 없습니다.');
        expect(markdown).toContain('종료 사유: 내부 수정 한도 도달');
      }
    }
  });
});

describe('comparison table rows and export follow every stored gap and its judged facts (record 034 audit U2)', () => {
  it('one row per gap: the microwave need with three gaps keeps all of them, and a dropped gap is caught', () => {
    for (const { snapshot } of RUNS) {
      const record = execution(snapshot);
      const scoped = runSources(snapshot, [], []);
      const rows = buildComparison(snapshot.output!, scoped.features, scoped.evidence);
      expect(rows.map(row => row.gap?.id).sort()).toEqual(record.output!.gaps.map(gap => gap.id).sort());
      const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-06T10:00:00.000Z', [snapshot]);
      expect(doc.comparison.map(row => row.gap_id).sort()).toEqual(record.output!.gaps.map(gap => gap.id).sort());
      expect(doc.completeness.missing_gaps).toEqual([]);
      const dropped = { ...doc, comparison: doc.comparison.slice(1) };
      expect(exportCompleteness(dropped, snapshot, scoped.features, scoped.evidence, [snapshot]).missing_gaps).toEqual([doc.comparison[0].gap_id]);
    }
    const microwave = execution(RUNS[3].snapshot).output!;
    const needOne = microwave.gaps.filter(gap => gap.need_id === microwave.needs[0].id).map(gap => gap.id);
    expect(needOne.length).toBeGreaterThan(1);
    const markdown = exportMarkdown(buildExport('live', RUNS[3].snapshot, [], [], '2026-10-06T10:00:00.000Z', [RUNS[3].snapshot]));
    for (const id of needOne) expect(markdown).toContain(`${microwave.needs[0].id}/${id}:`);
  });

  it('each row carries the stored resolution, basis mismatch, desired outcome and non-complaint citations', () => {
    for (const { snapshot } of RUNS) {
      const output = execution(snapshot).output!;
      const scoped = runSources(snapshot, [], []);
      const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-06T10:00:00.000Z', [snapshot]);
      for (const row of doc.comparison) {
        const assessment = output.gap_assessments.find(item => item.gap_id === row.gap_id);
        expect(row.resolution).toBe(assessment?.resolution ?? null);
        expect(row.desired_outcome).toBe(output.desired_outcomes.find(item => item.need_id === row.need_id)?.desired_outcome ?? null);
        const need = output.needs.find(item => item.id === row.need_id)!;
        const expectedFlags = need.evidence_ids.filter(id => { const p = output.review_assessments.find(item => item.evidence_id === id)?.polarity; return p !== undefined && p !== 'complaint' && p !== 'conflicting'; });
        expect(row.non_complaint_reviews.map(item => item.evidence_id)).toEqual(expectedFlags);
      }
      const markdown = exportMarkdown(doc);
      expect(markdown).toContain('코어가 채택하지 않은 실행');
      if (output.gap_assessments.some(item => item.resolution === 'remaining')) expect(markdown).toContain('불편 남음');
    }
    // NON_COMPLAINT_AS_NEED runs: some cited review was judged non-complaint by the same run; SUPPORT_BASIS_MISMATCH: a declared status differs from its basis.
    for (const { row, snapshot } of RUNS) {
      const codes = execution(snapshot).decision!.violations.map(item => item.code);
      const scoped = runSources(snapshot, [], []);
      const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-06T10:00:00.000Z', [snapshot]);
      expect(doc.comparison.some(item => item.non_complaint_reviews.length > 0), row.case).toBe(codes.includes('NON_COMPLAINT_AS_NEED'));
      if (codes.includes('SUPPORT_BASIS_MISMATCH')) expect(doc.comparison.some(item => item.basis_mismatch), row.case).toBe(true);
    }
  });
});

describe('exports explain the judgement and keep cited and uncited inputs apart (record 034 audit U4)', () => {
  // Expectations from the raw recordings: reviews the run assessed but no need/gap cites, and duplication rows without a candidate.
  const facts = (record: PlanningExecution) => {
    const output = record.output!;
    const cited = new Set([...output.needs.flatMap(need => need.evidence_ids), ...output.gaps.flatMap(gap => gap.evidence_ids)]);
    const orphans = [output, record.rejected_output].flatMap(out => out ? out.concept_assessments.filter(item => !out.concepts.some(concept => concept.id === item.concept_id)).map(item => item.concept_id) : []);
    return { unused: output.review_assessments.map(item => item.evidence_id).filter(id => !cited.has(id)), orphans };
  };

  it('summary and Markdown carry the review, gap and duplication declarations and the unused reviews', () => {
    for (const { snapshot } of RUNS) {
      const record = execution(snapshot);
      const { unused, orphans } = facts(record);
      const scoped = runSources(snapshot, [], []);
      const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-06T10:00:00.000Z', [snapshot]);
      const judgement = doc.judgement!;
      if (!judgement.record_valid) throw new Error('expected a valid record');
      expect(judgement.review_assessments.map(item => item.evidence_id)).toEqual(record.output!.review_assessments.map(item => item.evidence_id));
      expect(judgement.gap_assessments.map(item => item.gap_id)).toEqual(record.output!.gap_assessments.map(item => item.gap_id));
      expect(judgement.unused_review_ids).toEqual(unused);
      expect(judgement.concept_assessments.filter(item => !item.has_candidate).map(item => item.concept_id)).toEqual(orphans);
      expect(doc.completeness.complete).toBe(true);
      const markdown = exportMarkdown(doc);
      expect(markdown).toContain('리뷰 판단(판단 모델의 선언, 독립 검증 아님):');
      expect(markdown).toContain('기능 대조 판단(판단 모델의 선언):');
      if (unused.length) expect(markdown).toContain('어느 불편·Gap에도 쓰이지 않은 리뷰:');
      if (orphans.length) expect(markdown).toContain('이 ID의 후보 본문은 저장되지 않음');
      expect(markdown).toContain('후보 없음 검토 없음');
    }
    expect(facts(execution(RUNS[2].snapshot)).unused).toEqual(['REVIEW-EVIDENCE-006', 'REVIEW-EVIDENCE-009', 'REVIEW-EVIDENCE-010']);
  });

  it('inputs the judgement never cites are exported apart, and the no-candidate reason is listed once in the core section', () => {
    for (const { snapshot } of RUNS) {
      const record = execution(snapshot);
      const { unused } = facts(record);
      const scoped = runSources(snapshot, [], []);
      const doc = buildExport('live', snapshot, scoped.features, scoped.evidence, '2026-10-06T10:00:00.000Z', [snapshot]);
      for (const id of unused) expect(doc.uncited_input_ids).toContain(id);
      const markdown = exportMarkdown(doc);
      const [citedPart, uncitedPart = ''] = markdown.split('## 판단에 인용되지 않은 입력 원문');
      for (const id of unused) {
        expect(uncitedPart).toContain(`**${id}**`);
        expect(citedPart.split('## 인용 근거 원문')[1] ?? '').not.toContain(`**${id}**`);
      }
      // Every exported text is still present (nothing dropped by the split).
      for (const item of doc.evidence) expect(markdown).toContain(`**${item.id}**`);
      const section = markdown.split('## 콘셉트 후보')[1].split('## 실행 단위 미확인 사항')[0];
      for (const reason of record.output!.no_candidate_reasons) expect(section).not.toContain(reason);
    }
  });
});

describe('turned-down candidates, violation targets and check rounds read from the stored trace (R4 U3, record 042)', () => {
  // Expectations straight from the raw recording's trace, not from traceFacts.
  type Raw = { operation: string; outputs?: Record<string, { violations?: { code: string; gap_id?: string; concept_id?: string }[]; candidates?: { concept_id: string; valid: boolean }[] }> & { action?: string; violations?: { code: string }[] } };
  const raw = (record: PlanningExecution) => {
    const trace = record.trace as unknown as Raw[];
    const quality = [...trace].reverse().find(step => step.operation === 'quality_context')!.outputs!;
    const items = ['feature_support', 'residual_matrix', 'concept_lineage'].flatMap(part => quality[part]?.violations ?? []);
    const decisions = trace.filter(step => step.operation === 'review_decision').map(step => step.outputs!);
    return { items, candidates: quality.concept_lineage?.candidates ?? [], decisions };
  };

  it('violations name the gaps/candidates they target; questions with a code get the same IDs', () => {
    for (const { row, snapshot } of RUNS) {
      const record = execution(snapshot);
      const { items } = raw(record);
      const judgement = exportJudgement(snapshot)!;
      if (!judgement.record_valid) throw new Error('expected a valid record');
      for (const violation of record.decision!.violations) {
        const ids = [...new Set(items.filter(item => item.code === violation.code).map(item => item.gap_id ?? item.concept_id!))];
        const line = judgement.violations.find(text => text.includes(`(${violation.code} ·`))!;
        if (ids.length) expect(line, `${row.case} ${violation.code}`).toContain(`대상 ${ids.join(', ')}`);
        else expect(line).not.toContain('대상 ');
      }
    }
    const enumGuide = exportJudgement(RUNS[0].snapshot)!;
    if (!enumGuide.record_valid) throw new Error('expected a valid record');
    expect(enumGuide.violations.find(text => text.includes('(SUPPORT_UNKNOWN ·'))).toContain('대상 GAP-002, GAP-003, GAP-005, GAP-007, GAP-008');
  });

  it('each turned-down candidate carries its stored lineage verdict and own codes; one without codes is not called rejected on its merits', () => {
    for (const { snapshot } of HELD) {
      const record = execution(snapshot);
      const { items, candidates } = raw(record);
      const judgement = exportJudgement(snapshot)!;
      if (!judgement.record_valid) throw new Error('expected a valid record');
      for (const item of judgement.rejected_candidates) {
        expect(item.lineage_valid).toBe(candidates.find(candidate => candidate.concept_id === item.id)?.valid ?? null);
        expect(item.codes).toEqual([...new Set(items.filter(violation => violation.concept_id === item.id).map(violation => violation.code))]);
      }
      const markdown = exportMarkdown(buildExport('live', snapshot, [], [], '2026-10-06T10:00:00.000Z', [snapshot]));
      for (const item of judgement.rejected_candidates) expect(markdown).toContain(item.codes.length ? `${item.id} ${item.title} · 대응 Gap` : '자기 위반 없음, 실행 전체가 끝나 선택 불가');
    }
    const enumGuide = exportJudgement(RUNS[0].snapshot)!;
    if (!enumGuide.record_valid) throw new Error('expected a valid record');
    expect(enumGuide.rejected_candidates.map(item => [item.id, item.lineage_valid, item.codes])).toEqual([['CONCEPT-001', true, []], ['CONCEPT-002', false, ['CONCEPT_WITHOUT_CONFIRMED_GAP']]]);
  });

  it('check rounds follow every stored review decision and mark repeats; the 8B runs repeat the same violations to the revision limit', () => {
    for (const { row, snapshot } of RUNS) {
      const record = execution(snapshot);
      const { decisions } = raw(record);
      const judgement = exportJudgement(snapshot)!;
      if (!judgement.record_valid) throw new Error('expected a valid record');
      expect(judgement.check_rounds.map(round => [round.action, round.codes])).toEqual(decisions.map(item => [item.action, item.violations!.map(v => v.code)]));
      const markdown = exportMarkdown(buildExport('live', snapshot, [], [], '2026-10-06T10:00:00.000Z', [snapshot]));
      expect(markdown, row.case).toContain('회차별 검사 결과(Agent 내부 수정 회차, 사용자 조건 변경 회차와 다름):');
    }
    for (const { snapshot } of FAILED) {
      const judgement = exportJudgement(snapshot)!;
      if (!judgement.record_valid) throw new Error('expected a valid record');
      expect(judgement.check_rounds.map(round => [round.action, round.repeated])).toEqual([['revise', false], ['revise', true], ['unresolved', true]]);
    }
  });
});

describe('real held / failed runs in the actual React DOM (record 034)', () => {
  let host: HTMLDivElement;
  let root: Root;
  const onRerun = vi.fn<(request: PlanningRequest) => Promise<void>>().mockResolvedValue(undefined);
  const measure: MeasureControls = { records: [], start: () => {}, cancel: () => {}, exportRecords: () => {}, error: '' };
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    host = document.createElement('div');
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });

  it.each(RUNS.map(item => [item.row.case, item] as const))('%s: never looks successful or "none generated" when candidates were turned down', async (_name, { row, snapshot }) => {
    await act(async () => root.render(createElement(ConceptsView, { mode: 'live', runs: [snapshot], selected: snapshot, onSelect: () => {}, ...runSources(snapshot, [], []) })));
    const panel = host.querySelector('[aria-label="판단 실행 기록"]')!;
    const head = panel.querySelector('.planning-head .run-status')!;
    expect(head.className).toContain(row.recorded_status === 'failed' ? 'error' : 'notice');
    expect(head.className).not.toContain('done');
    expect(panel.textContent).not.toContain('계약 검사 통과');
    expect(host.querySelectorAll('.concept-card')).toHaveLength(0);
    const rejected = rejectedCandidateCount(snapshot);
    if (rejected) {
      expect(host.textContent).toContain(`채택된 후보가 없습니다. 모델이 만든 후보 ${rejected}개는 코어 검사 결과 보류로 끝나`);
      expect(host.textContent).not.toContain('생성된 후보가 없습니다.');
      expect(panel.textContent).toContain('보류를 일으킨 문제(근거 확인 필요)');
      expect(panel.textContent).toContain('함께 발견된 판단 오류(보류로 내부 수정하지 않음)');
    } else {
      expect(host.textContent).toContain('생성된 후보가 없습니다.');
    }
    if (row.recorded_status === 'failed') for (const item of host.querySelectorAll('.run-status[title]')) expect(item.getAttribute('title')).not.toContain('실행 중 오류');
    // Comparison table: one row per stored gap, the not-accepted note, and the stored resolution next to the support label.
    const output = execution(snapshot).output!;
    expect([...host.querySelectorAll('.comparison-table tbody tr')].map(tr => tr.getAttribute('data-gap-id')).sort()).toEqual(output.gaps.map(gap => gap.id).sort());
    expect(host.querySelector('[data-comparison-unaccepted]')).not.toBeNull();
    expect(host.querySelectorAll('.comparison-table [data-field="resolution"]')).toHaveLength(output.gaps.filter(gap => output.gap_assessments.some(item => item.gap_id === gap.id)).length);
    if (output.desired_outcomes.length) expect(host.querySelector('.comparison-table .desired-outcome')?.textContent).toContain('바라는 결과:');
    // Assessed reviews that no need/gap cites are flagged in the core record panel.
    const cited = new Set([...output.needs.flatMap(need => need.evidence_ids), ...output.gaps.flatMap(gap => gap.evidence_ids)]);
    const unused = output.review_assessments.map(item => item.evidence_id).filter(id => !cited.has(id));
    expect([...host.querySelectorAll('[data-unused-review]')].map(node => node.getAttribute('data-unused-review'))).toEqual(unused);
    // R4 U3: every rejected candidate states why, rows without a candidate body are listed, and check rounds are shown.
    const rejectedOutput = execution(snapshot).rejected_output;
    expect([...host.querySelectorAll('[data-rejected-concept]')].map(node => node.getAttribute('data-rejected-concept'))).toEqual((rejectedOutput?.concepts ?? []).map(concept => concept.id));
    for (const node of host.querySelectorAll('[data-rejected-concept]')) expect(node.querySelector('[data-field="rejection"]')).not.toBeNull();
    const orphans = (rejectedOutput?.concept_assessments ?? []).filter(item => !(rejectedOutput?.concepts ?? []).some(concept => concept.id === item.concept_id)).map(item => item.concept_id);
    expect([...host.querySelectorAll('[data-orphan-assessment]')].map(node => node.getAttribute('data-orphan-assessment'))).toEqual(orphans);
    expect(host.querySelectorAll('.check-rounds [data-round]').length).toBeGreaterThan(0);
    if (row.recorded_status === 'failed') expect(host.querySelector('.check-rounds [data-field="terminal"]')?.textContent).toContain('revision_limit');
  });

  it.each(RUNS.map(item => [item.row.case, item] as const))('%s: the revision timeline does not call a first run without candidates "the first run\'s candidates"', async (_name, { snapshot }) => {
    await act(async () => root.render(createElement(HistoryView, {
      mode: 'live', runs: [snapshot], selected: snapshot, original: snapshot.request, onSelect: () => {}, ...runSources(snapshot, [], []), onRerun, measure,
    })));
    const timeline = host.querySelector('[data-revision-timeline]')!;
    const rejected = rejectedCandidateCount(snapshot);
    const label = snapshot.run.status === 'held' ? '보류' : '실패';
    expect(timeline.textContent).not.toContain('첫 실행의 후보입니다.');
    expect(timeline.querySelector('[data-field="candidates"]')?.textContent).toBe(`첫 실행에서 채택된 후보가 없습니다(${label}${rejected ? ` · 검사에서 거절된 후보 ${rejected}개` : ''}).`);
    const status = timeline.querySelector('[data-field="run-status"]')!;
    if (snapshot.run.status === 'failed') expect(status.getAttribute('title')).toContain('내부 수정 한도(2회)');
  });
});
