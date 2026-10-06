# 세션 작업기록 — auto-cbcaed018a0634bacaef459fe7b7fa223a6fa812

- Job ID: `auto-cbcaed018a0634bacaef459fe7b7fa223a6fa812` (배정 PM-20261005-AUTO-cbcaed018a0634ba, 작업 P2-WEB-003, 시도 1/2)
- 담당자: 최길웅(choigilung) · 수행: 자동 Worker(Claude, 파일 도구만 제공) · 작성일: 2026-10-05
- 기준 commit: d95b225029171fec71fe50fcbcd66a65d849914d · 승인 참조: Issue #28 댓글 5985873087
- 요청 요구: R14, R25 · 선행 형식 작업: P2-WEB-002

## 원 요청(발췌)
"후보 제목·차별점 변경도 변경 전후 이력에 표시": 같은 ID·상태·요구사항·가정·근거 ID인 후보에서 title만, differentiation만, 둘 다 바뀐 경우를 이력에 표시하고 변경 전후 원문을 비교할 수 있게 한다. 기존 요구사항·가정·근거·상태 표시와 후보 추가/삭제·변화 없음·이전 실행 없음·not_implemented 의미를 유지한다. `conceptDetailChanges` 회귀와 fixture snapshot 기반 `HistoryView` 실제 DOM 회귀를 추가한다. 서버 계약·원본 snapshot·내보낸 원 실행 기록은 변경하지 않는다. 텍스트는 일반 React 텍스트로 렌더링한다. 외부 API·모델 서버·credential 없이 fixture/DOM으로 검증한다. 후보 선택→추가 조건→모델 재실행 및 P2-WEB-003 전체 live_service 완료는 주장하지 않는다.

허용 경로: `apps/web/src/planning.ts`, `apps/web/src/PlanningViews.tsx`, `apps/web/src/conceptTextChanges.test.ts`, 이 두 세션 문서.

## 해석
- 기존 `conceptDetailChanges`는 상태·요구사항·가정·근거 ID만 비교해, 제목·차별점만 바뀌면 후보가 목록에서 빠지고 화면이 "후보 변화가 없습니다"를 표시한다. 이를 고치는 것이 핵심이다.
- 변경 전후 텍스트 쌍은 두 실행에 모두 있는 후보에만 만든다. 추가/삭제된 후보는 기존대로 상태(없음↔값)로 표시한다(가정).
- 표시용 구조(`text` 필드)만 파생하며 snapshot·내보내기(`buildExport` 등)·계약 스키마는 건드리지 않는다.

## 실제 행동
1. AGENTS.md 전체와 CLAUDE.md 앞부분(5행)을 읽었다. CLAUDE.md의 나머지는 AGENTS.md와 동일하다고 명시되어 있으나 바이트 비교는 하지 않았다(도구 없음).
2. `apps/web/src/planning.ts`: `ConceptTextChange` 타입 추가, `ConceptDetailChange`에 `text: { title, differentiation }`(없으면 null) 추가, `conceptDetailChanges`가 원문 그대로(`===`) 비교하고 필터에 제목/차별점 변경을 포함하도록 수정.
3. `apps/web/src/PlanningViews.tsx`: `DetailChanges`에 `textDiff`를 추가해 "제목 변경/차별점 변경"과 "변경 전: …/변경 후: …"를 일반 React 텍스트로 표시(`white-space: pre-wrap`, `overflow-wrap: anywhere`, 빈 값은 "(비어 있음)"). `ConceptTextChange` 타입 import 추가. CSS 파일은 허용 경로가 아니라 변경하지 않았다(인라인 스타일 사용).
4. `apps/web/src/conceptTextChanges.test.ts` 신규: 데이터 회귀(제목만·차별점만·둘 다·빈 이전 값·변화 없음·상태 변화·후보 추가·원본 불변)와 `HistoryView` jsdom DOM 회귀(제목만·긴 한국어+HTML/마크다운 문자열 차별점만·둘 다+빈 이전 값·변화 없음 유지·not_implemented 유지).

## 검사
- 이 세션에서 **실행한 검사는 없다.** 셸/npm이 제공되지 않아 테스트·typecheck·build를 실행하지 못했다. 위 테스트는 작성만 했고 통과를 관찰하지 않았다.
- 예정(외부 신뢰 Worker 실행): `npm --prefix apps/web ci --offline --ignore-scripts --no-audit --no-fund`, `... run test`, `... run typecheck`, `... run build`.

## 실패·미완료·위험
- 테스트·타입 오류 가능성: 테스트의 fixture 필드(`first.run.status`, `request_revision`)와 jsdom 사용은 기존 `planning.test.ts` 패턴을 따랐으나 미실행. 한 선택자(`'b, script, strong + strong'`)는 불필요한 부분이 있으나 무해하다.
- 기존 테스트 중 `conceptDetailChanges` 결과를 `toEqual`로 전체 비교하는 것이 있다면 새 `text` 필드로 실패할 수 있다. 확인하지 못했다(`planning.test.ts:291` 이하는 `toMatchObject`/부분 비교로 보임).
- 실제 후보 선택→조건 추가→모델 재실행, live_service 경로, P2-WEB-003 전체 완료는 이 작업에 포함되지 않았고 주장하지 않는다.
- 커밋·푸시·git 설정·자격증명·하네스 상태 변경은 하지 않았다.

## 다음 행동
- Worker가 검증 명령을 실행하고 결과를 확인한다. 실패 시 이 기록은 불변이므로 새 시도 기록에 정정한다.
- PR 및 PM 독립 검수. 사용자 직접 할 일: 없음.
