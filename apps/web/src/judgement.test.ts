// @vitest-environment jsdom
// CORE-001 judgement contract (PR #51) on the web side. Inputs and outputs are the core's hand-written fixtures in
// evals/core-contract; the decisions are what lgax_core.judgement_contract.review_judgement actually returned when
// evals/core-contract/check_cases.py was run (saved under evals/web/20261004/p2-web-003-core-judgement/).
// Passing shows the web keeps and shows what the contract carries; it says nothing about a real model's judgement.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import canonical from '../../../packages/contracts/schemas/lgax.schema.json';
import outputSchema from '../../../evals/core-contract/schemas/output.json';
import { JudgementPanel } from './JudgementViews';
import { judgementDecisionErrors, judgementOutputErrors, judgementRunSnapshot, judgementView } from './judgement';
import type { JudgementDecision, JudgementInput, JudgementOutput } from './judgement';
import { buildComparison, buildExport, candidateChoicesFor, contractErrors, exportCompleteness, exportMarkdown, heldItems } from './planning';

// vitest runs from apps/web (npm test); repository files are read as plain data, not bundled.
const read = (path: string) => JSON.parse(readFileSync(resolve(process.cwd(), '../..', path), 'utf-8'));
const SUITES = ['development', 'heldout'] as const;
const TYPES = ['normal', 'duplicate', 'model_confusion', 'conflicting_reviews', 'missing_evidence', 'spec_change'];
const EXPECTED_ACTION: Record<string, JudgementDecision['action']> = {
  normal: 'accept', duplicate: 'revise', model_confusion: 'hold', conflicting_reviews: 'hold', missing_evidence: 'revise', spec_change: 'revise',
};

interface Case { suite: string; case_id: string; type: string; input: JudgementInput; output: JudgementOutput; decision: JudgementDecision; expected: { action: string; rerun_from: string | null; codes: string[] } }
const CASES: Case[] = SUITES.flatMap(suite => {
  const manifest = read(`evals/core-contract/${suite}/cases.json`);
  const run = read(`evals/web/20261004/p2-web-003-core-judgement/core-decisions-${suite}.json`);
  return manifest.cases.map((item: { case_id: string; type: string; input: string; fixture_output: string }) => {
    const observed = run.cases.find((row: { case_id: string }) => row.case_id === item.case_id);
    return {
      suite, case_id: item.case_id, type: item.type,
      input: read(`evals/core-contract/${suite}/${item.input}`), output: read(`evals/core-contract/${suite}/${item.fixture_output}`),
      decision: observed.decision, expected: read(`evals/core-contract/${suite}/expected.json`)[item.case_id],
    };
  });
});
const META = { run_id: 'RUN-CORE-FIXTURE', project_id: 'PROJ-CORE-FIXTURE', created_at: '2026-10-05T00:00:00.000000Z', dataset_sha256: 'a'.repeat(64), actor_id: 'core-judgement-fixture' };

describe('CORE-001 judgement contract cases on the web (core fixtures + actual core decisions)', () => {
  it('uses the reviewed Schema copy built from the shared 0.1.0 definitions', () => {
    const defs = (canonical as { $defs: Record<string, unknown> }).$defs;
    const copy = (outputSchema as { $defs: Record<string, unknown> }).$defs;
    for (const name of ['Need', 'Gap', 'Concept']) expect(copy[name]).toEqual(defs[name]);
    expect(copy.ID).toEqual((defs.Need as { properties: { id: unknown } }).properties.id);
  });

  it('covers the six core case types in both suites and all three products in the held-out suite', () => {
    for (const suite of SUITES) expect(CASES.filter(item => item.suite === suite).map(item => item.type)).toEqual(TYPES);
    expect(new Set(CASES.filter(item => item.suite === 'heldout').map(item => item.input.product.product_group))).toEqual(new Set(['fridge', 'dishwasher', 'microwave']));
  });

  it('every fixture declares itself completed, so only the core decision can tell the cases apart', () => {
    expect(new Set(CASES.map(item => item.output.status))).toEqual(new Set(['completed']));
  });

  describe.each(CASES)('$case_id', ({ type, input, output, decision, expected }) => {
    it('has a valid output, a consistent core decision and the expected action', () => {
      expect(judgementOutputErrors(output)).toEqual([]);
      expect(judgementDecisionErrors(decision)).toEqual([]);
      for (const source of input.sources) expect(contractErrors('Evidence', source)).toEqual([]);
      for (const feature of input.features) expect(contractErrors('Feature', feature)).toEqual([]);
      expect(contractErrors('PlanningRequest', input.request)).toEqual([]);
      expect({ action: decision.action, rerun_from: decision.rerun_from, codes: decision.violations.map(item => item.code).sort() }).toEqual(expected);
      expect(decision.action).toBe(EXPECTED_ACTION[type]);
    });

    it('reads the decision, not the declared status, and only an accepted judgement offers candidates', () => {
      const view = judgementView(input, output, decision);
      expect(view.candidates_selectable).toBe(decision.action === 'accept');
      expect(view.declared_status_overridden).toBe(decision.action !== 'accept');
      expect(view.violations).toHaveLength(decision.violations.length);
      for (const [index, item] of decision.violations.entries()) expect(view.violations[index]).toContain(item.code);
      expect(view.out_of_scope_sources.length > 0).toBe(type === 'model_confusion');
    });

    it('becomes a stored-run view only for a terminal decision, mapped as the core contract document says', () => {
      const snapshot = judgementRunSnapshot(input, output, decision, META);
      if (decision.action === 'revise') { expect(snapshot).toBeNull(); return; }
      expect(snapshot).not.toBeNull();
      expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
      expect(snapshot!.run.status).toBe(decision.action === 'accept' ? 'completed' : 'held');
      expect(snapshot!.run.concepts).toEqual(decision.action === 'accept' ? output.concepts : []);
      expect(Object.keys(candidateChoicesFor(snapshot!.request, snapshot!.run.concepts))).toHaveLength(snapshot!.run.concepts.length);
      for (const item of decision.violations) expect(snapshot!.run.unresolved.join('\n')).toContain(item.code);
      expect(heldItems(snapshot!).filter(item => item.kind === 'unresolved')).toHaveLength(snapshot!.run.unresolved.length);
      // Every cited source of the comparison is in the judgement input, with its own text.
      for (const row of buildComparison(snapshot!.output!, input.features, input.sources)) {
        expect(row.missingIds).toEqual([]);
        expect(row.evidence.length).toBeGreaterThan(0);
      }
      const doc = buildExport('live', snapshot!, input.features, input.sources, '2026-10-05T00:00:01.000Z');
      expect(exportCompleteness(doc, snapshot!, input.features, input.sources).complete).toBe(true);
      expect(doc.unresolved).toEqual(snapshot!.run.unresolved);
      expect(exportMarkdown(doc)).toContain(decision.action === 'accept' ? output.concepts[0].title : '미해결·보류');
    });
  });

  it('rejects malformed outputs and decisions instead of displaying them', () => {
    const output = CASES[0].output;
    expect(judgementOutputErrors({ ...output, status: 'done' })).not.toEqual([]);
    expect(judgementOutputErrors({ ...output, extra: true })).not.toEqual([]);
    const { questions: _dropped, ...missing } = output;
    expect(judgementOutputErrors(missing)).not.toEqual([]);
    expect(judgementOutputErrors({ ...output, concepts: [...output.concepts, ...output.concepts, ...output.concepts, ...output.concepts] })).not.toEqual([]);
    const decision = CASES[1].decision;
    expect(judgementDecisionErrors({ ...decision, valid: true })).toContain('/valid does not match violations');
    expect(judgementDecisionErrors({ ...decision, rerun_from: null })).toContain('/rerun_from is set only for revise');
    expect(judgementDecisionErrors({ ...decision, next_revision_count: decision.revision_count })).toContain('/next_revision_count must count only an actual revise');
    expect(judgementDecisionErrors({ ...decision, action: 'retry' })).not.toEqual([]);
  });

  it('preserves accepted zero-candidate reasons through snapshots and exports without calling them unresolved', () => {
    const { input, output: original, decision } = CASES.find(item => item.suite === 'development' && item.type === 'normal')!;
    const reasons = ['현재 조건에서 제안할 신규 콘셉트가 없습니다.', '추가 후보를 만들지 않은 검토 사유\n원문을 유지합니다.'];
    const output: JudgementOutput = { ...structuredClone(original), concepts: [], concept_assessments: [], no_candidate_reasons: [...reasons] };
    expect(judgementOutputErrors(output)).toEqual([]);
    const snapshot = judgementRunSnapshot(input, output, decision, META)!;
    expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
    expect(snapshot.run.status).toBe('completed');
    expect(snapshot.run.concepts).toEqual([]);
    expect(snapshot.run.unresolved).toEqual([]);
    expect(snapshot.output!.no_candidate_reasons).toEqual(reasons);
    output.no_candidate_reasons[0] = '원 선언을 이후에 변경';
    expect(snapshot.output!.no_candidate_reasons).toEqual(reasons);

    const doc = buildExport('fixture', snapshot, input.features, input.sources, '2026-10-05T00:00:01.000Z');
    expect(doc.no_candidate_reasons).toEqual(reasons);
    expect(doc.unresolved).toEqual([]);
    expect(doc.completeness.complete).toBe(true);
    const markdown = exportMarkdown(doc);
    expect(markdown).toContain(`후보 없음 사유:\n- ${reasons.join('\n- ')}`);
    expect(markdown).toContain('## 미해결·보류\n\n- 없음');

    for (const lost of [{ ...doc, no_candidate_reasons: undefined }, { ...doc, no_candidate_reasons: [] }, { ...doc, no_candidate_reasons: ['변조한 사유'] }]) {
      const completeness = exportCompleteness(lost, snapshot, input.features, input.sources);
      expect(completeness.complete).toBe(false);
      expect(completeness.mismatched_fields).toContain('후보 없음 사유');
    }
    doc.no_candidate_reasons![0] = '다운로드 문서를 이후에 변경';
    expect(snapshot.output!.no_candidate_reasons).toEqual(reasons);
  });
});

describe('JudgementPanel (rendered)', () => {
  let container: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
  });
  afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals(); });

  it.each(CASES.filter(item => item.suite === 'heldout'))('$case_id shows the decision, the fixture notice and the source text', ({ input, output, decision }) => {
    act(() => root.render(createElement(JudgementPanel, { input, output, decision, fixture: true })));
    const text = container.textContent ?? '';
    const view = judgementView(input, output, decision);
    expect(text).toContain(view.label);
    expect(text).toContain('모델이 생성한 결과가 아닙니다');
    for (const item of output.review_assessments) expect(text).toContain(input.sources.find(source => source.id === item.evidence_id)!.text);
    expect(text.includes('선택 불가')).toBe(decision.action !== 'accept');
    expect(text.includes(`스스로 선언한 상태는 '${output.status}'`)).toBe(decision.action !== 'accept');
    for (const item of view.violations) expect(text).toContain(item);
    for (const item of view.out_of_scope_sources) expect(text).toContain(item);
  });
});
