import { ApiError } from './api';
import { parsePlanningBrief } from './research';
import type { PlanningBrief, ResearchBundle, ResearchConcept } from './research';

// V1 first stage (record 최길웅-20261008-060): turn one concept of a stored PlanningBrief into a 30–45 second future-concept
// storyboard (title card → before/after shot per visual scene → closing card) with caption/narration text and a plain
// reference-image brief per shot. Everything is copied from the brief; nothing is generated here and no image, voice or
// video model is called. The result says it is a proposal and not evidence of real performance.

export const STORYBOARD_TARGET_SECONDS = { min: 30, max: 45 } as const;
const TITLE_SECONDS = 4;
const CLOSING_SECONDS = 5;
const PREFERRED_SHOT_SECONDS = 4;
const MIN_SHOT_SECONDS = 2;
export const STORYBOARD_DISCLAIMER = '미래 콘셉트 시안입니다. 실제 제품의 성능이나 검증된 효과를 보여 주는 영상이 아닙니다.';

export interface StoryboardShot {
  id: string;
  kind: 'title' | 'before' | 'after' | 'closing';
  scene_title: string | null;
  seconds: number;
  caption: string;
  narration: string;
  image_brief: string;
  /** Originals behind a "before" shot (the concept's problems). A proposed "after" shot has none of its own. */
  source_ids: string[];
  proposed: boolean;
}
export interface ConceptStoryboard {
  kind: 'future_concept_storyboard';
  storyboard_version: 'v1';
  disclaimer: string;
  source: { bundle_id: string; bundle_sha256: string | null; brief_id: string; run_id: string; revision: number; brief_status: PlanningBrief['status'] };
  concept: { id: string; title: string; status: ResearchConcept['status']; target_user: string; use_context: string };
  target_seconds: { min: number; max: number };
  total_seconds: number;
  warnings: string[];
  shots: StoryboardShot[];
  /** Still to do before any video exists: these stay open until checked by a person. */
  open_checks: string[];
}

const round = (value: number) => Math.round(value * 10) / 10;

export function buildConceptStoryboard(bundle: ResearchBundle, brief: PlanningBrief, conceptId: string): ConceptStoryboard {
  parsePlanningBrief(brief, bundle);
  const concept = brief.concepts.find(item => item.id === conceptId);
  if (!concept) throw new ApiError('NOT_FOUND', '선택한 개선안이 이 기획 결과에 없습니다.');
  const scenes = concept.visual_scenes.filter(scene => scene.before.trim() && scene.after.trim());
  if (!scenes.length) throw new ApiError('INVALID_ARGUMENT', '장면이 비어 있어 스토리보드를 만들지 않습니다.');
  const warnings: string[] = [];
  if (scenes.length < concept.visual_scenes.length) warnings.push(`이전·제안 설명이 빈 장면 ${concept.visual_scenes.length - scenes.length}개를 제외했습니다.`);
  if (concept.status !== 'supported') warnings.push(`개선안 상태가 '${concept.status === 'needs_sources' ? '근거 보강 필요' : '제안 초안'}'입니다. 영상 제작 전에 근거를 확인해야 합니다.`);
  if (brief.status !== 'complete') warnings.push(`기획 결과 상태가 '${brief.status}'입니다. 미확인 사항을 먼저 확인해야 합니다.`);

  const sceneShots = scenes.length * 2;
  const body = Math.min(STORYBOARD_TARGET_SECONDS.max, Math.max(STORYBOARD_TARGET_SECONDS.min, TITLE_SECONDS + CLOSING_SECONDS + sceneShots * PREFERRED_SHOT_SECONDS))
    - TITLE_SECONDS - CLOSING_SECONDS;
  // Split the body in tenths of a second so the total stays exactly inside the target; earlier shots take the remainder.
  const tenths = Math.round(body * 10);
  const base = Math.floor(tenths / sceneShots);
  const shotSeconds = (index: number) => (base + (index < tenths - base * sceneShots ? 1 : 0)) / 10;
  const perShot = base / 10;
  if (perShot < MIN_SHOT_SECONDS) warnings.push(`장면 ${scenes.length}개를 ${STORYBOARD_TARGET_SECONDS.max}초에 넣으면 장면당 ${perShot}초입니다. 장면 수를 줄이거나 나눠 주세요.`);

  const problemSources = [...new Set(brief.problems.filter(problem => concept.problem_ids.includes(problem.id)).flatMap(problem => problem.source_ids))];
  const setting = `${concept.use_context} · ${concept.target_user}`;
  const shots: StoryboardShot[] = [{
    id: 'S01', kind: 'title', scene_title: null, seconds: TITLE_SECONDS,
    caption: `${concept.title} — 미래 콘셉트`, narration: `${concept.target_user}의 ${concept.use_context}을(를) 다시 생각해 봅니다.`,
    image_brief: `제목 화면. ${concept.title}. '미래 콘셉트' 표시를 넣는다.`, source_ids: [], proposed: true,
  }];
  for (const [index, scene] of scenes.entries()) {
    shots.push({ id: '', kind: 'before', scene_title: scene.title, seconds: shotSeconds(index * 2), caption: `지금 · ${scene.before}`, narration: scene.before,
      image_brief: `${setting}. 현재 모습: ${scene.before}`, source_ids: problemSources, proposed: false });
    shots.push({ id: '', kind: 'after', scene_title: scene.title, seconds: shotSeconds(index * 2 + 1), caption: `제안 · ${scene.after}`, narration: scene.after,
      image_brief: `${setting}. 제안 모습(콘셉트): ${scene.after}`, source_ids: [], proposed: true });
  }
  shots.push({ id: '', kind: 'closing', scene_title: null, seconds: CLOSING_SECONDS, caption: STORYBOARD_DISCLAIMER,
    narration: `확인할 질문 ${concept.validation_questions.length}개와 검증 전 가정 ${concept.assumptions.length}개가 남아 있습니다.`,
    image_brief: '마무리 화면. 미래 콘셉트 안내와 검증 질문 수를 표시한다.', source_ids: [], proposed: true });
  shots.forEach((shot, index) => { shot.id = `S${String(index + 1).padStart(2, '0')}`; });

  const sha = brief.runtime.bundle_sha256;
  return {
    kind: 'future_concept_storyboard', storyboard_version: 'v1', disclaimer: STORYBOARD_DISCLAIMER,
    source: { bundle_id: brief.bundle_id, bundle_sha256: typeof sha === 'string' ? sha : null, brief_id: brief.brief_id, run_id: brief.run_id, revision: brief.revision, brief_status: brief.status },
    concept: { id: concept.id, title: concept.title, status: concept.status, target_user: concept.target_user, use_context: concept.use_context },
    target_seconds: { ...STORYBOARD_TARGET_SECONDS }, total_seconds: round(shots.reduce((sum, shot) => sum + shot.seconds, 0)),
    warnings, shots,
    open_checks: ['참조 이미지·영상·음성 생성 모델의 라이선스와 상업적 사용 조건', '생성 장비(GPU)와 실행 시간', '이 기획 revision이 시연 시점에도 최신인지',
      ...concept.validation_questions.map(question => `검증 질문: ${question}`)],
  };
}

const cell = (text: string) => text.replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
export function exportConceptStoryboard(storyboard: ConceptStoryboard): { json: string; markdown: string } {
  const { source, concept } = storyboard;
  const lines = [`# 콘셉트 스토리보드 · ${concept.title}`, '', `> ${storyboard.disclaimer}`, '',
    `- 기획: ${source.run_id} / 수정 ${source.revision} / 결과 상태 ${source.brief_status}`, `- 자료 묶음: ${source.bundle_id}${source.bundle_sha256 ? ` (${source.bundle_sha256})` : ''}`,
    `- 개선안: ${concept.id} · 상태 ${concept.status} · 대상 ${concept.target_user} · 맥락 ${concept.use_context}`,
    `- 길이: ${storyboard.total_seconds}초 (목표 ${storyboard.target_seconds.min}–${storyboard.target_seconds.max}초)`, ''];
  if (storyboard.warnings.length) lines.push('## 주의', ...storyboard.warnings.map(item => `- ${item}`), '');
  lines.push('## 장면', '', '| 컷 | 구분 | 장면 | 초 | 자막 | 근거 |', '|---|---|---|---|---|---|');
  const kindLabel = { title: '제목', before: '지금', after: '제안(콘셉트)', closing: '마무리' } as const;
  for (const shot of storyboard.shots) {
    lines.push(`| ${shot.id} | ${kindLabel[shot.kind]} | ${cell(shot.scene_title ?? '-')} | ${shot.seconds} | ${cell(shot.caption)} | ${shot.source_ids.join(', ') || (shot.proposed ? '제안' : '-')} |`);
  }
  lines.push('', '## 컷별 참조 이미지 메모와 내레이션', ...storyboard.shots.flatMap(shot => [`### ${shot.id}`, `- 이미지 메모: ${shot.image_brief}`, `- 내레이션: ${shot.narration}`]),
    '', '## 영상 제작 전 확인', ...storyboard.open_checks.map(item => `- [ ] ${item}`));
  return { json: `${JSON.stringify(storyboard, null, 2)}\n`, markdown: `${lines.join('\n')}\n` };
}
