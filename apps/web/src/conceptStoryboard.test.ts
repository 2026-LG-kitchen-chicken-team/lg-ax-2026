// The bundle uses one committed public review (fixtures/research-test-data). The brief is a hand-written test object in
// the shared PlanningBrief contract, not model output; it only exercises the storyboard conversion.
import { describe, expect, it } from 'vitest';
import { buildConceptStoryboard, exportConceptStoryboard, STORYBOARD_DISCLAIMER } from './conceptStoryboard';
import { heldBrief, REAL_RESEARCH_BUNDLE } from './fixtures/research-test-data';
import type { PlanningBrief, ResearchConcept } from './research';

const SOURCE = REAL_RESEARCH_BUNDLE.sources[0].source_id;
function concept(scenes: number, patch: Partial<ResearchConcept> = {}): ResearchConcept {
  return { id: 'CONCEPT-T1', title: '깊은 칸 안쪽 보기', problem_ids: ['PROBLEM-T1'], target_user: '맞벌이 가구', use_context: '주말 장보기 뒤 정리',
    before_steps: ['안쪽 식품을 꺼내 확인한다'], after_steps: ['문을 열면 안쪽 칸을 비춘다'], mechanism: '문 열림 감지로 안쪽 조명을 켠다',
    proposed_changes: ['안쪽 조명'], source_ids: [SOURCE], assumptions: ['조명이 전력에 큰 영향을 주지 않는다'], validation_questions: ['안쪽 확인 빈도는?'],
    visual_scenes: Array.from({ length: scenes }, (_, index) => ({ title: `장면 ${index + 1}`, before: `안쪽을 들여다본다 ${index + 1}`, after: `조명으로 바로 보인다 ${index + 1}` })),
    status: 'supported', ...patch };
}
function brief(scenes = 2, patch: Partial<ResearchConcept> = {}, status: PlanningBrief['status'] = 'complete'): PlanningBrief {
  return { ...heldBrief(), status, runtime: { bundle_sha256: 'a'.repeat(64) },
    problems: [{ id: 'PROBLEM-T1', title: '안쪽 식품 확인', description: '깊은 칸 안쪽이 잘 보이지 않는다', source_ids: [SOURCE], counter_source_ids: [], scope_caveat: '제품군 탐색' }],
    concepts: [concept(scenes, patch)] };
}

describe('buildConceptStoryboard', () => {
  it('turns visual scenes into title, before/after and closing shots inside 30–45 seconds, citing the problem sources', () => {
    const board = buildConceptStoryboard(REAL_RESEARCH_BUNDLE, brief(2), 'CONCEPT-T1');
    expect(board.shots.map(shot => `${shot.id}:${shot.kind}`)).toEqual(['S01:title', 'S02:before', 'S03:after', 'S04:before', 'S05:after', 'S06:closing']);
    expect(board.total_seconds).toBe(30);
    expect(board.shots.filter(shot => shot.kind === 'before').every(shot => shot.source_ids.join() === SOURCE && !shot.proposed)).toBe(true);
    expect(board.shots.filter(shot => shot.kind === 'after').every(shot => shot.proposed && shot.source_ids.length === 0)).toBe(true);
    expect(board.shots.at(-1)!.caption).toBe(STORYBOARD_DISCLAIMER);
    expect(board.source).toEqual({ bundle_id: REAL_RESEARCH_BUNDLE.bundle_id, bundle_sha256: 'a'.repeat(64), brief_id: 'TEST-held-brief', run_id: 'TEST-held-run', revision: 0, brief_status: 'complete' });
    expect(board.warnings).toEqual([]);
  });

  it('keeps the total exactly within the target for any scene count and warns when shots get too short', () => {
    for (const scenes of [1, 2, 3, 5, 7, 9, 10]) {
      const board = buildConceptStoryboard(REAL_RESEARCH_BUNDLE, brief(scenes), 'CONCEPT-T1');
      expect(board.total_seconds).toBeGreaterThanOrEqual(30);
      expect(board.total_seconds).toBeLessThanOrEqual(45);
      expect(Math.round(board.shots.reduce((sum, shot) => sum + shot.seconds, 0) * 10)).toBe(Math.round(board.total_seconds * 10));
    }
    expect(buildConceptStoryboard(REAL_RESEARCH_BUNDLE, brief(9), 'CONCEPT-T1').warnings).toEqual([]);
    expect(buildConceptStoryboard(REAL_RESEARCH_BUNDLE, brief(10), 'CONCEPT-T1').warnings.some(item => item.includes('장면당 1.8초'))).toBe(true);
  });

  it('flags drafts, unsupported concepts and incomplete briefs instead of presenting them as ready', () => {
    const board = buildConceptStoryboard(REAL_RESEARCH_BUNDLE, brief(2, { status: 'needs_sources' }, 'partial'), 'CONCEPT-T1');
    expect(board.warnings).toEqual([expect.stringContaining('근거 보강 필요'), expect.stringContaining("'partial'")]);
  });

  it('refuses a missing concept or a concept whose scenes are all empty, and drops only the empty scenes', () => {
    expect(() => buildConceptStoryboard(REAL_RESEARCH_BUNDLE, brief(2), 'NOPE')).toThrow('개선안이 이 기획 결과에 없습니다');
    const empty = brief(1); empty.concepts[0].visual_scenes = [{ title: 'x', before: ' ', after: '' }];
    expect(() => buildConceptStoryboard(REAL_RESEARCH_BUNDLE, empty, 'CONCEPT-T1')).toThrow('장면이 비어 있어');
    const partial = brief(2); partial.concepts[0].visual_scenes[1].after = '';
    const board = buildConceptStoryboard(REAL_RESEARCH_BUNDLE, partial, 'CONCEPT-T1');
    expect(board.shots.filter(shot => shot.kind === 'before')).toHaveLength(1);
    expect(board.warnings[0]).toContain('빈 장면 1개를 제외');
  });

  it('exports JSON and a Markdown shot table that carry the disclaimer, sources and open checks', () => {
    const { json, markdown } = exportConceptStoryboard(buildConceptStoryboard(REAL_RESEARCH_BUNDLE, brief(2), 'CONCEPT-T1'));
    expect(JSON.parse(json).kind).toBe('future_concept_storyboard');
    expect(markdown).toContain(`> ${STORYBOARD_DISCLAIMER}`);
    expect(markdown).toContain(`| S02 | 지금 | 장면 1 |`);
    expect(markdown).toContain(`| ${SOURCE} |`);
    expect(markdown).toContain('| S03 | 제안(콘셉트) | 장면 1 |');
    expect(markdown).toContain('- [ ] 참조 이미지·영상·음성 생성 모델의 라이선스와 상업적 사용 조건');
    expect(markdown).toContain('- [ ] 검증 질문: 안쪽 확인 빈도는?');
  });
});
