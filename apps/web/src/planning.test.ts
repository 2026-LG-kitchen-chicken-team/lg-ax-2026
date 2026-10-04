import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseBootstrap } from './api';
import type { Evidence } from './domain';
import { FIXTURE_BOOTSTRAP, FIXTURE_DATASET_SHA256, FIXTURE_ORIGINAL_REQUEST, FIXTURE_RUNS } from './fixtures/planning.fixture';
import {
  buildComparison, buildExport, canonical, conceptChanges, contractErrors, draftRunWithCondition, exportMarkdown,
  missingRequestQuestions, nextRequestRevision, requestChanges,
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
