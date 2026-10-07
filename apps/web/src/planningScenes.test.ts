// Inputs are hand-written objects (not model output, not shown in the product); they exercise the real adapter and
// rendering. The extra fields are the WEB proposal for P0 (#234), which the current contract does not allow yet.
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ConceptScenes } from './ConceptScenes';
import { conceptSceneView } from './planningScenes';
import type { Concept, Feature, Gap, Need } from './planning';

const CONCEPT: Concept = { id: 'CONCEPT-001', title: '선반 청소 안내', kind: 'feature', gap_ids: ['GAP-001'], evidence_ids: ['R-1', 'M-1'],
  differentiation: '청소 순서를 화면에 안내', requirements: ['선반 분리 순서 표시'], assumptions: [], status: 'proposed' };
const NEED: Need = { id: 'NEED-001', model_id: 'FRIDGE-A', situation: '주말 청소', pain: '선반 분리가 어렵다', evidence_ids: ['R-1'], uncertainties: [] };
const GAP: Gap = { id: 'GAP-001', need_id: 'NEED-001', model_id: 'FRIDGE-A', feature_ids: ['F-1'], support_status: 'supported',
  remaining_pain: '순서를 모른다', evidence_ids: ['R-1', 'M-1'], questions: [] };
const FEATURES: Feature[] = [{ id: 'F-1', model_id: 'FRIDGE-A', document_version: '1.0', name: '선반 분리', description: '', conditions: [], evidence_ids: ['M-1'] }];
const KNOWN = ['R-1', 'R-2', 'M-1'];

const withFields = (fields: Record<string, unknown>) => ({ ...CONCEPT, ...fields }) as unknown as Concept;
const view = (concept: Concept, gap: Gap = GAP, need: Need = NEED) => conceptSceneView(concept, { needs: [need], gaps: [gap] }, KNOWN);
const html = (concept: Concept, gap?: Gap, need?: Need) => renderToStaticMarkup(createElement(ConceptScenes, {
  view: view(concept, gap, need), features: FEATURES, refs: (ids: string[]) => createElement('span', { 'data-refs': ids.join(',') }) }));

const FULL = {
  target_user: '맞벌이 가구', usage_context: '주말 냉장고 청소',
  before_steps: [{ text: '선반을 빼려다 걸린다', basis: 'observed', evidence_ids: ['R-1'] }, { text: '설명서를 찾는다', basis: 'inferred' }],
  after_steps: [{ text: '화면이 분리 순서를 보여 준다', basis: 'inferred', evidence_ids: ['M-1'] }],
  mechanism: { summary: '문을 연 채 청소 모드를 켜면 순서를 표시', feature_ids: ['F-1', 'F-9'], conditions: ['청소 모드'] },
};

describe('conceptSceneView', () => {
  it('reports every field as not provided for a contract-valid concept today', () => {
    const result = view(CONCEPT);
    expect(result.provided).toBe(false);
    for (const field of [result.targetUser, result.usageContext, result.before, result.after, result.mechanism, result.counterEvidence]) expect(field.state).toBe('not_provided');
  });

  it('reads recorded scenes in order, keeps observed/inferred and flags citations missing from the data', () => {
    const result = view(withFields({ ...FULL, after_steps: [{ text: '순서 표시', basis: 'observed', evidence_ids: ['M-1', 'X-404'] }] }));
    expect(result.provided).toBe(true);
    expect(result.targetUser).toEqual({ state: 'ok', value: '맞벌이 가구' });
    expect(result.before.state === 'ok' && result.before.value.map(step => [step.order, step.basis, step.evidenceIds])).toEqual([[1, 'observed', ['R-1']], [2, 'inferred', []]]);
    expect(result.after.state === 'ok' && result.after.value[0].missingEvidenceIds).toEqual(['X-404']);
    expect(result.mechanism).toEqual({ state: 'ok', value: { summary: FULL.mechanism.summary, featureIds: ['F-1', 'F-9'], conditions: ['청소 모드'] } });
  });

  it('rejects an observed step without evidence and other wrong shapes instead of showing them', () => {
    expect(view(withFields({ before_steps: [{ text: '걸린다', basis: 'observed', evidence_ids: [] }] })).before)
      .toEqual({ state: 'malformed', reason: '개선 전 1단계는 관찰이라고 했지만 근거가 없습니다' });
    expect(view(withFields({ after_steps: [{ text: '표시', basis: 'guess' }] })).after.state).toBe('malformed');
    expect(view(withFields({ after_steps: [] })).after.state).toBe('malformed');
    expect(view(withFields({ target_user: 3 })).targetUser.state).toBe('malformed');
    expect(view(withFields({ mechanism: { summary: '' } })).mechanism.state).toBe('malformed');
    expect(view(withFields({ mechanism: { summary: '표시', conditions: 'always' } })).mechanism.state).toBe('malformed');
  });

  it('separates no counter case recorded from counter evidence not provided, and flags a citation used both ways', () => {
    const recordedNone = view(CONCEPT, { ...GAP, counter_evidence_ids: [] } as Gap);
    expect(recordedNone.counterEvidence).toEqual({ state: 'ok', value: [{ ownerId: 'GAP-001', evidenceIds: [], missingEvidenceIds: [], alsoSupportingIds: [] }] });
    const both = view(CONCEPT, GAP, { ...NEED, counter_evidence_ids: ['R-2', 'R-1'] } as Need);
    expect(both.counterEvidence).toEqual({ state: 'ok', value: [{ ownerId: 'NEED-001', evidenceIds: ['R-2', 'R-1'], missingEvidenceIds: [], alsoSupportingIds: ['R-1'] }] });
    expect(view(CONCEPT, { ...GAP, counter_evidence_ids: 'R-2' } as unknown as Gap).counterEvidence.state).toBe('malformed');
  });

  it('ignores counter evidence on gaps the concept does not address', () => {
    const other = { ...GAP, id: 'GAP-002', counter_evidence_ids: ['R-2'] } as Gap;
    expect(conceptSceneView(CONCEPT, { needs: [NEED], gaps: [GAP, other] }, KNOWN).counterEvidence.state).toBe('not_provided');
  });
});

describe('ConceptScenes', () => {
  it('says the run has no scenes rather than drawing any', () => {
    const markup = html(CONCEPT);
    expect(markup).toContain('data-scenes-not-provided');
    expect(markup).toContain('화면에서 만들어 넣지 않습니다');
    expect(markup).not.toContain('data-concept-scenes');
  });

  it('draws recorded before/after steps with their basis, features by name and citations through the caller', () => {
    const markup = html(withFields(FULL), { ...GAP, counter_evidence_ids: [] } as Gap);
    expect(markup).toContain('맞벌이 가구');
    expect(markup.match(/data-scene-step="observed"/g)).toHaveLength(1);
    expect(markup.match(/data-scene-step="inferred"/g)).toHaveLength(2);
    expect(markup).toContain('data-refs="R-1"');
    expect(markup).toContain('선반 분리, F-9(자료에 없는 기능)');
    expect(markup).toContain('반대 사례 없음(코어 기록)');
  });

  it('shows why a malformed field is withheld and marks the rest not provided', () => {
    const markup = html(withFields({ before_steps: [{ text: '걸린다', basis: 'observed' }] }));
    expect(markup).toContain('개선 전: 형식 불일치');
    expect(markup).not.toContain('걸린다');
    expect(markup).toContain('작동 방식: 미제공');
    expect(markup).toContain('반대 사례: 미제공');
  });
});
