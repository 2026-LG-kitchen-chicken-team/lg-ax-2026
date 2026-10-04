import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseBootstrap } from './api';
import type { Evidence } from './domain';
import { FIXTURE_BOOTSTRAP, FIXTURE_DATASET_SHA256, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import {
  buildComparison, buildExport, buildRerunRequest, canonical, conceptChanges, conceptDetailChanges, contractErrors, draftRunFromRequest,
  draftRunWithCondition, exportCompleteness, exportMarkdown, heldItems, missingRequestQuestions, nextRequestRevision, requestChanges, splitConditions,
} from './planning';
import type { Feature, PlanningRequest } from './planning';

const dataset = JSON.parse(readFileSync(new URL('../../../data/demo/dataset.json', import.meta.url), 'utf8'));
const evidence = FIXTURE_BOOTSTRAP.evidence as Evidence[];
const features = FIXTURE_BOOTSTRAP.features as unknown as Feature[];
const [first, second] = FIXTURE_RUNS;

describe('contract fixture', () => {
  it('passes the shared bootstrap contract through the same parser as the live API', () => {
    expect(() => parseBootstrap({ ok: true, data: FIXTURE_BOOTSTRAP })).not.toThrow();
  });
  it('copies demo dataset entries verbatim so fixture text cannot drift from the source', () => {
    for (const key of ['products', 'reviews', 'features', 'evidence'] as const) {
      for (const item of FIXTURE_BOOTSTRAP[key] as { id?: string; model_id: string }[]) {
        const source = (dataset[key] as { id?: string; model_id: string }[]).find(entry => (entry.id ?? entry.model_id) === (item.id ?? item.model_id));
        expect(source, `${key} ${item.id ?? item.model_id}`).toEqual(item);
      }
    }
  });
  it('records the canonical dataset hash used by the workspace server', () => {
    expect(createHash('sha256').update(canonical(dataset), 'utf8').digest('hex')).toBe(FIXTURE_DATASET_SHA256);
  });
  it('validates every run, need, gap and concept against the shared schema', () => {
    for (const snapshot of FIXTURE_RUNS) {
      expect(contractErrors('WorkspaceRunSnapshot', snapshot)).toEqual([]);
      for (const need of snapshot.output!.needs) expect(contractErrors('Need', need)).toEqual([]);
      for (const gap of snapshot.output!.gaps) expect(contractErrors('Gap', gap)).toEqual([]);
      expect(snapshot.run.concepts.length).toBeLessThanOrEqual(3);
    }
  });
  it('only cites evidence and features present in the fixture bootstrap', () => {
    const ids = new Set(evidence.map(item => item.id));
    const featureIds = new Set(features.map(item => item.id));
    for (const snapshot of FIXTURE_RUNS) {
      const cited = [...snapshot.run.evidence_ids, ...snapshot.run.concepts.flatMap(item => item.evidence_ids), ...snapshot.output!.needs.flatMap(item => item.evidence_ids), ...snapshot.output!.gaps.flatMap(item => item.evidence_ids)];
      expect(cited.filter(id => !ids.has(id))).toEqual([]);
      expect(snapshot.output!.gaps.flatMap(item => item.feature_ids).filter(id => !featureIds.has(id))).toEqual([]);
    }
  });
});

describe('R02 request validation, questions and change requests', () => {
  it('asks a question for each missing field instead of filling defaults', () => {
    const questions = missingRequestQuestions({ ...FIXTURE_ORIGINAL_REQUEST, target_customer: '  ', use_situation: '', model_ids: [], dataset_version: '' });
    expect(questions.map(item => item.field)).toEqual(['target_customer', 'use_situation', 'model_ids', 'dataset_version']);
    expect(missingRequestQuestions(FIXTURE_ORIGINAL_REQUEST)).toEqual([]);
  });
  it('rejects requests outside the shared contract', () => {
    expect(contractErrors('PlanningRequest', FIXTURE_ORIGINAL_REQUEST)).toEqual([]);
    expect(contractErrors('PlanningRequest', { ...FIXTURE_ORIGINAL_REQUEST, product_group: 'oven' }).length).toBeGreaterThan(0);
  });
  it('lists field-level changes and follows the server request revision rule', () => {
    const changed: PlanningRequest = { ...FIXTURE_ORIGINAL_REQUEST, use_situation: '우유를 흘린 구역만 청소' };
    expect(requestChanges(FIXTURE_ORIGINAL_REQUEST, changed)).toEqual([{ field: 'use_situation', label: '사용 상황', before: FIXTURE_ORIGINAL_REQUEST.use_situation, after: '우유를 흘린 구역만 청소' }]);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, null, FIXTURE_ORIGINAL_REQUEST)).toBe(0);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, null, changed)).toBe(1);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, second, second.request)).toBe(1);
    expect(nextRequestRevision(FIXTURE_ORIGINAL_REQUEST, second, changed)).toBe(2);
  });
});

describe('R14 comparison table', () => {
  it('joins needs, features, conditions, remaining pain and evidence', () => {
    const rows = buildComparison(first.output!, features, evidence);
    expect(rows).toHaveLength(2);
    expect(rows[0].features.map(item => item.id)).toEqual(['FEATURE-001']);
    expect(rows[0].conditions).toEqual(['선반 위 식품을 모두 이동']);
    expect(rows[0].gap?.support_status).toBe('unsupported');
    expect(rows[0].evidence.map(item => item.id)).toContain('MANUAL-001');
    expect(rows[1].gap?.support_status).toBe('insufficient_evidence');
    expect(rows.every(row => row.missingIds.length === 0)).toBe(true);
  });
  it('reports missing source IDs instead of dropping them silently', () => {
    const rows = buildComparison(first.output!, [], evidence.filter(item => item.id !== 'MANUAL-001'));
    expect(rows[0].missingIds).toEqual(['FEATURE-001', 'MANUAL-001']);
  });
});

describe('R21 additional condition creates a new linked run', () => {
  it('creates a contract-valid not_implemented draft without inventing concepts', () => {
    const draft = draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '1인 가구 소형 모델만', 'RUN-DRAFT-1', '2026-10-04T09:00:00.000Z');
    expect(draft.previous_run_id).toBe('RUN-FX-002');
    expect(draft.request_revision).toBe(2);
    expect(draft.request.exclusions.at(-1)).toBe('1인 가구 소형 모델만');
    expect(draft.run.status).toBe('not_implemented');
    expect(draft.run.concepts).toEqual([]);
    expect(draft.output).toBeNull();
    expect(second.request.exclusions).not.toContain('1인 가구 소형 모델만');
  });
  it('rejects empty or duplicate conditions', () => {
    expect(() => draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '  ', 'RUN-DRAFT-2', '2026-10-04T09:00:00.000Z')).toThrow(/추가할 조건/);
    expect(() => draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '실기기 제어', 'RUN-DRAFT-3', '2026-10-04T09:00:00.000Z')).toThrow(/이미 같은 조건/);
  });
  it('shows concept status changes between linked runs', () => {
    expect(conceptChanges(first, second)).toEqual([{ id: 'CONCEPT-FX-001', title: '오염 구획만 꺼내는 분리 청소 트레이', before: 'needs_review', after: 'rejected' }]);
    expect(conceptChanges(undefined, first).map(item => item.after)).toEqual(['needs_review', 'proposed']);
  });
});

describe('P2-WEB-003 candidate choices, condition correction and combined review', () => {
  const concepts = first.run.concepts;
  it('writes excluded and focused candidates into the request within the shared contract', () => {
    const next = buildRerunRequest(first.request, concepts, { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' }, ['실기기 제어', '1인 가구 소형 모델만']);
    expect(next.exclusions).toEqual(['실기기 제어', '1인 가구 소형 모델만', '후보 제외: 오염 구획만 꺼내는 분리 청소 트레이 (CONCEPT-FX-001)']);
    expect(next.improvement_task).toBe(`${first.request.improvement_task} [집중 검토: 청소 전 식품 이동 범위 안내 (CONCEPT-FX-002)]`);
    expect(next.model_ids).toEqual(first.request.model_ids);
    expect(contractErrors('PlanningRequest', next)).toEqual([]);
  });
  it('is idempotent across reruns: focus suffix and candidate exclusions are replaced, not stacked', () => {
    const once = buildRerunRequest(first.request, concepts, { 'CONCEPT-FX-001': 'exclude', 'CONCEPT-FX-002': 'focus' }, splitConditions(first.request).conditions);
    const twice = buildRerunRequest(once, concepts, { 'CONCEPT-FX-001': 'keep', 'CONCEPT-FX-002': 'keep' }, splitConditions(once).conditions);
    expect(twice.improvement_task).toBe(first.request.improvement_task);
    expect(twice.exclusions).toEqual(first.request.exclusions);
    expect(splitConditions(once)).toEqual({ conditions: first.request.exclusions, excludedCandidates: ['후보 제외: 오염 구획만 꺼내는 분리 청소 트레이 (CONCEPT-FX-001)'] });
  });
  it('corrects conditions: edits, removals and blanks are applied, duplicates collapse', () => {
    const next = buildRerunRequest(first.request, [], {}, ['실기기 제어', '  ', '실기기 제어', '제조용 CAD 제외']);
    expect(next.exclusions).toEqual(['실기기 제어', '제조용 CAD 제외']);
    expect(requestChanges(first.request, next).map(item => item.field)).toEqual(['exclusions']);
  });
  it('shows what changed inside each candidate between linked runs', () => {
    const changes = conceptDetailChanges(first, second);
    expect(changes).toHaveLength(1);
    expect(changes[0]).toMatchObject({ id: 'CONCEPT-FX-001', status: ['needs_review', 'rejected'] });
    expect(changes[0].added.assumptions).toEqual(['추가 조건에 따라 문서 2.0 FEATURE-006과 중복 가능성이 있어 제외']);
    expect(changes[0].removed).toEqual({ requirements: [], assumptions: [], evidence_ids: [] });
  });
  it('lists held items: insufficient-evidence gaps with their questions, then unresolved notes', () => {
    const held = heldItems(second);
    expect(held[0]).toMatchObject({ kind: 'insufficient_evidence', id: 'GAP-FX-002' });
    expect(held[0].questions[0]).toContain('임시 보관');
    expect(held.filter(item => item.kind === 'unresolved').map(item => item.text)).toEqual(second.run.unresolved);
  });
  it('creates a linked draft from a full rerun request in fixture mode', () => {
    const next = buildRerunRequest(second.request, second.run.concepts, { 'CONCEPT-FX-002': 'focus' }, splitConditions(second.request).conditions);
    const draft = draftRunFromRequest(second, FIXTURE_ORIGINAL_REQUEST, next, 'RUN-DRAFT-9', '2026-10-04T10:00:00.000Z');
    expect(draft).toMatchObject({ previous_run_id: 'RUN-FX-002', request_revision: 2, output: null });
    expect(draft.run.status).toBe('not_implemented');
  });
});

describe('R27 meeting export', () => {
  const doc = buildExport('fixture', second, features, evidence, '2026-10-04T09:00:00.000Z');
  const markdown = exportMarkdown(doc);
  it('includes every cited evidence text, requirement, assumption and unresolved item', () => {
    const cited = new Set([...second.run.evidence_ids, ...second.run.concepts.flatMap(item => item.evidence_ids), ...second.output!.needs.flatMap(item => item.evidence_ids), ...second.output!.gaps.flatMap(item => item.evidence_ids)]);
    expect(doc.evidence.map(item => item.id).sort()).toEqual([...cited].sort());
    for (const item of doc.evidence) expect(markdown).toContain(item.text);
    for (const concept of second.run.concepts) {
      for (const text of [...concept.requirements, ...concept.assumptions]) expect(markdown).toContain(text);
    }
    for (const text of [...second.run.unresolved, ...second.unconfirmed]) expect(markdown).toContain(text);
  });
  it('P2-WEB-004: includes held items and lineage, and its self-check passes', () => {
    const full = buildExport('fixture', second, features, evidence, '2026-10-04T09:00:00.000Z', FIXTURE_RUNS);
    expect(full.held.map(item => item.id)).toEqual(['GAP-FX-002']);
    expect(full.lineage.map(item => [item.run_id, item.request_revision])).toEqual([['RUN-FX-001', 0], ['RUN-FX-002', 1]]);
    expect(full.completeness).toEqual({ complete: true, missing_evidence: [], missing_requirements: [], missing_assumptions: [], missing_unresolved: [], missing_held: [] });
    const md = exportMarkdown(full);
    expect(md).toContain('## 근거 부족으로 보류한 불편');
    expect(md).toContain('RUN-FX-001 · 요청 회차 0');
    expect(md).toContain('보류가 모두 포함되었습니다');
  });
  it('P2-WEB-004: the self-check reports what an export would leave out', () => {
    const lossy = buildExport('fixture', second, features, evidence.filter(item => item.id !== 'MANUAL-001'), '2026-10-04T09:00:00.000Z');
    expect(lossy.completeness.complete).toBe(false);
    expect(lossy.completeness.missing_evidence).toEqual(['MANUAL-001']);
    const trimmed = { ...lossy, requirements: lossy.requirements.slice(1), assumptions: [], held: [] };
    const check = exportCompleteness(trimmed, second);
    expect(check.missing_requirements).toHaveLength(1);
    expect(check.missing_assumptions).toContain('문서 범위를 2.0으로 확대할지 기획자 결정 필요');
    expect(check.missing_held).toEqual(['GAP-FX-002']);
    expect(exportMarkdown(lossy)).toContain('누락이 있습니다');
  });
  it('keeps the compared model on every comparison row', () => {
    expect(doc.comparison.every(row => row.model_id === 'FRIDGE-A')).toBe(true);
    expect(markdown).toContain('| 모델 | 불편 |');
    expect(markdown).toContain('| FRIDGE-A | NEED-FX-001');
  });
  it('accepts the shared multi-model sample requests', () => {
    const samples = JSON.parse(readFileSync(new URL('../../../data/demo/planning_requests.json', import.meta.url), 'utf8')) as PlanningRequest[];
    expect(samples[0].model_ids).toEqual(['FRIDGE-A', 'FRIDGE-B', 'FRIDGE-C']);
    for (const sample of samples) {
      expect(contractErrors('PlanningRequest', sample)).toEqual([]);
      expect(missingRequestQuestions(sample)).toEqual([]);
    }
  });
  it('labels fixture exports so they are not mistaken for Agent output', () => {
    expect(doc.meta.mode).toBe('fixture');
    expect(markdown).toContain('Agent 출력이나 서버 응답이 아니며');
    expect(JSON.parse(JSON.stringify(doc)).meta.notice).toBe(doc.meta.notice);
  });
  it('keeps the export usable for a draft without results', () => {
    const draft = draftRunWithCondition(second, FIXTURE_ORIGINAL_REQUEST, '추가 조건', 'RUN-DRAFT-4', '2026-10-04T09:00:00.000Z');
    const empty = exportMarkdown(buildExport('fixture', draft, features, evidence, '2026-10-04T09:00:00.000Z'));
    expect(empty).toContain('생성된 콘셉트가 없습니다.');
    expect(empty).toContain('not_implemented');
  });
});
