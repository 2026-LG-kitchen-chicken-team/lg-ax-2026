// Inputs are hand-written objects, not model output or a live service; they exercise the real comparison and rendering.
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Evidence } from './domain';
import { EvidenceTracePanel, buildEvidenceTrace, currentEvidenceForSnapshot, subjectFromGap } from './EvidenceTracePanel';
import type { Feature, Gap } from './planning';
import { FIXTURE_BOOTSTRAP, FIXTURE_RUNS } from './fixtures/planning.fixture';

const SCOPE = { model_id: 'FRIDGE-A', document_version: 'v2' };
const source = (id: string, patch: Partial<Evidence> = {}): Evidence => ({
  id, model_id: 'FRIDGE-A', document_version: 'v2', source_kind: 'synthetic', source_type: 'review', source_id: `src-${id}`,
  locator: { page: 3, row: 12 }, text: `원문 ${id}`, feature_ids: [], ...patch,
});
const FEATURE: Feature = { id: 'F-1', model_id: 'FRIDGE-A', document_version: 'v2', name: '선반 분리', description: '', conditions: [], evidence_ids: ['M-1'] };
const GAP: Gap = { id: 'G-1', need_id: 'N-1', model_id: 'FRIDGE-A', feature_ids: ['F-1'], support_status: 'unsupported', remaining_pain: '', evidence_ids: ['R-1', 'M-1'], questions: [] };
const REVIEW = source('R-1');
const MANUAL = source('M-1', { source_type: 'manual', locator: { page: 41, section: '청소' }, text: '선반은 분리할 수 있습니다.' });

const trace = (evidence: Evidence[], judged?: Evidence[], gap: Gap = GAP, features: Feature[] = [FEATURE]) => buildEvidenceTrace({ subject: subjectFromGap(gap, '선반 청소'), scope: SCOPE, features, evidence, judged });
const status = (result: ReturnType<typeof trace>, id: string) => result.rows.find(row => row.id === id)?.status;

describe('buildEvidenceTrace', () => {
  it('does not treat a public bootstrap as current private-workspace data without matching dataset identity', () => {
    expect(currentEvidenceForSnapshot(FIXTURE_BOOTSTRAP, FIXTURE_RUNS[0])).toBeUndefined();
    const unrelated = { ...FIXTURE_BOOTSTRAP, manifest: { ...FIXTURE_BOOTSTRAP.manifest, dataset_sha256: 'f'.repeat(64) } };
    expect(currentEvidenceForSnapshot(unrelated, FIXTURE_RUNS[0])).toBeUndefined();
    const matched = { ...FIXTURE_BOOTSTRAP, manifest: { ...FIXTURE_BOOTSTRAP.manifest, dataset_sha256: FIXTURE_RUNS[0].dataset_sha256 } };
    expect(currentEvidenceForSnapshot(matched, FIXTURE_RUNS[0])).toBe(matched.evidence);
  });
  it('accepts review and manual sources inside the model and document version', () => {
    const result = trace([REVIEW, MANUAL]);
    expect(result.rows.map(row => [row.id, row.status, row.role])).toEqual([['R-1', 'usable', 'review'], ['M-1', 'usable', 'manual']]);
    expect(result.sufficient).toBe(true);
    expect(result.insufficiency).toEqual([]);
  });

  it('tells apart a different model, a different version, a deleted source and one never found', () => {
    const result = trace(
      [source('R-1', { model_id: 'DISH-B' }), source('M-1', { source_type: 'manual', document_version: 'v1' })],
      [REVIEW, MANUAL, source('R-9')],
      { ...GAP, evidence_ids: ['R-1', 'M-1', 'R-9', 'R-404'] },
    );
    expect(status(result, 'R-1')).toBe('other_model');
    expect(status(result, 'M-1')).toBe('other_version');
    expect(status(result, 'R-9')).toBe('deleted');
    expect(status(result, 'R-404')).toBe('not_found');
    expect(result.rows.find(row => row.id === 'R-1')?.source?.model_id).toBe(REVIEW.model_id);
    expect(result.rows.find(row => row.id === 'R-1')?.current?.model_id).toBe('DISH-B');
    expect(result.rows.find(row => row.id === 'M-1')?.source?.document_version).toBe(MANUAL.document_version);
    expect(result.rows.find(row => row.id === 'M-1')?.current?.document_version).toBe('v1');
    expect(result.rows.find(row => row.id === 'R-9')?.source?.text).toBe('원문 R-9');
    expect(result.rows.find(row => row.id === 'R-404')?.source).toBeNull();
    expect(result.sufficient).toBe(false);
    expect(result.insufficiency.join(' ')).toContain('범위 일치가 아닌 인용이 4건');
  });

  it('flags a source whose text changed after the judgement instead of counting it as support', () => {
    const result = trace([REVIEW, source('M-1', { source_type: 'manual', text: '선반은 분리할 수 없습니다.' })], [REVIEW, MANUAL]);
    expect(status(result, 'M-1')).toBe('changed');
    expect(result.rows.find(row => row.id === 'M-1')?.source?.text).toBe(MANUAL.text);
    expect(result.rows.find(row => row.id === 'M-1')?.current?.text).toBe('선반은 분리할 수 없습니다.');
    expect(result.sufficient).toBe(false);
    expect(result.insufficiency.join(' ')).toContain("기능 '선반 분리'(F-1)의 설명서 원문");
  });

  it('reports insufficiency when only manual evidence is usable, or a compared feature is missing', () => {
    const noReview = trace([MANUAL]);
    expect(noReview.sufficient).toBe(false);
    expect(noReview.insufficiency.join(' ')).toContain('고객 리뷰 원문이 없어');
    const noFeature = trace([REVIEW, MANUAL], undefined, GAP, []);
    expect(noFeature.insufficiency).toContain('비교 대상 기능 F-1의 자료가 없습니다.');
  });

  it('counts a citation-less judgement as insufficient and does not invent rows', () => {
    const result = trace([REVIEW], undefined, { ...GAP, evidence_ids: [], feature_ids: [] }, []);
    expect(result.rows).toEqual([]);
    expect(result.insufficiency).toEqual(['이 판단에 인용된 근거가 없습니다.']);
  });

  it('adds the feature manual sources the gap itself did not cite, and reports them missing', () => {
    const result = trace([REVIEW], undefined, { ...GAP, evidence_ids: ['R-1'] });
    expect(result.rows.map(row => [row.id, row.status, row.role])).toEqual([['R-1', 'usable', 'review'], ['M-1', 'not_found', 'manual']]);
    expect(result.sufficient).toBe(false);
  });

  it('does not change the sources it reads', () => {
    const evidence = [REVIEW, MANUAL];
    const before = JSON.stringify(evidence);
    trace(evidence, [REVIEW, MANUAL]);
    expect(JSON.stringify(evidence)).toBe(before);
  });
});

describe('EvidenceTracePanel', () => {
  const html = (result: ReturnType<typeof trace>) => renderToStaticMarkup(createElement(EvidenceTracePanel, { trace: result }));

  it('shows original text, page/row, model, version and real/synthetic kind', () => {
    const markup = html(trace([REVIEW, source('M-1', { source_type: 'manual', source_kind: 'public', locator: { page: 41, section: '청소' } })]));
    expect(markup).toContain('원문 R-1');
    expect(markup).toContain('3쪽 · 12행');
    expect(markup).toContain('41쪽 · 청소');
    expect(markup).toContain('FRIDGE-A · 문서 v2');
    expect(markup).toContain('합성 자료');
    expect(markup).toContain('공개 실제 자료');
    expect(markup).toContain('data-trace="sufficient"');
  });

  it('shows the insufficiency alert with deleted and not-found rows kept apart', () => {
    const markup = html(trace([source('M-1', { source_type: 'manual' })], [REVIEW], { ...GAP, evidence_ids: ['R-1', 'R-404', 'M-1'] }));
    expect(markup).toContain('data-trace="insufficient"');
    expect(markup).toContain('role="alert"');
    expect(markup).toContain('data-status="deleted"');
    expect(markup).toContain('삭제된 자료');
    expect(markup).toContain('data-status="not_found"');
    expect(markup).toContain('R-404 · 원문을 찾을 수 없습니다(자료 누락)');
  });

  it('renders source text as plain text, never as markup', () => {
    const markup = html(trace([source('R-1', { text: '<img src=x onerror=alert(1)> **굵게**' }), MANUAL]));
    expect(markup).not.toContain('<img');
    expect(markup).toContain('&lt;img src=x onerror=alert(1)&gt; **굵게**');
  });

  it('does not claim a current-source check when only the stored inputs are available', () => {
    const markup = renderToStaticMarkup(createElement(EvidenceTracePanel, { trace: trace([REVIEW, MANUAL]), currentAvailable: false }));
    expect(markup).toContain('현재 자료를 조회하지 못해');
    expect(markup).toContain('변경·삭제 여부는 확인되지 않았습니다');
    expect(markup).not.toContain('조회한 자료의');
  });
});
